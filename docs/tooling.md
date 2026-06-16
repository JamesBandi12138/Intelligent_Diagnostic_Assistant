# 工具、数据库与模型使用说明

本文档列出项目后续开发会用到的主要工具，以及推荐的下载和使用方式。当前仓库是框架阶段，不要求一次性启动全部组件。

## 必需工具

### Python

- 建议版本：Python 3.11 或 3.12。
- 用途：FastAPI 后端、LangGraph 工作流、测试。
- 安装方式：https://www.python.org/downloads/

```bash
python --version
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r backend\requirements.txt
```

### Node.js

- 建议版本：Node.js 20+。
- 用途：Vue3 + Vite 前端。
- 安装方式：https://nodejs.org/

```bash
cd frontend
npm install
npm run dev
```

### Docker Desktop

- 用途：本地启动数据库、缓存和对象存储。
- 安装方式：https://www.docker.com/products/docker-desktop/

```bash
docker compose up -d --build
docker compose ps
```

## 数据库与基础设施

### MySQL

- 用途：导诊会话、患者基础信息、导诊结果、报告元数据。
- Docker 镜像：`mysql:8.0`
- 本项目端口：`3308:3306`

### PostgreSQL

- 用途：对话记忆、LangGraph checkpoint、长期多轮状态。
- Docker 镜像：`postgres:16-alpine`
- 本项目端口：`5433:5432`

### Redis

- 用途：缓存、队列、限流、临时状态。
- Docker 镜像：`redis:7-alpine`
- 本项目端口：`6380:6379`

### MinIO

- 用途：报告 PDF、上传附件、检查报告图片。
- Docker 镜像：`minio/minio`
- 本项目端口：
  - API：`9002`
  - 控制台：`9003`

### Milvus

- 用途：可选 RAG 向量库，用于常见症状知识库、科室规则、就医指南。
- 官方文档：https://milvus.io/docs/install_standalone-docker.md
- 当前状态：未默认加入 `docker-compose.yml`，避免框架阶段过重。

后续启用建议：

```yaml
milvus:
  image: milvusdb/milvus:v2.5.0
  command: ["milvus", "run", "standalone"]
```

## LLM 与 Embedding

### 中文 LLM

推荐优先使用云端 OpenAI-compatible API：

- DeepSeek：当前默认接入，适合中文推理、结构化输出和导诊解释。
- 通义千问：可作为备选中文对话模型。
- 医疗领域模型：需要额外评估安全性和合规性。

`.env` 示例：

```env
LLM_PROVIDER=deepseek
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=replace-with-your-deepseek-api-key
LLM_MODEL=deepseek-v4-flash
ENABLE_LLM_TRIAGE=true
```

真实 API key 只放在本地 `backend/.env`，不要写入 README、设计文档或提交记录。

### Embedding 模型

知识库阶段可选：

- 云端 embedding API：部署简单。
- 本地 `BAAI/bge-m3`：中英文效果均衡，适合症状规则和指南检索。

注意：医疗知识库内容必须经过人工审核，不建议直接把网络抓取内容无审核入库。

## 搜索与可观测

### Tavily

- 用途：检索医院、科室、医生公开信息。
- 官网：https://tavily.com/
- 配置：

```env
ENABLE_TAVILY_SEARCH=true
TAVILY_API_KEY=replace-with-your-tavily-key
```

### LangSmith

- 用途：追踪 LangGraph 节点、调试 Agent 决策路径。
- 官网：https://smith.langchain.com/
- 配置：

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=replace-with-your-langsmith-key
```

## 推荐启用顺序

1. 只启动后端和前端，验证 API/页面框架。
2. 启动 MySQL、PostgreSQL、Redis、MinIO，补会话和报告存储。
3. 接入 DeepSeek LLM，替换仅靠规则模板的导诊输出。
4. 接入 Tavily，补医院/科室公开信息检索。
5. 接入 Milvus + embedding，建设人工审核后的知识库。
