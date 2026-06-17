import asyncio
from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app
from app.schemas.triage import PatientProfile, TriageRequest
from common.config import settings
from services.triage_graph.graph import _result_agent


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


def test_abdominal_pain_follow_up_asks_route_specific_red_flag_question_first():
    session_id = f"abdomen-session-{uuid4()}"
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
            "symptom_text": "肚子疼",
        },
    )

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "needs_follow_up"
    assert "右下腹" in data["question"] or "具体在肚子哪个位置" in data["question"] or "固定在某一侧" in data["question"]
    assert "持续多久" not in data["question"]


def test_headache_follow_up_asks_route_specific_neuro_red_flag_question_first():
    session_id = f"headache-session-{uuid4()}"
    response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "patient": {
                "age": 32,
                "sex": "male",
                "medical_history": [],
                "allergies": [],
                "medications": [],
            },
            "symptom_text": "头痛",
        },
    )

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "needs_follow_up"
    assert "突然" in data["question"] or "视物" in data["question"] or "肢体" in data["question"] or "说话" in data["question"]
    assert "持续多久" not in data["question"]


def test_throat_follow_up_asks_route_specific_ent_question_first():
    session_id = f"throat-session-{uuid4()}"
    response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "patient": {
                "age": 27,
                "sex": "female",
                "medical_history": [],
                "allergies": [],
                "medications": [],
            },
            "symptom_text": "喉咙痛",
        },
    )

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "needs_follow_up"
    assert "发热" in data["question"] or "吞咽困难" in data["question"] or "呼吸受限" in data["question"]
    assert "持续多久" not in data["question"]


def test_eye_follow_up_asks_route_specific_ophthalmology_question_first():
    session_id = f"eye-session-{uuid4()}"
    response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "patient": {
                "age": 30,
                "sex": "male",
                "medical_history": [],
                "allergies": [],
                "medications": [],
            },
            "symptom_text": "眼睛不舒服",
        },
    )

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "needs_follow_up"
    assert "视力下降" in data["question"] or "畏光" in data["question"] or "隐形眼镜" in data["question"] or "外伤" in data["question"]
    assert "持续多久" not in data["question"]


def test_chest_pain_follow_up_asks_route_specific_question_first_when_not_emergency():
    session_id = f"chest-session-{uuid4()}"
    response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "patient": {
                "age": 24,
                "sex": "male",
                "medical_history": [],
                "allergies": [],
                "medications": [],
            },
            "symptom_text": "胸口有点刺痛",
        },
    )

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "needs_follow_up"
    assert "压榨样" in data["question"] or "刺痛样" in data["question"] or "左肩背部放射" in data["question"]
    assert "持续多久" not in data["question"]


def test_multi_symptom_input_asks_patient_to_prioritize_primary_problem_first():
    session_id = f"multi-symptom-session-{uuid4()}"
    response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "patient": {
                "age": 28,
                "sex": "female",
                "medical_history": [],
                "allergies": [],
                "medications": [],
            },
            "symptom_text": "喉咙痛两天，还伴有头痛，今天更明显",
        },
    )

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "needs_follow_up"
    assert "喉咙" in data["question"]
    assert "头痛" in data["question"]
    assert "哪个" in data["question"] or "更影响" in data["question"]
    assert "持续多久" not in data["question"]


def test_multi_symptom_follow_up_routes_into_selected_primary_complaint_path():
    session_id = f"multi-symptom-route-session-{uuid4()}"
    first_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "patient": {
                "age": 28,
                "sex": "female",
                "medical_history": [],
                "allergies": [],
                "medications": [],
            },
            "symptom_text": "喉咙痛两天，还伴有头痛，今天更明显",
        },
    )

    assert first_response.status_code == 200
    assert first_response.json()["status"] == "needs_follow_up"

    second_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "answer": "主要还是喉咙更难受，吞咽时更明显",
        },
    )

    data = second_response.json()
    assert second_response.status_code == 200
    assert data["status"] == "needs_follow_up"
    assert "发热" in data["question"] or "吞咽困难" in data["question"] or "呼吸受限" in data["question"]
    assert "头痛" not in data["question"]


