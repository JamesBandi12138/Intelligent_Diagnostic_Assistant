from __future__ import annotations

import json
import re
from functools import lru_cache
from uuid import uuid4

from fastapi import HTTPException
from langgraph.graph import END, StateGraph

from app.schemas.triage import (
    AnalyzeResponse,
    DepartmentRecommendation,
    FollowUpResponse,
    LlmTraceEntry,
    PatientProfile,
    RiskLevel,
    TriageMessage,
    TriageRequest,
    TriageResponse,
    TriageStatus,
)
from common.config import settings
from services.knowledge_base.local_cards import KNOWLEDGE_CARDS
from services.knowledge_base.milvus_store import knowledge_store
from services.safety_guardrails.service import detect_risk
from services.session_store import create_session, get_session, save_session
from services.triage_graph.state import TriageGraphState


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
    "severity": "现在不舒服的程度大概有多重？可以用轻微、中等、严重，或者 0 到 10 分描述。",
    "accompanying_symptoms": "除了主要症状，还有没有发热、咳嗽、流鼻涕、胸闷、腹泻、呕吐等伴随症状？",
    "special_context": "你是否有慢性病、怀孕、术后恢复、长期用药，或者属于儿童、老人等需要特别注意的情况？",
}

COMPLAINT_ROUTE_QUESTIONS = {
    "abdominal_location_detail": "肚子痛更具体在肚子哪个位置，比如上腹、肚脐周围、右下腹，还是固定在某一侧？",
    "abdominal_red_flags": "除了肚子痛，还有没有发热、呕吐、腹泻、黑便，或者按压时明显更痛？",
    "headache_red_flags": "这次头痛是突然一下子很重，还是慢慢加重？同时有没有视物模糊、说话不清、肢体无力、呕吐或发热？",
    "eye_red_flags": "有没有视力下降、畏光、明显分泌物增多、外伤，或者最近佩戴隐形眼镜后加重？",
    "throat_red_flags": "除了咽喉痛，还有没有发热、咳嗽、吞咽困难，或者呼吸受限？",
    "chest_red_flags": "胸痛是压榨样还是刺痛样？有没有活动后加重、大汗、气短，或者向左肩背部放射？",
}

COMPLAINT_ALIAS_TO_CATEGORY = {
    alias: card.card_id
    for card in KNOWLEDGE_CARDS
    for alias in card.aliases
}

COMPLAINT_CATEGORY_PROMPTS = {
    "abdominal_pain": (
        ("abdominal_location_detail", "肚子痛更具体在肚子哪个位置，比如上腹、肚脐周围、右下腹，还是固定在某一侧？"),
        ("abdominal_red_flags", "除了肚子痛，还有没有发热、呕吐、腹泻、黑便，或者按压时明显更痛？"),
    ),
    "headache": (
        ("headache_red_flags", "这次头痛是突然一下子很重，还是慢慢加重？同时有没有视物模糊、说话不清、肢体无力、呕吐或发热？"),
    ),
    "eye_discomfort": (
        ("eye_red_flags", "有没有视力下降、畏光、明显分泌物增多、外伤，或者最近佩戴隐形眼镜后加重？"),
    ),
    "throat_discomfort": (
        ("throat_red_flags", "除了咽喉痛，还有没有发热、咳嗽、吞咽困难，或者呼吸受限？"),
    ),
    "chest_pain": (
        ("chest_red_flags", "胸痛是压榨样还是刺痛样？有没有活动后加重、大汗、气短，或者向左肩背部放射？"),
    ),
}

CATEGORY_DISPLAY_NAMES = {
    "abdominal_pain": "腹痛",
    "headache": "头痛",
    "eye_discomfort": "眼部不适",
    "throat_discomfort": "喉咙不适",
    "chest_pain": "胸部不适",
}

CATEGORY_KEYWORDS = {
    "abdominal_pain": ("肚子", "腹痛", "胃痛", "右下腹", "上腹", "腹部"),
    "headache": ("头痛", "头疼", "脑袋", "头晕", "偏头痛", "头部"),
    "eye_discomfort": ("眼睛", "眼痛", "眼红", "眼痒", "异物感", "视物模糊", "眼部"),
    "throat_discomfort": ("喉咙", "咽痛", "咽喉", "吞咽痛", "嗓子"),
    "chest_pain": ("胸痛", "胸闷", "胸口痛", "胸前区", "胸口", "胸部"),
}


async def run_triage(request: TriageRequest, llm_client=None) -> AnalyzeResponse:
    record = _load_or_create_record(request)
    if record.status == TriageStatus.COMPLETED and request.answer:
        return _handle_completed_session_follow_up(record, request.answer)

    initial_state: TriageGraphState = {
        "request": request,
        "llm_client": llm_client,
        "iteration_count": 0,
    }
    final_state = await _compiled_graph().ainvoke(initial_state)
    return final_state["response"]


def _load_or_create_record(request: TriageRequest):
    if request.session_id:
        session = get_session(request.session_id)
        if session is not None:
            return session
        if request.answer and not request.symptom_text:
            raise HTTPException(status_code=404, detail="Triage session not found.")
        return create_session(request.session_id)

    return create_session(str(uuid4()))


def _completed_base_response(record) -> TriageResponse:
    payload = record.final_result or (record.latest_result.model_dump(mode="json") if record.latest_result else None)
    if not payload:
        raise HTTPException(status_code=409, detail="Completed session has no final triage result to explain.")
    return TriageResponse.model_validate(payload)


def _build_completed_follow_up_summary(record, answer: str, base_response: TriageResponse) -> str:
    intent = _classify_follow_up_intent(answer)
    department = base_response.recommended_departments[0].name if base_response.recommended_departments else "相关科室"
    reason = base_response.recommended_departments[0].reason if base_response.recommended_departments else "当前信息更适合先做专科评估。"
    care_path = base_response.care_path
    checklist = [item.strip("。") for item in base_response.preparation_checklist if item.strip()]
    checklist_summary = "；".join(checklist[:3]) if checklist else "携带身份证件、既往病历和当前用药信息"

    if intent in {"ask_department", "ask_why", "ask_general_question"}:
        return f"目前更建议优先看 {department}，主要因为 {reason}"
    if intent == "ask_urgency":
        if base_response.risk_level == RiskLevel.EMERGENCY:
            return "按当前结果，已经属于需要优先急诊处理的情况，建议立刻去急诊或拨打 120。"
        if base_response.risk_level == RiskLevel.HIGH:
            return f"按当前结果，这次不建议继续拖延，{care_path}"
        return f"按当前结果，暂时不像必须立刻急诊，但还是建议按导诊路径处理：{care_path}"
    if intent == "ask_next_step":
        return f"你现在最该先做的是按这个路径就医：{care_path}。如果暂时还不能立刻去，先把症状开始时间、加重变化和目前用药整理好，方便门诊更快判断。"
    if intent == "ask_preparation":
        return f"去医院前建议先准备这几样：{checklist_summary}。如果症状有变化，也可以顺手记下开始时间、加重过程和已经试过的处理。"
    if intent == "ask_online_visit":
        if base_response.risk_level in {RiskLevel.HIGH, RiskLevel.EMERGENCY}:
            return f"按当前风险，更建议直接线下就医，不建议只停留在线上问诊。更稳妥的做法是：{care_path}"
        return f"可以先线上问诊做初步咨询，但如果症状持续、加重，或出现新的危险信号，还是要尽快线下就医。当前更推荐的处理路径是：{care_path}"
    if intent == "ask_severity_scale":
        return "如果按 0 到 10 分来描述，1 到 3 分通常算轻，4 到 6 分算中等，7 分以上偏重。你也可以直接说轻微、中等或明显加重。"
    raise HTTPException(status_code=409, detail="This triage session has already been completed. Start a new session for new symptoms.")


