"""Intervention writes persist to the new CSV-backed working dataset."""
import pandas as pd
from app.data_service import DataService


def csv_rows(data_dir):
    return pd.read_csv(data_dir / "interventions.csv", dtype=str, keep_default_na=False)


def test_create_intervention_is_saved_and_survives_reload(writable_client):
    c = writable_client
    response = c.post("/api/interventions", json={"student_id":"STU20260001", "intervention_type":"mentoring", "status":"assigned", "assigned_date":"2026-10-09", "follow_up_notes":"Meet on Monday"})
    assert response.status_code == 201, response.text
    record = response.json()["data"]
    assert record["intervention_id"] == "INT0001" and record["student_id"] == "STU20260001"
    assert len(csv_rows(c.data_dir)) == 1
    assert "INT0001" in set(DataService(c.data_dir).load().interventions["intervention_id"])


def test_intervention_validation_and_update(writable_client):
    c = writable_client
    assert c.post("/api/interventions", json={"student_id":"STU99999999", "intervention_type":"Mentoring"}).status_code == 404
    assert c.post("/api/interventions", json={"student_id":"STU20260001", "intervention_type":"Magic"}).status_code == 422
    c.post("/api/interventions", json={"student_id":"STU20260001", "intervention_type":"Mentoring"})
    response = c.patch("/api/interventions/INT0001", json={"status":"Completed", "follow_up_notes":"Done"})
    assert response.status_code == 200
    saved = csv_rows(c.data_dir).iloc[0]
    assert saved["status"] == "Completed" and saved["follow_up_notes"] == "Done"
