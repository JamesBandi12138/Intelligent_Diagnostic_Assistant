# LangGraph + Multi-Agent Triage Design

日期：2026-06-16
项目：Intelligent Diagnostic Assistant
状态：基础多 Agent 设计，已由患者体验与 DeepSeek 接入方案补充

> 说明：本文定义了 LangGraph 多 Agent 的基础形态。当前最新产品与模型接入方向见 `docs/superpowers/specs/2026-06-16-deepseek-multi-agent-patient-experience-design.md`，强调患者无感的内部多 Agent 分工、DeepSeek 结构化输出和简化操作体验。

## 1. 目标

把当前手写导诊状态机重构为真正的 `LangGraph` 工作流，并引入“中心化多 Agent 编排”。

本次重构强调三件事：

- 结构清晰，方便讲解
- 保持当前外部 API 基本稳定
- 能真实体现 `LangGraph + 多Agent`，而不是只改目录命名

## 2. 设计原则

### 2.1 简化优先

第一版不追求复杂的自治 Agent Network，而采用：

- 一个 `Supervisor`
- 若干职责单一的 Specialist Agent
- 一个共享状态
- 一个统一落盘节点

这样最容易维护、测试和展示。

### 2.2 稳定优先

导诊主流程仍然保留“规则兜底”：

- 安全判断优先走规则
- 缺失字段判断优先走规则
- LLM 参与边界判断、问题润色、知识摘要和结果表达

这保证系统既有“智能感”，又不会因为模型波动破坏核心导诊流程。

### 2.3 可观察优先

由于本次选择“中度升级”，设计必须支持调试可视化：

- 当前节点是谁
- 路由为什么这样走
- 哪些 Agent 参与了
- 知识库有没有参与

## 3. 方案选择

本次采用：

- `单 Supervisor + 多 Specialist Agent`

不采用：

- 多个自治 Agent 彼此自由协商
- 事件网络式分布式编排
- 过早引入复杂并行图

原因：

- 当前项目已有稳定 API 和前端页面
- 需要平滑升级，不适合大面积打散
- 演示和讲解时，中心化编排更直观

## 4. 总体架构

导诊图由以下节点组成：

1. `bootstrap_context`
2. `supervisor_route`
3. `safety_agent`
4. `triage_agent`
5. `knowledge_agent`
6. `follow_up_agent`
7. `result_agent`
8. `persist_state`

核心思想：

- `Supervisor` 只负责决定“下一步找谁做事”
- 每个 Agent 只负责一个清晰职责
- 所有 Agent 都读写同一个 `LangGraph state`
- 最后统一由 `persist_state` 写回 `session_store`

## 5. 状态模型

为了避免状态过多难以理解，第一版共享状态只保留六组信息。

### 5.1 输入上下文

作用：保存当前会话和用户输入。

字段：

- `session_id`
- `patient`
- `city`
- `symptom_text`
- `latest_answer`
- `conversation_messages`

说明：

- `symptom_text` 保存首轮主诉
- `latest_answer` 保存本轮追问回答
- `conversation_messages` 继续用于前端恢复和调试

### 5.2 结构化事实

作用：作为导诊推理的共同底座。

字段：

- `extracted_facts`
- `missing_fields`
- `fact_confidence`
- `special_context_flags`

第一版核心字段仍然是：

- `location`
- `duration`
- `severity`
- `accompanying_symptoms`
- `special_context`

### 5.3 风险判断

作用：给安全相关决策提供唯一可信出口。

字段：

- `risk_level`
- `risk_reasons`
- `emergency_advice`
- `safety_decision`

其中 `safety_decision` 固定为：

- `continue`
- `needs_clarification`
- `escalate_emergency`

### 5.4 编排控制

作用：记录工作流当前在哪一步，以及下一步怎么走。

字段：

- `workflow_status`
- `next_agent`
- `follow_up_question`
- `follow_up_rationale`
- `iteration_count`
- `completed`

`workflow_status` 第一版建议取值：

- `initialized`
- `safety_checked`
- `facts_updated`
- `knowledge_enriched`
- `awaiting_follow_up`
- `ready_to_complete`
- `completed`

### 5.5 知识增强

作用：为 `Knowledge Agent` 预留标准接口。

字段：

- `knowledge_hits`
- `knowledge_summary`
- `knowledge_used`

说明：

- 第一版允许真实进入图，但 Milvus 可以先返回空结果
- 重点是把知识节点和状态流跑通

### 5.6 结果与调试

作用：支撑前端展示、调试追踪和最终结果返回。

字段：

- `final_result`
- `agent_trace`
- `node_trace`
- `route_reason`
- `debug_snapshot`

说明：

- `agent_trace` 记录每个 Agent 做了什么
- `node_trace` 记录节点执行顺序
- `route_reason` 记录 Supervisor 的路由原因

## 6. 节点设计

### 6.1 `bootstrap_context`

职责：

- 读取或创建会话
- 合并本轮输入
- 写入用户消息
- 初始化 graph state

为什么保留这个节点：

- 让后续 Agent 不需要碰 HTTP 请求对象
- 所有 Agent 都只面对纯状态

### 6.2 `supervisor_route`

职责：

- 读取当前状态
- 决定下一跳 Agent
- 写入 `next_agent` 和 `route_reason`

第一版路由顺序：

1. 如果 `completed=True`，结束
2. 如果尚未完成安全检查，去 `safety_agent`
3. 如果安全升级，去 `result_agent`
4. 如果结构化事实尚未更新，去 `triage_agent`
5. 如果需要知识增强，去 `knowledge_agent`
6. 如果仍有缺失字段，去 `follow_up_agent`
7. 否则去 `result_agent`

