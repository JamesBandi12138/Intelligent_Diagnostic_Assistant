import asyncio

from app.schemas.triage import PatientProfile, TriageRequest
from services.safety_guardrails.service import detect_risk
from services.triage_graph.graph import run_triage
from services.triage_graph.graph import _extract_facts


def test_detect_risk_marks_persistent_fever_and_cough_as_high():
    risk_level, emergency_advice = detect_risk("发烧4天，咳嗽加重，乏力，咽痛，精神一般")

    assert risk_level == "high"
    assert emergency_advice is None


def test_detect_risk_marks_mild_sore_throat_as_medium():
    risk_level, emergency_advice = detect_risk("喉咙有点疼，轻微流鼻涕")

    assert risk_level == "medium"
    assert emergency_advice is None


def test_detect_risk_does_not_escalate_when_common_symptoms_are_explicitly_denied():
    risk_level, emergency_advice = detect_risk("喉咙痛三天，没有发烧咳嗽，也没有胸闷气短")

    assert risk_level in ("low", "medium")
    assert emergency_advice is None


def test_extract_facts_does_not_mark_chronic_disease_when_explicitly_denied():
    _, _, flags = _extract_facts("右眼发红两天，没有慢性病", PatientProfile(age=31, sex="female"))

    assert flags["chronic_disease"] is False


def test_run_triage_keeps_high_risk_cases_in_follow_up_when_not_emergency():
    response = asyncio.run(
        run_triage(
            TriageRequest(
                patient=PatientProfile(age=41, sex="male"),
                symptom_text="发烧4天，咳嗽加重，乏力，咽痛，精神一般",
                city="北京",
            )
        )
    )

    assert response.status == "needs_follow_up"
    assert response.risk_level == "high"
    assert response.question
