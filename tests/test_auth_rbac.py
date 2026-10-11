"""Smoke tests for authentication boundaries (use synthetic demo data only)."""
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.main import create_app


def test_login_accepts_form_data_and_returns_access_token(monkeypatch):
    monkeypatch.setattr(
        "app.routers.auth_routes.authenticate_user",
        lambda username, password: {"username": username, "role": "admin"},
    )
    monkeypatch.setattr("app.routers.auth_routes.issue_token", lambda user: ("signed-token", 1800))

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/auth/login",
            data={"username": "test-admin", "password": "correct-password"},
        )

    assert response.status_code == 200
    assert response.json()["access_token"] == "signed-token"
    assert response.json()["token_type"] == "bearer"


def test_dashboard_requires_authentication():
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/dashboard/summary")
    assert response.status_code == 401


def test_judge_cannot_access_student_level_records():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: {"username": "judge", "role": "judge_demo"}
    with TestClient(app) as client:
        assert client.get("/api/dashboard/summary").status_code == 200
        assert client.get("/api/students").status_code == 403
        assert client.get("/api/interventions").status_code == 403


def test_json_user_store_hashes_password_and_issues_valid_token(tmp_path, monkeypatch):
    import app.auth as auth
    monkeypatch.setattr(auth, "USERS_FILE", tmp_path / "users.json")
    user = auth.create_user("csv_admin", "A-very-long-test-password!", "admin")
    assert user["role"] == "admin"
    stored = auth._read_users()["csv_admin"]
    assert stored["password_hash"] != "A-very-long-test-password!"
    assert auth.authenticate_user("csv_admin", "A-very-long-test-password!")["username"] == "csv_admin"
    assert auth.authenticate_user("csv_admin", "wrong-password") is None
    token, _ = auth.issue_token(user)
    assert auth.get_current_user(token)["username"] == "csv_admin"
