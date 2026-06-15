# Initial Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a documented initial framework for the Intelligent Diagnostic Assistant repository without implementing the full product.

**Architecture:** Use ScholarMind's repository organization as an engineering reference while adapting the domain to a LangGraph-based pre-consultation triage assistant. Keep backend behavior minimal and deterministic, with clear extension points for real LLM agents.

**Tech Stack:** FastAPI, Pydantic, LangGraph-ready service layout, Vue 3, Vite, Pinia, Vue Router, Docker Compose, OpenAI-compatible LLM configuration.

---

### Task 1: Documentation and Repository Skeleton

**Files:**
- Create: `README.md`
- Create: `docs/architecture.md`
- Create: `docs/api.md`
- Create: `docs/data-contracts.md`
- Create: `docs/safety.md`
- Create: `docs/deploy.md`
- Create: `docs/roadmap.md`
- Create: `.gitignore`
- Create: `docker-compose.yml`

- [x] Write Chinese README based on the user concept and ScholarMind style.
- [x] Define architecture, API, data contracts, safety boundary, deployment notes, and roadmap.
- [x] Keep scope limited to framework and documentation.

### Task 2: Backend Skeleton

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/app/routers/triage.py`
- Create: `backend/app/schemas/triage.py`
- Create: `backend/services/triage_graph/state.py`
- Create: `backend/services/triage_graph/graph.py`
- Create: `backend/services/safety_guardrails/service.py`
- Create: `backend/common/config.py`
- Create: `backend/common/logging.py`
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/Dockerfile`
- Create: `backend/tests/test_triage_api.py`

- [ ] Write tests first for health check and deterministic triage skeleton.
- [ ] Implement minimal code needed to pass tests.

### Task 3: Frontend Skeleton

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/src/main.ts`
- Create: `frontend/src/App.vue`
- Create: `frontend/src/style.css`
- Create: `frontend/src/api/index.ts`
- Create: `frontend/src/router/index.ts`
- Create: `frontend/src/views/Triage.vue`
- Create: `frontend/.env.example`

- [ ] Create Vue3 app skeleton and a triage page shell.
- [ ] Keep UI as a lightweight starting point, not a finished product.

### Task 4: Prompts and Verification

**Files:**
- Create: `prompts/safety_guardrail.md`
- Create: `prompts/symptom_analyzer.md`
- Create: `prompts/triage_recommender.md`
- Create: `prompts/guide_explainer.md`

- [ ] Add Chinese prompt templates with non-diagnostic boundaries.
- [ ] Run backend tests.
- [ ] Run Python compile check.
- [ ] Review git diff.
- [ ] Commit and push.
