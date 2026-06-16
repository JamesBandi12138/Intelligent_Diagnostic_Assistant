import re

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
    "剧烈头痛",
    "突发视物不清",
    "孕妇腹痛",
    "阴道出血",
    "胎动异常",
    "婴幼儿精神反应差",
    "持续高热不退",
)

HIGH_RISK_KEYWORDS = (
    "高烧",
    "高热",
    "发烧",
    "咳嗽",
    "咳痰",
    "气促",
    "呼吸急促",
    "腹痛",
    "腹泻",
    "呕吐",
    "黑便",
    "血尿",
    "乏力",
    "明显加重",
    "精神一般",
)

MEDIUM_RISK_KEYWORDS = (
    "喉咙痛",
    "咽痛",
    "流鼻涕",
    "鼻塞",
    "打喷嚏",
    "头痛",
    "发热",
    "食欲差",
    "胃痛",
    "轻微",
)


def detect_risk(symptom_text: str) -> tuple[RiskLevel, str | None]:
    normalized = symptom_text.strip()
    positive_text = _remove_negated_phrases(normalized)

    if any(keyword in positive_text for keyword in EMERGENCY_KEYWORDS):
        return (
            RiskLevel.EMERGENCY,
            "当前描述包含可能的急危重症信号，建议立刻前往急诊或拨打 120，不要等待线上建议。",
        )

    if any(keyword in positive_text for keyword in HIGH_RISK_KEYWORDS):
        return RiskLevel.HIGH, None

    if any(keyword in positive_text for keyword in MEDIUM_RISK_KEYWORDS):
        return RiskLevel.MEDIUM, None

    return RiskLevel.LOW, None


def _remove_negated_phrases(text: str) -> str:
    return re.sub(r"(没有|无)([^，。；,;]*)", "", text)