def _handle_completed_session_follow_up(record, answer: str) -> TriageResponse:
    base_response = _completed_base_response(record)
    summary = _build_completed_follow_up_summary(record, answer, base_response)
    response = TriageResponse(
        session_id=record.session_id,
        status=TriageStatus.COMPLETED,
        risk_level=base_response.risk_level,
        emergency_advice=base_response.emergency_advice,
        recommended_departments=base_response.recommended_departments,
        care_path=base_response.care_path,
        preparation_checklist=base_response.preparation_checklist,
        report_summary=summary,
        disclaimer=base_response.disclaimer,
    )
    messages = list(record.messages)
    messages = _append_message(messages, "user", answer, kind="answer")
    messages = _append_message(messages, "assistant", summary, kind="result_follow_up")
    record.messages = messages
    record.latest_result = response
    record.latest_request = TriageRequest(session_id=record.session_id, answer=answer)
    record.status = TriageStatus.COMPLETED
    record.current_question = None
    record.current_agent = "result_explainer_agent"
    record.route_reason = "completed session follow-up explanation"
    record.workflow_status = "completed_follow_up_answered"
    save_session(record)
    return response


def _append_message(messages: list[TriageMessage], role: str, content: str, kind: str) -> list[TriageMessage]:
    updated = list(messages)
    updated.append(TriageMessage(role=role, content=content, kind=kind))
    return updated


def _is_correction_message(text: str) -> bool:
    lowered = text.strip()
    return any(
        token in lowered
        for token in (
            "刚才说错",
            "说错了",
            "更正一下",
            "改一下",
            "改成",
            "改为",
            "改口",
            "其实是",
            "换成",
            "重新说",
            "不是",
        )
    )


def _drop_negated_phrases(text: str) -> str:
    return re.sub(r"(没有|无|否认)([^，。；,;]*)", "", text)


def _has_positive_location(text: str) -> bool:
    positive_text = _drop_negated_phrases(text)
    location_keywords = (
        "眼",
        "视物",
        "喉咙",
        "咽",
        "胸",
        "肚子",
        "腹",
        "胃",
        "头痛",
        "头疼",
        "头晕",
        "头部",
        "脑袋",
        "偏头痛",
    )
    return any(keyword in positive_text for keyword in location_keywords)


def _normalize_correction_text(text: str) -> str:
    normalized = re.sub(r"^(?:我)?(?:刚才)?(?:说错了|说错|更正一下|改一下|改成|改为|改口|其实是|换成|重新说)[，,：:\s]*", "", text.strip())
    normalized = re.sub(r"^不是[^，。；,;]*[，,、\s]*(?:是|改成|改为)?", "", normalized)
    return normalized.strip("，。；;：: ")


def _relevant_user_messages(messages: list[TriageMessage]) -> list[TriageMessage]:
    user_messages = [message for message in messages if message.role == "user" and message.kind in {"symptom", "answer"}]
    last_correction_index = -1
    for index, message in enumerate(user_messages):
        if _is_correction_message(message.content):
            last_correction_index = index
    if last_correction_index >= 0:
        return user_messages[last_correction_index:]
    return user_messages


def _trace_node(state: TriageGraphState, node_name: str) -> list[str]:
    trace = list(state.get("node_trace", []))
    trace.append(node_name)
    return trace


def _trace_agent(state: TriageGraphState, agent_name: str, summary: str) -> list[dict[str, str]]:
    trace = list(state.get("agent_trace", []))
    trace.append({"agent": agent_name, "summary": summary})
    return trace


def _combined_text_from_parts(symptom_text: str | None, latest_answer: str | None, messages: list[TriageMessage]) -> str:
    if latest_answer and (_is_correction_message(latest_answer) or _has_positive_location(latest_answer)):
        return _normalize_correction_text(latest_answer) or latest_answer.strip()

    relevant_messages = _relevant_user_messages(messages)
    parts = [message.content for message in relevant_messages if message.content.strip()]
    if not parts:
        if symptom_text:
            parts.append(symptom_text)
        if latest_answer:
            parts.append(latest_answer)
    return " ".join(part.strip() for part in parts if part and part.strip()).strip()


def _chief_complaint_text(state: TriageGraphState, combined_text: str) -> str:
    latest_answer = state.get("latest_answer", "").strip()
    if latest_answer and (_is_correction_message(latest_answer) or _has_positive_location(latest_answer)):
        return _normalize_correction_text(latest_answer) or latest_answer

    symptom_text = (state.get("symptom_text") or "").strip()
    if symptom_text:
        return symptom_text

    return combined_text


def _special_context_flags(patient: PatientProfile | None, text: str) -> dict[str, bool]:
    chronic_denied = any(token in text for token in ("没有慢性病", "无慢性病"))
    pregnancy_applicable = bool(patient and patient.sex != "male")
    return {
        "pregnancy": pregnancy_applicable and (bool(patient and patient.pregnancy_status) or ("怀孕" in text)),
        "elderly": bool(patient and patient.age >= 65),
        "child": bool(patient and patient.age <= 6),
        "chronic_disease": (bool(patient and patient.medical_history) or any(token in text for token in ("高血压", "糖尿病", "慢性病")))
        and not chronic_denied,
        "post_surgery": "术后" in text,
    }


def _extract_facts(text: str, patient: PatientProfile | None) -> tuple[dict[str, str], dict[str, str], dict[str, bool]]:
    facts: dict[str, str] = {}
    confidence: dict[str, str] = {}

    location_matchers = (
        ("眼部", ("眼", "视物", "眼红", "眼痒", "眼痛", "异物感")),
        ("咽喉", ("喉咙", "咽痛", "吞咽")),
        ("胸部", ("胸痛", "胸闷", "胸口")),
        ("腹部", ("腹痛", "胃痛", "肚子")),
        ("头部", ("头痛", "头疼", "头晕", "头部", "脑袋", "偏头痛")),
    )
    for label, keywords in location_matchers:
        if any(keyword in text for keyword in keywords):
            facts["location"] = label
            confidence["location"] = "rule"
            break

    duration_match = re.search(r"([0-9一二三四五六七八九十两半]+(?:到[0-9一二三四五六七八九十两半]+)?)(分钟|小时|天|周|个月|月)", text)
    if duration_match:
        facts["duration"] = "".join(duration_match.groups())
        confidence["duration"] = "rule"

    severity_match = re.search(r"([0-9]+(?:\.[0-9]+)?分)", text)
    if severity_match:
        facts["severity"] = severity_match.group(1)
        confidence["severity"] = "rule"
    else:
        severity_aliases = (
            ("1到3分", ("一点点疼", "有一点疼", "有点疼", "不太疼", "不严重", "轻微")),
            ("4到6分", ("中等", "还挺疼", "有些疼", "比较疼", "明显疼")),
            ("7到10分", ("很疼", "疼得厉害", "特别疼", "剧烈", "难以忍受")),
        )
        for label, keywords in severity_aliases:
            if any(keyword in text for keyword in keywords):
                facts["severity"] = label
                confidence["severity"] = "rule"
                break
    if "severity" not in facts:
        for keyword in ("轻微", "中等", "严重", "剧烈", "明显"):
            if keyword in text:
                facts["severity"] = keyword
                confidence["severity"] = "rule"
                break

    symptom_keywords = ["发热", "发烧", "咳嗽", "流鼻涕", "胸闷", "腹泻", "呕吐", "吞咽痛"]
    found_symptoms = [keyword for keyword in symptom_keywords if keyword in text]
    if found_symptoms:
        facts["accompanying_symptoms"] = "、".join(found_symptoms)
        confidence["accompanying_symptoms"] = "rule"
    elif any(
        keyword in text
        for keyword in (
            "没有发热",
            "没有咳嗽",
            "无发热",
            "无咳嗽",
            "没有胸闷",
            "没有胸痛",
            "没有气短",
            "无胸闷",
            "无胸痛",
            "无气短",
        )
    ):
        facts["accompanying_symptoms"] = "已否认常见伴随症状"
        confidence["accompanying_symptoms"] = "negation_rule"

    if patient and patient.medical_history:
        facts["special_context"] = "、".join(patient.medical_history)
        confidence["special_context"] = "patient_profile"
    elif patient and patient.sex != "male" and patient.pregnancy_status:
        facts["special_context"] = patient.pregnancy_status
        confidence["special_context"] = "patient_profile"
    elif patient and (patient.age <= 6 or patient.age >= 65):
        facts["special_context"] = "特殊年龄段"
        confidence["special_context"] = "patient_profile"
    elif any(keyword in text for keyword in ("慢性病", "高血压", "糖尿病", "怀孕", "术后", "长期用药")):
        if "没有慢性病" in text or "无慢性病" in text:
            facts["special_context"] = "无慢性病"
            confidence["special_context"] = "negation_rule"
        else:
            facts["special_context"] = "存在特殊背景"
            confidence["special_context"] = "rule"

    return facts, confidence, _special_context_flags(patient, text)


