import asyncio

from app.schemas.triage import PatientProfile, TriageRequest
from services.triage_graph.graph import run_triage


class _FakeChatCompletions:
    def __init__(self, content: str):
        self._content = content

    async def create(self, **kwargs):
        return type(
            "Response",
            (),
            {
                "choices": [
                    type("Choice", (), {"message": type("Message", (), {"content": self._content})()})()
                ]
            },
        )()


class _FakeClient:
    def __init__(self, content: str):
        self.chat = type("Chat", (), {"completions": _FakeChatCompletions(content)})()


def test_run_triage_keeps_follow_up_contract_when_llm_client_is_supplied():
    request = TriageRequest(
        patient=PatientProfile(age=29, sex="female"),
        symptom_text="喉咙不舒服",
        city="上海",
    )
    llm_payload = """{
      "session_id": "llm-session",
      "risk_level": "medium",
      "emergency_advice": null,
      "recommended_departments": [
        {"name": "耳鼻喉科", "reason": "咽喉症状为主", "priority": 1}
      ],
      "care_path": "建议尽快门诊评估。",
      "preparation_checklist": ["携带既往检查报告"],
      "report_summary": "模型摘要",
      "disclaimer": "模型免责声明"
    }"""

    response = asyncio.run(run_triage(request, llm_client=_FakeClient(llm_payload)))

    assert response.status == "needs_follow_up"
    assert response.risk_level in ("low", "medium")
    assert response.question


def test_run_triage_returns_emergency_completion_even_if_llm_client_fails():
    class _FailingCompletions:
        async def create(self, **kwargs):
            raise RuntimeError("network unavailable")

    class _FailingClient:
        chat = type("Chat", (), {"completions": _FailingCompletions()})()

    request = TriageRequest(
        patient=PatientProfile(age=41, sex="male"),
        symptom_text="突然胸痛胸闷，大汗，感觉喘不上气",
        city="北京",
    )

    response = asyncio.run(run_triage(request, llm_client=_FailingClient()))

    assert response.status == "completed"
    assert response.risk_level == "emergency"
    assert response.recommended_departments[0].name == "急诊科"
