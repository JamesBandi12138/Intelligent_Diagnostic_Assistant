import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "dev"
    APP_PORT: int = 8000
    CORS_ORIGINS: list[str] = ["*"]

    LLM_PROVIDER: str = "qwen"
    LLM_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    LLM_API_KEY: str = "replace-with-your-api-key"
    LLM_MODEL: str = "qwen-plus"
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 2048
    ENABLE_LLM_TRIAGE: bool = False

    ENABLE_TAVILY_SEARCH: bool = False
    TAVILY_API_KEY: str = ""

    REDIS_URL: str = "redis://localhost:6380/0"
    REDIS_PREFIX: str = "ida"
    SESSION_TTL_SECONDS: int = 60 * 60 * 24 * 7

    MILVUS_ENABLED: bool = False
    MILVUS_URI: str = "http://localhost:19530"
    MILVUS_TOKEN: str = ""
    MILVUS_COLLECTION: str = "ida_knowledge"

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
