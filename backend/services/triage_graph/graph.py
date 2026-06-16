from __future__ import annotations

import re
from uuid import uuid4

from fastapi import HTTPException

from app.schemas.triage import (
    DepartmentRecommendation,
    FollowUpResponse,
    RiskLevel,
    TriageMessage,
    TriageRequest,
    TriageResponse,
    TriageStatus,
)
from services.safety_guardrails.service import detect_risk
from services.session_store import SessionRecord, create_session, get_session, save_session


DISCLAIMER = "本结果仅用于诊前导诊参考，不能替代医生诊断、检查或治疗决策。"

FIELD_ORDER = [
    "location",
    "duration",
    "severity",
    "accompanying_symptoms",
    "special_context",
]

FOLLOW_UP_QUESTIONS = {
    "location": "你现在最不舒服的部位主要是哪里？",
    "duration": "这种不舒服持续多久了？是突然开始还是逐渐加重的？",
    "severity": "现在不舒服的程度大概有多重？可以用轻微、中等、严重，或 0 到 10 分描述。",
    "accompanying_symptoms": "除了主要症状，还有没有发热、咳嗽、流鼻涕、胸闷、腹泻、呕吐等伴随症状？",
    "special_context": "你是否有慢性病、怀孕、术后恢复、长期用药，或属于儿童、老人等需要特别注意的情况？",
}


async def run_triage(request: TriageRequest, llm_client=None):
    record = _load_or_create_record(request)

    if record.status == TriageStatus.COMPLETED and request.answer:
        raise HTTPException(status_code=409, detail="This triage session has already been completed.")

    if request.patient and record.patient is None:
        record.patient = request.patient
    if request.city and record.city is None:
        record.city = request.city

    if request.symptom_text:
        record.symptom_text = request.symptom_text
        _append_message(record, "user", request.symptom_text, kind="symptom")
    if request.answer:
        record.answered_follow_ups.append(request.answer)
        _append_message(record, "user", request.answer, kind="answer")

    record.latest_request = request

    combined_text = _combined_text(record)
    risk_level, emergency_advice = detect_risk(combined_text)
    record.risk_level = risk_level
    record.extracted_facts = _extract_facts(record)
    record.missing_fields = _missing_fields(record)

    if risk_level == RiskLevel.EMERGENCY:
        return _complete_with_risk(record, emergency_advice)

    if record.missing_fields:
        record.status = TriageStatus.COLLECTING
        question_key = record.missing_fields[0]
        question = FOLLOW_UP_QUESTIONS[question_key]
        record.current_question = question
        follow_up = FollowUpResponse(
            session_id=record.session_id,
            status=TriageStatus.NEEDS_FOLLOW_UP,
            risk_level=risk_level,
            question=question,
            known_facts_summary=_build_known_facts_summary(record),
            missing_fields=record.missing_fields,
        )
        record.latest_result = follow_up
        _append_message(record, "assistant", question, kind="follow_up")
        save_session(record)
        return follow_up

    return _complete_with_guidance(record, risk_level)


def _load_or_create_record(request: TriageRequest) -> SessionRecord:
    if request.session_id:
        session = get_session(request.session_id)
        if session is not None:
            return session
        if request.answer and not request.symptom_text:
            raise HTTPException(status_code=404, detail="Triage session not found.")
        return create_session(request.session_id)

    return create_session(str(uuid4()))


def _append_message(record: SessionRecord, role: str, content: str, kind: str) -> None:
    record.messages.append(TriageMessage(role=role, content=content, kind=kind))


def _combined_text(record: SessionRecord) -> str:
    parts = [record.symptom_text or ""]
    parts.extend(record.answered_follow_ups)
    return " ".join(part for part in parts if part).strip()


def _extract_facts(record: SessionRecord) -> dict[str, str]:
    text = _combined_text(record)
    patient = record.patient
    facts: dict[str, str] = {}

    location_matchers = (
        ("喉咙", ("喉咙", "咽", "吞咽")),
        ("胸部", ("胸痛", "胸闷", "胸口")),
        ("腹部", ("腹痛", "胃痛", "肚子")),
        ("头部", ("头痛", "头晕")),
    )
    for label, keywords in location_matchers:
        if any(keyword in text for keyword in keywords):
            facts["location"] = label
            break

    duration_match = re.search(r"([0-9一二三四五六七八九十两半]+(?:到[0-9一二三四五六七八九十两半]+)?)(分钟|小时|天|周|个月|月)", text)
    if duration_match:
        facts["duration"] = "".join(duration_match.groups())

    severity_match = re.search(r"([0-9]+(?:到[0-9]+)?分)", text)
    if severity_match:
        facts["severity"] = severity_match.group(1)
    elif any(keyword in text for keyword in ("轻微", "中等", "严重", "剧烈", "明显")):
        facts["severity"] = next(keyword for keyword in ("轻微", "中等", "严重", "剧烈", "明显") if keyword in text)

    symptom_keywords = ["发热", "发烧", "咳嗽", "流鼻涕", "胸闷", "腹泻", "呕吐", "吞咽痛"]
    found_symptoms = [keyword for keyword in symptom_keywords if keyword in text]
    if found_symptoms:
        facts["accompanying_symptoms"] = "、".join(found_symptoms)
    elif any(keyword in text for keyword in ("没有发热", "没有咳嗽", "无发热", "无咳嗽", "没有发烧")):
        facts["accompanying_symptoms"] = "已否认常见伴随症状"

    if patient and patient.medical_history:
        facts["special_context"] = "、".join(patient.medical_history)
    elif patient and patient.pregnancy_status:
        facts["special_context"] = patient.pregnancy_status
    elif patient and (patient.age <= 6 or patient.age >= 65):
        facts["special_context"] = "特殊年龄段"
    elif any(keyword in text for keyword in ("慢性病", "高血压", "糖尿病", "怀孕", "术后", "长期用药")):
        if "没有慢性病" in text or "无慢性病" in text:
            facts["special_context"] = "无慢性病"
        else:
            facts["special_context"] = "存在特殊背景"

    return facts


