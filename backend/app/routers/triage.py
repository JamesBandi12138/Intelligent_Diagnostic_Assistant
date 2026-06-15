from fastapi import APIRouter

from app.schemas.triage import TriageRequest, TriageResponse, TriageSessionResponse
from services.triage_graph.graph import run_triage


router = APIRouter(prefix="/triage", tags=["triage"])


@router.post(
    "/sessions",
    response_model=TriageSessionResponse,
    summary="创建导诊会话",
)
async def create_session() -> TriageSessionResponse:
    return TriageSessionResponse.create()


@router.post(
    "/analyze",
    response_model=TriageResponse,
    summary="提交症状并获取导诊建议",
    description="当前为框架阶段的确定性导诊骨架，后续替换为 LangGraph 多 Agent 实现。",
)
async def analyze_triage(request: TriageRequest) -> TriageResponse:
    return run_triage(request)