def test_multi_symptom_session_detail_exposes_candidates_and_focus_state():
    session_id = f"multi-symptom-detail-session-{uuid4()}"
    client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "patient": {
                "age": 28,
                "sex": "female",
                "medical_history": [],
                "allergies": [],
                "medications": [],
            },
            "symptom_text": "喉咙痛两天，还伴有头痛，今天更明显",
        },
    )

    detail_response = client.get(f"/api/triage/sessions/{session_id}")
    detail = detail_response.json()

    assert detail_response.status_code == 200
    assert detail["current_follow_up_topic"] == "multi_symptom_priority"
    assert "throat_discomfort" in detail["complaint_candidates"]
    assert "headache" in detail["complaint_candidates"]
    assert detail["primary_focus_confirmed"] is False


def test_throat_follow_up_does_not_repeat_same_route_question_after_patient_answered_it():
    session_id = f"throat-repeat-session-{uuid4()}"
    first_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "patient": {
                "age": 27,
                "sex": "female",
                "medical_history": [],
                "allergies": [],
                "medications": [],
            },
            "symptom_text": "喉咙痛",
        },
    )

    assert first_response.status_code == 200
    first_data = first_response.json()
    assert first_data["status"] == "needs_follow_up"
    assert "发热" in first_data["question"] or "吞咽困难" in first_data["question"]

    second_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "answer": "没有发热，没有咳嗽，也没有吞咽困难或呼吸受限",
        },
    )

    second_data = second_response.json()
    assert second_response.status_code == 200
    assert second_data["status"] == "needs_follow_up"
    assert "发热" not in second_data["question"]
    assert "吞咽困难" not in second_data["question"]


def test_follow_up_can_answer_severity_scale_question_before_continuing_triage():
    session_id = f"severity-scale-session-{uuid4()}"
    first_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "patient": {
                "age": 29,
                "sex": "female",
                "medical_history": [],
                "allergies": [],
                "medications": [],
            },
            "symptom_text": "喉咙痛",
        },
    )

    assert first_response.status_code == 200
    assert first_response.json()["status"] == "needs_follow_up"

    second_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "answer": "1到10分的话一般怎么算？",
        },
    )

    second_data = second_response.json()
    assert second_response.status_code == 200
    assert second_data["status"] == "needs_follow_up"
    assert "1 到 3 分通常算轻" in second_data["question"] or "4 到 6 分" in second_data["question"]
    assert "现在不舒服的程度" in second_data["question"] or "大概几分" in second_data["question"]


def test_follow_up_can_explain_why_it_is_asking_current_question():
    session_id = f"why-asking-session-{uuid4()}"
    first_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "patient": {
                "age": 29,
                "sex": "female",
                "medical_history": [],
                "allergies": [],
                "medications": [],
            },
            "symptom_text": "眼睛不舒服",
        },
    )

    assert first_response.status_code == 200
    assert first_response.json()["status"] == "needs_follow_up"

    second_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "answer": "为什么要问这个？",
        },
    )

    second_data = second_response.json()
    assert second_response.status_code == 200
    assert second_data["status"] == "needs_follow_up"
    assert "这是为了判断" in second_data["question"] or "我这样问主要是为了判断" in second_data["question"]


def test_throat_case_can_complete_without_special_context_when_route_info_is_sufficient():
    session_id = f"throat-stop-session-{uuid4()}"
    first_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "patient": {
                "age": 29,
                "sex": "female",
                "medical_history": [],
                "allergies": [],
                "medications": [],
            },
            "symptom_text": "喉咙痛",
        },
    )

    assert first_response.status_code == 200
    assert first_response.json()["status"] == "needs_follow_up"

    second_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "answer": "三天了，吞咽时更明显，4分，没有发热咳嗽，也没有吞咽困难",
        },
    )

    second_data = second_response.json()
    assert second_response.status_code == 200
    assert second_data["status"] == "completed"
    assert second_data["recommended_departments"][0]["name"] == "耳鼻喉科"


