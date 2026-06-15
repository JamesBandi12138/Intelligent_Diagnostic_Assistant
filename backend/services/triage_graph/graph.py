from uuid import uuid4

from app.schemas.triage import DepartmentRecommendation, TriageRequest, TriageResponse
from services.safety_guardrails.service import detect_risk


DISCLAIMER = "本结果仅用于诊前导诊参考，不能替代医生诊断、检查或治疗决策。"


def run_triage(request: TriageRequest) -> TriageResponse:
    session_id = request.session_id or str(uuid4())
    risk_level, emergency_advice = detect_risk(request.symptom_text)

    if risk_level == "emergency":
        return TriageResponse(
            session_id=session_id,
            risk_level=risk_level,
            emergency_advice=emergency_advice,
            recommended_departments=[
                DepartmentRecommendation(
                    name="急诊科",
                    reason="症状描述中存在急危重症风险信号，应优先进行急诊评估。",
                    priority=1,
                )
            ],
            follow_up_questions=[],
            care_path="请优先前往最近医院急诊或拨打 120，并尽量由家属陪同。",
            preparation_checklist=["携带身份证/医保卡", "携带既往病历和当前用药", "记录症状开始时间"],
            report_summary=f"患者描述：{request.symptom_text}。系统识别为急诊优先场景。",
            disclaimer=DISCLAIMER,
        )

    department = _recommend_department(request.symptom_text)
    return TriageResponse(
        session_id=session_id,
        risk_level=risk_level,
        emergency_advice=None,
        recommended_departments=[department],
        follow_up_questions=_missing_information_questions(request),
        care_path="建议根据症状持续时间和严重程度选择线下门诊；若症状明显加重，应及时急诊评估。",
        preparation_checklist=[
            "记录症状开始时间、变化过程和诱因",
            "携带既往病历、检查报告和当前用药清单",
            "说明药物过敏史、基础病和近期就诊情况",
        ],
        report_summary=f"主诉：{request.symptom_text}。建议优先咨询{department.name}。",
        disclaimer=DISCLAIMER,
    )


def _recommend_department(symptom_text: str) -> DepartmentRecommendation:
    if any(keyword in symptom_text for keyword in ("喉咙", "咽", "吞咽", "鼻", "耳")):
        return DepartmentRecommendation(
            name="耳鼻喉科",
            reason="症状集中在咽喉、耳鼻相关部位，适合优先由耳鼻喉科评估。",
            priority=1,
        )
    if any(keyword in symptom_text for keyword in ("腹痛", "腹泻", "胃", "恶心", "呕吐")):
        return DepartmentRecommendation(
            name="消化内科",
            reason="症状集中在胃肠道，适合优先由消化内科评估。",
            priority=1,
        )
    if any(keyword in symptom_text for keyword in ("咳嗽", "发热", "流涕", "感冒")):
        return DepartmentRecommendation(
            name="呼吸内科",
            reason="症状偏向呼吸道感染或呼吸系统问题，适合优先由呼吸内科评估。",
            priority=1,
        )
    return DepartmentRecommendation(
        name="全科医学科",
        reason="当前描述暂无法稳定指向单一专科，建议先由全科医学科进行初步评估。",
        priority=1,
    )


def _missing_information_questions(request: TriageRequest) -> list[str]:
    questions: list[str] = []
    if len(request.symptom_text) < 12:
        questions.append("请补充症状持续多久、是否加重、是否伴随发热或疼痛。")
    if not request.patient.medical_history:
        questions.append("请补充是否有慢性病、手术史或长期用药。")
    return questions

