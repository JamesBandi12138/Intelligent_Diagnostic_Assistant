import asyncio
from uuid import uuid4

from app.schemas.triage import PatientProfile, TriageRequest
from services.session_store import get_session
from services.triage_graph.graph import run_triage


LLM_EXTRACT_THROAT_LOCATION = '{"facts":{"location":"咽喉"},"missing_fields":["duration","severity","accompanying_symptoms","special_context"]}'
LLM_EXTRACT_THROAT_COMPLETE = (
    '{"facts":{"location":"咽喉","duration":"三天","severity":"4分",'
    '"accompanying_symptoms":"吞咽时更明显，否认发烧咳嗽","special_context":"无慢性病"},'
    '"missing_fields":[]}'
)


class _FakeChatCompletions:
    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        content = self._responses.pop(0)
        return type(
            "Response",
            (),
            {
                "choices": [
                    type("Choice", (), {"message": type("Message", (), {"content": content})()})()
                ]
            },
        )()


class _FakeClient:
    def __init__(self, responses: list[str]):
        self.completions = _FakeChatCompletions(responses)
        self.chat = type("Chat", (), {"completions": self.completions})()


def test_follow_up_agent_prefers_llm_rewritten_question_and_records_trace():
    session_id = f"llm-follow-up-{uuid4()}"
    request = TriageRequest(
        session_id=session_id,
        patient=PatientProfile(age=29, sex="female"),
        symptom_text="喉咙不舒服",
        city="上海",
    )

    response = asyncio.run(
        run_triage(
            request,
            llm_client=_FakeClient(
                [
                    LLM_EXTRACT_THROAT_LOCATION,
                    '{"question":"喉咙不舒服大概持续多久了，是突然开始还是慢慢加重的？"}',
                ]
            ),
        )
    )

    session = get_session(session_id)

    assert response.status == "needs_follow_up"
    assert response.question == "喉咙不舒服大概持续多久了，是突然开始还是慢慢加重的？"
    assert session is not None
    assert session.route_reason
    assert any(item["agent"] == "follow_up_agent" for item in session.agent_trace)
    assert session.to_payload()["llm_used"] is True
    assert session.to_payload()["raw_follow_up_question"]
    assert session.to_payload()["llm_follow_up_question"] == response.question
    assert session.to_payload()["llm_trace"][1]["task"] == "rewrite_follow_up_question"


def test_deepseek_json_calls_disable_thinking_and_request_json_output():
    from common.config import settings

    settings.LLM_PROVIDER = "deepseek"
    session_id = f"llm-deepseek-options-{uuid4()}"
    request = TriageRequest(
        session_id=session_id,
        patient=PatientProfile(age=29, sex="female"),
        symptom_text="喉咙不舒服",
        city="上海",
    )
    client = _FakeClient([LLM_EXTRACT_THROAT_LOCATION, '{"question":"喉咙不舒服持续多久了？"}'])

    asyncio.run(run_triage(request, llm_client=client))

    call = client.completions.calls[0]
    assert call["response_format"] == {"type": "json_object"}
    assert call["extra_body"] == {"thinking": {"type": "disabled"}}


def test_symptom_intake_agent_uses_llm_structured_facts_before_follow_up_or_result():
    session_id = f"llm-symptom-intake-{uuid4()}"
    request = TriageRequest(
        session_id=session_id,
        patient=PatientProfile(age=31, sex="female"),
        symptom_text="右眼发红发痒两天，有异物感，疼痛大概2分，没有视物模糊，也没有慢性病",
        city="杭州",
    )
    client = _FakeClient(
        [
            (
                '{"facts":{"location":"眼部","duration":"两天","severity":"2分",'
                '"accompanying_symptoms":"发红、发痒、异物感，否认视物模糊",'
                '"special_context":"无慢性病"},"missing_fields":[]}'
            ),
            '{"report_summary":"已整理眼部不适信息，建议先线下门诊评估。"}',
        ]
    )

    response = asyncio.run(run_triage(request, llm_client=client))
    session = get_session(session_id)

    assert response.status == "completed"
    assert response.recommended_departments[0].name == "眼科"
    assert session is not None
    assert session.extracted_facts["location"] == "眼部"
    assert session.extracted_facts["duration"] == "两天"
    assert session.extracted_facts["severity"] == "2分"
    assert session.missing_fields == []
    assert session.fact_confidence["location"] == "rule"
    assert any(entry.task == "extract_structured_symptoms" and entry.used for entry in session.llm_trace)


