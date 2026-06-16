from __future__ import annotations

from typing import Any, TypedDict

from app.schemas.triage import AnalyzeResponse, LlmTraceEntry, PatientProfile, TriageMessage, TriageRequest


class TriageGraphState(TypedDict, total=False):
    llm_client: Any
    request: TriageRequest
    response: AnalyzeResponse
    session_id: str
    patient: PatientProfile | None
    city: str | None
    symptom_text: str
    latest_answer: str
    conversation_messages: list[TriageMessage]
    extracted_facts: dict[str, str]
    missing_fields: list[str]
    fact_confidence: dict[str, str]
    special_context_flags: dict[str, bool]
    risk_level: str
    risk_reasons: list[str]
    emergency_advice: str | None
    safety_decision: str
    workflow_status: str
    next_agent: str
    follow_up_question: str | None
    follow_up_rationale: str | None
    iteration_count: int
    completed: bool
    knowledge_hits: list[dict[str, Any]]
    knowledge_summary: str | None
    knowledge_used: bool
    current_agent: str | None
    node_trace: list[str]
    agent_trace: list[dict[str, str]]
    route_reason: str | None
    debug_snapshot: dict[str, Any]
    safety_checked: bool
    facts_updated: bool
    knowledge_checked: bool
    raw_follow_up_question: str | None
    llm_follow_up_question: str | None
    raw_report_summary: str | None
    llm_report_summary: str | None
    llm_used: bool
    llm_error: str | None
    llm_trace: list[LlmTraceEntry]
