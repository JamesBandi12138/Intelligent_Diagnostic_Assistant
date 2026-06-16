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

## `POST /api/triage/sessions`

### 响应示例

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

## `POST /api/triage/analyze` 响应

接口只会返回两种状态：

### 1. 需要继续追问

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

### 2. 已完成导诊

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

### 响应示例

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
    }
  ]
}
```
