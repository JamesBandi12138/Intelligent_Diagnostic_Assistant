from __future__ import annotations

from openai import AsyncOpenAI

from common.config import settings


def get_triage_llm_client() -> AsyncOpenAI | None:
    if not settings.ENABLE_LLM_TRIAGE:
        return None

    api_key = settings.LLM_API_KEY.strip()
    if not api_key or api_key == "replace-with-your-api-key":
        return None

    return AsyncOpenAI(
        api_key=api_key,
        base_url=settings.LLM_BASE_URL,
    )
