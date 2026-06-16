# 架构设计

## 设计目标

本项目不是“AI 医生”，而是“诊前导诊助手”。架构重点不是让模型直接给诊断，而是把导诊过程拆成可控节点：

1. 先识别风险，急症优先。
2. 再结构化症状，减少用户表达不清带来的偏差。
3. 信息不足时追问，不强行生成。
4. 推荐科室和就医路径，而不是治疗方案。
5. 生成便于医生快速阅读的就医摘要。

## 总体分层

```text
Vue 3 前端
  └─ FastAPI API 网关
      └─ LangGraph Supervisor
          ├─ Safety Guardrail Agent
          ├─ Symptom Intake Agent
          ├─ Follow-up Agent
          ├─ Department Agent
          └─ Report Agent
```

当前阶段采用“患者无感、内部真实分工”的多 Agent 方案。前端不把 Agent 名称作为主体验展示，患者只看到清晰的导诊流程；Agent Trace 和 LLM Trace 仅用于开发调试。

## 与 ScholarMind 的参考关系

ScholarMind 提供的是成熟工程组织方式，本项目借鉴：

- `backend/app/routers`：API 边界清晰。
- `backend/app/schemas`：Pydantic schema 作为接口契约。
- `backend/services`：业务能力按服务拆分。
- `backend/common`：配置、日志、模型客户端等公共能力。
- `prompts`：运行时提示词外置。
- `docs`：架构、API、数据契约作为团队协作真相源。

本项目不照搬 ScholarMind 的论文解析/RAG 入库链路，而是按诊前导诊场景重构为 LangGraph 多 Agent 工作流。

## 核心状态

导诊工作流共享一个 `TriageState`：

- 用户基本信息：年龄、性别、孕产状态、基础病、过敏史。
- 症状描述：主诉、持续时间、部位、严重程度、伴随症状。
- 风险识别：红旗症状、风险等级、是否建议急诊。
- 信息缺口：需要继续追问的问题。
- 导诊建议：推荐科室、就医路径、检查准备方向。
- 输出报告：就医摘要、注意事项、免责声明。

## 条件路由

```text
输入症状
  ├─ Safety Agent 命中急危重症红旗 → 输出急诊提示
  └─ Symptom Intake Agent 结构化症状
      ├─ 关键信息不足 → Follow-up Agent 只追问一个问题
      └─ 信息足够 → Department Agent 科室推荐 → Report Agent 就医摘要
```

DeepSeek 通过 OpenAI-compatible API 接入，参与结构化理解、追问生成、科室推荐理由和报告表达；红旗症状、禁答边界和急诊升级仍由规则优先兜底。

## 数据存储建议

- MySQL：用户导诊会话、结构化症状、推荐结果、报告元数据。
- PostgreSQL：多轮对话记忆和 LangGraph checkpoint。
- Redis：短期缓存、队列、限流、临时状态。
- MinIO：用户上传的报告附件、生成的 PDF 报告。
- Milvus：可选，用于常见症状知识库、科室规则、就医指南检索。

## 可扩展方向

- 接入医院科室和医生排班数据。
- 接入本地三甲医院科室知识库。
- 支持语音输入和 OCR 识别检查报告。
- 支持慢病随访、复诊提醒、电子病历摘要。
- 增加医生审核后台，用于评估导诊建议质量。
