from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from app.schemas.triage import DepartmentRecommendation, PatientProfile, RiskLevel


class ReportCreateRequest(BaseModel):
    session_id: str


class ReportPatientSnapshot(BaseModel):
    age: int
    sex: str
    pregnancy_status: str | None = None
    medical_history: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)

    @classmethod
    def from_patient(cls, patient: PatientProfile) -> "ReportPatientSnapshot":
        return cls(**patient.model_dump(mode="json"))


class ReportTriageSummary(BaseModel):
    chief_complaint: str
    risk_level: RiskLevel
    recommended_departments: list[DepartmentRecommendation] = Field(default_factory=list)
    care_path: str
    generated_from_session_status: str


class DoctorView(BaseModel):
    chief_complaint: str
    key_facts: dict[str, str] = Field(default_factory=dict)
    risk_notes: str
    recommended_department_summary: str
    preparation_checklist: list[str] = Field(default_factory=list)


class PatientView(BaseModel):
    what_this_means: str
    why_this_department: str
    what_to_prepare: list[str] = Field(default_factory=list)
    when_to_seek_urgent_care: str


class ReportResponse(BaseModel):
    report_id: str
    session_id: str
    status: str = "ready"
    created_at: datetime
    patient_snapshot: ReportPatientSnapshot
    triage_summary: ReportTriageSummary
    doctor_view: DoctorView
    patient_view: PatientView
    disclaimer: str

    @classmethod
    def create(
        cls,
        *,
        session_id: str,
        patient_snapshot: ReportPatientSnapshot,
        triage_summary: ReportTriageSummary,
        doctor_view: DoctorView,
        patient_view: PatientView,
        disclaimer: str,
    ) -> "ReportResponse":
        return cls(
            report_id=str(uuid4()),
            session_id=session_id,
            created_at=datetime.now(timezone.utc),
            patient_snapshot=patient_snapshot,
            triage_summary=triage_summary,
            doctor_view=doctor_view,
            patient_view=patient_view,
            disclaimer=disclaimer,
        )
