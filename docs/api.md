# API 约定

Base URL: `http://localhost:8000`

## 健康检查

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 返回服务状态 |

## 导诊

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/triage/sessions` | 创建导诊会话 |
| POST | `/api/triage/analyze` | 提交用户症状并返回导诊建议 |
| GET | `/api/triage/sessions/{session_id}` | 获取会话详情 |

## 请求示例

```json
{
  "session_id": "demo-session",
  "patient": {
    "age": 32,
    "sex": "female",
    "medical_history": ["过敏性鼻炎"],
    "medications": []
  },
  "symptom_text": "喉咙痛三天，有点发热，吞咽疼，不知道挂什么科",
  "city": "北京"
}
```

## 响应示例

```json
{
  "session_id": "demo-session",
  "risk_level": "low",
  "emergency_advice": null,
  "recommended_departments": [
    {
      "name": "耳鼻喉科",
      "reason": "咽喉痛、吞咽痛持续三天，优先考虑耳鼻喉科评估"
    }
  ],
  "follow_up_questions": [],
  "care_path": "建议线下门诊就诊，如高热不退或呼吸困难应及时急诊",
  "preparation_checklist": [
    "记录体温变化",
    "携带既往病历和用药清单",
    "说明是否有药物过敏史"
  ],
  "disclaimer": "本结果仅用于诊前导诊参考，不能替代医生诊断。"
}
```

## SSE 扩展方向

后续可将 `/api/triage/analyze` 扩展为 SSE 流式输出：

```text
event: status
data: {"stage":"symptom_analyzing"}

event: question
data: {"text":"请问体温最高多少度？"}

event: result
data: {"risk_level":"low"}

event: done
data: {"latency_ms":1200}
```