说明：

- 多 Agent 的“编排感”主要由这个节点体现
- 但逻辑保持线性，方便讲解

### 6.3 `safety_agent`

职责：

- 做红旗症状识别
- 给出风险等级
- 必要时直接升级为急诊建议

策略：

- 规则结果优先
- LLM 只做解释增强和边界情况辅助

输出：

- `risk_level`
- `risk_reasons`
- `emergency_advice`
- `safety_decision`

### 6.4 `triage_agent`

职责：

- 提取结构化事实
- 识别缺失字段
- 判断信息是否足够进入完成态

策略：

- 规则抽取为主
- LLM 负责表达归一和弱补全

输出：

- `extracted_facts`
- `missing_fields`
- `fact_confidence`
- `workflow_status`

### 6.5 `knowledge_agent`

职责：

- 基于主诉和结构化事实构造检索查询
- 调用知识库接口
- 生成简短知识摘要

第一版策略：

- 节点真实存在
- Milvus 先保留空实现或 mock
- 重点是走通“编排链路”和调试信息

输出：

- `knowledge_hits`
- `knowledge_summary`
- `knowledge_used`

### 6.6 `follow_up_agent`

职责：

- 一次只生成一个追问问题
- 说明为什么问这个问题

策略：

- 问题目标由规则决定
- 问题表述由 LLM 润色

输出：

- `follow_up_question`
- `follow_up_rationale`
- `workflow_status=awaiting_follow_up`

### 6.7 `result_agent`

职责：

- 统一收口最终导诊结果
- 支持急诊完成和普通完成两条路径
- 为报告生成阶段提供稳定输入

输出：

- `final_result`
- `completed=True`
- `workflow_status=completed`

### 6.8 `persist_state`

职责：

- 把 graph 最终状态写回 `session_store`
- 更新当前问题、最新结果、调试快照

为什么单独保留：

- 避免每个 Agent 各自直接写 Redis
- 保证副作用集中，便于测试

## 7. 图结构

第一版图结构刻意保持简单：

1. `bootstrap_context`
2. `supervisor_route`
3. 条件跳转到某个 Agent
4. Agent 执行后回到 `supervisor_route`
5. `result_agent`
6. `persist_state`
7. 结束

也就是说：

- 一个中心调度点
- 一个共享状态
- 多个专职 Agent
- 一个统一落盘点

这套结构既是真正的 `LangGraph`，又不难讲。

## 8. Agent 输入输出契约

为了控制复杂度，所有 Agent 使用统一约定：

- 输入：完整 graph state
- 输出：只更新自己负责的状态片段
- 不直接负责 HTTP 返回
- 不直接负责 Redis 写入

这样可以保证：

- 节点职责清晰
- 状态变更容易追踪
- 单元测试更简单

## 9. Session 映射策略

为了平滑迁移，第一版不改现有外部会话接口，只扩展内部结构。

建议 `session_store` 增补以下可持久化字段：

- `workflow_status`
- `agent_trace`
- `node_trace`
- `route_reason`
- `knowledge_summary`
- `debug_snapshot`

原有字段继续保留：

- `status`
- `current_question`
- `latest_result`
- `report_id`
- `messages`

这样前端刷新恢复逻辑不需要推倒重来。

## 10. 对外接口策略

### 保持不变的部分

- `POST /api/triage/sessions`
- `POST /api/triage/analyze`
- `GET /api/triage/sessions/{session_id}`
- 报告接口

### 增强的部分

在 session detail 或调试字段中增加：

- `current_agent`
- `node_trace`
- `agent_trace`
- `route_reason`
- `knowledge_summary`

这样可以在不破坏前端主流程的情况下观察编排效果。

## 11. 复杂度控制

为了保证结构逻辑清晰，第一版明确做减法：

- 不做多个 Agent 并行执行
- 不做 Agent 之间自由消息协商
- 不做复杂的子图嵌套
- 不做流式事件图
- 不让 LLM 主导所有路由
- 不在第一版引入真实 Milvus 主流程依赖

## 12. 测试策略

第一版测试重点不是“模型有多聪明”，而是“图是否稳定推进”。

需要覆盖：

- 首轮高风险直接完成
- 首轮信息不足进入追问
- 追问回答后完成导诊
- 已完成会话拒绝继续回答
- `Supervisor` 路由符合预期
- `Knowledge Agent` 参与时状态不报错
- `persist_state` 能正确写回调试信息

## 13. 迁移路径

实施顺序建议：

1. 先定义新的 graph state
2. 再创建 `Supervisor` 和各 Agent 节点
3. 用 `LangGraph StateGraph` 替换现有手写 `run_triage()`
4. 扩展 session 持久化字段
5. 扩展 session detail 调试响应
6. 补齐测试
7. 前端按需展示调试信息

## 14. 验收标准

完成后应满足：

- 导诊主流程真实运行在 `LangGraph` 上
- 至少存在 `Supervisor + Safety/Triage/Knowledge/FollowUp/Result` 多 Agent 分工
- 原有导诊 API 继续可用
- 前端导诊与报告流程不回退
- 测试通过
- Docker 环境中可真实运行
- Session detail 可看到基本编排轨迹

## 15. 最终结论

本次重构采用“简单但真实”的路线：

- 用真正的 `LangGraph`
- 用中心化多 Agent 编排
- 保持主流程稳定
- 增加调试可观察性

这不是最炫的多 Agent 方案，但它最适合当前项目：

- 好实现
- 好验证
- 好讲解
- 好继续演进
