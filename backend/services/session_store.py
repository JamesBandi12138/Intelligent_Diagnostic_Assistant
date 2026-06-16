from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from redis import Redis

from app.schemas.triage import AnalyzeResponse, PatientProfile, TriageMessage, TriageRequest
from common.config import settings


@dataclass
class SessionRecord:
    session_id: str
    status: str = "created"
    patient: PatientProfile | None = None
    city: str | None = None
    symptom_text: str | None = None
    extracted_facts: dict[str, str] = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    answered_follow_ups: list[str] = field(default_factory=list)
    current_question: str | None = None
    risk_level: str | None = None
    latest_request: TriageRequest | None = None
    latest_result: AnalyzeResponse | None = None
    final_result: dict[str, Any] | None = None
    messages: list[TriageMessage] = field(default_factory=list)

    def to_payload(self) -> dict:
        return {
            "session_id": self.session_id,
            "status": self.status,
            "patient": self.patient.model_dump(mode="json") if self.patient else None,
            "city": self.city,
            "symptom_text": self.symptom_text,
            "extracted_facts": self.extracted_facts,
            "missing_fields": self.missing_fields,
            "answered_follow_ups": self.answered_follow_ups,
            "current_question": self.current_question,
            "risk_level": self.risk_level,
            "latest_request": self.latest_request.model_dump(mode="json") if self.latest_request else None,
            "latest_result": self.latest_result.model_dump(mode="json") if self.latest_result else None,
            "final_result": self.final_result,
            "messages": [message.model_dump(mode="json") for message in self.messages],
        }

    @classmethod
    def from_payload(cls, payload: dict) -> "SessionRecord":
        latest_request = payload.get("latest_request")
        latest_result = payload.get("latest_result")
        patient = payload.get("patient")
        return cls(
            session_id=payload["session_id"],
            status=payload.get("status", "created"),
            patient=PatientProfile.model_validate(patient) if patient else None,
            city=payload.get("city"),
            symptom_text=payload.get("symptom_text"),
            extracted_facts=payload.get("extracted_facts", {}),
            missing_fields=payload.get("missing_fields", []),
            answered_follow_ups=payload.get("answered_follow_ups", []),
            current_question=payload.get("current_question"),
            risk_level=payload.get("risk_level"),
            latest_request=TriageRequest.model_validate(latest_request) if latest_request else None,
            latest_result=_validate_analyze_response(latest_result),
            final_result=payload.get("final_result"),
            messages=[TriageMessage.model_validate(item) for item in payload.get("messages", [])],
        )


def _validate_analyze_response(payload: dict | None) -> AnalyzeResponse | None:
    if not payload:
        return None
    if payload.get("status") == "needs_follow_up":
        from app.schemas.triage import FollowUpResponse

        return FollowUpResponse.model_validate(payload)
    from app.schemas.triage import TriageResponse

    return TriageResponse.model_validate(payload)


_MEMORY_SESSIONS: dict[str, SessionRecord] = {}


@lru_cache(maxsize=1)
def _redis_client() -> Redis | None:
    try:
        client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None


def _session_key(session_id: str) -> str:
    return f"{settings.REDIS_PREFIX}:session:{session_id}"


def _save_record(record: SessionRecord) -> SessionRecord:
    client = _redis_client()
    if client is None:
        _MEMORY_SESSIONS[record.session_id] = record
        return record

    client.set(
        _session_key(record.session_id),
        json.dumps(record.to_payload(), ensure_ascii=False),
        ex=settings.SESSION_TTL_SECONDS,
    )
    return record


def create_session(session_id: str) -> SessionRecord:
    return _save_record(SessionRecord(session_id=session_id))


def save_session(record: SessionRecord) -> SessionRecord:
    return _save_record(record)


def get_session(session_id: str) -> SessionRecord | None:
    client = _redis_client()
    if client is None:
        return _MEMORY_SESSIONS.get(session_id)

    raw = client.get(_session_key(session_id))
    if not raw:
        return None
    return SessionRecord.from_payload(json.loads(raw))
