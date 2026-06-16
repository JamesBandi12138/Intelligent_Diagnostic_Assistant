# LangGraph + Multi-Agent Triage Implementation Plan

日期：2026-06-16
项目：Intelligent Diagnostic Assistant
设计参考：`docs/superpowers/specs/2026-06-16-langgraph-multi-agent-triage-design.md`

## 目标

把当前手写导诊状态机重构为真正运行在 `LangGraph` 上的中心化多 Agent 编排流程，同时保持现有导诊 API 和前端主流程基本稳定，并补充可观察的调试字段。

## 任务 1：扩展后端契约与会话调试字段

文件：

- 更新 `backend/app/schemas/triage.py`
- 更新 `backend/services/session_store.py`
- 更新 `backend/app/routers/triage.py`

验收点：

- 为 session detail 增加调试字段：
  - `current_agent`
  - `node_trace`
  - `agent_trace`
  - `route_reason`
  - `knowledge_summary`
- 保持现有 `AnalyzeResponse` 对前端兼容
- 会话序列化和反序列化支持新增字段

## 任务 2：定义 LangGraph 共享状态与辅助契约

文件：

- 更新 `backend/services/triage_graph/state.py`
- 新建或更新 `backend/services/triage_graph/` 下辅助模块

验收点：

- 定义结构清晰的共享状态模型
- 把输入上下文、结构化事实、风险判断、编排控制、知识增强、调试信息纳入统一状态
- 状态字段与 `session_store` 可映射

## 任务 3：先写失败测试覆盖新编排行为

文件：

- 更新 `backend/tests/test_triage_api.py`
- 视需要新增 `backend/tests/test_triage_graph.py`

验收点：

- 先写出并跑出红灯，覆盖：
  - session detail 返回调试轨迹
  - 首轮信息不足时会经过 `supervisor`、`safety_agent`、`triage_agent`、`follow_up_agent`
  - 高风险场景走 `safety_agent -> result_agent`
  - `knowledge_agent` 在流程中有参与痕迹，即使当前返回空结果

## 任务 4：实现 LangGraph 多 Agent 图

文件：

- 更新 `backend/services/triage_graph/graph.py`
- 视需要新建：
  - `backend/services/triage_graph/agents.py`
  - `backend/services/triage_graph/helpers.py`

验收点：

- 用真正的 `StateGraph` 替换手写流程
- 节点至少包括：
  - `bootstrap_context`
  - `supervisor_route`
  - `safety_agent`
  - `triage_agent`
  - `knowledge_agent`
  - `follow_up_agent`
  - `result_agent`
  - `persist_state`
- 路由逻辑与设计文档一致
- 不破坏现有导诊行为

## 任务 5：接入 LLM 参与的混合决策

文件：

- 更新 `backend/common/clients/llm.py`
- 更新 `backend/services/triage_graph/` 相关实现

验收点：

- 规则仍然是主兜底
- LLM 参与：
  - 追问润色
  - 风险解释增强
  - 知识摘要增强
- 在 LLM 不可用时能优雅降级，不影响主流程

## 任务 6：保留接口的 Knowledge Agent

文件：

- 更新 `backend/services/knowledge_base/milvus_store.py`
- 更新 `backend/services/triage_graph/` 相关实现

验收点：

- `Knowledge Agent` 真实参与图编排
- 当前允许 Milvus 返回空结果
- session debug 信息里能看到知识节点参与和摘要结果

## 任务 7：前端按需展示调试信息

文件：

- 更新 `frontend/src/api/index.ts`
- 更新 `frontend/src/views/Triage.vue`

验收点：

- 不干扰现有导诊和报告主流程
- 在界面中增加轻量调试展示，至少可看到：
  - 当前 agent
  - 节点轨迹
  - 路由原因
  - 知识摘要

## 任务 8：全量验证与发布

文件：

- 更新 `docs/api.md`（如有必要）
- 更新 `开发日报/2026-06-16-开发日报.md`

验收点：

- 后端测试通过
- 前端测试通过
- 前端构建通过
- Docker 环境可真实访问
- 推送 GitHub
- 开发日报补充本次 LangGraph 重构内容

## 建议顺序

1. 先补 schema 与 session 调试字段
2. 写失败测试，确认红灯
3. 实现 LangGraph state 和节点图
4. 跑通后端测试
5. 接前端轻量调试展示
6. 做整链验证、提交和推送

## 完成定义

- 导诊流程真实运行在 `LangGraph` 上
- 至少形成 `Supervisor + Safety/Triage/Knowledge/FollowUp/Result` 的多 Agent 分工
- 外部 API 保持可用
- session detail 可以看到调试轨迹
- 自动化测试和真实运行验证全部通过
