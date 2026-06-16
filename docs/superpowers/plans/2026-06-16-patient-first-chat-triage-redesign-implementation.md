# 患者可用型聊天导诊重构实现计划

日期：2026-06-16
项目：Intelligent Diagnostic Assistant
设计参考：`docs/superpowers/specs/2026-06-16-patient-first-chat-triage-redesign.md`

## 目标

将当前导诊页面与追问逻辑重构为“患者优先”的聊天式导诊体验，并支持自然改口后的重新判断。

## 任务 1：补失败测试覆盖自然改口与避免重复追问

文件：

- `backend/tests/test_triage_api.py`
- 视情况补充 `backend/tests/test_triage_llm.py`

验收点：

- 患者改口后，下一问不再机械重复旧问题
- 改口后的事实会影响当前追问方向

## 任务 2：重构后端追问逻辑

文件：

- `backend/services/triage_graph/graph.py`
- 视情况更新 `backend/services/triage_graph/state.py`
- 视情况更新 `backend/services/session_store.py`

验收点：

- 引入纠错识别
- 引入更灵活的追问优先级
- 降低重复追问概率

## 任务 3：重做前端聊天界面

文件：

- `frontend/src/views/Triage.vue`
- `frontend/src/style.css`
- `frontend/src/views/Triage.spec.ts`

验收点：

- 首屏只突出症状、年龄、性别
- 主界面以聊天为中心
- 调试信息收纳到次级区域
- 结果区改为患者可读的建议卡

## 任务 4：更新前端测试

文件：

- `frontend/src/views/Triage.spec.ts`

验收点：

- 能渲染新的聊天式首页
- 能渲染追问和结果卡片
- 调试区折叠后不干扰主流程

## 任务 5：整体验证与服务启动

执行：

- `pytest backend/tests -q`
- `npm --prefix frontend test -- --run`
- `npm --prefix frontend run build`
- `docker compose restart backend frontend`
- 实际访问页面验证

验收点：

- 自动化测试通过
- 构建通过
- 页面可访问
- 聊天体验明显优于旧版
