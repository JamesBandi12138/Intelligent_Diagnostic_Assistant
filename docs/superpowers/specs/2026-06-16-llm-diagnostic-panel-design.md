# LLM 运行状态 / 配置诊断面板设计

日期：2026-06-16
项目：Intelligent Diagnostic Assistant
状态：设计完成，待实现

## 1. 目标

在现有导诊页面中新增一个独立的“LLM 运行状态 / 配置诊断面板”，让开发调试时能一眼看出：

- 当前导诊链路是否启用了 LLM
- 当前使用的是哪个 provider / model
- 最近一次 LLM 调用是否真正生效
- 是否发生了 fallback
- 如果失败，失败属于哪一类

本次设计强调“开发调试可读性”，而不是面向普通用户的简化展示。

## 2. 范围

### 2.1 本次包含

- 在会话详情接口中补充最小运行配置字段
- 在前端新增独立 LLM 诊断卡片
- 对现有 `llm_used`、`llm_error`、`llm_trace` 做更直观映射
- 在测试中覆盖“启用但回退”和“启用且成功”两种典型状态

### 2.2 本次不包含

- 不新增独立诊断接口
- 不暴露 API Key 或任何敏感信息
- 不做复杂的折叠面板、日志下载或历史快照
- 不改变现有 LangGraph 节点编排逻辑

## 3. 设计原则

### 3.1 与编排调试分离

现有“编排调试”主要回答：

- 走了哪些节点
- 当前 agent 是谁
- route reason 是什么

新的 LLM 诊断卡片主要回答：

- LLM 有没有启用
- 启用了以后有没有实际生效
- 为什么没生效
- 最近一次 LLM 调用落在哪个 agent / task

两块信息要互补，而不是混在一起。

### 3.2 只展示最小必要配置

后端只向前端暴露以下非敏感配置：

- `llm_enabled`
- `llm_provider`
- `llm_model`
- `llm_base_url`

不返回：

- `llm_api_key`
- 任何鉴权头或密钥片段

### 3.3 状态优先，明细其次

卡片顶部先展示“状态结论”，例如：

- LLM 已生效
- 已回退到规则结果
- LLM 未启用
- 本轮未调用 LLM

再在下面给出 provider / model / error / trace 等明细。

## 4. 方案比较

### 方案 A：继续塞进现有编排调试块

优点：

- 改动最小

缺点：

- 编排信息和模型运行信息混杂
- 可读性会继续下降

### 方案 B：独立卡片展示（推荐）

优点：

- 结构清晰
- 演示和排障都更自然
- 后续接入更多 provider 时也容易扩展

缺点：

- 前端需要增加一块展示区域

### 方案 C：折叠式高级诊断抽屉

优点：

- 主界面更干净

缺点：

- 当前开发阶段不利于频繁排障
- 信息被藏起来，不适合演示

最终选择：方案 B。

## 5. 后端设计

### 5.1 会话详情扩展字段

在 `TriageSessionDetailResponse` 中新增：

- `llm_enabled: bool`
- `llm_provider: str | None`
- `llm_model: str | None`
- `llm_base_url: str | None`

这些字段不需要持久化到 session store，因为它们属于“当前服务运行配置”，不是会话业务状态。

### 5.2 数据来源

这些字段直接来自后端运行配置：

- `settings.ENABLE_LLM_TRIAGE`
- `settings.LLM_PROVIDER`
- `settings.LLM_MODEL`
- `settings.LLM_BASE_URL`

这样能保证诊断面板反映的是“当前服务真实运行配置”，而不是历史快照。

## 6. 前端设计

### 6.1 卡片结构

新增独立卡片标题：

- `LLM 运行状态 / 配置诊断`

卡片分为三组内容。

#### 第一组：运行配置

- `enabled`
- `provider`
- `model`
- `base_url`
- `current_agent`

#### 第二组：状态结论

- `status_label`
- `llm_used`
- `fallback`
- `llm_error`
- `last_agent`
- `last_task`

#### 第三组：调试明细

- `raw_follow_up_question`
- `llm_follow_up_question`
- `raw_report_summary`
- `llm_report_summary`
- `llm_trace`

### 6.2 状态映射

前端通过现有字段组合出更直观的状态：

- `llm_enabled=false`
  - 显示：`LLM 未启用`
- `llm_enabled=true` 且 `llm_used=true`
  - 显示：`LLM 已生效`
- `llm_enabled=true` 且最近一次 trace 的 `fallback=true`
  - 显示：`已回退到规则结果`
- `llm_enabled=true` 且 `llm_used=false` 且没有 error / trace
  - 显示：`本轮未调用 LLM`

### 6.3 错误文案映射

- `transport_error`
  - `供应商 / 网络 / 鉴权 / 额度异常`
- `format_error`
  - `模型输出格式不可解析`
- `safety_reject`
  - `模型输出未通过安全约束`

保留原始错误码，同时给出中文解释。

## 7. 测试策略

### 7.1 后端

新增或补充测试验证：

- session detail 返回 `llm_enabled`
- session detail 返回 `llm_provider`
- session detail 返回 `llm_model`
- session detail 返回 `llm_base_url`

### 7.2 前端

至少覆盖两种典型场景：

- `enabled=true + llm_used=false + llm_error=transport_error`
  - 页面显示“已回退到规则结果”
- `enabled=true + llm_used=true`
  - 页面显示“LLM 已生效”

## 8. 验收标准

完成后应满足：

- 页面中存在独立 LLM 诊断卡片
- 能清楚看出 `enabled / provider / model / fallback / provider error`
- 不暴露敏感配置
- 原有编排调试卡片继续可用
- 前端测试、后端测试、前端构建通过
- 启动服务后，真实页面可访问并能展示诊断卡片

## 9. 结论

本次采用“独立 LLM 诊断卡片 + 最小运行配置暴露 + 状态映射”的方案。

这样既不会把 LangGraph 编排信息搅乱，也能把“启用、命中、回退、供应商异常”讲清楚，非常适合当前项目继续开发和演示。
