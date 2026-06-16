from fastapi import APIRouter, HTTPException

from app.schemas.report import ReportCreateRequest, ReportResponse
from services.report_generation.generator import generate_or_get_report
from services.report_generation.store import get_report


router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", response_model=ReportResponse, summary="生成导诊报告")
async def create_report(request: ReportCreateRequest) -> ReportResponse:
    return generate_or_get_report(request.session_id)


@router.get("/{report_id}", response_model=ReportResponse, summary="获取导诊报告详情")
async def get_report_detail(report_id: str) -> ReportResponse:
    report = get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return report
