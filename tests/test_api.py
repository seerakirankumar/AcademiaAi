"""API smoke tests against the replacement workbook-derived CSV data."""
import json
import pandas as pd

from tests.conftest import working_student_count

N = working_student_count()
import pytest

ALL_GET_ENDPOINTS = [
    "/", "/api/health", "/api/dashboard/summary", "/api/students",
    "/api/students/STU20260001", "/api/students/STU20260001/score", "/api/risks",
    "/api/students/STU20260001/recommendations", "/api/analytics/departments",
    "/api/analytics/trends", "/api/segments", "/api/interventions", "/api/metadata",
]


def strict_json(response):
    def reject(token):
        raise AssertionError(f"Invalid JSON constant {token!r}")
    return json.loads(response.text, parse_constant=reject)


@pytest.mark.parametrize("url", ALL_GET_ENDPOINTS)
def test_endpoints_return_success_envelope(client, url):
    response = client.get(url)
    assert response.status_code == 200, response.text
    body = strict_json(response)
    assert body["status"] == "success" and "data" in body and "meta" in body


def test_new_dataset_loads_and_health_reports_working_data_students(client):
    health = client.get("/api/health").json()["data"]
    assert health["service"] == "healthy"
    assert health["student_count"] == N
    assert set(health["datasets"]) == {"students", "academics", "attendance", "lms", "engagement", "placements", "skills", "feedback", "interventions"}
    assert health["intervention_count"] == 0


def test_dashboard_is_calculated_from_new_csvs(client):
    summary = client.get("/api/dashboard/summary").json()["data"]
    attendance = pd.read_csv(client.data_dir / "attendance.csv")["overall_attendance_pct"].mean()
    assert summary["total_students"] == N
    assert summary["average_attendance_pct"] == pytest.approx(attendance, abs=0.1)
    assert sum(summary["segments"].values()) == N


def test_students_list_search_pagination_and_full_department_name(client):
    page = client.get("/api/students?limit=10&offset=5").json()
    assert page["meta"]["total"] == N and page["meta"]["count"] == 10
    assert page["data"][0]["student_id"] == "STU20260006"
    match = client.get("/api/students?search=STU20260001").json()["data"]
    assert match[0]["student_name"] == "Neha Singh"
    department = client.get("/api/students?department=Computer%20Science%20and%20Engineering&limit=200").json()
    assert department["meta"]["total"] == 107


def test_admin_can_add_and_update_student_and_changes_persist_to_csv(writable_client):
    c = writable_client
    created = c.post("/api/students", json={
        "student_name": "CSV Test Student", "department": "Artificial Intelligence and Machine Learning",
        "year_of_study": 1, "section": "A", "admission_year": 2026,
        "student_email": "csv-test@example.edu", "cgpa": 8.2, "backlogs": 0,
        "overall_attendance_pct": 92, "subjects_below_attendance_threshold": 0,
        "placement_status": "Not started", "club_participation": "None", "support_requested": "No"
    })
    assert created.status_code == 201, created.text
    sid = created.json()["data"]["student_id"]
    assert sid.startswith("STU")
    assert len(c.app.state.service.students) == N + 1
    update = c.patch(f"/api/students/{sid}", json={"student_name": "CSV Updated Student", "cgpa": 9.1})
    assert update.status_code == 200, update.text
    assert update.json()["data"]["personal"]["student_name"] == "CSV Updated Student"
    assert update.json()["data"]["academics"]["cgpa"] == pytest.approx(9.1)
    assert pd.read_csv(c.data_dir / "students.csv").iloc[-1]["student_name"] == "CSV Updated Student"
    assert pd.read_csv(c.data_dir / "academics.csv").iloc[-1]["cgpa"] == pytest.approx(9.1)


def test_student_write_validation_and_not_found(writable_client):
    c = writable_client
    assert c.post("/api/students", json={"student_name":"X"}).status_code == 422
    assert c.patch("/api/students/STU99999999", json={"cgpa":8}).status_code == 404
    assert len(pd.read_csv(c.data_dir / "students.csv")) == N
