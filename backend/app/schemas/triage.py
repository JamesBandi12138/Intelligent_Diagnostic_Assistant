from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class Sex(StrEnum):
    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EMERGENCY = "emergency"


class PatientProfile(BaseModel):
    age: int = Field(ge=0, le=130)
    sex: Sex = Sex.UNKNOWN
    pregnancy_status: str | None = None
    medical_history: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)


class TriageRequest(BaseModel):
    session_id: str | None = None
    patient: PatientProfile
    symptom_text: str = Field(min_length=2, max_length=3000)
    city: str | None = None


class DepartmentRecommendation(BaseModel):
    name: str
    reason: str
    priority: int = Field(ge=1)


class TriageResponse(BaseModel):
    session_id: str
    risk_level: RiskLevel
    emergency_advice: str | None = None
    recommended_departments: list[DepartmentRecommendation] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    care_path: str
    preparation_checklist: list[str] = Field(default_factory=list)
    report_summary: str
    disclaimer: str


class TriageSessionResponse(BaseModel):
    session_id: str
    status: str

    @classmethod
    def create(cls) -> "TriageSessionResponse":
        return cls(session_id=str(uuid4()), status="created")