def _missing_fields(facts: dict[str, str]) -> list[str]:
    return [field for field in FIELD_ORDER if field not in facts]


def _sanitize_llm_facts(payload: dict) -> tuple[dict[str, str], list[str]]:
    raw_facts = payload.get("facts")
    if not isinstance(raw_facts, dict):
        return {}, FIELD_ORDER.copy()

    facts: dict[str, str] = {}
    for field_name in FIELD_ORDER:
        value = raw_facts.get(field_name)
        if isinstance(value, str) and value.strip():
            facts[field_name] = value.strip()

    raw_missing = payload.get("missing_fields")
    if isinstance(raw_missing, list):
        missing_fields = [
            item
            for item in raw_missing
            if isinstance(item, str) and item in FIELD_ORDER and item not in facts
        ]
    else:
        missing_fields = _missing_fields(facts)

    return facts, missing_fields


async def _extract_facts_with_llm(
    *,
    llm_client,
    combined_text: str,
    patient: PatientProfile | None,
    city: str | None,
) -> tuple[dict[str, str] | None, list[str] | None, str | None]:
    if llm_client is None:
        return None, None, None

    patient_payload = patient.model_dump(mode="json") if patient else None
    prompt = (
        "You are the Symptom Intake Agent for a Chinese pre-visit triage assistant.\n"
        "Extract only facts stated by the user or patient profile. Do not diagnose.\n"
        "Use concise Chinese values.\n"
        "Required fact keys: location, duration, severity, accompanying_symptoms, special_context.\n"
        "If a key is unknown, omit it and include the key in missing_fields.\n"
        "special_context should include pregnancy, chronic disease, elderly/child, surgery, medication, or explicit denial such as 无慢性病.\n"
        f"patient_profile: {json.dumps(patient_payload, ensure_ascii=False)}\n"
        f"city: {city or ''}\n"
        f"user_text: {combined_text}\n"
        'Return JSON only like {"facts":{"location":"..."},"missing_fields":["duration"]}'
    )
    try:
        payload = await _call_llm_json(llm_client, prompt, max_tokens=360)
        facts, missing_fields = _sanitize_llm_facts(payload)
        if not facts:
            return None, None, "format_error"
        return facts, missing_fields, None
    except json.JSONDecodeError:
        return None, None, "format_error"
    except Exception as error:
        return None, None, _classify_llm_error(error)


def _choose_follow_up_field(state: TriageGraphState, combined_text: str) -> str:
    facts = state.get("extracted_facts", {})
    missing_fields = list(state.get("missing_fields", []))
    if not missing_fields:
        return "special_context"

    latest_answer = state.get("latest_answer", "")
    correction_detected = _is_correction_message(latest_answer)

    if correction_detected and "location" in missing_fields:
        return "location"

    symptom_focus = combined_text
    has_location_context = "location" not in missing_fields or bool(facts.get("location"))

    if has_location_context and "duration" in missing_fields:
        return "duration"

    if any(token in symptom_focus for token in ("胸", "喘", "呼吸", "腹", "呕吐", "发热")):
        if "accompanying_symptoms" in missing_fields:
            return "accompanying_symptoms"

    for field_name in ("location", "duration", "severity", "accompanying_symptoms", "special_context"):
        if field_name in missing_fields:
            return field_name

    return missing_fields[0]


def _classify_complaint_category(combined_text: str, facts: dict[str, str]) -> str:
    for alias, category in COMPLAINT_ALIAS_TO_CATEGORY.items():
        if alias in combined_text:
            return category

    location = facts.get("location", "")
    if location == "腹部" or any(token in combined_text for token in ("肚子", "腹痛", "胃痛", "右下腹", "上腹")):
        return "abdominal_pain"
    if location == "头部" or any(token in combined_text for token in ("头痛", "头疼", "脑袋", "头晕", "偏头痛")):
        return "headache"
    if location == "眼部" or any(token in combined_text for token in ("眼睛", "眼痛", "眼红", "眼痒", "异物感", "视物模糊")):
        return "eye_discomfort"
    if location == "咽喉" or any(token in combined_text for token in ("喉咙", "咽痛", "咽喉", "吞咽痛")):
        return "throat_discomfort"
    if location == "胸部" or any(token in combined_text for token in ("胸痛", "胸闷", "胸口痛", "胸前区", "胸口")):
        return "chest_pain"
    return "general"


def _category_sort_index(category: str) -> int:
    ordered = list(CATEGORY_DISPLAY_NAMES.keys())
    return ordered.index(category) if category in ordered else len(ordered)


def _detect_complaint_candidates(combined_text: str, facts: dict[str, str]) -> list[str]:
    positive_text = _drop_negated_phrases(combined_text)
    scores: dict[str, int] = {}

    for alias, category in COMPLAINT_ALIAS_TO_CATEGORY.items():
        if alias in positive_text:
            scores[category] = scores.get(category, 0) + 2

    for category, keywords in CATEGORY_KEYWORDS.items():
        keyword_hits = sum(1 for keyword in keywords if keyword in positive_text)
        if keyword_hits:
            scores[category] = scores.get(category, 0) + keyword_hits

    location_to_category = {
        "腹部": "abdominal_pain",
        "头部": "headache",
        "眼部": "eye_discomfort",
        "咽喉": "throat_discomfort",
        "胸部": "chest_pain",
    }
    location_category = location_to_category.get(facts.get("location", ""))
    if location_category:
        scores[location_category] = scores.get(location_category, 0) + 2

    if not scores:
        category = _classify_complaint_category(combined_text, facts)
        return [category] if category != "general" else []

    return sorted(scores, key=lambda item: (-scores[item], _category_sort_index(item)))


def _build_multi_symptom_priority_question(candidates: list[str]) -> str:
    labels = [_candidate_display_name(category) for category in candidates[:3]]
    if len(labels) == 2:
        joined = "和".join(labels)
    else:
        joined = "、".join(labels)
    return (
        f"你刚才同时提到{joined}。现在哪个最影响你，或者哪个更需要优先处理？"
        "如果两个都差不多，也可以直接告诉我哪个更先出现，或者哪个更难受。"
    )


def _candidate_display_name(category: str) -> str:
    return CATEGORY_DISPLAY_NAMES.get(category, category)


