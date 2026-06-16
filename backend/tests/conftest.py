import pytest

from common.config import settings


@pytest.fixture(autouse=True)
def isolate_llm_settings():
    original = {
        "ENABLE_LLM_TRIAGE": settings.ENABLE_LLM_TRIAGE,
        "LLM_PROVIDER": settings.LLM_PROVIDER,
        "LLM_BASE_URL": settings.LLM_BASE_URL,
        "LLM_API_KEY": settings.LLM_API_KEY,
        "LLM_MODEL": settings.LLM_MODEL,
    }

    settings.ENABLE_LLM_TRIAGE = False
    settings.LLM_PROVIDER = "deepseek"
    settings.LLM_BASE_URL = "https://api.deepseek.com"
    settings.LLM_API_KEY = "replace-with-your-deepseek-api-key"
    settings.LLM_MODEL = "deepseek-v4-flash"

    yield

    for key, value in original.items():
        setattr(settings, key, value)
