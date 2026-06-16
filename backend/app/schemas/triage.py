from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class Sex(StrEnum):
    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EMERGENCY = "emergency"


class TriageStatus(StrEnum):
    CREATED = "created"
    COLLECTING = "collecting"
    RISK_ESCALATED = "risk_escalated"
    READY_TO_COMPLETE = "ready_to_complete"
    NEEDS_FOLLOW_UP = "needs_follow_up"
    COMPLETED = "completed"
    NOT_FOUND = "not_found"


class PatientProfile(BaseModel):
    age: int = Field(ge=0, le=130)
    sex: Sex = Sex.UNKNOWN
    pregnancy_status: str | None = None
    medical_history: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)


class TriageRequest(BaseModel):
    session_id: str | None = None
    patient: PatientProfile | None = None
    symptom_text: str | None = Field(default=None, min_length=2, max_length=3000)
    city: str | None = None
    answer: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_request_shape(self) -> "TriageRequest":
        has_initial_payload = bool(self.patient and self.symptom_text)
        has_follow_up_payload = bool(self.session_id and self.answer)

        if not has_initial_payload and not has_follow_up_payload:
            raise ValueError("Provide either patient + symptom_text, or session_id + answer.")
        return self


class DepartmentRecommendation(BaseModel):
    name: str
    reason: str
    priority: int = Field(ge=1)


class TriageMessage(BaseModel):
    role: str
    content: str
    kind: str = "text"


class LlmTraceEntry(BaseModel):
    agent: str
    task: str
    used: bool
    fallback: bool
    error: str | None = None


class FollowUpResponse(BaseModel):
    session_id: str
    status: TriageStatus = TriageStatus.NEEDS_FOLLOW_UP
    risk_level: RiskLevel
    question: str
    known_facts_summary: str
    missing_fields: list[str] = Field(default_factory=list)


class TriageResponse(BaseModel):
    session_id: str
    status: TriageStatus = TriageStatus.COMPLETED
    risk_level: RiskLevel
    emergency_advice: str | None = None
    recommended_departments: list[DepartmentRecommendation] = Field(default_factory=list)
    care_path: str
    preparation_checklist: list[str] = Field(default_factory=list)
    report_summary: str
    disclaimer: str


AnalyzeResponse = FollowUpResponse | TriageResponse


class TriageSessionResponse(BaseModel):
    session_id: str
    status: str

    @classmethod
    def create(cls) -> "TriageSessionResponse":
        return cls(session_id=str(uuid4()), status=TriageStatus.CREATED)


class TriageSessionDetailResponse(BaseModel):
    session_id: str
    status: str
    latest_request: TriageRequest | None = None
    latest_result: AnalyzeResponse | None = None
    current_question: str | None = None
    report_id: str | None = None
    messages: list[TriageMessage] = Field(default_factory=list)
    current_agent: str | None = None
    node_trace: list[str] = Field(default_factory=list)
    agent_trace: list[dict[str, str]] = Field(default_factory=list)
    route_reason: str | None = None
    knowledge_summary: str | None = None
    raw_follow_up_question: str | None = None
    llm_follow_up_question: str | None = None
    raw_report_summary: str | None = None
    llm_report_summary: str | None = None
    llm_enabled: bool = False
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_base_url: str | None = None
    llm_used: bool = False
    llm_error: str | None = None
    llm_trace: list[LlmTraceEntry] = Field(default_factory=list)