def _extract_primary_focus_from_answer(answer: str, candidates: list[str]) -> str | None:
    if not answer.strip() or not candidates:
        return None

    positive_text = _drop_negated_phrases(answer)
    scores: dict[str, int] = {}
    for category in candidates:
        score = 0
        for keyword in CATEGORY_KEYWORDS.get(category, ()):
            if keyword in positive_text:
                score += 1
            if re.search(fr"(主要|先按|更像是|更难受|更明显).{{0,6}}{re.escape(keyword)}", positive_text):
                score += 3
            if re.search(fr"{re.escape(keyword)}.{{0,6}}(更难受|更明显|更严重|主要)", positive_text):
                score += 3
        if score:
            scores[category] = score

    if scores:
        return sorted(scores, key=lambda item: (-scores[item], _category_sort_index(item)))[0]

    if any(token in answer for token in ("都差不多", "一起出现", "两个都有", "都很明显", "差不多一起")):
        return candidates[0]
    return None


def _has_location_detail(text: str) -> bool:
    return any(token in text for token in ("右下腹", "左下腹", "右上腹", "左上腹", "上腹", "下腹", "肚脐", "一侧", "固定在"))


def _topic_already_addressed(topic_key: str, combined_text: str, facts: dict[str, str]) -> bool:
    if topic_key == "abdominal_location_detail":
        return _has_location_detail(combined_text)
    if topic_key == "abdominal_red_flags":
        return any(
            token in combined_text
            for token in (
                "发热",
                "发烧",
                "呕吐",
                "腹泻",
                "黑便",
                "按压",
                "压痛",
                "没有发热",
                "没有呕吐",
                "没有腹泻",
                "无发热",
                "无呕吐",
                "无腹泻",
            )
        )
    if topic_key == "headache_red_flags":
        return any(
            token in combined_text
            for token in (
                "突然",
                "慢慢加重",
                "逐渐加重",
                "视物",
                "视力",
                "说话",
                "肢体",
                "无力",
                "呕吐",
                "发热",
                "没有视物",
                "没有肢体",
                "没有呕吐",
                "没有发热",
            )
        )
    if topic_key == "eye_red_flags":
        return any(
            token in combined_text
            for token in (
                "视力下降",
                "视物模糊",
                "畏光",
                "分泌物",
                "外伤",
                "隐形眼镜",
                "没有视力下降",
                "没有畏光",
                "没有外伤",
                "无视力下降",
                "无畏光",
                "无外伤",
            )
        )
    if topic_key == "throat_red_flags":
        return any(
            token in combined_text
            for token in (
                "发热",
                "发烧",
                "咳嗽",
                "吞咽困难",
                "呼吸受限",
                "呼吸困难",
                "没有发热",
                "没有咳嗽",
                "没有吞咽困难",
                "无发热",
                "无咳嗽",
                "无吞咽困难",
            )
        )
    if topic_key == "chest_red_flags":
        return any(
            token in combined_text
            for token in (
                "活动后加重",
                "大汗",
                "气短",
                "左肩",
                "肩背",
                "放射",
                "没有大汗",
                "没有气短",
                "无大汗",
                "无气短",
            )
        )
    return topic_key in facts


def _choose_dynamic_follow_up_topic(state: TriageGraphState, combined_text: str) -> tuple[str, str]:
    facts = state.get("extracted_facts", {})
    complaint_candidates = list(state.get("complaint_candidates", []))
    if len(complaint_candidates) > 1 and not state.get("primary_focus_confirmed"):
        return "multi_symptom_priority", _build_multi_symptom_priority_question(complaint_candidates)

    complaint_category = state.get("complaint_category", "general")
    asked_topics = set(state.get("route_follow_up_history", []))
    for topic_key, question in COMPLAINT_CATEGORY_PROMPTS.get(complaint_category, ()):
        if _topic_already_addressed(topic_key, combined_text, facts):
            continue
        if topic_key in asked_topics:
            continue
        return topic_key, question

    field_name = _choose_follow_up_field(state, combined_text)
    return field_name, FOLLOW_UP_QUESTIONS[field_name]


def _build_known_facts_summary(facts: dict[str, str]) -> str:
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


def _augment_known_facts_summary_with_candidates(summary: str, complaint_candidates: list[str]) -> str:
    if len(complaint_candidates) <= 1:
        return summary
    candidate_text = "、".join(_candidate_display_name(category) for category in complaint_candidates[:3])
    if not summary:
        return f"当前识别到可能同时涉及：{candidate_text}"
    return f"{summary}；当前识别到可能同时涉及：{candidate_text}"


def _classify_follow_up_intent(text: str) -> str:
    lowered = text.strip()
    if not lowered:
        return "provide_medical_info"
    if any(token in lowered for token in ("说不清", "不太确定", "不确定", "不知道", "不好说", "记不清", "不清楚", "不太想回答", "先说别的", "先不回答", "这个先不说")):
        return "express_uncertainty"
    if any(token in lowered for token in ("为什么要问", "为什么问这个", "为啥问", "问这个干嘛", "问这个做什么")):
        return "ask_why"
    if any(token in lowered for token in ("1到10分", "0到10分", "怎么算", "几分算", "低到高", "怎么分级")):
        return "ask_severity_scale"
    if any(token in lowered for token in ("挂什么科", "看什么科", "去什么科", "哪个科")):
        return "ask_department"
    if any(token in lowered for token in ("严重吗", "要紧吗", "要不要去医院", "需要急诊吗", "急不急", "马上去医院", "立刻去医院")):
        return "ask_urgency"
    if any(token in lowered for token in ("先做什么", "下一步", "接下来怎么办", "现在怎么办", "最该先做什么")):
        return "ask_next_step"
    if any(token in lowered for token in ("准备什么", "带什么", "要准备什么", "就诊准备", "病历资料", "检查报告")):
        return "ask_preparation"
    if any(token in lowered for token in ("线上问诊", "在线问诊", "互联网医院", "线上咨询", "先线上")):
        return "ask_online_visit"
    if lowered.endswith("？") or lowered.endswith("?"):
        return "ask_general_question"
    return "provide_medical_info"


def _topic_explanation(question_key: str) -> str:
    explanations = {
        "multi_symptom_priority": "这是为了先确认这次最需要优先处理的主问题，避免多个不适混在一起时把追问方向问散了。",
        "abdominal_location_detail": "我这样问主要是为了判断腹痛范围，区分更偏消化内科还是外科方向。",
        "abdominal_red_flags": "这是为了判断腹痛有没有伴随需要尽快线下处理的危险信号。",
        "headache_red_flags": "这是为了先排除头痛相关的急症风险，比如神经系统受累的情况。",
        "eye_red_flags": "这是为了判断眼部不适是否涉及视力、外伤或角膜刺激等需要尽快处理的问题。",
        "throat_red_flags": "这是为了判断咽喉不适有没有感染加重或影响吞咽、呼吸的风险。",
        "chest_red_flags": "这是为了先区分胸痛是肌肉骨骼不适，还是需要警惕心肺方向的问题。",
        "severity": "这是为了判断你当前不舒服的大概程度，会影响是否建议尽快线下就医。",
        "duration": "这是为了判断症状是突然发作还是逐渐加重，也会影响分诊方向。",
        "location": "这是为了先确认最主要的不适部位，才能更准确判断应该优先看哪个科。",
        "accompanying_symptoms": "这是为了判断是否存在感染、炎症或其他需要优先排查的情况。",
        "special_context": "这是为了结合基础病、孕产、术后或长期用药这些背景一起判断风险。",
    }
    return explanations.get(question_key, "我先把关键情况补齐，这样才能更稳地判断下一步导诊方向。")


