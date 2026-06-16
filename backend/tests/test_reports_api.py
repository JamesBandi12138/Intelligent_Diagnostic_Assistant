from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _complete_triage_session() -> str:
    session_id = f"report-session-{uuid4()}"
    first_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "patient": {
                "age": 34,
                "sex": "female",
                "medical_history": ["过敏性鼻炎"],
                "allergies": ["青霉素"],
                "medications": [],
            },
            "symptom_text": "喉咙不舒服",
            "city": "上海",
        },
    )
    assert first_response.status_code == 200
    assert first_response.json()["status"] == "needs_follow_up"

    second_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "answer": "喉咙痛三天，吞咽时更明显，疼痛程度约4到5分，没有发烧咳嗽，也没有慢性病",
        },
    )
    assert second_response.status_code == 200
    assert second_response.json()["status"] == "completed"
    return session_id


def test_report_can_be_generated_for_completed_session():
    session_id = _complete_triage_session()

    response = client.post("/api/reports", json={"session_id": session_id})

    data = response.json()
    assert response.status_code == 200
    assert data["session_id"] == session_id
    assert data["status"] == "ready"
    assert data["doctor_view"]["chief_complaint"]
    assert data["patient_view"]["why_this_department"]


def test_report_generation_rejects_incomplete_session():
    session_id = f"report-session-{uuid4()}"
    first_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "patient": {
                "age": 40,
                "sex": "male",
                "medical_history": [],
                "allergies": [],
                "medications": [],
            },
            "symptom_text": "肚子不舒服",
            "city": "北京",
        },
    )
    assert first_response.status_code == 200
    assert first_response.json()["status"] == "needs_follow_up"

    response = client.post("/api/reports", json={"session_id": session_id})

    assert response.status_code == 409


def test_report_generation_is_idempotent_for_same_session():
    session_id = _complete_triage_session()

    first_report = client.post("/api/reports", json={"session_id": session_id})
    second_report = client.post("/api/reports", json={"session_id": session_id})

    assert first_report.status_code == 200
    assert second_report.status_code == 200
    assert first_report.json()["report_id"] == second_report.json()["report_id"]


def test_report_can_be_loaded_by_report_id_and_session_detail_exposes_report_id():
    session_id = _complete_triage_session()
    create_report_response = client.post("/api/reports", json={"session_id": session_id})
    report_id = create_report_response.json()["report_id"]

    report_response = client.get(f"/api/reports/{report_id}")
    session_response = client.get(f"/api/triage/sessions/{session_id}")

    assert report_response.status_code == 200
    assert report_response.json()["report_id"] == report_id
    assert report_response.json()["doctor_view"]["recommended_department_summary"]

    assert session_response.status_code == 200
    assert session_response.json()["report_id"] == report_id
