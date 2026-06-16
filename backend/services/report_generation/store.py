from __future__ import annotations

import json
from typing import Any

from app.schemas.report import ReportResponse
from services.session_store import _redis_client


_MEMORY_REPORTS: dict[str, ReportResponse] = {}
_MEMORY_SESSION_REPORTS: dict[str, str] = {}


def _report_key(report_id: str) -> str:
    return f"ida:report:{report_id}"


def _session_report_key(session_id: str) -> str:
    return f"ida:session-report:{session_id}"


def save_report(report: ReportResponse) -> ReportResponse:
    client = _redis_client()
    if client is None:
        _MEMORY_REPORTS[report.report_id] = report
        _MEMORY_SESSION_REPORTS[report.session_id] = report.report_id
        return report

    client.set(_report_key(report.report_id), json.dumps(report.model_dump(mode="json"), ensure_ascii=False))
    client.set(_session_report_key(report.session_id), report.report_id)
    return report


def get_report(report_id: str) -> ReportResponse | None:
    client = _redis_client()
    if client is None:
        return _MEMORY_REPORTS.get(report_id)

    raw = client.get(_report_key(report_id))
    if not raw:
        return None
    return ReportResponse.model_validate(json.loads(raw))


def get_report_id_for_session(session_id: str) -> str | None:
    client = _redis_client()
    if client is None:
        return _MEMORY_SESSION_REPORTS.get(session_id)
    return client.get(_session_report_key(session_id))


def get_report_for_session(session_id: str) -> ReportResponse | None:
    report_id = get_report_id_for_session(session_id)
    if not report_id:
        return None
    return get_report(report_id)