def _intent_aware_prefix(*, state: TriageGraphState, question_key: str) -> str:
    latest_answer = (state.get("latest_answer") or "").strip()
    if not latest_answer:
        return ""

    intent = _classify_follow_up_intent(latest_answer)
    risk_level = RiskLevel(state.get("risk_level", RiskLevel.LOW))
    department_guess = _recommend_department(_combined_text_from_parts(state.get("symptom_text"), latest_answer, state.get("conversation_messages", []))).name

    if intent == "ask_why":
        return _topic_explanation(question_key)
    if intent == "ask_severity_scale":
        return "如果按 0 到 10 分来描述，1 到 3 分通常算轻，4 到 6 分算中等，7 分以上偏重。"
    if intent == "ask_department":
        return f"现在还没到最终定科的时候，不过目前初步倾向会往 {department_guess} 方向判断。"
    if intent == "ask_urgency":
        if risk_level == RiskLevel.EMERGENCY:
            return "按目前信息，已经有急诊风险信号，建议优先急诊。"
        if risk_level == RiskLevel.HIGH:
            return "按目前信息，这次不太建议继续拖，最好尽快线下面诊。"
        return "按目前信息暂时不像必须立刻急诊，但还要继续补几条关键情况。"
    if intent == "ask_general_question":
        return "我先顺着你的问题补一句说明，然后继续把导诊关键信息补齐。"
    if intent == "express_uncertainty":
        return "如果暂时说不清也没关系，你先告诉我更接近哪一种，或者先说你最确定的部分就行。"

    severity = state.get("extracted_facts", {}).get("severity")
    if severity:
        return f"收到，我先记下你说的不舒服程度大约是 {severity}。"
    return ""


def _should_hold_current_topic(state: TriageGraphState) -> bool:
    latest_answer = (state.get("latest_answer") or "").strip()
    if not latest_answer:
        return False
    return _classify_follow_up_intent(latest_answer) in {
        "express_uncertainty",
        "ask_department",
        "ask_urgency",
        "ask_general_question",
        "ask_why",
    }


def _completion_ready(state: TriageGraphState) -> bool:
    if state.get("safety_decision") == "escalate_emergency":
        return True
    if len(state.get("complaint_candidates", [])) > 1 and not state.get("primary_focus_confirmed"):
        return False

    facts = state.get("extracted_facts", {})
    category = state.get("complaint_category", "general")
    risk_level = RiskLevel(state.get("risk_level", RiskLevel.LOW))
    route_history = set(state.get("route_follow_up_history", []))

    if category == "throat_discomfort":
        has_core = all(field in facts for field in ("location", "duration"))
        has_severity_or_companion = "severity" in facts or "accompanying_symptoms" in facts
        route_ok = "throat_red_flags" in route_history or any(
            token in (facts.get("accompanying_symptoms", "") + " " + _combined_text_from_parts(state.get("symptom_text"), state.get("latest_answer"), state.get("conversation_messages", [])))
            for token in ("发热", "咳嗽", "吞咽困难", "呼吸受限", "没有发热", "没有咳嗽", "没有吞咽困难")
        )
        return has_core and has_severity_or_companion and route_ok and risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM)

    if category == "eye_discomfort":
        has_core = all(field in facts for field in ("location", "duration"))
        route_ok = "eye_red_flags" in route_history or any(
            token in _combined_text_from_parts(state.get("symptom_text"), state.get("latest_answer"), state.get("conversation_messages", []))
            for token in ("视力下降", "畏光", "外伤", "隐形眼镜", "没有视力下降", "没有畏光", "没有外伤")
        )
        return has_core and route_ok and risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM)

    if category == "headache":
        has_core = all(field in facts for field in ("location", "duration"))
        route_ok = "headache_red_flags" in route_history or any(
            token in _combined_text_from_parts(state.get("symptom_text"), state.get("latest_answer"), state.get("conversation_messages", []))
            for token in ("突然", "视物", "说话", "肢体", "呕吐", "发热")
        )
        return has_core and route_ok and risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM)

    if category == "abdominal_pain":
        has_core = all(field in facts for field in ("location", "duration"))
        route_ok = "abdominal_location_detail" in route_history and "abdominal_red_flags" in route_history
        return has_core and route_ok and risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM)

    if category == "chest_pain":
        has_core = all(field in facts for field in ("location", "duration"))
        route_ok = "chest_red_flags" in route_history
        return has_core and route_ok and risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM)

    return not state.get("missing_fields")


def _build_care_path(risk_level: RiskLevel) -> str:
    if risk_level == RiskLevel.HIGH:
        return "建议尽快线下面诊，优先选择门诊或急诊评估，避免继续拖延观察。"
    if risk_level == RiskLevel.MEDIUM:
        return "建议尽快安排线下门诊评估；如症状加重或出现新的红旗信号，请及时急诊就医。"
    return "建议根据症状持续时间和严重程度选择线下门诊；若症状明显加重，应及时急诊评估。"


def _extract_segment(content: str, label: str, end_markers: tuple[str, ...]) -> str:
    start_token = f"{label}："
    if start_token not in content:
        return ""
    segment = content.split(start_token, 1)[1]
    cut_index = len(segment)
    for marker in end_markers:
        marker_index = segment.find(marker)
        if marker_index >= 0:
            cut_index = min(cut_index, marker_index)
    return segment[:cut_index].strip("。；; ")


def _build_knowledge_note(state: TriageGraphState) -> str:
    hits = state.get("knowledge_hits", [])
    if not hits:
        return ""

    primary_hit = hits[0]
    title = str(primary_hit.get("title") or "").strip()
    content = str(primary_hit.get("content") or "").strip()
    if not title or not content:
        return ""

    red_flags = _extract_segment(content, "红旗信号", (" 优先追问：", " 候选科室：", " 图谱高频科室："))
    departments = _extract_segment(content, "候选科室", (" 图谱高频科室：",))
    graph_departments = _extract_segment(content, "图谱高频科室", ())

    parts = [f"结合本地导诊知识（{title}）"]
    if red_flags:
        parts.append(f"当前需要重点留意 {red_flags}")

    department_part = departments or graph_departments
    if department_part:
        parts.append(f"常见分诊方向包括 {department_part}")

    note = "；".join(parts).strip("；")
    return f"{note}。" if note else ""


def _recommend_department(symptom_text: str) -> DepartmentRecommendation:
    positive_text = re.sub(r"(没有|无)([^，。；,;]*)", "", symptom_text)
    if any(keyword in positive_text for keyword in ("眼", "视物", "眼红", "眼痒", "异物感", "眼痛")):
        return DepartmentRecommendation(
            name="眼科",
            reason="症状集中在眼部或视物相关不适，适合优先由眼科评估。",
            priority=1,
        )
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
    if any(keyword in positive_text for keyword in ("头痛", "头疼", "头晕", "头部", "脑袋", "偏头痛")):
        return DepartmentRecommendation(
            name="神经内科",
            reason="症状集中在头部疼痛或头晕等神经系统相关不适，适合优先由神经内科评估。",
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
        reason="当前描述暂时无法稳定指向单一专科，建议先由全科医学科进行初步评估。",
        priority=1,
    )


def _classify_llm_error(error: Exception) -> str:
    message = str(error).lower()
    if any(
        token in message
        for token in (
            "timeout",
            "network",
            "auth",
            "unavailable",
            "access denied",
            "arrearage",
            "quota",
            "insufficient",
        )
    ):
        return "transport_error"
    return "format_error"


def _build_llm_trace(
    *,
    agent: str,
    task: str,
    used: bool,
    fallback: bool,
    error: str | None,
    existing: list[LlmTraceEntry] | None = None,
) -> list[LlmTraceEntry]:
    trace = list(existing or [])
    trace.append(LlmTraceEntry(agent=agent, task=task, used=used, fallback=fallback, error=error))
    return trace


async def _call_llm_json(llm_client, prompt: str, max_tokens: int = 240) -> dict:
    provider_options = {}
    if settings.LLM_PROVIDER.lower() == "deepseek":
        provider_options = {
            "response_format": {"type": "json_object"},
            "extra_body": {"thinking": {"type": "disabled"}},
        }

    response = await llm_client.chat.completions.create(
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": "You are a careful Chinese triage writing assistant."},
            {"role": "user", "content": prompt},
        ],
        **provider_options,
    )
    content = response.choices[0].message.content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        if len(lines) >= 3:
            content = "\n".join(lines[1:-1]).strip()
    return json.loads(content)


