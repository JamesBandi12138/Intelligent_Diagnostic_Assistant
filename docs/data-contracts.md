# 数据契约

本文档是项目数据结构的协作约定。当前阶段仅定义 MVP 需要的核心字段。

## PatientProfile

| 字段 | 类型 | 说明 |
|---|---|---|
| age | int | 年龄 |
| sex | string | `male`、`female`、`unknown` |
| pregnancy_status | string/null | 孕产状态，适用于女性用户 |
| medical_history | string[] | 既往史 |
| allergies | string[] | 过敏史 |
| medications | string[] | 当前用药 |

## TriageRequest

| 字段 | 类型 | 说明 |
|---|---|---|
| session_id | string/null | 会话 ID，不传则后端创建 |
| patient | PatientProfile/null | 首轮提交时的患者基本信息 |
| symptom_text | string/null | 首轮用户症状描述 |
| city | string/null | 所在城市，用于后续医院信息检索 |
| answer | string/null | 追问回答，同一个会话继续推进时使用 |

请求必须满足以下任一形态：

- 首轮：`patient + symptom_text`
- 追问：`session_id + answer`

## TriageResponse

| 字段 | 类型 | 说明 |
|---|---|---|
| session_id | string | 会话 ID |
| status | string | 固定为 `completed` |
| risk_level | string | `low`、`medium`、`high`、`emergency` |
| emergency_advice | string/null | 急诊建议 |
| recommended_departments | DepartmentRecommendation[] | 科室建议 |
| care_path | string | 就医路径建议 |
| preparation_checklist | string[] | 就医准备清单 |
| report_summary | string | 就医摘要 |
| disclaimer | string | 免责声明 |

## FollowUpResponse

信息不足时，`POST /api/triage/analyze` 会返回追问响应：

| 字段 | 类型 | 说明 |
|---|---|---|
| session_id | string | 会话 ID |
| status | string | 固定为 `needs_follow_up` |
| risk_level | string | 当前风险等级 |
| question | string | 本轮只问一个关键问题 |
| known_facts_summary | string | 已知信息摘要 |
| missing_fields | string[] | 仍缺失的核心字段 |

## 结构化症状事实

后端内部使用 `extracted_facts` 和 `fact_confidence` 记录症状结构化结果。当前核心字段为：

| 字段 | 说明 |
|---|---|
| location | 症状部位 |
| duration | 持续时间 |
| severity | 严重程度 |
| accompanying_symptoms | 伴随症状或已否认症状 |
| special_context | 慢病、孕产、年龄、术后等特殊背景 |

`fact_confidence` 标记事实来源，常见取值包括 `rule`、`llm`、`negation_rule`、`patient_profile`。规则层会优先纠偏明确事实，例如眼部症状不会被 LLM 误覆盖成腹部。

## DepartmentRecommendation

| 字段 | 类型 | 说明 |
|---|---|---|
| name | string | 科室名称 |
| reason | string | 推荐理由 |
| priority | int | 推荐优先级，1 为最高 |

## 风险等级

| 等级 | 含义 | 系统行为 |
|---|---|---|
| low | 暂未发现明显急症信号 | 给出普通门诊/线上问诊建议 |
| medium | 建议尽快线下评估 | 强调及时就诊 |
| high | 可能存在较高风险 | 建议尽快医院就诊，并提示观察红旗症状 |
| emergency | 命中急危重症信号 | 优先提示急诊或 120 |
