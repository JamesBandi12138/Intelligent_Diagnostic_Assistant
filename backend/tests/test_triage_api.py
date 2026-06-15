from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_check_returns_service_status():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["service"] == "intelligent-diagnostic-assistant"


def test_triage_analyze_returns_safe_skeleton_response():
    response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": "demo-session",
            "patient": {
                "age": 32,
                "sex": "female",
                "medical_history": ["过敏性鼻炎"],
                "allergies": [],
                "medications": [],
            },
            "symptom_text": "喉咙痛三天，有点发热，吞咽疼，不知道挂什么科",
            "city": "北京",
        },
    )

    data = response.json()
    assert response.status_code == 200
    assert data["session_id"] == "demo-session"
    assert data["risk_level"] == "low"
    assert data["recommended_departments"][0]["name"] == "耳鼻喉科"
    assert "不能替代医生诊断" in data["disclaimer"]


def test_triage_analyze_flags_emergency_symptom():
    response = client.post(
        "/api/triage/analyze",
        json={
            "patient": {
                "age": 68,
                "sex": "male",
                "medical_history": ["高血压"],
                "allergies": [],
                "medications": [],
            },
            "symptom_text": "突然胸痛胸闷，大汗，感觉喘不上气",
        },
    )

    data = response.json()
    assert response.status_code == 200
    assert data["risk_level"] == "emergency"
    assert data["emergency_advice"] is not None
    assert "急诊" in data["emergency_advice"]
