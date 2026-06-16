# API 约定

Base URL: `http://localhost:8000`

## 健康检查

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 返回服务状态 |

## 导诊会话

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/triage/sessions` | 创建导诊会话 |
| POST | `/api/triage/analyze` | 提交首轮症状或继续回答追问 |
| GET | `/api/triage/sessions/{session_id}` | 获取会话详情与当前状态 |

## 导诊报告

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/reports` | 基于已完成会话生成报告 |
| GET | `/api/reports/{report_id}` | 获取单份报告详情 |

## `POST /api/triage/sessions`

```json
{
  "session_id": "demo-session",
  "status": "created"
}
```

## `POST /api/triage/analyze`

同一个接口承担两种语义：

1. 首轮提交
2. 追问回答

### 首轮请求示例

```json
{
  "session_id": "demo-session",
  "patient": {
    "age": 32,
    "sex": "female",
    "medical_history": [],
    "allergies": [],
    "medications": []
  },
  "symptom_text": "喉咙不舒服",
  "city": "北京"
}
```

### 追问回答示例

```json
{
  "session_id": "demo-session",
  "answer": "喉咙痛三天，吞咽时更明显，疼痛约 4 到 5 分，没有发烧咳嗽，也没有慢性病"
}
```

### 继续追问响应

```json
{
  "session_id": "demo-session",
  "status": "needs_follow_up",
  "risk_level": "medium",
  "question": "这种不舒服持续多久了？是突然开始还是逐渐加重的？",
  "known_facts_summary": "部位：喉咙",
  "missing_fields": ["duration", "severity", "accompanying_symptoms", "special_context"]
}
```

### 导诊完成响应

```json
{
  "session_id": "demo-session",
  "status": "completed",
  "risk_level": "medium",
  "emergency_advice": null,
  "recommended_departments": [
    {
      "name": "耳鼻喉科",
      "reason": "症状集中在咽喉、鼻腔或耳部区域，适合优先由耳鼻喉科评估。",
      "priority": 1
    }
  ],
  "care_path": "建议尽快安排线下门诊评估；如症状加重或出现新的红旗信号，请及时急诊就医。",
  "preparation_checklist": [
    "记录症状开始时间、变化过程和诱因",
    "携带既往病历、检查报告和当前用药清单",
    "说明药物过敏史、基础病和近期就诊情况"
  ],
  "report_summary": "主诉：喉咙不舒服。当前补全信息后，建议优先咨询耳鼻喉科。",
  "disclaimer": "本结果仅用于诊前导诊参考，不能替代医生诊断、检查或治疗决策。"
}
```

## `GET /api/triage/sessions/{session_id}`

```json
{
  "session_id": "demo-session",
  "status": "completed",
  "latest_request": {
    "session_id": "demo-session",
    "answer": "喉咙痛三天，吞咽时更明显，疼痛约 4 到 5 分，没有发烧咳嗽，也没有慢性病"
  },
  "latest_result": {
    "session_id": "demo-session",
    "status": "completed",
    "risk_level": "medium",
    "emergency_advice": null,
    "recommended_departments": [
      {
        "name": "耳鼻喉科",
        "reason": "症状集中在咽喉、鼻腔或耳部区域，适合优先由耳鼻喉科评估。",
        "priority": 1
      }
    ],
    "care_path": "建议尽快安排线下门诊评估；如症状加重或出现新的红旗信号，请及时急诊就医。",
    "preparation_checklist": [
      "记录症状开始时间、变化过程和诱因",
      "携带既往病历、检查报告和当前用药清单",
      "说明药物过敏史、基础病和近期就诊情况"
    ],
    "report_summary": "主诉：喉咙不舒服。当前补全信息后，建议优先咨询耳鼻喉科。",
    "disclaimer": "本结果仅用于诊前导诊参考，不能替代医生诊断、检查或治疗决策。"
  },
  "current_question": null,
  "report_id": "report-demo-id",
  "messages": [
    {
      "role": "user",
      "content": "喉咙不舒服",
      "kind": "symptom"
    },
    {
      "role": "assistant",
      "content": "这种不舒服持续多久了？是突然开始还是逐渐加重的？",
      "kind": "follow_up"
    },
    {
      "role": "user",
      "content": "喉咙痛三天，吞咽时更明显，疼痛约 4 到 5 分，没有发烧咳嗽，也没有慢性病",
      "kind": "answer"
    },
    {
      "role": "assistant",
      "content": "主诉：喉咙不舒服。当前补全信息后，建议优先咨询耳鼻喉科。",
      "kind": "result"
    }
  ]
}
```

## Session Debug Fields

