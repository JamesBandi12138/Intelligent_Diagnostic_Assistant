# Intelligent Diagnostic Assistant（智能导诊与就医助手）

**诊前智能导诊与就医助手多 Agent 系统**：面向中国患者常见的“挂错科、反复跑医院、症状说不清、就医准备不足”等问题，基于 LangGraph Supervisor 多 Agent 工作流，为用户提供诊前症状梳理、科室推荐、就医路径建议、风险提示和就医报告生成。

> 本项目定位为“就医辅助与诊前分流”，不是诊断系统，不替代医生问诊、检查和治疗决策。出现急危重症信号时，应优先拨打 120 或前往急诊。

## 项目背景

在中国真实就医场景中，很多患者的第一道障碍不是治疗本身，而是“不知道该怎么开始看病”：

- 不知道应该挂哪个科，挂错科后需要重新排队、重新挂号。
- 老年人、外地患者、慢病患者对医院流程不熟悉，沟通成本高。
- 症状描述不完整，医生短时间内难以快速获得关键信息。
- 不清楚轻症是否适合线上问诊，或是否必须尽快线下就医。
- 不知道就诊前应准备哪些资料、检查报告、病史信息。

本项目希望把“症状描述 → 信息补全 → 风险识别 → 科室推荐 → 就医准备 → 报告生成”做成一个清晰、可控、可追踪的多 Agent 流程，帮助患者更高效地完成诊前准备，减少无效就医成本。

## 核心能力

- **症状结构化分析**：从自然语言症状描述中提取部位、持续时间、严重程度、伴随症状、既往史、用药史等信息。
- **信息不足追问**：当关键导诊信息缺失时，先追问用户，而不是强行给结论。
- **急诊风险提示**：识别胸痛、呼吸困难、意识障碍、卒中迹象、大出血、高热惊厥等红旗症状，优先提示急诊/120。
- **科室推荐**：给出主推荐科室、备选科室和推荐理由，降低挂错科概率。
- **就医路径建议**：结合症状紧急程度，建议线上问诊、门诊、急诊或专科就诊路径。
- **就诊准备清单**：提示需要携带的资料、既往检查、用药清单、医保/身份证件等。
- **导诊报告生成**：生成一份便于患者复制、打印或给医生查看的结构化就医摘要。
- **可观测与可调试**：预留 LangSmith/日志/会话记录能力，便于追踪 Agent 决策路径。

## 技术栈

本项目以用户需求文档中的技术栈为准，并参考 ScholarMind 的工程组织方式进行优化。

| 模块 | 技术 |
|---|---|
| 多 Agent 编排 | LangGraph Supervisor、StateGraph、conditional edges、checkpoint |
| LLM 接入 | 通义千问 / DeepSeek / 医疗领域模型，OpenAI-compatible API |
| 工具调用 | LangChain tools，Tavily 搜索，医院/科室信息检索 |
| 可选知识库 | 简单 RAG，面向常见症状、科室规则、就医指南 |
| 后端 | Python 3.11、FastAPI、Pydantic |
| 前端 | Vue 3、Vite、Pinia、Vue Router |
| 数据与基础设施 | MySQL、PostgreSQL、Redis、MinIO；Milvus 作为可选向量库 |
| 可观测 | LangSmith、结构化日志、导诊流程记录 |
| 部署 | Docker Compose，本地运行或合规私有化部署 |

## 架构设计

