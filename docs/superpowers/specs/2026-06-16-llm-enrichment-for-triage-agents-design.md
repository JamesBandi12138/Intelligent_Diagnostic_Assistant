# LLM Enrichment for Follow-Up and Result Agents

日期：2026-06-16
项目：Intelligent Diagnostic Assistant
状态：设计完成，待实现

## 1. 目标

在不破坏当前 `LangGraph + 多Agent` 导诊主链路稳定性的前提下，让 LLM 在以下两个节点中更明显参与：

- `follow_up_agent`
- `result_agent`

本次增强强调三件事：

- 用户能直接感知到文案更自然
- 调试面板能清楚看到 “规则底稿 vs LLM 润色稿”
- LLM 失败时能自动回退，不影响主流程

## 2. 范围

### 2.1 本次包含

- 让 `follow_up_agent` 使用 LLM 润色追问问题
- 让 `result_agent` 使用 LLM 润色结果摘要
- 在 session detail 中暴露 LLM 参与痕迹
- 在前端调试卡片中展示 raw/llm 对照与回退状态
- 为上述行为补充后端与前端测试

### 2.2 本次不包含

- 不让 LLM 改动风险等级
- 不让 LLM 改动推荐科室
- 不让 LLM 决定是否急诊
- 不让 LLM 决定缺失字段是什么
- 不让 LLM 主导 Supervisor 路由

## 3. 核心原则

### 3.1 规则决定内容，LLM 决定表达

这次增强只允许 LLM 做“表达增强”，不允许 LLM 改动核心医疗逻辑。

也就是说：

- 规则决定问什么
- LLM 决定怎么问得更自然
- 规则决定导诊结果结构
- LLM 决定怎么总结得更易懂

### 3.2 所有增强都必须可回退

只要 LLM 出现以下任一情况，就直接回退到规则稿：

- 超时
- 网络错误
- 鉴权失败
- 空返回
- 格式异常
- 返回内容偏离要求

### 3.3 所有增强都必须可观察

每次 LLM 参与都要留下结构化痕迹，便于前端展示和后端排查。

## 4. 方案选择

本次采用：

- 规则产出 raw 版本
- LLM 产出 llm 版本
- 主流程优先使用 llm 版本
- 失败时回退 raw 版本
- 调试区同时展示 raw 和 llm

不采用：

- 让 LLM 直接替代 follow-up 逻辑
- 让 LLM 直接生成最终完整导诊决策
- 让 LLM 自由改写风险或科室推荐

原因：

- 当前项目必须保持导诊稳定性
- 这套方式最容易讲清楚
- 用户和调试视角都能看到 LLM 的真实参与

## 5. Follow-Up Agent 设计

### 5.1 两阶段行为

#### 阶段一：规则产出原始追问

仍然按照当前逻辑：

- 根据 `missing_fields[0]` 确定本轮追问目标
- 生成稳定的 `raw_follow_up_question`

这个版本必须永远可用，不依赖 LLM。

#### 阶段二：LLM 润色追问

LLM 接收以下上下文：

- 当前缺失字段
- 已知事实摘要
- 规则版追问
- 语气要求

LLM 只负责把问题改写得更自然、更像真实导诊助理，但不能改变问题目标。

### 5.2 输出约束

LLM 输出必须满足：

- 一次只问一个问题
- 不得新增第二个并行问题
- 不得偏离当前缺失字段目标
- 不得加入诊断结论
- 尽量简短、可直接回答

### 5.3 最终输出

返回给前端的 `question` 取值规则：

- 优先使用 `llm_follow_up_question`
- 如果失败则使用 `raw_follow_up_question`

## 6. Result Agent 设计

### 6.1 两阶段行为

#### 阶段一：规则产出原始摘要

当前规则继续负责生成稳定的结果结构：

- `risk_level`
- `recommended_departments`
- `care_path`
- `preparation_checklist`
- `raw_report_summary`

#### 阶段二：LLM 润色摘要

LLM 接收以下上下文：

- 主诉
- 风险等级
- 推荐科室
- 就医路径
- 规则版摘要

