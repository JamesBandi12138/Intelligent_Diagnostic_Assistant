from common.config import settings


def test_get_triage_llm_client_returns_async_client_when_enabled():
    from services.llm.factory import get_triage_llm_client

    settings.ENABLE_LLM_TRIAGE = True
    settings.LLM_PROVIDER = "deepseek"
    settings.LLM_BASE_URL = "https://api.deepseek.com"
    settings.LLM_API_KEY = "test-key"
    settings.LLM_MODEL = "deepseek-v4-flash"

    client = get_triage_llm_client()

    assert client is not None
    assert str(client.base_url).rstrip("/") == "https://api.deepseek.com"


def test_get_triage_llm_client_returns_none_when_disabled():
    from services.llm.factory import get_triage_llm_client

    settings.ENABLE_LLM_TRIAGE = False

    assert get_triage_llm_client() is None


def test_get_triage_llm_client_rejects_deepseek_placeholder_key():
    from services.llm.factory import get_triage_llm_client

    settings.ENABLE_LLM_TRIAGE = True
    settings.LLM_PROVIDER = "deepseek"
    settings.LLM_BASE_URL = "https://api.deepseek.com"
    settings.LLM_API_KEY = "replace-with-your-deepseek-api-key"
    settings.LLM_MODEL = "deepseek-v4-flash"

    assert get_triage_llm_client() is None