def test_uncertain_answer_keeps_current_follow_up_topic_instead_of_skipping_ahead():
    session_id = f"uncertain-follow-up-session-{uuid4()}"
    first_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "patient": {
                "age": 30,
                "sex": "female",
                "medical_history": [],
                "allergies": [],
                "medications": [],
            },
            "symptom_text": "眼睛不舒服",
        },
    )

    first_data = first_response.json()
    assert first_response.status_code == 200
    assert first_data["status"] == "needs_follow_up"
    assert "视力下降" in first_data["question"] or "畏光" in first_data["question"] or "外伤" in first_data["question"]

    second_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "answer": "我有点说不清楚，也不太确定",
        },
    )

    second_data = second_response.json()
    assert second_response.status_code == 200
    assert second_data["status"] == "needs_follow_up"
    assert "如果暂时说不清" in second_data["question"] or "先告诉我更接近" in second_data["question"]
    assert "视力下降" in second_data["question"] or "畏光" in second_data["question"] or "外伤" in second_data["question"]


def test_follow_up_can_answer_department_intent_without_losing_current_topic():
    session_id = f"ask-department-session-{uuid4()}"
    first_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "patient": {
                "age": 31,
                "sex": "female",
                "medical_history": [],
                "allergies": [],
                "medications": [],
            },
            "symptom_text": "喉咙痛",
        },
    )

    assert first_response.status_code == 200
    assert first_response.json()["status"] == "needs_follow_up"

    second_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "answer": "那我大概挂什么科？",
        },
    )

    second_data = second_response.json()
    assert second_response.status_code == 200
    assert second_data["status"] == "needs_follow_up"
    assert "耳鼻喉科" in second_data["question"] or "方向判断" in second_data["question"]
    assert "发热" in second_data["question"] or "吞咽困难" in second_data["question"]


def test_follow_up_can_answer_urgency_intent_without_losing_current_topic():
    session_id = f"ask-urgency-session-{uuid4()}"
    first_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "patient": {
                "age": 31,
                "sex": "male",
                "medical_history": [],
                "allergies": [],
                "medications": [],
            },
            "symptom_text": "胸口有点刺痛",
        },
    )

    assert first_response.status_code == 200
    assert first_response.json()["status"] == "needs_follow_up"

    second_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "answer": "那我现在要马上去医院吗？",
        },
    )

    second_data = second_response.json()
    assert second_response.status_code == 200
    assert second_data["status"] == "needs_follow_up"
    assert "暂时不像必须立刻急诊" in second_data["question"] or "最好尽快线下面诊" in second_data["question"]
    assert "压榨样" in second_data["question"] or "刺痛样" in second_data["question"] or "左肩背部放射" in second_data["question"]


def test_defer_answer_keeps_same_follow_up_topic_with_gentle_prompt():
    session_id = f"defer-answer-session-{uuid4()}"
    first_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "patient": {
                "age": 31,
                "sex": "female",
                "medical_history": [],
                "allergies": [],
                "medications": [],
            },
            "symptom_text": "眼睛不舒服",
        },
    )

    assert first_response.status_code == 200
    assert first_response.json()["status"] == "needs_follow_up"

    second_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "answer": "这个我现在不太想回答，先说别的",
        },
    )

    second_data = second_response.json()
    assert second_response.status_code == 200
    assert second_data["status"] == "needs_follow_up"
    assert "如果暂时说不清也没关系" in second_data["question"] or "先告诉我更接近哪一种" in second_data["question"]
    assert "视力下降" in second_data["question"] or "畏光" in second_data["question"] or "外伤" in second_data["question"]


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


def test_male_patient_cannot_submit_pregnancy_status():
    response = client.post(
        "/api/triage/analyze",
        json={
            "patient": {
                "age": 32,
                "sex": "male",
                "pregnancy_status": "孕早期",
                "medical_history": [],
                "allergies": [],
                "medications": [],
            },
            "symptom_text": "肚子疼两天，疼痛4分，没有发热呕吐",
        },
    )

    assert response.status_code == 422
    assert "男性不能填写孕产状态" in response.text


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


