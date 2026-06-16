# DeepSeek 多 Agent 导诊与患者体验重构设计

日期：2026-06-16
项目：Intelligent Diagnostic Assistant
状态：已确认，进行中

## 当前实现进展

- 已接入 DeepSeek OpenAI-compatible API，默认模型为 `deepseek-v4-flash`。
- `Symptom Intake Agent` 已开始使用 DeepSeek JSON 输出做结构化症状抽取，并由规则层对明确事实进行纠偏。
- DeepSeek JSON 调用已关闭 thinking 并启用 `json_object` 输出，减少空 content 和格式不可解析问题。
- 已补充眼部症状到眼科的基础科室规则。
- 普通测试默认关闭真实 LLM，避免测试误打外部 API；真实 DeepSeek 冒烟需要单独运行。

## 1. 目标

本次重构把项目从“规则模板 + 少量 LLM 润色”的 demo，推进为真正可用的诊前导诊助手。

核心目标：

- 保留多 Agent，但让它成为内部专业分工，不把复杂度暴露给患者。
- 接入 DeepSeek OpenAI-compatible API，让模型参与症状结构化、追问、科室建议和报告生成。
- 前端体验以患者为中心，首屏能直接开始，不让用户先填一堆表。
- 安全边界必须可控，急症红旗、禁答规则和免责声明不依赖模型自由发挥。

## 2. 产品定位

本项目不是“AI 医生”，而是“诊前导诊与就医准备助手”。

它应该帮助患者回答四个问题：

1. 我现在是否有需要急诊或拨打 120 的危险信号？
2. 还缺哪些影响分诊判断的关键信息？
3. 更适合优先挂哪个科，备选科室是什么？
4. 去医院前要准备什么，怎么向医生说清楚？

系统不输出确定性诊断，不开药，不给剂量，不替代医生。

## 3. 多 Agent 方案

采用“一个 Supervisor + 五个专职 Agent”的 LangGraph 工作流。

```text
用户输入
  ↓
Supervisor
  ↓
Safety Agent
  ├─ 急症红旗命中 → 急诊建议 + 急诊摘要
  ↓
Symptom Intake Agent
  ↓
Supervisor 判断信息是否足够
  ├─ 不足 → Follow-up Agent → 等用户回答
  └─ 足够 → Department Agent → Report Agent
```

### 3.1 Supervisor

职责：

- 读取共享状态。
- 决定下一步进入哪个 Agent。
- 控制“安全优先、信息补全、结果生成”的顺序。
- 限制追问轮数，避免患者被反复盘问。

Supervisor 不直接生成医疗内容，只做路由。

### 3.2 Safety Agent

职责：

- 识别红旗症状。
- 判断是否需要急诊或 120。
- 拦截诊断、处方、剂量、停药等越界请求。

实现策略：

- 规则优先命中明确红旗。
- DeepSeek 可辅助解释边界情况，但不能降低规则识别到的风险。
- 急症链路不等待其他 Agent。

### 3.3 Symptom Intake Agent

职责：

- 将自然语言症状整理成结构化字段。
- 支持患者自然改口和补充。
- 输出已知事实、缺失信息和置信来源。

核心字段：

- `chief_complaint`
- `location`
- `duration`
- `severity`
- `accompanying_symptoms`
- `onset_and_trigger`
- `medical_history`
- `medications`
- `allergies`
- `special_population`
- `missing_fields`

DeepSeek 在这里必须输出 JSON，后端用 Pydantic 校验。

### 3.4 Follow-up Agent

职责：

- 基于缺失字段生成一个最关键追问。
- 一次只问一个问题。
- 如果患者已经补充或改口，不重复旧问题。

体验要求：

- 问题要短。
- 患者能直接回答。
- 不把所有缺失项一次性塞给患者。

### 3.5 Department Agent

职责：

- 根据结构化事实和风险等级推荐科室。
- 输出 1 个主推荐科室，最多 2 个备选科室。
- 给出推荐理由和就医路径。

边界：

- 可以说“更建议优先考虑耳鼻喉科/呼吸内科/急诊科”。
- 不可以说“你就是某某病”。
- 不可以承诺推荐一定正确。

### 3.6 Report Agent

职责：

- 生成患者版建议。
- 生成医生版摘要。
- 汇总准备清单、危险变化提醒和免责声明。

患者版要可执行，医生版要简洁结构化。

## 4. DeepSeek 接入

采用 DeepSeek 官方 OpenAI-compatible API。

推荐开发配置：

```env
LLM_PROVIDER=deepseek
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=replace-with-your-deepseek-api-key
LLM_MODEL=deepseek-v4-flash
ENABLE_LLM_TRIAGE=true
```

说明：

- `deepseek-v4-flash` 用于默认导诊链路，响应速度和成本更适合 MVP。
- 后续复杂推理或评测可切换 `deepseek-v4-pro`。
- 真实 API key 只写本地 `.env`，不写入 README、设计文档或提交记录。

## 5. 患者体验原则

### 5.1 少填表，先开始

首屏只保留：

- 这次哪里不舒服。
- 年龄。
- 性别。

城市、既往史、用药、过敏、孕产状态等信息按需追问或放进“补充信息”。

### 5.2 一次只问一个关键问题

患者不应该看到长问卷。系统每轮只问当前最影响分诊判断的一项。

### 5.3 调试信息默认不打扰患者

Agent Trace、LLM Trace、知识库命中等信息保留给开发调试，但默认折叠或仅开发模式展示。

### 5.4 输出像导诊建议，不像聊天废话

完成后优先展示：

- 风险等级和是否急诊。
- 推荐科室。
- 为什么推荐。
- 下一步怎么做。
- 去之前准备什么。
- 给医生看的摘要。

## 6. 安全与回退

所有 LLM 输出必须满足：

- JSON 可解析。
- Pydantic 校验通过。
- 不含诊断结论、处方、剂量或停药建议。
- 不覆盖规则层急症升级。

失败时回退：

- Safety Agent 回退规则风险判断。
- Symptom Intake Agent 回退已有规则抽取。
- Follow-up Agent 回退模板追问。
- Department Agent 回退规则科室映射。
- Report Agent 回退规则摘要。

## 7. 实施顺序

1. 先切换 DeepSeek 配置，保证本地 API key 能被当前链路使用。
2. 更新文档，把多 Agent 定位从“调试展示”改成“内部专业分工”。
3. 重构 LLM 调用，从“润色追问/摘要”升级为“结构化理解 + Agent JSON 输出”。
4. 改造前端，把主视图做成患者分诊台，调试信息退到开发区。
5. 增加红旗症状、结构化输出、追问、科室推荐和报告的测试集。

## 8. 验收标准

- 本地 `.env` 已能启用 DeepSeek。
- 文档明确当前阶段不优先接向量数据库，但保留知识增强扩展点。
- 后端至少具备 Supervisor + Safety/Symptom/Follow-up/Department/Report 的职责边界。
- 患者侧首屏操作简单，能快速开始导诊。
- 每轮追问不超过一个核心问题。
- 调试信息不干扰主流程。
- API key 不进入受版本控制的文件。

## 9. 结论

这个项目有必要做多 Agent，但必须做成“导诊专业分工”，不是为了展示 Agent 名词。

当前最重要的路线是：

```text
DeepSeek 接入
  → 多 Agent 职责重整
  → 患者分诊台体验
  → 本地规则库和安全评测
  → 后续再考虑向量知识库
```