`GET /api/triage/sessions/{session_id}` 现在会额外返回一组轻量调试字段，用于观察 LangGraph + 多Agent 编排过程：

```json
{
  "current_agent": "follow_up_agent",
  "node_trace": [
    "bootstrap_context",
    "supervisor_route",
    "safety_agent",
    "supervisor_route",
    "triage_agent",
    "supervisor_route",
    "knowledge_agent",
    "supervisor_route",
    "follow_up_agent",
    "persist_state"
  ],
  "agent_trace": [
    {
      "agent": "safety_agent",
      "summary": "risk=medium decision=continue"
    },
    {
      "agent": "knowledge_agent",
      "summary": "hits=0"
    }
  ],
  "route_reason": "missing core fields require one follow-up question",
  "knowledge_summary": "No knowledge hits retrieved for the current triage turn."
}
```

这些字段用于调试和可视化，不影响原有导诊主结果结构。

LLM 润色与回退相关的调试字段也会在 `GET /api/triage/sessions/{session_id}` 中返回：

```json
{
  "raw_follow_up_question": "这种不舒服持续多久了？",
  "llm_follow_up_question": "这种不舒服大概持续多久了，是突然开始还是慢慢加重的？",
  "raw_report_summary": "主诉：喉咙不舒服。目前信息补全后，建议优先咨询耳鼻喉科。",
  "llm_report_summary": "根据你补充的情况，目前更建议优先到耳鼻喉科门诊评估喉咙不适。",
  "llm_used": true,
  "llm_error": null,
  "llm_trace": [
    {
      "agent": "follow_up_agent",
      "task": "rewrite_follow_up_question",
      "used": true,
      "fallback": false,
      "error": null
    },
    {
      "agent": "result_agent",
      "task": "rewrite_report_summary",
      "used": true,
      "fallback": false,
      "error": null
    }
  ]
}
```

- `raw_follow_up_question` / `raw_report_summary` 是规则层生成的原始文本。
- `llm_follow_up_question` / `llm_report_summary` 是 LLM 润色后的最终文本。
- `llm_used=false` 表示本轮回落到了规则结果，`llm_error` 用于区分 `transport_error`、`format_error` 或 `safety_reject`。
- `llm_trace` 用于查看每个 agent 的 LLM 调用参与情况。

## `POST /api/reports`

### 请求示例

```json
{
  "session_id": "demo-session"
}
```

### 响应示例

```json
{
  "report_id": "report-demo-id",
  "session_id": "demo-session",
  "status": "ready",
  "created_at": "2026-06-16T12:00:00Z",
  "patient_snapshot": {
    "age": 32,
    "sex": "female",
    "pregnancy_status": null,
    "medical_history": [],
    "allergies": [],
    "medications": []
  },
  "triage_summary": {
    "chief_complaint": "喉咙不舒服",
    "risk_level": "medium",
    "recommended_departments": [
      {
        "name": "耳鼻喉科",
        "reason": "症状集中在咽喉、鼻腔或耳部区域，适合优先由耳鼻喉科评估。",
        "priority": 1
      }
    ],
    "care_path": "建议尽快安排线下门诊评估；如症状加重或出现新的红旗信号，请及时急诊就医。",
    "generated_from_session_status": "completed"
  },
  "doctor_view": {
    "chief_complaint": "喉咙不舒服",
    "key_facts": {
      "duration": "三天",
      "severity": "4到5分"
    },
    "risk_notes": "当前导诊风险等级为 medium，建议结合线下面诊进一步确认。",
    "recommended_department_summary": "建议优先就诊：耳鼻喉科",
    "preparation_checklist": [
      "记录症状开始时间、变化过程和诱因",
      "携带既往病历、检查报告和当前用药清单",
      "说明药物过敏史、基础病和近期就诊情况"
    ]
  },
  "patient_view": {
    "what_this_means": "这份报告是根据你当前补充的症状信息整理出的诊前摘要，建议优先考虑耳鼻喉科。",
    "why_this_department": "症状集中在咽喉、鼻腔或耳部区域，适合优先由耳鼻喉科评估。",
    "what_to_prepare": [
      "记录症状开始时间、变化过程和诱因",
      "携带既往病历、检查报告和当前用药清单",
      "说明药物过敏史、基础病和近期就诊情况"
    ],
    "when_to_seek_urgent_care": "如果出现胸痛、呼吸困难、意识异常、大出血或症状明显加重，请不要等待，尽快急诊就医。"
  },
  "disclaimer": "本结果仅用于诊前导诊参考，不能替代医生诊断、检查或治疗决策。"
}
```

## `GET /api/reports/{report_id}`

返回结构与 `POST /api/reports` 响应主体一致。
