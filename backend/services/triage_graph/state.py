from typing import TypedDict


class TriageState(TypedDict, total=False):
    session_id: str
    symptom_text: str
    risk_level: str
    emergency_advice: str | None
    recommended_departments: list[dict[str, object]]
    follow_up_questions: list[str]
    care_path: str
    preparation_checklist: list[str]
    report_summary: str