```text
┌────────────────────────────────────────────────────────────┐
│                    Vue 3 前端                               │
│  症状输入 · 信息补全 · 导诊结果 · 就医报告 · 历史记录        │
└───────────────────────────┬────────────────────────────────┘
                            │ HTTP / SSE
┌───────────────────────────▼────────────────────────────────┐
│                    FastAPI API 网关                          │
│  参数校验 · 会话管理 · 免责声明 · 访问日志 · 流式输出         │
└───────────────┬────────────────────────────────────────────┘
                │
┌───────────────▼────────────────────────────────────────────┐
│              LangGraph Supervisor 工作流                    │
│  安全边界检查 · 动态路由 · 信息不足追问 · 多 Agent 状态共享  │
└──┬──────────────┬────────────────┬────────────────┬───────┘
   │              │                │                │
┌──▼────────┐ ┌───▼──────────┐ ┌───▼────────────┐ ┌──▼────────────┐
│ Safety   │ │ Symptom       │ │ Triage         │ │ Guide &       │
│ Guardrail│ │ Analyzer      │ │ Recommender    │ │ Explainer     │
└──────────┘ └──────────────┘ └────────────────┘ └───────────────┘
   │              │                │                │
   └──────────────▼────────────────▼────────────────▼────────────┐
                     Report Generator / Memory / Logs             │
┌─────────────────────────────────────────────────────────────────▼┐
│ MySQL 业务数据 · PostgreSQL 对话记忆 · Redis checkpoint/cache     │
│ MinIO 报告附件 · Milvus/Tavily 可选知识与医院信息检索             │
└──────────────────────────────────────────────────────────────────┘
```

## Agent 分工

| Agent | 职责 | 输出 |
|---|---|---|
| Supervisor / Planner | 统一编排流程，判断是否需要追问、搜索、急诊提示或生成报告 | 下一步路由、任务状态 |
| Safety Guardrail Agent | 识别急危重症红旗信号和不应回答的医疗边界 | 风险等级、急诊建议、安全提示 |
| Symptom Analyzer Agent | 解析用户症状，提取结构化患者画像 | 症状 profile、缺失字段 |
| Triage Recommender Agent | 推荐科室、就医方式、检查准备方向 | 科室建议、线上/线下路径 |
| Guide & Explainer Agent | 用患者能理解的语言生成就医指导 | 准备清单、注意事项、解释 |
| Report Generator | 生成医生可快速阅读的导诊摘要 | 就医报告 |

## 推荐目录结构

```text
.
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── routers/
│   │   └── schemas/
│   ├── common/
│   │   ├── config.py
│   │   ├── logging.py
│   │   └── clients/
│   ├── services/
│   │   ├── triage_graph/
│   │   ├── symptom_analyzer/
│   │   ├── triage_recommender/
│   │   ├── guide_explainer/
│   │   ├── safety_guardrails/
│   │   └── report_generation/
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── router/
│   │   ├── stores/
│   │   └── views/
│   └── package.json
├── prompts/
├── docs/
└── docker-compose.yml
```

## API 草案

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 服务健康检查 |
| POST | `/api/triage/sessions` | 创建导诊会话 |
| POST | `/api/triage/analyze` | 提交症状并获取导诊建议 |
| GET | `/api/triage/sessions/{id}` | 获取导诊会话详情 |
| POST | `/api/reports` | 生成就医报告 |
| GET | `/api/reports/{id}` | 获取报告详情 |
| GET | `/api/logs/triage` | 查看导诊流程日志 |

## 快速开始

## 工具与模型准备

本项目当前只搭建框架，完整运行多 Agent 和知识增强能力时，需要按需准备以下工具。