async def _rewrite_follow_up_question_with_llm(
    *,
    llm_client,
    raw_question: str,
    known_facts_summary: str,
    missing_field: str,
) -> tuple[str | None, str | None]:
    if llm_client is None:
        return None, None

    prompt = (
        "Rewrite one Chinese triage follow-up question.\n"
        "Keep exactly one question.\n"
        "Do not change the target field.\n"
        "Be concise and natural.\n"
        f"missing_field: {missing_field}\n"
        f"known_facts_summary: {known_facts_summary}\n"
        f"raw_question: {raw_question}\n"
        'Return JSON only like {"question":"..."}'
    )
    try:
        payload = await _call_llm_json(llm_client, prompt, max_tokens=180)
        question = payload.get("question")
        if not isinstance(question, str) or not question.strip():
            return None, "format_error"
        stripped = question.strip()
        if stripped.count("？") + stripped.count("?") > 1:
            return None, "safety_reject"
        return stripped, None
    except json.JSONDecodeError:
        return None, "format_error"
    except Exception as error:
        return None, _classify_llm_error(error)


async def _rewrite_report_summary_with_llm(
    *,
    llm_client,
    raw_summary: str,
    symptom_text: str,
    risk_level: str,
    department_name: str,
    care_path: str,
) -> tuple[str | None, str | None]:
    if llm_client is None:
        return None, None

    prompt = (
        "Rewrite one Chinese triage summary for a patient.\n"
        "Do not change risk level or department.\n"
        "Do not add new facts.\n"
        "Be natural and concise.\n"
        f"symptom_text: {symptom_text}\n"
        f"risk_level: {risk_level}\n"
        f"department: {department_name}\n"
        f"care_path: {care_path}\n"
        f"raw_summary: {raw_summary}\n"
        'Return JSON only like {"report_summary":"..."}'
    )
    try:
        payload = await _call_llm_json(llm_client, prompt, max_tokens=220)
        summary = payload.get("report_summary")
        if not isinstance(summary, str) or not summary.strip():
            return None, "format_error"
        return summary.strip(), None
    except json.JSONDecodeError:
        return None, "format_error"
    except Exception as error:
        return None, _classify_llm_error(error)


def _bootstrap_context(state: TriageGraphState) -> TriageGraphState:
    request = state["request"]
    record = _load_or_create_record(request)

    if record.status == TriageStatus.COMPLETED and request.answer:
        raise HTTPException(status_code=409, detail="This triage session has already been completed.")

    messages = list(record.messages)
    if request.symptom_text:
        messages = _append_message(messages, "user", request.symptom_text, kind="symptom")
    if request.answer:
        messages = _append_message(messages, "user", request.answer, kind="answer")

    return {
        "llm_client": state.get("llm_client"),
        "session_id": record.session_id,
        "patient": request.patient or record.patient,
        "city": request.city or record.city,
        "symptom_text": request.symptom_text or record.symptom_text or "",
        "latest_answer": request.answer or "",
        "conversation_messages": messages,
        "extracted_facts": dict(record.extracted_facts),
        "missing_fields": list(record.missing_fields),
        "fact_confidence": {},
        "special_context_flags": {},
        "risk_level": record.risk_level or RiskLevel.LOW,
        "risk_reasons": [],
        "emergency_advice": None,
        "safety_decision": "continue",
        "workflow_status": "initialized",
        "next_agent": "",
        "follow_up_question": None,
        "follow_up_rationale": None,
        "iteration_count": state.get("iteration_count", 0) + 1,
        "completed": False,
        "knowledge_hits": [],
        "knowledge_summary": None,
        "knowledge_used": False,
        "complaint_category": "",
        "complaint_routed": False,
        "current_agent": None,
        "node_trace": ["bootstrap_context"],
        "agent_trace": [],
        "route_reason": None,
        "route_follow_up_history": list(record.route_follow_up_history),
        "current_follow_up_topic": record.current_follow_up_topic,
        "complaint_candidates": list(record.complaint_candidates),
        "primary_focus_confirmed": record.primary_focus_confirmed,
        "debug_snapshot": {},
        "safety_checked": False,
        "facts_updated": False,
        "knowledge_checked": False,
        "raw_follow_up_question": record.raw_follow_up_question,
        "llm_follow_up_question": record.llm_follow_up_question,
        "raw_report_summary": record.raw_report_summary,
        "llm_report_summary": record.llm_report_summary,
        "llm_used": record.llm_used,
        "llm_error": record.llm_error,
        "llm_trace": list(record.llm_trace),
    }


def _supervisor_route(state: TriageGraphState) -> TriageGraphState:
    node_trace = _trace_node(state, "supervisor_route")

    if state.get("completed"):
        return {
            "node_trace": node_trace,
            "next_agent": "persist_state",
            "route_reason": "workflow already completed",
        }
    if not state.get("safety_checked"):
        return {
            "node_trace": node_trace,
            "next_agent": "safety_agent",
            "route_reason": "run safety check before any other agent",
        }
    if state.get("safety_decision") == "escalate_emergency":
        return {
            "node_trace": node_trace,
            "next_agent": "result_agent",
            "route_reason": "emergency risk detected by safety agent",
        }
    if not state.get("facts_updated"):
        return {
            "node_trace": node_trace,
            "next_agent": "triage_agent",
            "route_reason": "structured facts need to be updated",
        }
    if not state.get("complaint_routed"):
        return {
            "node_trace": node_trace,
            "next_agent": "chief_complaint_router_agent",
            "route_reason": "chief complaint should be routed before follow-up selection",
        }
    if not state.get("knowledge_checked"):
        return {
            "node_trace": node_trace,
            "next_agent": "knowledge_agent",
            "route_reason": "knowledge agent should enrich the current triage context",
        }
    if _should_hold_current_topic(state):
        return {
            "node_trace": node_trace,
            "next_agent": "follow_up_agent",
            "route_reason": "user expressed uncertainty, keep current follow-up topic with guidance",
        }
    if _completion_ready(state):
        return {
            "node_trace": node_trace,
            "next_agent": "result_agent",
            "route_reason": "current complaint path has enough information for a triage recommendation",
        }
    if state.get("missing_fields"):
        return {
            "node_trace": node_trace,
            "next_agent": "follow_up_agent",
            "route_reason": "missing core fields require one follow-up question",
        }
    return {
        "node_trace": node_trace,
        "next_agent": "result_agent",
        "route_reason": "all core fields are ready for final triage result",
    }


def _safety_agent(state: TriageGraphState) -> TriageGraphState:
    node_trace = _trace_node(state, "safety_agent")
    combined_text = _combined_text_from_parts(
        state.get("symptom_text"),
        state.get("latest_answer"),
        state.get("conversation_messages", []),
    )
    risk_level, emergency_advice = detect_risk(combined_text)
    safety_decision = "escalate_emergency" if risk_level == RiskLevel.EMERGENCY else "continue"
    risk_reasons = ["emergency keywords detected"] if safety_decision == "escalate_emergency" else ["no emergency escalation"]
    return {
        "node_trace": node_trace,
        "agent_trace": _trace_agent(state, "safety_agent", f"risk={risk_level} decision={safety_decision}"),
        "current_agent": "safety_agent",
        "risk_level": risk_level,
        "risk_reasons": risk_reasons,
        "emergency_advice": emergency_advice,
        "safety_decision": safety_decision,
        "workflow_status": "safety_checked",
        "safety_checked": True,
    }


