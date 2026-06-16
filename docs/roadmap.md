# 开发计划

## Phase 1：项目框架

- 中文 README。
- FastAPI 后端骨架。
- Vue3 前端骨架。
- LangGraph 多 Agent 目录结构。
- prompts 模板。
- 安全边界文档。

## Phase 2：导诊 MVP

- 实现 Safety Guardrail。
- 实现 Symptom Intake Agent，使用 DeepSeek 做结构化症状理解。
- 实现 Follow-up Agent，一次只追问一个关键问题。
- 实现 Department Agent，给出主推荐科室、备选科室和理由。
- 实现 Report Agent，生成患者版建议和医生版摘要。
- 支持多轮追问。
- 生成结构化导诊报告。
- 前端改为患者分诊台体验，减少首屏操作和表单负担。

当前进展：DeepSeek 已接入，Symptom Intake Agent 已开始使用 DeepSeek JSON 做结构化抽取，并由规则层对明确症状事实进行纠偏。

## Phase 3：知识增强

- 建立常见症状到科室规则库。
- 接入 Tavily 检索医院/医生公开信息。
- 在有人工审核资料后再接入可选 RAG/向量知识库。
- 增加导诊建议可解释性。

## Phase 4：产品化

- 用户登录。
- 历史会话。
- PDF 报告导出。
- LangSmith 追踪。
- 医生审核后台。

## Phase 5：合规与质量

- 医生评测集。
- 红旗症状测试集。
- 隐私合规检查。
- 安全提示词评估。
