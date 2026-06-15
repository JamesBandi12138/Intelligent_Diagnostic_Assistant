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
| patient | PatientProfile | 患者基本信息 |
| symptom_text | string | 用户症状描述 |
| city | string/null | 所在城市，用于后续医院信息检索 |

## TriageResponse

| 字段 | 类型 | 说明 |
|---|---|---|
| session_id | string | 会话 ID |
| risk_level | string | `low`、`medium`、`high`、`emergency` |
| emergency_advice | string/null | 急诊建议 |
| recommended_departments | DepartmentRecommendation[] | 科室建议 |
| follow_up_questions | string[] | 信息不足时的追问 |
| care_path | string | 就医路径建议 |
| preparation_checklist | string[] | 就医准备清单 |
| report_summary | string | 就医摘要 |
| disclaimer | string | 免责声明 |

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

