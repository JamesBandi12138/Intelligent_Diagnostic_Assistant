from app.schemas.triage import RiskLevel


EMERGENCY_KEYWORDS = (
    "胸痛",
    "胸闷",
    "呼吸困难",
    "喘不上气",
    "意识不清",
    "昏迷",
    "抽搐",
    "大出血",
    "偏瘫",
    "口角歪斜",
    "言语不清",
)


def detect_risk(symptom_text: str) -> tuple[RiskLevel, str | None]:
    normalized = symptom_text.strip()
    if any(keyword in normalized for keyword in EMERGENCY_KEYWORDS):
        return (
            RiskLevel.EMERGENCY,
            "当前描述包含可能的急危重症信号，建议立即前往急诊或拨打 120，不要等待线上建议。",
        )
    return RiskLevel.LOW, None

