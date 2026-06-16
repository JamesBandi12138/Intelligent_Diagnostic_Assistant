from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app
from common.config import settings


client = TestClient(app)


def test_health_check_returns_service_status():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["service"] == "intelligent-diagnostic-assistant"


def test_triage_analyze_returns_follow_up_when_information_is_incomplete():
    session_id = f"test-session-{uuid4()}"
    response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "patient": {
                "age": 32,
                "sex": "female",
                "medical_history": [],
                "allergies": [],
                "medications": [],
            },
            "symptom_text": "喉咙不舒服",
            "city": "北京",
        },
    )

    data = response.json()
    assert response.status_code == 200
    assert data["session_id"] == session_id
    assert data["status"] == "needs_follow_up"
    assert data["question"]
    assert "duration" in data["missing_fields"]


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
    assert data["status"] == "completed"
    assert data["risk_level"] == "emergency"
    assert data["emergency_advice"] is not None
    assert "急诊" in data["emergency_advice"]


def test_triage_follow_up_answer_can_complete_session():
    create_response = client.post("/api/triage/sessions")
    session_id = create_response.json()["session_id"]

    first_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "patient": {
                "age": 26,
                "sex": "female",
                "medical_history": [],
                "allergies": ["青霉素"],
                "medications": [],
            },
            "symptom_text": "喉咙不舒服",
            "city": "上海",
        },
    )

    first_data = first_response.json()
    assert first_response.status_code == 200
    assert first_data["status"] == "needs_follow_up"

    analyze_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "answer": "喉咙痛三天，吞咽时更明显，疼痛程度约4到5分，没有发烧咳嗽，也没有慢性病",
        },
    )

    result_data = analyze_response.json()
    assert analyze_response.status_code == 200
    assert result_data["status"] == "completed"
    assert result_data["risk_level"] in ("low", "medium")
    assert result_data["recommended_departments"][0]["name"] == "耳鼻喉科"

    session_response = client.get(f"/api/triage/sessions/{session_id}")
    session_data = session_response.json()

    assert session_response.status_code == 200
    assert session_data["session_id"] == session_id
    assert session_data["status"] == "completed"
    assert session_data["current_question"] is None
    assert session_data["latest_result"]["status"] == "completed"
    assert len(session_data["messages"]) >= 3


def test_completed_session_rejects_additional_answers():
    create_response = client.post("/api/triage/sessions")
    session_id = create_response.json()["session_id"]

    first_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
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

    assert first_response.status_code == 200
    assert first_response.json()["status"] == "completed"

    extra_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "answer": "现在几乎说不出话",
        },
    )

    assert extra_response.status_code == 409


def test_session_detail_exposes_langgraph_debug_trace_for_follow_up_flow():
    session_id = f"graph-session-{uuid4()}"
    analyze_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "patient": {
                "age": 32,
                "sex": "female",
                "medical_history": [],
                "allergies": [],
                "medications": [],
            },
            "symptom_text": "喉咙不舒服",
            "city": "鍖椾含",
        },
    )

    assert analyze_response.status_code == 200
    assert analyze_response.json()["status"] == "needs_follow_up"

    session_response = client.get(f"/api/triage/sessions/{session_id}")
    session_data = session_response.json()

    assert session_response.status_code == 200
    assert session_data["current_agent"] == "follow_up_agent"
    assert "supervisor_route" in session_data["node_trace"]
    assert "safety_agent" in session_data["node_trace"]
    assert "triage_agent" in session_data["node_trace"]
    assert "knowledge_agent" in session_data["node_trace"]
    assert "follow_up_agent" in session_data["node_trace"]
    assert any(item["agent"] == "knowledge_agent" for item in session_data["agent_trace"])
    assert session_data["route_reason"]
    assert "knowledge_summary" in session_data
    assert "llm_enabled" in session_data
    assert "llm_provider" in session_data
    assert "llm_model" in session_data
    assert "llm_base_url" in session_data


def test_emergency_flow_trace_routes_from_safety_to_result_without_follow_up():
    session_id = f"graph-session-{uuid4()}"
    analyze_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
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

    assert analyze_response.status_code == 200
    assert analyze_response.json()["status"] == "completed"

    session_response = client.get(f"/api/triage/sessions/{session_id}")
    session_data = session_response.json()

    assert session_response.status_code == 200
    assert session_data["current_agent"] == "result_agent"
    assert "safety_agent" in session_data["node_trace"]
    assert "result_agent" in session_data["node_trace"]
    assert "follow_up_agent" not in session_data["node_trace"]
    assert any(item["agent"] == "safety_agent" for item in session_data["agent_trace"])
    assert "emergency" in session_data["route_reason"].lower()


def test_triage_analyze_injects_llm_client_when_enabled(monkeypatch):
    from app.routers import triage as triage_router

    captured = {}

    async def fake_run_triage(request, llm_client=None):
        captured["llm_client"] = llm_client
        return {
            "session_id": request.session_id,
            "status": "needs_follow_up",
            "risk_level": "low",
            "question": "请补充症状部位",
            "known_facts_summary": "信息不足",
            "missing_fields": ["location"],
        }

    sentinel_client = object()
    monkeypatch.setattr(triage_router, "run_triage", fake_run_triage)
    monkeypatch.setattr(triage_router, "get_triage_llm_client", lambda: sentinel_client, raising=False)
    settings.ENABLE_LLM_TRIAGE = True

    response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": f"llm-session-{uuid4()}",
            "patient": {
                "age": 32,
                "sex": "female",
                "medical_history": [],
                "allergies": [],
                "medications": [],
            },
            "symptom_text": "喉咙不舒服",
        },
    )

    assert response.status_code == 200
    assert captured["llm_client"] is sentinel_client