def test_completed_session_can_answer_department_reason_follow_up():
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
    assert first_response.status_code == 200

    complete_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "answer": "喉咙痛三天，吞咽时更明显，疼痛程度约4到5分，没有发烧咳嗽，也没有慢性病",
        },
    )
    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == "completed"

    explain_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "answer": "为什么建议这个科？",
        },
    )

    data = explain_response.json()
    assert explain_response.status_code == 200
    assert data["status"] == "completed"
    assert "耳鼻喉科" in data["report_summary"]
    assert "咽喉" in data["report_summary"] or "吞咽" in data["report_summary"]


def test_completed_session_can_answer_urgency_follow_up():
    create_response = client.post("/api/triage/sessions")
    session_id = create_response.json()["session_id"]

    client.post(
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
    client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "answer": "喉咙痛三天，吞咽时更明显，疼痛程度约4到5分，没有发烧咳嗽，也没有慢性病",
        },
    )

    explain_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "answer": "我现在要不要马上去医院？",
        },
    )

    data = explain_response.json()
    assert explain_response.status_code == 200
    assert data["status"] == "completed"
    assert "急诊" in data["report_summary"] or "线下面诊" in data["report_summary"] or "门诊" in data["report_summary"]


def test_completed_session_can_answer_next_step_follow_up():
    create_response = client.post("/api/triage/sessions")
    session_id = create_response.json()["session_id"]

    client.post(
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
    client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "answer": "喉咙痛三天，吞咽时更明显，疼痛程度约4到5分，没有发烧咳嗽，也没有慢性病",
        },
    )

    explain_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "answer": "那我现在最该先做什么？",
        },
    )

    data = explain_response.json()
    assert explain_response.status_code == 200
    assert data["status"] == "completed"
    assert "下一步" in data["report_summary"] or "先" in data["report_summary"]
    assert "门诊" in data["report_summary"] or "就医" in data["report_summary"]


def test_completed_session_can_answer_preparation_follow_up():
    create_response = client.post("/api/triage/sessions")
    session_id = create_response.json()["session_id"]

    client.post(
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
    client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "answer": "喉咙痛三天，吞咽时更明显，疼痛程度约4到5分，没有发烧咳嗽，也没有慢性病",
        },
    )

    explain_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "answer": "去医院前我要准备什么？",
        },
    )

    data = explain_response.json()
    assert explain_response.status_code == 200
    assert data["status"] == "completed"
    assert "准备" in data["report_summary"] or "携带" in data["report_summary"]
    assert "病历" in data["report_summary"] or "用药" in data["report_summary"]


def test_completed_session_can_answer_online_visit_follow_up():
    create_response = client.post("/api/triage/sessions")
    session_id = create_response.json()["session_id"]

    client.post(
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
    client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "answer": "喉咙痛三天，吞咽时更明显，疼痛程度约4到5分，没有发烧咳嗽，也没有慢性病",
        },
    )

    explain_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "answer": "我可以先线上问诊吗？",
        },
    )

    data = explain_response.json()
    assert explain_response.status_code == 200
    assert data["status"] == "completed"
    assert "线上" in data["report_summary"] or "线下" in data["report_summary"]


def test_completed_session_still_rejects_new_symptom_input():
    create_response = client.post("/api/triage/sessions")
    session_id = create_response.json()["session_id"]

    client.post(
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
    client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "answer": "喉咙痛三天，吞咽时更明显，疼痛程度约4到5分，没有发烧咳嗽，也没有慢性病",
        },
    )

    explain_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "answer": "我现在又开始肚子疼了，还有点恶心",
        },
    )

    assert explain_response.status_code == 409


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
            "city": "北京",
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


def test_route_specific_follow_up_flow_persists_local_knowledge_summary():
    session_id = f"knowledge-session-{uuid4()}"
    analyze_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "patient": {
                "age": 28,
                "sex": "female",
                "medical_history": [],
                "allergies": [],
                "medications": [],
            },
            "symptom_text": "肚子疼",
        },
    )

    assert analyze_response.status_code == 200

    session_response = client.get(f"/api/triage/sessions/{session_id}")
    session_data = session_response.json()

    assert session_response.status_code == 200
    assert session_data["knowledge_summary"]
    assert "腹痛" in session_data["knowledge_summary"]


