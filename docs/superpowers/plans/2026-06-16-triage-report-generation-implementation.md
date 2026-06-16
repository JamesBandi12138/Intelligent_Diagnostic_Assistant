# Triage Report Generation Implementation Plan

> **Goal:** Implement a first practical report generation flow that creates one stable report per completed triage session, stores it as an independent resource, and lets the frontend generate and view it.

**Design Reference:** `docs/superpowers/specs/2026-06-16-triage-report-generation-design.md`

**Scope:** This plan covers report data models, report storage, report API endpoints, session-to-report linkage, frontend generation/view flow, and verification. It does not include PDF export, report editing, or report version history.

---

### Task 1: Add Report Schemas and API Contracts

**Files:**
- Create: `backend/app/schemas/report.py`
- Update: `backend/app/schemas/triage.py`
- Update: `docs/api.md`

- [ ] Define request and response models for `POST /api/reports`.
- [ ] Define the full report response model for `GET /api/reports/{report_id}`.
- [ ] Extend session detail response to include `report_id`.
- [ ] Keep the report structure split into `patient_snapshot`, `triage_summary`, `doctor_view`, `patient_view`, and `disclaimer`.

### Task 2: Add Report Storage and Generation Services

**Files:**
- Create: `backend/services/report_generation/__init__.py`
- Create: `backend/services/report_generation/store.py`
- Create: `backend/services/report_generation/generator.py`
- Update: `backend/services/session_store.py`

- [ ] Store reports independently from sessions.
- [ ] Add a session-to-report mapping lookup.
- [ ] Persist and read reports from Redis, with in-memory fallback for development.
- [ ] Extend session storage to retain `report_id` once a report is created.
- [ ] Generate one stable report per completed session.

### Task 3: Add Report API Endpoints

**Files:**
- Create: `backend/app/routers/reports.py`
- Update: `backend/app/main.py`

- [ ] Implement `POST /api/reports` with completed-session validation.
- [ ] Implement idempotent behavior for repeated report generation from the same session.
- [ ] Implement `GET /api/reports/{report_id}`.
- [ ] Return `404` for missing sessions or reports and `409` for incomplete sessions.

### Task 4: Add Backend Test Coverage First

**Files:**
- Create: `backend/tests/test_reports_api.py`
- Update existing tests only if session detail behavior changes

- [ ] Write a failing test for generating a report from a completed session.
- [ ] Write a failing test for rejecting report generation from an incomplete session.
- [ ] Write a failing test for reusing the same report on repeated generation.
- [ ] Write a failing test for retrieving a report by `report_id`.
- [ ] Write a failing test proving session detail exposes `report_id` after generation.

### Task 5: Add Frontend Report Generation and View Flow

**Files:**
- Update: `frontend/src/api/index.ts`
- Update: `frontend/src/views/Triage.vue`
- Update: `frontend/src/style.css`

- [ ] Add report API client methods.
- [ ] Show a “generate report” action only after triage completes.
- [ ] If the session already has `report_id`, show a “view report” path instead of forcing regeneration.
- [ ] Render report details with separate doctor and patient sections.
- [ ] Keep the report UI secondary to the triage result, not mixed into the chat timeline.

### Task 6: Verification and Runtime Checks

**Files:**
- Update: `docs/api.md`
- Update: user-facing docs only if behavior changed materially

- [ ] Run backend tests.
- [ ] Run frontend build.
- [ ] Rebuild and restart Docker services.
- [ ] Verify the web page loads.
- [ ] Verify one real flow: complete triage -> generate report -> read report -> refresh and restore report state.

---

## Suggested Execution Order

1. Write failing backend report tests.
2. Implement report schemas and storage.
3. Add report endpoints and session linkage.
4. Make backend tests green.
5. Add frontend generate/view report flow.
6. Rebuild Docker and run a real browser-facing validation.

## Definition of Done

- Reports can only be generated from completed sessions.
- The same session always maps to one stable report in the MVP.
- Reports are retrievable by `report_id`.
- Session detail includes `report_id` once present.
- Frontend can generate and display the report from a completed triage result.
- Backend tests and frontend build pass.
- The Docker-served web app and report flow are verified end-to-end.