def test_symptom_intake_keeps_rule_facts_when_llm_conflicts_with_clear_text():
    session_id = f"llm-symptom-conflict-{uuid4()}"
    request = TriageRequest(
        session_id=session_id,
        patient=PatientProfile(age=31, sex="female"),
        symptom_text="右眼发红发痒两天，有异物感，疼痛大概2分，没有视物模糊，也没有慢性病",
        city="杭州",
    )
    client = _FakeClient(
        [
            (
                '{"facts":{"location":"腹部","duration":"两天",'
                '"accompanying_symptoms":"发红、发痒","special_context":"无慢性病"},'
                '"missing_fields":["severity"]}'
            ),
            '{"report_summary":"已整理眼部不适信息，建议先眼科门诊评估。"}',
        ]
    )

    response = asyncio.run(run_triage(request, llm_client=client))
    session = get_session(session_id)

    assert response.status == "completed"
    assert response.recommended_departments[0].name == "眼科"
    assert session is not None
    assert session.extracted_facts["location"] == "眼部"
    assert session.extracted_facts["severity"] == "2分"
    assert session.fact_confidence["location"] == "rule"
    assert session.fact_confidence["severity"] == "rule"


def test_follow_up_agent_accepts_markdown_wrapped_json_from_llm():
    session_id = f"llm-follow-up-markdown-{uuid4()}"
    request = TriageRequest(
        session_id=session_id,
        patient=PatientProfile(age=29, sex="female"),
        symptom_text="throat discomfort",
        city="涓婃捣",
    )

    response = asyncio.run(
        run_triage(
            request,
            llm_client=_FakeClient(
                [
                    LLM_EXTRACT_THROAT_LOCATION,
                    '```json\n{"question":"鍠夊挋涓嶈垝鏈嶅ぇ姒傛寔缁涔呬簡锛屾槸绐佺劧寮€濮嬭繕鏄參鎱㈠姞閲嶇殑锛?"}\n```'
                ]
            ),
        )
    )

    session = get_session(session_id)

    assert response.status == "needs_follow_up"
    assert session is not None
    assert session.to_payload()["llm_used"] is True
    assert session.to_payload()["llm_error"] is None
    assert session.to_payload()["llm_follow_up_question"] == response.question


def test_follow_up_agent_maps_provider_access_denied_to_transport_error():
    class _QuotaDeniedCompletions:
        async def create(self, **kwargs):
            raise RuntimeError("Access denied, account Arrearage, insufficient quota")

    class _QuotaDeniedClient:
        chat = type("Chat", (), {"completions": _QuotaDeniedCompletions()})()

    session_id = f"llm-follow-up-quota-{uuid4()}"
    request = TriageRequest(
        session_id=session_id,
        patient=PatientProfile(age=29, sex="female"),
        symptom_text="throat discomfort",
        city="上海",
    )

    response = asyncio.run(run_triage(request, llm_client=_QuotaDeniedClient()))
    session = get_session(session_id)

    assert response.status == "needs_follow_up"
    assert session is not None
    assert session.to_payload()["llm_used"] is False
    assert session.to_payload()["llm_error"] == "transport_error"


def test_follow_up_agent_falls_back_to_rule_question_when_llm_fails():
    class _FailingCompletions:
        async def create(self, **kwargs):
            raise RuntimeError("network unavailable")

    class _FailingClient:
        chat = type("Chat", (), {"completions": _FailingCompletions()})()

    session_id = f"llm-follow-up-{uuid4()}"
    request = TriageRequest(
        session_id=session_id,
        patient=PatientProfile(age=29, sex="female"),
        symptom_text="喉咙不舒服",
        city="上海",
    )

    response = asyncio.run(run_triage(request, llm_client=_FailingClient()))
    session = get_session(session_id)

    assert response.status == "needs_follow_up"
    assert "发热" in response.question or "吞咽困难" in response.question or "呼吸受限" in response.question
    assert session is not None
    assert session.to_payload()["llm_used"] is False
    assert session.to_payload()["llm_error"] == "transport_error"
    assert session.to_payload()["raw_follow_up_question"] == response.question
    assert session.to_payload()["llm_follow_up_question"] is None
    assert session.to_payload()["llm_trace"][0]["fallback"] is True


