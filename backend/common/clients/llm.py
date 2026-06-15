from openai import AsyncOpenAI

from common.config import settings


def get_llm_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        timeout=60,
        max_retries=2,
    )

