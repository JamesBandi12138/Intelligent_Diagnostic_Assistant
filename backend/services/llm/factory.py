from __future__ import annotations

from openai import AsyncOpenAI

from common.config import settings


PLACEHOLDER_API_KEYS = {
    "replace-with-your-api-key",
    "replace-with-your-deepseek-api-key",
    "your-api-key",
    "your-deepseek-api-key",
}


def _has_real_api_key(api_key: str) -> bool:
    normalized = api_key.strip()
    return bool(normalized) and normalized.lower() not in PLACEHOLDER_API_KEYS


def get_triage_llm_client() -> AsyncOpenAI | None:
    if not settings.ENABLE_LLM_TRIAGE:
        return None

    api_key = settings.LLM_API_KEY.strip()
    if not _has_real_api_key(api_key):
        return None

    return AsyncOpenAI(
        api_key=api_key,
        base_url=settings.LLM_BASE_URL,
    )
