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


async def run_triage(request: TriageRequest, llm_client=None) -> AnalyzeResponse:
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


def _append_message(messages: list[TriageMessage], role: str, content: str, kind: str) -> list[TriageMessage]:
    updated = list(messages)
    updated.append(TriageMessage(role=role, content=content, kind=kind))
    return updated


def _is_correction_message(text: str) -> bool:
    lowered = text.strip()
    return any(token in lowered for token in ("刚才说错", "说错了", "更正一下", "改一下", "不是"))


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
    if latest_answer and _is_correction_message(latest_answer):
        normalized = re.sub(r"^(?:我)?刚才说错了?[，,：:\s]*", "", latest_answer)
        normalized = re.sub(r"^不是[^，。；,;]*[，,、\s]*是", "", normalized)
        normalized = normalized.strip("，,。；;：: ")
        return normalized or latest_answer

    symptom_text = (state.get("symptom_text") or "").strip()
    if symptom_text:
        return symptom_text

    return combined_text


def _special_context_flags(patient: PatientProfile | None, text: str) -> dict[str, bool]:
    return {
        "pregnancy": bool(patient and patient.pregnancy_status) or ("怀孕" in text),
        "elderly": bool(patient and patient.age >= 65),
        "child": bool(patient and patient.age <= 6),
        "chronic_disease": bool(patient and patient.medical_history) or any(
            token in text for token in ("高血压", "糖尿病", "慢性病")
        ),
        "post_surgery": "术后" in text,
    }


def _extract_facts(text: str, patient: PatientProfile | None) -> tuple[dict[str, str], dict[str, str], dict[str, bool]]:
    facts: dict[str, str] = {}
    confidence: dict[str, str] = {}

    location_matchers = (
        ("咽喉", ("喉咙", "咽痛", "吞咽")),
        ("胸部", ("胸痛", "胸闷", "胸口")),
        ("腹部", ("腹痛", "胃痛", "肚子")),
        ("头部", ("头痛", "头晕")),
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
    elif patient and patient.pregnancy_status:
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
    response = await llm_client.chat.completions.create(
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": "You are a careful Chinese triage writing assistant."},
            {"role": "user", "content": prompt},
        ],
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
        "current_agent": None,
        "node_trace": ["bootstrap_context"],
        "agent_trace": [],
        "route_reason": None,
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
    if not state.get("knowledge_checked"):
        return {
            "node_trace": node_trace,
            "next_agent": "knowledge_agent",
            "route_reason": "knowledge agent should enrich the current triage context",
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


def _triage_agent(state: TriageGraphState) -> TriageGraphState:
    node_trace = _trace_node(state, "triage_agent")
    combined_text = _combined_text_from_parts(
        state.get("symptom_text"),
        state.get("latest_answer"),
        state.get("conversation_messages", []),
    )
    facts, confidence, flags = _extract_facts(combined_text, state.get("patient"))
    missing_fields = _missing_fields(facts)
    return {
        "node_trace": node_trace,
        "agent_trace": _trace_agent(state, "triage_agent", f"facts={len(facts)} missing={len(missing_fields)}"),
        "current_agent": "triage_agent",
        "extracted_facts": facts,
        "missing_fields": missing_fields,
        "fact_confidence": confidence,
        "special_context_flags": flags,
        "workflow_status": "facts_updated",
        "facts_updated": True,
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
    summary = "；".join(hit.title for hit in hits) if hits else "No knowledge hits retrieved for the current triage turn."
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
    question_key = _choose_follow_up_field(state, combined_text)
    raw_question = FOLLOW_UP_QUESTIONS[question_key]
    known_facts_summary = _build_known_facts_summary(state.get("extracted_facts", {}))
    llm_question, llm_error = await _rewrite_follow_up_question_with_llm(
        llm_client=state.get("llm_client"),
        raw_question=raw_question,
        known_facts_summary=known_facts_summary,
        missing_field=question_key,
    )
    question = llm_question or raw_question
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
    return {
        "node_trace": node_trace,
        "agent_trace": _trace_agent(state, "follow_up_agent", f"question={question_key}"),
        "current_agent": "follow_up_agent",
        "follow_up_question": question,
        "follow_up_rationale": f"Missing core field: {question_key}",
        "workflow_status": "awaiting_follow_up",
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
        raw_summary = f"主诉：{chief_complaint}。当前补全信息后，建议优先咨询 {department.name}。"
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
            "knowledge_agent": "knowledge_agent",
            "follow_up_agent": "follow_up_agent",
            "result_agent": "result_agent",
            "persist_state": "persist_state",
        },
    )
    workflow.add_edge("safety_agent", "supervisor_route")
    workflow.add_edge("triage_agent", "supervisor_route")
    workflow.add_edge("knowledge_agent", "supervisor_route")
    workflow.add_edge("follow_up_agent", "persist_state")
    workflow.add_edge("result_agent", "persist_state")
    workflow.add_edge("persist_state", END)
    return workflow.compile()
