# 部署说明

## 本地开发

后端：

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

复制 `.env.example` 后，需要填写自己的 DeepSeek API Key：

```env
LLM_PROVIDER=deepseek
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=replace-with-your-deepseek-api-key
LLM_MODEL=deepseek-v4-flash
ENABLE_LLM_TRIAGE=true
```

真实 API Key 只放在本地 `backend/.env`，不要提交到仓库。

前端：

```bash
cd frontend
npm install
npm run dev
```

## Docker Compose

```bash
copy backend\.env.example backend\.env
docker compose up -d --build
```

默认端口：

| 服务 | 地址 |
|---|---|
| Backend | http://localhost:8000 |
| Frontend | http://localhost:5173 |
| MySQL | localhost:3308 |
| PostgreSQL | localhost:5433 |
| Redis | localhost:6380 |
| MinIO API | http://localhost:9002 |
| MinIO Console | http://localhost:9003 |

## 生产部署注意事项

- 必须关闭默认密码。
- 必须启用 HTTPS。
- LLM API Key 不得提交到仓库。
- 用户健康信息属于敏感数据，需要最小化采集、加密存储和访问审计。
- 上线前应由专业医生审核提示词、风险规则和输出格式。