def test_completed_triage_result_includes_local_knowledge_note_for_abdominal_pain():
    state = {
        "request": TriageRequest(
            session_id=f"knowledge-result-session-{uuid4()}",
            patient=PatientProfile(age=32, sex="female", medical_history=[], allergies=[], medications=[]),
            symptom_text="右下腹疼了一天，疼痛6分，没有发热，没有黑便，也没有明显呕吐，也没有慢性病",
        ),
        "session_id": f"knowledge-result-session-{uuid4()}",
        "patient": PatientProfile(age=32, sex="female", medical_history=[], allergies=[], medications=[]),
        "symptom_text": "右下腹疼了一天，疼痛6分，没有发热，没有黑便，也没有明显呕吐，也没有慢性病",
        "latest_answer": "",
        "conversation_messages": [],
        "risk_level": "medium",
        "safety_decision": "continue",
        "node_trace": [],
        "agent_trace": [],
        "llm_trace": [],
        "knowledge_hits": [
            {
                "title": "腹痛导诊卡",
                "content": "腹痛导诊优先确认疼痛位置、起病时间、疼痛程度，以及是否伴随发热、呕吐、黑便或压痛加重。 红旗信号：持续加重的右下腹痛、呕吐明显、黑便、腹部压痛反跳痛。 优先追问：疼痛最明显在上腹、脐周还是右下腹；是否有发热、呕吐、腹泻或黑便；疼痛是持续痛还是阵发性绞痛。 候选科室：消化内科、普外科、急诊科。 图谱高频科室：内科、消化内科、外科。",
                "score": "6.0",
            }
        ],
    }

    result_state = asyncio.run(_result_agent(state))
    response = result_state["response"]

    assert response.status == "completed"
    assert "本地导诊知识" in response.report_summary
    assert "消化内科" in response.report_summary or "普外科" in response.report_summary or "急诊科" in response.report_summary


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


def test_latest_follow_up_symptom_replaces_old_location_without_magic_correction_words():
    create_response = client.post("/api/triage/sessions")
    session_id = create_response.json()["session_id"]

    first_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "patient": {
                "age": 34,
                "sex": "male",
                "medical_history": [],
                "allergies": [],
                "medications": [],
            },
            "symptom_text": "肚子疼",
        },
    )

    assert first_response.status_code == 200
    assert first_response.json()["status"] == "needs_follow_up"

    corrected_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "answer": "改成脑袋疼，两天了，疼痛6分，没有发热呕吐，也没有慢性病。",
        },
    )

    corrected_data = corrected_response.json()
    session_data = client.get(f"/api/triage/sessions/{session_id}").json()

    assert corrected_response.status_code == 200
    assert corrected_data["status"] == "completed"
    assert corrected_data["recommended_departments"][0]["name"] == "神经内科"
    assert "脑袋疼" in corrected_data["report_summary"]
    assert session_data["latest_result"]["recommended_departments"][0]["name"] == "神经内科"


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


def test_correction_message_replaces_initial_wrong_symptom_and_changes_department():
    create_response = client.post("/api/triage/sessions")
    session_id = create_response.json()["session_id"]

    first_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "patient": {
                "age": 30,
                "sex": "female",
                "medical_history": [],
                "allergies": [],
                "medications": [],
            },
            "symptom_text": "胸口疼",
        },
    )

    assert first_response.status_code == 200
    assert first_response.json()["status"] == "needs_follow_up"

    corrected_response = client.post(
        "/api/triage/analyze",
        json={
            "session_id": session_id,
            "answer": "刚才说错了，不是胸口，是喉咙痛三天，吞咽时更明显，轻微，没有胸痛气短，也没有慢性病。",
        },
    )

    corrected_data = corrected_response.json()

    assert corrected_response.status_code == 200
    assert corrected_data["status"] == "completed"
    assert corrected_data["recommended_departments"][0]["name"] == "耳鼻喉科"
    assert corrected_data["risk_level"] in ("low", "medium")
    assert "喉咙" in corrected_data["report_summary"]
    assert "刚才说错" not in corrected_data["report_summary"]
