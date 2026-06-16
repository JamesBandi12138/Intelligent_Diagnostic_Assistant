# Follow-Up Triage Implementation Plan

> **Goal:** Implement the first practical version of multi-turn triage follow-up so the system can ask one question at a time, stop early on high risk, and return a structured triage result when core fields are complete.

**Design Reference:** `docs/superpowers/specs/2026-06-16-follow-up-triage-design.md`

**Scope:** This plan covers backend state flow, session persistence, API response contracts, frontend chat-style interaction, and verification for the multi-turn follow-up MVP. It does not include SSE, user accounts, WeChat Mini Program support, or full knowledge-base integration.

---

### Task 1: Expand Backend Contracts

**Files:**
- Update: `backend/app/schemas/triage.py`
- Update: `backend/app/routers/triage.py`
- Update: `docs/api.md`

- [ ] Add explicit response variants for `needs_follow_up` and `completed`.
- [ ] Add request semantics for initial symptom submission versus follow-up answer submission.
- [ ] Ensure the session detail response can expose current status, current question, and current result snapshot.
- [ ] Keep router responses stable and easy for the frontend to branch on without guessing.

### Task 2: Extend Session State and Persistence

**Files:**
- Update: `backend/services/session_store.py`
- Update: `backend/services/triage_graph/state.py`
- Update: `backend/common/config.py` if needed

- [ ] Expand session state to store symptom text, extracted facts, answered follow-ups, pending question, missing fields, risk level, status, and final result.
- [ ] Preserve Redis as the primary store with in-memory fallback only for development.
- [ ] Ensure completed sessions reject new answers cleanly.
- [ ] Ensure session reads are sufficient for frontend refresh and state recovery.

### Task 3: Implement Multi-Turn Triage State Machine

**Files:**
- Update: `backend/services/triage_graph/graph.py`
- Update: `backend/services/safety_guardrails/service.py`
- Create or Update: follow-up generation logic under `backend/services/`

- [ ] Refactor the triage flow into four states: `collecting`, `risk_escalated`, `ready_to_complete`, `completed`.
- [ ] Run risk checks on the initial symptom text and again after follow-up answers are merged.
- [ ] Track the minimum completion fields: symptom location, duration, severity, accompanying symptoms, and special population/history context.
- [ ] Generate exactly one follow-up question at a time from the highest-priority missing field.
- [ ] Compose a final result when risk escalates or completion fields are satisfied.

### Task 4: Strengthen Backend Test Coverage

**Files:**
- Update: `backend/tests/test_triage_api.py`
- Update: `backend/tests/test_triage_risk.py`
- Update: `backend/tests/test_triage_llm.py` if applicable
- Create additional targeted tests as needed

- [ ] Add a test where the first request returns `needs_follow_up`.
- [ ] Add a test where a follow-up answer completes the triage flow.
- [ ] Add a test where a high-risk symptom bypasses follow-up and returns `completed`.
- [ ] Add a test where a completed session rejects further answers.
- [ ] Add a test that verifies session state persistence across requests.

### Task 5: Convert Frontend to Chat-Style Follow-Up UI

**Files:**
- Update: `frontend/src/views/Triage.vue`
- Update: `frontend/src/api/index.ts`
- Update: `frontend/src/style.css`
- Update: router or state files only if needed

- [ ] Represent the triage flow as a chat-style message timeline.
- [ ] Submit the initial symptom description and render the system's next question when follow-up is needed.
- [ ] Submit one answer at a time and continue until the backend returns `completed`.
- [ ] Render high-risk advice with stronger visual emphasis.
- [ ] Render the final structured result separately from the message timeline.

### Task 6: Add Frontend Recovery and Guardrails

**Files:**
- Update: `frontend/src/views/Triage.vue`
- Update: `frontend/src/api/index.ts`

- [ ] Restore current session state from `GET /api/triage/sessions/{session_id}` on refresh when a session exists.
- [ ] Prevent duplicate submissions while a request is in flight.
- [ ] Keep user input intact on request failure and show a clear retry message.
- [ ] Lock or reset the input once a session is complete.

### Task 7: Documentation and Manual Verification

**Files:**
- Update: `docs/api.md`
- Update: `README.md` if user-facing behavior changes materially

- [ ] Update API examples to show a follow-up flow.
- [ ] Verify backend tests pass.
- [ ] Verify frontend build passes.
- [ ] Verify Docker-based local run still works after the changes.
- [ ] Manually validate one low-risk multi-turn scenario and one high-risk immediate-stop scenario.

---

## Suggested Execution Order

1. Finish backend schema and session state.
2. Implement the triage state machine and follow-up generation.
3. Add backend tests until the flow is stable.
4. Update the frontend for chat-style follow-up rendering.
5. Add refresh recovery and error handling.
6. Run end-to-end verification in Docker.

## Definition of Done

- A first symptom submission can return either `needs_follow_up` or `completed`.
- A follow-up answer can advance the same session toward completion.
- High-risk cases stop immediately and return urgent guidance.
- Low-risk incomplete cases continue one question at a time.
- Completed sessions return structured triage advice and reject further answers.
- Frontend clearly displays the follow-up conversation and final result.
- Backend tests and frontend build both pass.
