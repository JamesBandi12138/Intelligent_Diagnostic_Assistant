from __future__ import annotations

from fastapi import HTTPException

from app.schemas.report import DoctorView, PatientView, ReportPatientSnapshot, ReportResponse, ReportTriageSummary
from app.schemas.triage import TriageResponse, TriageStatus
from services.report_generation.store import get_report_for_session, save_report
from services.session_store import SessionRecord, get_session, save_session


def generate_or_get_report(session_id: str) -> ReportResponse:
    existing = get_report_for_session(session_id)
    if existing is not None:
        return existing

    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Triage session not found.")
    if session.status != TriageStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="Report can only be generated after triage is completed.")
    if session.patient is None:
        raise HTTPException(status_code=409, detail="Completed session is missing patient information.")
    if session.latest_result is None or not isinstance(session.latest_result, TriageResponse):
        raise HTTPException(status_code=409, detail="Completed session is missing final triage result.")

    report = ReportResponse.create(
        session_id=session.session_id,
        patient_snapshot=ReportPatientSnapshot.from_patient(session.patient),
        triage_summary=ReportTriageSummary(
            chief_complaint=session.symptom_text or session.latest_result.report_summary,
            risk_level=session.latest_result.risk_level,
            recommended_departments=session.latest_result.recommended_departments,
            care_path=session.latest_result.care_path,
            generated_from_session_status=session.status,
        ),
        doctor_view=_build_doctor_view(session),
        patient_view=_build_patient_view(session),
        disclaimer=session.latest_result.disclaimer,
    )

    save_report(report)
    session.report_id = report.report_id
    save_session(session)
    return report


def _build_doctor_view(session: SessionRecord) -> DoctorView:
    final_result = session.latest_result
    assert isinstance(final_result, TriageResponse)
    department_text = "、".join(item.name for item in final_result.recommended_departments) or "暂未推荐"

    if final_result.emergency_advice:
        risk_notes = final_result.emergency_advice
    else:
        risk_notes = f"当前导诊风险等级为 {final_result.risk_level}，建议结合线下面诊进一步确认。"

    return DoctorView(
        chief_complaint=session.symptom_text or "未记录",
        key_facts=session.extracted_facts,
        risk_notes=risk_notes,
        recommended_department_summary=f"建议优先就诊：{department_text}",
        preparation_checklist=final_result.preparation_checklist,
    )


def _build_patient_view(session: SessionRecord) -> PatientView:
    final_result = session.latest_result
    assert isinstance(final_result, TriageResponse)
    department_names = "、".join(item.name for item in final_result.recommended_departments) or "相关门诊"
    primary_reason = final_result.recommended_departments[0].reason if final_result.recommended_departments else "系统根据你补充的信息整理了当前更合适的就诊方向。"
    urgent_note = (
        final_result.emergency_advice
        or "如果出现胸痛、呼吸困难、意识异常、大出血或症状明显加重，请不要等待，尽快急诊就医。"
    )

    return PatientView(
        what_this_means=f"这份报告是根据你当前补充的症状信息整理出的诊前摘要，建议优先考虑 {department_names}。",
        why_this_department=primary_reason,
        what_to_prepare=final_result.preparation_checklist,
        when_to_seek_urgent_care=urgent_note,
    )
