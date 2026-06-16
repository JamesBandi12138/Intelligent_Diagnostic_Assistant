from common.config import settings


def test_get_triage_llm_client_returns_async_client_when_enabled():
    from services.llm.factory import get_triage_llm_client

    settings.ENABLE_LLM_TRIAGE = True
    settings.LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    settings.LLM_API_KEY = "test-key"

    client = get_triage_llm_client()

    assert client is not None
    assert str(client.base_url) == "https://dashscope.aliyuncs.com/compatible-mode/v1/"


def test_get_triage_llm_client_returns_none_when_disabled():
    from services.llm.factory import get_triage_llm_client

    settings.ENABLE_LLM_TRIAGE = False

    assert get_triage_llm_client() is None
