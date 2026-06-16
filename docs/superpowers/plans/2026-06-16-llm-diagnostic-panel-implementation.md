# LLM 运行状态 / 配置诊断面板实现计划

日期：2026-06-16
项目：Intelligent Diagnostic Assistant
设计参考：`docs/superpowers/specs/2026-06-16-llm-diagnostic-panel-design.md`

## 目标

新增一块独立的 LLM 运行状态 / 配置诊断面板，让前端可以清晰展示：

- 是否启用 LLM
- 当前 provider / model / base_url
- 最近一次调用是否生效
- 是否回退
- 当前错误分类和最近一次 trace

## 任务 1：补充会话详情诊断字段

文件：

- `backend/app/schemas/triage.py`
- `backend/app/routers/triage.py`

验收点：

- session detail 返回：
  - `llm_enabled`
  - `llm_provider`
  - `llm_model`
  - `llm_base_url`

## 任务 2：补充后端 API 测试

文件：

- `backend/tests/test_triage_api.py`

验收点：

- session detail 测试覆盖新配置字段
- 不影响现有 triage API 测试

## 任务 3：扩展前端 API 类型

文件：

- `frontend/src/api/index.ts`

验收点：

- `TriageSessionDetailResponse` 新增配置诊断字段

## 任务 4：实现前端诊断卡片

文件：

- `frontend/src/views/Triage.vue`
- `frontend/src/style.css`

验收点：

- 页面新增独立 LLM 诊断卡片
- 拆分展示：
  - 运行配置
  - 状态结论
  - 调试明细
- 增加状态文案和错误文案映射

## 任务 5：补充前端视图测试

文件：

- `frontend/src/views/Triage.spec.ts`

验收点：

- 覆盖“已回退到规则结果”
- 覆盖“LLM 已生效”

## 任务 6：整体验证与服务启动

执行：

- `pytest backend/tests -q`
- `npm --prefix frontend test -- --run`
- `npm --prefix frontend run build`
- 重启或重建容器
- 验证前端页面可访问

验收点：

- 自动化测试通过
- 构建通过
- 页面可访问
- 能在真实界面看到新的 LLM 诊断卡片