LLM 只负责把 `report_summary` 改写得更自然、更像面向用户的导诊总结。

### 6.2 输出约束

LLM 输出必须满足：

- 不得修改风险等级
- 不得修改推荐科室
- 不得添加未出现的症状或病史
- 不得夸大紧急程度
- 语气自然、清晰、简洁

### 6.3 最终输出

返回给前端和报告生成链路的 `report_summary` 取值规则：

- 优先使用 `llm_report_summary`
- 如果失败则使用 `raw_report_summary`

## 7. 状态设计

为了避免状态爆炸，本次只新增一组 `llm_enrichment` 相关字段。

### 7.1 新增 graph/session 字段

- `raw_follow_up_question`
- `llm_follow_up_question`
- `raw_report_summary`
- `llm_report_summary`
- `llm_used`
- `llm_error`
- `llm_trace`

### 7.2 字段语义

- `raw_*`
  - 规则产出的原始稿
- `llm_*`
  - LLM 润色后的成稿
- `llm_used`
  - 本轮是否成功采用了 LLM 输出
- `llm_error`
  - 本轮 LLM 失败摘要
- `llm_trace`
  - 本轮 LLM 参与记录

## 8. Debug 结构设计

推荐 `llm_trace` 结构如下：

```json
[
  {
    "agent": "follow_up_agent",
    "task": "rewrite_follow_up_question",
    "used": true,
    "fallback": false,
    "error": null
  },
  {
    "agent": "result_agent",
    "task": "rewrite_report_summary",
    "used": true,
    "fallback": false,
    "error": null
  }
]
```

失败时示例：

```json
[
  {
    "agent": "follow_up_agent",
    "task": "rewrite_follow_up_question",
    "used": false,
    "fallback": true,
    "error": "timeout"
  }
]
```

## 9. 错误处理

### 9.1 错误分类

建议把 LLM 失败统一归入三类：

- `transport_error`
  - 网络、超时、鉴权
- `format_error`
  - 空返回、JSON 不合法、字段缺失
- `safety_reject`
  - 内容太长、多问题、偏离目标

### 9.2 统一回退策略

对于 `follow_up_agent`：

- 失败则回退 `raw_follow_up_question`

对于 `result_agent`：

- 失败则回退 `raw_report_summary`

### 9.3 主流程保证

无论 LLM 是否可用，以下必须保持稳定：

- risk level
- missing fields
- emergency stop
- recommended departments
- final completion route

## 10. 前端展示策略

### 10.1 用户主视图

用户只看到最终成品：

- 追问框显示润色后的问题
- 结果卡显示润色后的摘要

### 10.2 调试视图

在现有“编排调试”卡片中增加：

- `follow_up_rewrite`
  - `raw`
  - `llm`
- `summary_rewrite`
  - `raw`
  - `llm`
- `llm_used`
- `llm_error`
- `llm_trace`

这样能直接展示：

- 规则原稿
- LLM 成稿
- 是否回退
- 出错原因

## 11. 测试策略

### 11.1 后端测试

至少覆盖：

- `follow_up_agent` 成功使用 LLM 润色问题
- `follow_up_agent` LLM 失败时回退规则稿
- `result_agent` 成功使用 LLM 润色摘要
- `result_agent` LLM 失败时回退规则稿
- 急诊链路不受 LLM 失败影响
- session detail 能看到 `llm_trace`

### 11.2 前端测试

至少覆盖：

- 调试卡片显示 follow-up 的 raw/llm 对照
- 调试卡片显示 summary 的 raw/llm 对照
- LLM 失败时显示 fallback 信息

## 12. 验收标准

完成后应满足：

- `follow_up_agent` 的追问文案明显更自然
- `result_agent` 的摘要文案明显更自然
- 调试区能看到 raw/llm 对照
- LLM 失败时主流程仍可继续
- 后端测试、前端测试、构建、容器实跑全部通过

## 13. 最终结论

这次增强采用“规则底稿 + LLM 润色 + 调试对照 + 自动回退”的路线。

它的优点是：

- 变化明显
- 风险可控
- 解释清楚
- 非常适合当前项目继续演进