async def _triage_agent(state: TriageGraphState) -> TriageGraphState:
    node_trace = _trace_node(state, "triage_agent")
    combined_text = _combined_text_from_parts(
        state.get("symptom_text"),
        state.get("latest_answer"),
        state.get("conversation_messages", []),
    )
    rule_facts, rule_confidence, flags = _extract_facts(combined_text, state.get("patient"))
    llm_facts, llm_missing_fields, llm_error = await _extract_facts_with_llm(
        llm_client=state.get("llm_client"),
        combined_text=combined_text,
        patient=state.get("patient"),
        city=state.get("city"),
    )

    if llm_facts is not None:
        facts = {**llm_facts, **rule_facts}
        confidence = {**{key: "llm" for key in llm_facts}, **rule_confidence}
        missing_fields = llm_missing_fields if llm_missing_fields is not None else _missing_fields(facts)
        llm_used = True
    else:
        facts = rule_facts
        confidence = rule_confidence
        missing_fields = _missing_fields(facts)
        llm_used = False

    missing_fields = [field for field in missing_fields if field in FIELD_ORDER and field not in facts]
    llm_trace = _build_llm_trace(
        agent="triage_agent",
        task="extract_structured_symptoms",
        used=llm_used,
        fallback=not llm_used,
        error=llm_error,
        existing=state.get("llm_trace"),
    )
    return {
        "node_trace": node_trace,
        "agent_trace": _trace_agent(
            state,
            "triage_agent",
            f"facts={len(facts)} missing={len(missing_fields)} llm_used={llm_used}",
        ),
        "current_agent": "triage_agent",
        "extracted_facts": facts,
        "missing_fields": missing_fields,
        "fact_confidence": confidence,
        "special_context_flags": flags,
        "workflow_status": "facts_updated",
        "facts_updated": True,
        "llm_used": bool(state.get("llm_used")) or llm_used,
        "llm_error": llm_error,
        "llm_trace": llm_trace,
    }


def _chief_complaint_router_agent(state: TriageGraphState) -> TriageGraphState:
    node_trace = _trace_node(state, "chief_complaint_router_agent")
    combined_text = _combined_text_from_parts(
        state.get("symptom_text"),
        state.get("latest_answer"),
        state.get("conversation_messages", []),
    )
    facts = state.get("extracted_facts", {})
    complaint_candidates = _detect_complaint_candidates(combined_text, facts)
    chosen_focus = _extract_primary_focus_from_answer(state.get("latest_answer", ""), complaint_candidates)
    complaint_category = (
        chosen_focus
        or state.get("complaint_category")
        or (complaint_candidates[0] if complaint_candidates else _classify_complaint_category(combined_text, facts))
    )
    if complaint_category == "general" and complaint_candidates:
        complaint_category = complaint_candidates[0]
    primary_focus_confirmed = bool(chosen_focus or len(complaint_candidates) <= 1)
    return {
        "node_trace": node_trace,
        "agent_trace": _trace_agent(
            state,
            "chief_complaint_router_agent",
            f"category={complaint_category} candidates={len(complaint_candidates)} focus_confirmed={primary_focus_confirmed}",
        ),
        "current_agent": "chief_complaint_router_agent",
        "complaint_category": complaint_category,
        "complaint_candidates": complaint_candidates,
        "primary_focus_confirmed": primary_focus_confirmed,
        "complaint_routed": True,
        "workflow_status": "complaint_routed",
    }


def _knowledge_agent(state: TriageGraphState) -> TriageGraphState:
    node_trace = _trace_node(state, "knowledge_agent")
    query = _combined_text_from_parts(
        state.get("symptom_text"),
        state.get("latest_answer"),
        state.get("conversation_messages", []),
    )
    hits = knowledge_store.search(query, top_k=3)
    serialized_hits = [{"title": hit.title, "content": hit.content, "score": str(hit.score)} for hit in hits]
    summary = f"{hits[0].title}：{hits[0].content}" if hits else "未命中本地导诊知识卡。"
    return {
        "node_trace": node_trace,
        "agent_trace": _trace_agent(state, "knowledge_agent", f"hits={len(hits)}"),
        "current_agent": "knowledge_agent",
        "knowledge_hits": serialized_hits,
        "knowledge_summary": summary,
        "knowledge_used": bool(hits),
        "workflow_status": "knowledge_enriched",
        "knowledge_checked": True,
    }


async def _follow_up_agent(state: TriageGraphState) -> TriageGraphState:
    node_trace = _trace_node(state, "follow_up_agent")
    combined_text = _combined_text_from_parts(
        state.get("symptom_text"),
        state.get("latest_answer"),
        state.get("conversation_messages", []),
    )
    question_key, raw_question = _choose_dynamic_follow_up_topic(state, combined_text)
    known_facts_summary = _augment_known_facts_summary_with_candidates(
        _build_known_facts_summary(state.get("extracted_facts", {})),
        list(state.get("complaint_candidates", [])),
    )
    latest_answer = (state.get("latest_answer") or "").strip()
    follow_up_intent = _classify_follow_up_intent(latest_answer)
    current_follow_up_topic = state.get("current_follow_up_topic")
    if _should_hold_current_topic(state) and current_follow_up_topic:
        question_key = current_follow_up_topic
        raw_question = COMPLAINT_ROUTE_QUESTIONS.get(current_follow_up_topic, FOLLOW_UP_QUESTIONS.get(current_follow_up_topic, raw_question))
    if follow_up_intent == "ask_severity_scale":
        question_key = "severity"
        raw_question = FOLLOW_UP_QUESTIONS["severity"]
    intent_prefix = _intent_aware_prefix(state=state, question_key=question_key)
    llm_question, llm_error = await _rewrite_follow_up_question_with_llm(
        llm_client=state.get("llm_client"),
        raw_question=raw_question,
        known_facts_summary=known_facts_summary,
        missing_field=question_key,
    )
    question_core = llm_question or raw_question
    question = f"{intent_prefix} {question_core}".strip() if intent_prefix else question_core
    llm_used = llm_question is not None
    llm_trace = _build_llm_trace(
        agent="follow_up_agent",
        task="rewrite_follow_up_question",
        used=llm_used,
        fallback=not llm_used,
        error=llm_error,
        existing=state.get("llm_trace"),
    )

    response = FollowUpResponse(
        session_id=state["session_id"],
        status=TriageStatus.NEEDS_FOLLOW_UP,
        risk_level=RiskLevel(state["risk_level"]),
        question=question,
        known_facts_summary=known_facts_summary,
        missing_fields=state.get("missing_fields", []),
    )

    messages = _append_message(state.get("conversation_messages", []), "assistant", question, kind="follow_up")
    route_follow_up_history = list(state.get("route_follow_up_history", []))
    if follow_up_intent != "express_uncertainty" and question_key not in FIELD_ORDER and question_key not in route_follow_up_history:
        route_follow_up_history.append(question_key)
    return {
        "node_trace": node_trace,
        "agent_trace": _trace_agent(state, "follow_up_agent", f"question={question_key}"),
        "current_agent": "follow_up_agent",
        "follow_up_question": question,
        "follow_up_rationale": f"Next follow-up topic: {question_key}",
        "workflow_status": "awaiting_follow_up",
        "route_follow_up_history": route_follow_up_history,
        "current_follow_up_topic": question_key,
        "conversation_messages": messages,
        "response": response,
        "raw_follow_up_question": raw_question,
        "llm_follow_up_question": llm_question,
        "llm_used": llm_used,
        "llm_error": llm_error,
        "llm_trace": llm_trace,
    }


