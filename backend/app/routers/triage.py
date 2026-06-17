from fastapi import APIRouter

from app.schemas.triage import AnalyzeResponse, TriageRequest, TriageSessionDetailResponse, TriageSessionResponse
from common.config import settings
from services.llm.factory import get_triage_llm_client
from services.session_store import create_session as create_session_record, get_session
from services.triage_graph.graph import run_triage


router = APIRouter(prefix="/triage", tags=["triage"])


@router.post(
    "/sessions",
    response_model=TriageSessionResponse,
    summary="创建导诊会话",
)
async def create_session() -> TriageSessionResponse:
    session = TriageSessionResponse.create()
    create_session_record(session.session_id)
    return session


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="提交症状或追问回答并推进导诊流程",
)
async def analyze_triage(request: TriageRequest):
    return await run_triage(request, llm_client=get_triage_llm_client())


@router.get(
    "/sessions/{session_id}",
    response_model=TriageSessionDetailResponse,
    summary="获取导诊会话详情",
)
async def get_session_detail(session_id: str) -> TriageSessionDetailResponse:
    session = get_session(session_id)
    if session is None:
        return TriageSessionDetailResponse(session_id=session_id, status="not_found")
    return TriageSessionDetailResponse(
        session_id=session.session_id,
        status=session.status,
        latest_request=session.latest_request,
        latest_result=session.latest_result,
        current_question=session.current_question,
        report_id=session.report_id,
        messages=session.messages,
        current_agent=session.current_agent,
        node_trace=session.node_trace,
        agent_trace=session.agent_trace,
        route_reason=session.route_reason,
        knowledge_summary=session.knowledge_summary,
        route_follow_up_history=session.route_follow_up_history,
        current_follow_up_topic=session.current_follow_up_topic,
        complaint_candidates=session.complaint_candidates,
        primary_focus_confirmed=session.primary_focus_confirmed,
        raw_follow_up_question=session.raw_follow_up_question,
        llm_follow_up_question=session.llm_follow_up_question,
        raw_report_summary=session.raw_report_summary,
        llm_report_summary=session.llm_report_summary,
        llm_enabled=settings.ENABLE_LLM_TRIAGE,
        llm_provider=settings.LLM_PROVIDER,
        llm_model=settings.LLM_MODEL,
        llm_base_url=settings.LLM_BASE_URL,
        llm_used=session.llm_used,
        llm_error=session.llm_error,
        llm_trace=session.llm_trace,
    )
