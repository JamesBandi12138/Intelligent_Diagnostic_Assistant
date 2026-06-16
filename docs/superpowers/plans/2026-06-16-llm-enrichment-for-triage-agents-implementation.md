# LLM Enrichment for Follow-Up and Result Agents Implementation Plan

日期：2026-06-16
项目：Intelligent Diagnostic Assistant
设计参考：`docs/superpowers/specs/2026-06-16-llm-enrichment-for-triage-agents-design.md`

## 目标

在保持当前 LangGraph 多 Agent 导诊链路稳定的前提下，让 LLM 在 `follow_up_agent` 和 `result_agent` 中更明显参与文案润色与摘要生成，并把参与痕迹完整暴露到调试字段和前端调试卡片中。

## 任务 1：扩展 graph state 与 session debug 字段

文件：

- 更新 `backend/services/triage_graph/state.py`
- 更新 `backend/services/session_store.py`
- 更新 `backend/app/schemas/triage.py`
- 更新 `backend/app/routers/triage.py`

验收点：

- 新增以下字段并可持久化：
  - `raw_follow_up_question`
  - `llm_follow_up_question`
  - `raw_report_summary`
  - `llm_report_summary`
  - `llm_used`
  - `llm_error`
  - `llm_trace`
- session detail 可返回这些调试字段

## 任务 2：补后端红灯测试覆盖 LLM 润色与回退

文件：

- 更新 `backend/tests/test_triage_llm.py`
- 视需要更新 `backend/tests/test_triage_api.py`

验收点：

- 先写并跑出失败测试，覆盖：
  - follow-up 追问被 LLM 润色
  - follow-up 在 LLM 失败时回退
  - result summary 被 LLM 润色
  - result summary 在 LLM 失败时回退
  - session detail 返回 `llm_trace`

## 任务 3：实现 follow_up_agent 的 LLM 润色链路

文件：

- 更新 `backend/services/triage_graph/graph.py`
- 视需要拆分辅助函数到 `backend/services/triage_graph/`

验收点：

- 规则版追问先生成 `raw_follow_up_question`
- LLM 成功时生成 `llm_follow_up_question`
- 返回给用户的 `question` 优先使用 LLM 版
- 出错时自动回退到规则版
- `llm_trace` 正确记录

## 任务 4：实现 result_agent 的 LLM 摘要润色链路

文件：

- 更新 `backend/services/triage_graph/graph.py`

验收点：

- 规则版摘要先生成 `raw_report_summary`
- LLM 成功时生成 `llm_report_summary`
- 最终 `report_summary` 优先使用 LLM 版
- 出错时自动回退到规则版
- 不允许 LLM 改动风险和推荐科室结构

## 任务 5：统一 LLM 错误分类与回退记录

文件：

- 更新 `backend/services/triage_graph/graph.py`
- 视需要更新 `backend/common/clients/llm.py`

验收点：

- 统一记录：
  - `transport_error`
  - `format_error`
  - `safety_reject`
- `llm_error` 和 `llm_trace` 对应清晰
- LLM 异常不影响导诊主流程继续运行

## 任务 6：前端展示 raw/llm 对照与回退信息

文件：

- 更新 `frontend/src/api/index.ts`
- 更新 `frontend/src/views/Triage.vue`
- 更新 `frontend/src/style.css`
- 更新 `frontend/src/views/Triage.spec.ts`

验收点：

- 调试卡片新增：
  - follow-up raw/llm 对照
  - summary raw/llm 对照
  - `llm_used`
  - `llm_error`
  - `llm_trace`
- 不影响当前主导诊和报告展示

## 任务 7：全量验证与文档更新

文件：

- 更新 `docs/api.md`
- 更新 `开发日报/2026-06-16-开发日报.md`

验收点：

- 后端测试通过
- 前端测试通过
- 前端构建通过
- Docker 容器重建后真实运行通过
- 实际请求能返回新的 LLM 调试字段

## 建议顺序

1. 先补状态字段和 session detail 契约
2. 写失败测试
3. 实现 follow-up LLM 润色
4. 实现 result summary LLM 润色
5. 接前端调试展示
6. 做整链验证

## 完成定义

- 用户可见追问文案和摘要文案变得更自然
- 调试面板可见 raw/llm 对照
- LLM 失败时自动回退
- 主导诊链路稳定
- 自动化测试与真实运行验证通过