| 工具 | 用途 | 获取方式 | 本项目使用方式 |
|---|---|---|---|
| Python 3.11+ | 后端 FastAPI、LangGraph 工作流 | [Python 官网](https://www.python.org/downloads/) 或 Conda | 推荐在项目根目录创建 `.venv` |
| Node.js 20+ | Vue3/Vite 前端开发 | [Node.js 官网](https://nodejs.org/) | `cd frontend && npm install && npm run dev` |
| Docker Desktop | 本地启动 MySQL、PostgreSQL、Redis、MinIO | [Docker 官网](https://www.docker.com/products/docker-desktop/) | `docker compose up -d --build` |
| MySQL 8 | 存储导诊会话、用户输入、推荐结果 | Docker Compose 自动拉取 `mysql:8.0` | 默认端口 `3308` |
| PostgreSQL 16 | 存储多轮对话记忆、LangGraph checkpoint | Docker Compose 自动拉取 `postgres:16-alpine` | 默认端口 `5433` |
| Redis 7 | 缓存、队列、临时状态、限流 | Docker Compose 自动拉取 `redis:7-alpine` | 默认端口 `6380` |
| MinIO | 存储报告 PDF、上传附件、检查报告图片 | Docker Compose 自动拉取 `minio/minio` | API `9002`，控制台 `9003` |
| Milvus | 可选向量库，用于常见症状/科室规则/指南 RAG | [Milvus Docker 文档](https://milvus.io/docs/install_standalone-docker.md) | 当前未默认启动，后续知识库阶段加入 |
| 通义千问 / DeepSeek | 中文 LLM 推理 | 阿里云百炼 DashScope / DeepSeek 开放平台 | 通过 OpenAI-compatible API 配置 |
| Embedding 模型 | 可选 RAG 向量化 | DashScope embedding API 或本地 `BAAI/bge-m3` | 知识库阶段启用 |
| Tavily | 医院、科室、医生公开信息检索 | [Tavily 官网](https://tavily.com/) | 设置 `TAVILY_API_KEY` 后启用 |
| LangSmith | LangGraph 流程追踪与调试 | [LangSmith 官网](https://smith.langchain.com/) | 设置 `LANGSMITH_TRACING=true` 后启用 |

### 推荐本地环境

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r backend\requirements.txt
```

### 模型配置建议

开发阶段建议先使用云端 OpenAI-compatible API，减少本地模型部署成本：

```env
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=你的 API Key
LLM_MODEL=qwen-plus
```

知识库阶段再启用 embedding 和 Milvus：

- 轻量方案：使用 DashScope / OpenAI-compatible embedding API。
- 本地方案：使用 `BAAI/bge-m3` 做中英文 embedding，Milvus 存储向量。
- 医疗场景建议：常见症状、科室规则、医院就医指南应经过人工审核后入库。

### 1. 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

访问：

- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

访问：

- 前端页面：http://localhost:5173

### 3. Docker Compose

```bash
copy backend\.env.example backend\.env
docker compose up -d --build
```

## 当前开发状态

当前版本是项目初始框架，重点是：

- 明确中国诊前导诊场景。
- 明确系统安全边界。
- 搭建 FastAPI + Vue3 + LangGraph 风格的目录骨架。
- 提供基础 API schema、示例路由、提示词模板和文档。

暂不包含：

- 完整医疗知识库。
- 真实医院/医生实时数据接入。
- 完整 LangGraph 生产级节点实现。
- 真实用户体系和权限隔离。
- 医疗器械或诊疗级合规认证。

## 安全与合规边界

本项目必须坚持以下边界：

- 只做导诊和就医准备辅助，不输出确定性诊断。
- 不提供处方、药物剂量、治疗方案或替代医生决策。
- 对急危重症信号优先提示急诊，而不是继续普通问答。
- 对儿童、孕妇、老人、慢病患者、术后患者等高风险人群提高谨慎程度。
- 所有建议需要保留不确定性表达，并鼓励线下就医确认。
- 生产部署前必须经过专业医生审核、数据合规评估和安全测试。

详见 [docs/safety.md](docs/safety.md)。

## 简历描述示例

- 基于 LangGraph 构建诊前智能导诊多 Agent 系统，采用 Supervisor 架构编排 Safety Guardrail、Symptom Analyzer、Triage Recommender、Guide Explainer 等 Agent，面向中国患者“挂错科、反复就医、就医准备不足”等真实痛点提供辅助分诊和就医路径建议。
- 设计 Human-in-the-Loop 信息补全机制与 conditional routing，根据症状风险等级动态路由至急诊提示、补充追问或科室推荐流程，提升医疗场景下多 Agent 输出的可控性和安全性。
- 参考生产级 RAG 项目工程结构，使用 FastAPI、Vue3、OpenAI-compatible LLM、Tavily 和可选 RAG 知识库搭建端到端导诊框架，并通过外置 prompts、结构化 schema 和日志记录提升可维护性。

## 文档

- [架构设计](docs/architecture.md)
- [API 约定](docs/api.md)
- [数据契约](docs/data-contracts.md)
- [安全边界](docs/safety.md)
- [部署说明](docs/deploy.md)
- [工具与模型使用说明](docs/tooling.md)
- [开发计划](docs/roadmap.md)
