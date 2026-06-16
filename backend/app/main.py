from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.reports import router as reports_router
from app.routers.triage import router as triage_router
from common.config import settings
from common.logging import logger


app = FastAPI(
    title="Intelligent Diagnostic Assistant API",
    description="诊前智能导诊与就医助手后端 API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(triage_router, prefix="/api")
app.include_router(reports_router, prefix="/api")


@app.get("/health")
async def health_check() -> dict[str, str]:
    logger.info("health check requested")
    return {
        "status": "healthy",
        "service": "intelligent-diagnostic-assistant",
        "env": settings.APP_ENV,
    }