def _missing_fields(record: SessionRecord) -> list[str]:
    return [field for field in FIELD_ORDER if field not in record.extracted_facts]


def _build_known_facts_summary(record: SessionRecord) -> str:
    facts = record.extracted_facts
    if not facts:
        return "目前只知道你有不适症状，还需要补充更具体的信息。"

    labels = {
        "location": "部位",
        "duration": "持续时间",
        "severity": "严重程度",
        "accompanying_symptoms": "伴随症状",
        "special_context": "特殊情况",
    }
    items = [f"{labels[key]}：{value}" for key, value in facts.items() if value]
    return "；".join(items)


def _complete_with_risk(record: SessionRecord, emergency_advice: str | None) -> TriageResponse:
    record.status = TriageStatus.COMPLETED
    record.current_question = None
    result = TriageResponse(
        session_id=record.session_id,
        status=TriageStatus.COMPLETED,
        risk_level=RiskLevel.EMERGENCY,
        emergency_advice=emergency_advice or "建议立即前往急诊或拨打 120。",
        recommended_departments=[
            DepartmentRecommendation(
                name="急诊科",
                reason="当前症状包含需要优先排除的急危重信号。",
                priority=1,
            )
        ],
        care_path="请立即前往最近医院急诊，必要时拨打 120，并尽量由家属陪同。",
        preparation_checklist=[
            "携带身份证、医保卡",
            "携带既往病历和当前用药清单",
            "记录症状开始时间和变化过程",
        ],
        report_summary=f"系统识别到急危重风险信号：{record.symptom_text or _combined_text(record)}",
        disclaimer=DISCLAIMER,
    )
    record.latest_result = result
    record.final_result = result.model_dump(mode="json")
    _append_message(record, "assistant", result.emergency_advice or result.care_path, kind="result")
    save_session(record)
    return result


def _complete_with_guidance(record: SessionRecord, risk_level: RiskLevel) -> TriageResponse:
    record.status = TriageStatus.COMPLETED
    record.current_question = None
    department = _recommend_department(_combined_text(record))
    result = TriageResponse(
        session_id=record.session_id,
        status=TriageStatus.COMPLETED,
        risk_level=risk_level,
        emergency_advice=None,
        recommended_departments=[department],
        care_path=_build_care_path(risk_level),
        preparation_checklist=[
            "记录症状开始时间、变化过程和诱因",
            "携带既往病历、检查报告和当前用药清单",
            "说明药物过敏史、基础病和近期就诊情况",
        ],
        report_summary=f"主诉：{record.symptom_text}。当前补全信息后，建议优先咨询{department.name}。",
        disclaimer=DISCLAIMER,
    )
    record.latest_result = result
    record.final_result = result.model_dump(mode="json")
    _append_message(record, "assistant", result.report_summary, kind="result")
    save_session(record)
    return result


def _build_care_path(risk_level: RiskLevel) -> str:
    if risk_level == RiskLevel.HIGH:
        return "建议尽快线下面诊，优先选择门诊或急诊评估，避免继续拖延观察。"
    if risk_level == RiskLevel.MEDIUM:
        return "建议尽快安排线下门诊评估；如症状加重或出现新的红旗信号，请及时急诊就医。"
    return "建议根据症状持续时间和严重程度选择线下门诊；若症状明显加重，应及时急诊评估。"


def _recommend_department(symptom_text: str) -> DepartmentRecommendation:
    positive_text = re.sub(r"(没有|无)([^，。；,;]*)", "", symptom_text)
    if any(keyword in positive_text for keyword in ("咳嗽", "咳痰", "气促", "呼吸急促", "胸痛", "胸闷")):
        return DepartmentRecommendation(
            name="呼吸内科",
            reason="症状偏向呼吸道或胸部不适，适合优先由呼吸内科评估。",
            priority=1,
        )
    if any(keyword in positive_text for keyword in ("喉咙", "咽痛", "吞咽", "鼻塞", "流鼻涕", "耳痛")):
        return DepartmentRecommendation(
            name="耳鼻喉科",
            reason="症状集中在咽喉、鼻腔或耳部区域，适合优先由耳鼻喉科评估。",
            priority=1,
        )
    if any(keyword in positive_text for keyword in ("腹痛", "腹泻", "恶心", "呕吐", "胃痛", "黑便")):
        return DepartmentRecommendation(
            name="消化内科",
            reason="症状偏向消化道，适合优先由消化内科评估。",
            priority=1,
        )
    return DepartmentRecommendation(
        name="全科医学科",
        reason="当前描述暂无法稳定指向单一专科，建议先由全科医学科进行初步评估。",
        priority=1,
    )