def test_result_agent_prefers_llm_rewritten_summary_and_records_trace():
    session_id = f"llm-result-{uuid4()}"
    initial_request = TriageRequest(
        session_id=session_id,
        patient=PatientProfile(age=26, sex="female"),
        symptom_text="喉咙不舒服",
        city="上海",
    )
    asyncio.run(
        run_triage(
            initial_request,
            llm_client=_FakeClient(
                [
                    LLM_EXTRACT_THROAT_LOCATION,
                    '{"question":"这次喉咙不舒服已经持续多久了？吞咽时会更明显吗？"}',
                ]
            ),
        )
    )

    follow_up_request = TriageRequest(
        session_id=session_id,
        answer="喉咙痛三天，吞咽时更明显，疼痛大约4分，没有发烧咳嗽，也没有慢性病",
    )
    response = asyncio.run(
        run_triage(
            follow_up_request,
            llm_client=_FakeClient(
                [
                    LLM_EXTRACT_THROAT_COMPLETE,
                    '{"report_summary":"根据你补充的情况，目前更建议优先到耳鼻喉科门诊评估喉咙不适。"}',
                ]
            ),
        )
    )

    session = get_session(session_id)

    assert response.status == "completed"
    assert response.report_summary == "根据你补充的情况，目前更建议优先到耳鼻喉科门诊评估喉咙不适。"
    assert session is not None
    assert session.to_payload()["llm_used"] is True
    assert session.to_payload()["raw_report_summary"]
    assert session.to_payload()["llm_report_summary"] == response.report_summary
    assert session.to_payload()["llm_trace"][-1]["task"] == "rewrite_report_summary"


def test_result_agent_falls_back_to_rule_summary_when_llm_output_is_invalid():
    session_id = f"llm-result-{uuid4()}"
    initial_request = TriageRequest(
        session_id=session_id,
        patient=PatientProfile(age=26, sex="female"),
        symptom_text="喉咙不舒服",
        city="上海",
    )
    asyncio.run(
        run_triage(
            initial_request,
            llm_client=_FakeClient(
                [
                    LLM_EXTRACT_THROAT_LOCATION,
                    '{"question":"这次喉咙不舒服已经持续多久了？吞咽时会更明显吗？"}',
                ]
            ),
        )
    )

    follow_up_request = TriageRequest(
        session_id=session_id,
        answer="喉咙痛三天，吞咽时更明显，疼痛大约4分，没有发烧咳嗽，也没有慢性病",
    )
    response = asyncio.run(run_triage(follow_up_request, llm_client=_FakeClient([LLM_EXTRACT_THROAT_COMPLETE, '{}'])))
    session = get_session(session_id)

    assert response.status == "completed"
    assert "建议优先咨询" in response.report_summary
    assert session is not None
    assert session.to_payload()["llm_used"] is False
    assert session.to_payload()["llm_error"] == "format_error"
    assert session.to_payload()["raw_report_summary"] == response.report_summary
    assert session.to_payload()["llm_report_summary"] is None


def test_run_triage_returns_emergency_completion_even_if_llm_client_fails():
    class _FailingCompletions:
        async def create(self, **kwargs):
            raise RuntimeError("network unavailable")

    class _FailingClient:
        chat = type("Chat", (), {"completions": _FailingCompletions()})()

    request = TriageRequest(
        session_id=f"llm-emergency-{uuid4()}",
        patient=PatientProfile(age=41, sex="male"),
        symptom_text="突然胸痛胸闷，大汗，感觉喘不上气",
        city="北京",
    )

    response = asyncio.run(run_triage(request, llm_client=_FailingClient()))

    assert response.status == "completed"
    assert response.risk_level == "emergency"
    assert response.recommended_departments[0].name == "急诊科"
