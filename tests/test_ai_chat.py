"""Offline tests for Groq chat preparation; no external API calls are made."""
from app.data_service import DataService
from app.routers.ai_chat import ChatRequest, _aggregate_context, _deidentify, _skill_query_rows
from app.auth import get_current_user


def test_chat_request_rejects_blank_question():
    try:
        ChatRequest(message="   ")
    except ValueError:
        return
    raise AssertionError("blank questions should be rejected")


def test_aggregate_context_uses_loaded_csv_data():
    service = DataService().load()
    context = _aggregate_context(service)
    assert context["total_students"] == len(service.students)
    assert context["average_success_score"] is None or isinstance(context["average_success_score"], float)
    assert isinstance(context["departments"], dict)
    assert "data_quality_note" in context


def test_student_records_are_deidentified_before_provider_context():
    service = DataService().load()
    sid = str(service.students.index[0])
    row = service.student_row(sid)
    safe_rows, aliases, _ = _deidentify([row])
    serialized = str(safe_rows)
    assert "student_name" not in serialized
    assert "student_email" not in serialized
    assert sid not in serialized
    assert "Learner 1" in serialized
    assert "Learner 1" in aliases


def test_skill_lookup_matches_any_skill_in_dataset():
    service = DataService().load()

    for skill_name in service.student_skills["Skill Name"].dropna().unique():
        rows = _skill_query_rows(service, f"Who has {skill_name} skills?")
        expected = set(service.student_skills.loc[
            service.student_skills["Skill Name"].str.casefold() == skill_name.casefold(),
            "Student ID",
        ])
        assert rows is not None
        assert {row["student_id"] for row in rows} == expected
        assert all(row["matched_skill"].casefold() == skill_name.casefold() for row in rows)


def test_skill_chat_returns_dataset_names_without_calling_groq(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    service = DataService(client.data_dir).load()
    git_count = service.student_skills.loc[
        service.student_skills["Skill Name"].str.casefold() == "git", "Student ID"
    ].nunique()

    response = client.post("/api/ai/chat", json={"message": "Who has Git skills?"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model"] == "csv-direct"
    assert f"Git ({git_count} student(s))" in data["answer"]
    assert "Neha Singh" in data["answer"]
    assert "Neha Gupta" in data["answer"]


def test_skill_chat_keeps_names_hidden_for_demo_role(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    service = DataService(client.data_dir).load()
    client.app.dependency_overrides[get_current_user] = lambda: {
        "username": "demo-judge",
        "role": "judge_demo",
    }
    git_count = service.student_skills.loc[
        service.student_skills["Skill Name"].str.casefold() == "git", "Student ID"
    ].nunique()

    response = client.post("/api/ai/chat", json={"message": "Who has Git skills?"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert f"{git_count} student(s)" in data["answer"]
    assert "Neha Singh" not in data["answer"]


def test_chat_explains_when_groq_key_is_not_configured(client, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr("app.routers.ai_chat.dotenv_values", lambda _: {})
    response = client.post("/api/ai/chat", json={"message": "Summarize student success"})
    assert response.status_code == 503
    assert "GROQ_API_KEY" in response.json()["error"]["message"]


def test_greeting_does_not_require_groq_key(client, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    response = client.post("/api/ai/chat", json={"message": "hi"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model"] == "local"
    assert "student skills" in data["answer"]


def test_acknowledgement_does_not_require_groq_key(client, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    response = client.post("/api/ai/chat", json={"message": "ok thanks"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model"] == "local"
    assert "You're welcome" in data["answer"]


def test_chat_uses_groq_chat_completions_api(client, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(
        "app.routers.ai_chat.dotenv_values",
        lambda _: {"GROQ_API_KEY": "test-groq-key"},
    )
    monkeypatch.setenv("GROQ_MODEL", "test-model")
    captured = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"choices": [{"message": {"content": "1. **Summary:** Data loaded."}}]}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_value, traceback):
            return False

        async def post(self, url, headers, json):
            captured.update(url=url, headers=headers, payload=json)
            return FakeResponse()

    monkeypatch.setattr("app.routers.ai_chat.httpx.AsyncClient", FakeAsyncClient)
    response = client.post("/api/ai/chat", json={"message": "Summarize student success"})

    assert response.status_code == 200
    assert response.json()["data"]["answer"] == "1. **Summary:** Data loaded."
    assert captured["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-groq-key"
    assert captured["payload"]["model"] == "test-model"
    assert captured["payload"]["messages"][0]["role"] == "user"