async def _result_agent(state: TriageGraphState) -> TriageGraphState:
    node_trace = _trace_node(state, "result_agent")
    combined_text = _combined_text_from_parts(
        state.get("symptom_text"),
        state.get("latest_answer"),
        state.get("conversation_messages", []),
    )

    if state.get("safety_decision") == "escalate_emergency":
        raw_summary = f"系统识别到急危重风险信号：{state.get('symptom_text') or combined_text}"
        response = TriageResponse(
            session_id=state["session_id"],
            status=TriageStatus.COMPLETED,
            risk_level=RiskLevel.EMERGENCY,
            emergency_advice=state.get("emergency_advice") or "建议立刻前往急诊或拨打 120。",
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
            report_summary=raw_summary,
            disclaimer=DISCLAIMER,
        )
        llm_summary = None
        llm_error = None
        llm_used = False
        llm_trace = list(state.get("llm_trace", []))
    else:
        department = _recommend_department(combined_text)
        care_path = _build_care_path(RiskLevel(state["risk_level"]))
        chief_complaint = _chief_complaint_text(state, combined_text).rstrip("。！？!?；;，, ")
        knowledge_note = _build_knowledge_note(state)
        raw_summary = f"主诉：{chief_complaint}。当前补全信息后，建议优先咨询 {department.name}。"
        if knowledge_note:
            raw_summary = f"{raw_summary} {knowledge_note}"
        llm_summary, llm_error = await _rewrite_report_summary_with_llm(
            llm_client=state.get("llm_client"),
            raw_summary=raw_summary,
            symptom_text=chief_complaint,
            risk_level=state["risk_level"],
            department_name=department.name,
            care_path=care_path,
        )
        llm_used = llm_summary is not None
        llm_trace = _build_llm_trace(
            agent="result_agent",
            task="rewrite_report_summary",
            used=llm_used,
            fallback=not llm_used,
            error=llm_error,
            existing=state.get("llm_trace"),
        )
        response = TriageResponse(
            session_id=state["session_id"],
            status=TriageStatus.COMPLETED,
            risk_level=RiskLevel(state["risk_level"]),
            emergency_advice=None,
            recommended_departments=[department],
            care_path=care_path,
            preparation_checklist=[
                "记录症状开始时间、变化过程和诱因",
                "携带既往病历、检查报告和当前用药清单",
                "说明药物过敏史、基础病和近期就诊情况",
            ],
            report_summary=llm_summary or raw_summary,
            disclaimer=DISCLAIMER,
        )

    messages = _append_message(
        state.get("conversation_messages", []),
        "assistant",
        response.emergency_advice or response.report_summary,
        kind="result",
    )

    return {
        "node_trace": node_trace,
        "agent_trace": _trace_agent(state, "result_agent", f"status={response.status} risk={response.risk_level}"),
        "current_agent": "result_agent",
        "workflow_status": "completed",
        "completed": True,
        "conversation_messages": messages,
        "response": response,
        "raw_report_summary": raw_summary,
        "llm_report_summary": llm_summary,
        "llm_used": llm_used,
        "llm_error": llm_error,
        "llm_trace": llm_trace,
    }


def _persist_state(state: TriageGraphState) -> TriageGraphState:
    node_trace = _trace_node(state, "persist_state")
    record = get_session(state["session_id"]) or create_session(state["session_id"])
    request = state["request"]

    record.patient = state.get("patient")
    record.city = state.get("city")
    record.symptom_text = state.get("symptom_text") or record.symptom_text
    record.extracted_facts = dict(state.get("extracted_facts", {}))
    record.missing_fields = list(state.get("missing_fields", []))
    record.fact_confidence = dict(state.get("fact_confidence", {}))
    if state.get("latest_answer"):
        if not record.answered_follow_ups or record.answered_follow_ups[-1] != state["latest_answer"]:
            record.answered_follow_ups.append(state["latest_answer"])
    record.current_question = state.get("follow_up_question")
    record.risk_level = state.get("risk_level")
    record.latest_request = request
    record.latest_result = state["response"]
    record.messages = list(state.get("conversation_messages", []))
    record.workflow_status = state.get("workflow_status", record.workflow_status)
    record.current_agent = state.get("current_agent")
    record.node_trace = node_trace
    record.agent_trace = list(state.get("agent_trace", []))
    record.route_reason = state.get("route_reason")
    record.knowledge_summary = state.get("knowledge_summary")
    record.route_follow_up_history = list(state.get("route_follow_up_history", []))
    record.current_follow_up_topic = state.get("current_follow_up_topic")
    record.complaint_candidates = list(state.get("complaint_candidates", []))
    record.primary_focus_confirmed = state.get("primary_focus_confirmed", False)
    record.raw_follow_up_question = state.get("raw_follow_up_question")
    record.llm_follow_up_question = state.get("llm_follow_up_question")
    record.raw_report_summary = state.get("raw_report_summary")
    record.llm_report_summary = state.get("llm_report_summary")
    record.llm_used = state.get("llm_used", False)
    record.llm_error = state.get("llm_error")
    record.llm_trace = list(state.get("llm_trace", []))

    if state["response"].status == TriageStatus.COMPLETED:
        record.status = TriageStatus.COMPLETED
        record.current_question = None
        record.current_follow_up_topic = None
        record.final_result = state["response"].model_dump(mode="json")
    else:
        record.status = TriageStatus.NEEDS_FOLLOW_UP
        record.final_result = None

    save_session(record)
    return {
        "node_trace": node_trace,
        "debug_snapshot": {
            "current_agent": state.get("current_agent"),
            "node_trace": node_trace,
            "agent_trace": state.get("agent_trace", []),
            "route_reason": state.get("route_reason"),
            "knowledge_summary": state.get("knowledge_summary"),
            "complaint_candidates": state.get("complaint_candidates", []),
            "primary_focus_confirmed": state.get("primary_focus_confirmed", False),
            "raw_follow_up_question": state.get("raw_follow_up_question"),
            "llm_follow_up_question": state.get("llm_follow_up_question"),
            "raw_report_summary": state.get("raw_report_summary"),
            "llm_report_summary": state.get("llm_report_summary"),
            "llm_used": state.get("llm_used", False),
            "llm_error": state.get("llm_error"),
            "llm_trace": [entry.model_dump(mode="json") for entry in state.get("llm_trace", [])],
        },
    }


def _route_from_supervisor(state: TriageGraphState) -> str:
    return state["next_agent"]


@lru_cache(maxsize=1)
def _compiled_graph():
    workflow = StateGraph(TriageGraphState)
    workflow.add_node("bootstrap_context", _bootstrap_context)
    workflow.add_node("supervisor_route", _supervisor_route)
    workflow.add_node("safety_agent", _safety_agent)
    workflow.add_node("triage_agent", _triage_agent)
    workflow.add_node("chief_complaint_router_agent", _chief_complaint_router_agent)
    workflow.add_node("knowledge_agent", _knowledge_agent)
    workflow.add_node("follow_up_agent", _follow_up_agent)
    workflow.add_node("result_agent", _result_agent)
    workflow.add_node("persist_state", _persist_state)

    workflow.set_entry_point("bootstrap_context")
    workflow.add_edge("bootstrap_context", "supervisor_route")
    workflow.add_conditional_edges(
        "supervisor_route",
        _route_from_supervisor,
        {
            "safety_agent": "safety_agent",
            "triage_agent": "triage_agent",
            "chief_complaint_router_agent": "chief_complaint_router_agent",
            "knowledge_agent": "knowledge_agent",
            "follow_up_agent": "follow_up_agent",
            "result_agent": "result_agent",
            "persist_state": "persist_state",
        },
    )
    workflow.add_edge("safety_agent", "supervisor_route")
    workflow.add_edge("triage_agent", "supervisor_route")
    workflow.add_edge("chief_complaint_router_agent", "supervisor_route")
    workflow.add_edge("knowledge_agent", "supervisor_route")
    workflow.add_edge("follow_up_agent", "persist_state")
    workflow.add_edge("result_agent", "persist_state")
    workflow.add_edge("persist_state", END)
    return workflow.compile()
