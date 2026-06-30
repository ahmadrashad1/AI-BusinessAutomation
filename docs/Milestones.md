# Milestones
# AI Business Process Automation Platform

| Field | Value |
|-------|-------|
| Version | 1.0.0 |
| Date | 2026-06-30 |
| Reference | docs/DevelopmentPlan.md v1.0.0 |

All weeks are relative to project start (Week 1 = first sprint).

---

## Milestone Map

```
 Week  1 ──► M0  Dev Environment
 Week  2 ──► M1  Auth & Security
 Week  5 ──► M2  Organizations & RBAC
 Week  7 ──► M3  Workflow Builder (UI)
 Week  9 ──► M4  Execution Engine
 Week 12 ──► M5  AI Features
 Week 14 ──► M6  Platform Admin
 Week 17 ──► M7  Real-Time & Analytics
 Week 19 ──► M8  Beta Launch
 Week 22 ──► M9  General Availability
```

---

## M0 — Dev Environment
**Target:** End of Week 1 · Phase 1

### Delivers
- `docker-compose up` runs all services: Postgres (pgvector), Redis, MinIO, Celery worker, Flower, Nginx, Next.js dev server
- `pgvector`, `pg_trgm`, `uuid-ossp` extensions enabled via first Alembic revision
- GitHub Actions CI pipeline: lint (ruff, mypy, ESLint, tsc) + test jobs, coverage gate ≥ 80 %
- `.env.example` covers every required variable; onboarding takes < 30 min for a new engineer

### Exit Criteria
- [ ] `docker-compose up` reaches healthy state on a clean machine in < 2 min
- [ ] `pytest backend/tests/` passes (empty suite is fine at this point)
- [ ] CI pipeline runs on every push to `main`
- [ ] All engineers have a working local environment

### Blocked By
- Nothing (first milestone)

---

## M1 — Auth & Security
**Target:** End of Week 2 · Phase 1

### Delivers
- Full authentication API: register, verify email, login, token refresh, logout, forgot/reset password, Google OAuth
- JWT with two mutually exclusive scopes: `"org"` (customer users) and `"platform"` (AutoFlow staff)
- Refresh token rotation — old token invalidated on use (replay attack prevention)
- Rate limiting on `/auth/login`: 5 requests / 15 min
- Frontend: login, register, verify-email, reset-password pages + Zustand auth store + axios token interceptor

### Exit Criteria
- [ ] Register → verify email → login → receive access + refresh tokens — works end-to-end
- [ ] Expired JWT returns `401 TOKEN_EXPIRED`
- [ ] Tampered JWT returns `401 INVALID_TOKEN`
- [ ] Refresh token replay returns `401 REFRESH_TOKEN_REUSED`
- [ ] Login rate limit triggers on the 6th attempt
- [ ] Auth module test coverage ≥ 80 %

### Blocked By
- M0

---

## M2 — Organizations & RBAC
**Target:** End of Week 5 · Phase 2

### Delivers
- Organizations, members, departments, invitations, API keys — full CRUD
- `require_org_role()` dependency with rank hierarchy (owner=6 … viewer=1)
- Tenant isolation enforced in middleware: `organization_id` always from JWT, never from request body
- Cross-tenant resource lookup returns 404 (not 403)
- `bpa_sk_` API key authentication with scope-based access control
- Frontend: members page, invitations, settings, API keys page, `PermissionGate` component

### Exit Criteria
- [ ] Owner invites a member by email; member accepts and gets correct role
- [ ] Viewer cannot `POST /workflows` (returns `403 INSUFFICIENT_ROLE`)
- [ ] API key with `workflow:read` scope cannot call `POST /workflows`
- [ ] User in Org A cannot read any Org B resource (returns 404)
- [ ] Ownership transfer promotes new owner, demotes previous to `admin`
- [ ] Integration + tenant isolation tests pass; coverage ≥ 80 % on `organizations` module

### Blocked By
- M1

---

## M3 — Workflow Builder (UI)
**Target:** End of Week 7 · Phase 3 (front half)

### Delivers
- Visual workflow builder: React Flow canvas, node palette, node config panel, toolbar
- Workflow CRUD + DAG validation on publish (cycle detection, connected subgraph, trigger count)
- Node plugin system: `BaseNode` ABC, `NODE_REGISTRY`, `@register_node` decorator
- All non-AI node types implemented: manual, schedule, webhook, email triggers; http_request, send_email, condition, delay, db_write actions
- Workflow versioning: snapshot on publish, revert to previous version
- Frontend: builder page, workflow list, version history panel

### Exit Criteria
- [ ] Manager builds a workflow with a Manual trigger + HTTP Request action, publishes it
- [ ] Publishing a cyclic graph returns `422` with a node-level error message
- [ ] Publishing a valid graph creates a new `workflow_versions` snapshot
- [ ] Reverting to a previous version restores the graph
- [ ] Node registry rejects duplicate `node_type` registration
- [ ] `test_graph_validator.py` and `test_node_registry.py` pass

### Blocked By
- M2

---

## M4 — Execution Engine
**Target:** End of Week 9 · Phase 3 (back half)

### Delivers
- Async DAG executor: topological sort, parallel branch execution, output-as-input chaining
- `POST /executions` returns `202 Accepted` + `run_id`; Celery task does the work
- `WorkflowRun` and `NodeExecution` rows created per run
- `cancel_run` and `retry_from_node` operations
- Schedule-trigger sync to celery-redbeat
- Frontend: executions list, run detail page with node timeline and log lines

### Exit Criteria
- [ ] Triggering a workflow creates a `workflow_run` and `node_execution` rows for every node
- [ ] A failed node sets `run.status = failed`; subsequent nodes do not execute
- [ ] `retry_from_node` re-runs only from the failed node onward
- [ ] Schedule-triggered workflow fires at the configured cron time (verified in dev)
- [ ] `test_workflow_engine.py` and `test_execution_flow.py` pass

### Blocked By
- M3

---

## M5 — AI Features
**Target:** End of Week 12 · Phase 4

### Delivers
- Document upload (presigned PUT → MinIO), text extraction (PDF, DOCX, XLSX, scanned PDF via OCR), chunking, embedding, pgvector upsert
- RAG query endpoint: top-K HNSW cosine search scoped to `organization_id`
- AI node types: extraction, classification, summarization, prompt, RAG retrieval, multi-agent (LangGraph)
- `ModelProvider` protocol with OpenAI + Anthropic implementations; factory driven by env var
- Token usage logged to `ai_usage_stats` per call
- Frontend: documents page, knowledge-base RAG query UI, AI node config panels in builder

### Exit Criteria
- [ ] Uploaded PDF is searchable via `/ai/query` within 30 seconds
- [ ] RAG query never returns embeddings from another organization
- [ ] Extraction node correctly extracts named fields from JSON input in a workflow run
- [ ] RAG node passes retrieved context to a downstream Prompt node
- [ ] OCR fallback extracts text from a scanned-image PDF
- [ ] Token usage is recorded per call in `ai_usage_stats`
- [ ] AI module test coverage ≥ 80 %

### Blocked By
- M4 (AI nodes run inside the execution engine)

---

## M6 — Platform Admin
**Target:** End of Week 14 · Phase 5

### Delivers
- Separate `platform_users` table and `scope: "platform"` JWT — mutually exclusive from org scope
- `platform/` backend module: org suspension/reinstatement, support access grants (max 24 h TTL), support tickets, feature flags, immutable audit log
- `create_super_admin` CLI bootstrap (guarded by `COUNT(*) = 0`)
- Frontend: platform admin dashboard — org list, org detail, support tickets, system health, audit logs
- Feature flag evaluation endpoint used by frontend to gate unreleased features

### Exit Criteria
- [ ] CLI creates first super admin; running it twice is rejected
- [ ] Platform admin can suspend an org; suspended org's users receive `403 ORG_SUSPENDED`
- [ ] Support engineer without an active grant cannot read org detail (`403 SUPPORT_GRANT_REQUIRED`)
- [ ] Grant expires after 24 h; post-expiry access is denied
- [ ] All platform actions appear in audit log; `DELETE` on `platform_audit_logs` is blocked at DB level
- [ ] Org scope token cannot access any `/platform/*` endpoint

### Blocked By
- M2 (needs `organizations` table for suspension logic)

---

## M7 — Real-Time & Analytics
**Target:** End of Week 17 · Phase 6

### Delivers
- WebSocket endpoint (`/ws`) with Redis pub/sub: 8 server-push event types for execution and notification
- Live execution overlay on the builder canvas: node status updates within 500 ms
- Reconnection with exponential backoff (max 30 s); ping/pong keepalive
- In-app notification system: bell badge, notification feed, mark-read
- Email notifications via SendGrid: invitation, run failed, password reset
- Analytics dashboard: KPI tiles, execution time-series (Recharts), AI token breakdown
- Nightly celery-beat rollup task: `workflow_runs` → `daily_execution_stats`

### Exit Criteria
- [ ] Triggering a workflow shows node-by-node status on the canvas within 500 ms of each completion
- [ ] Dropping the WebSocket connection and reconnecting resumes live events transparently
- [ ] `notification.new` event increments bell badge without a page reload
- [ ] Invitation email delivered within 30 seconds
- [ ] Analytics dashboard loads in < 1 second (Redis cache hit)
- [ ] Nightly rollup produces counts matching raw `workflow_runs` rows

### Blocked By
- M4 (execution events source)
- M5 (AI usage stats)
- M6 (platform health stats optional but preferred)

---

## M8 — Beta Launch
**Target:** End of Week 19 · Phase 7 (weeks 1–2)

### Delivers
- Internal penetration test complete — zero high-severity findings
- HMAC-SHA256 webhook signature validation + 5-minute replay window
- Load test: 50 concurrent users, p95 API response < 200 ms
- Structured JSON logging; `/health` endpoint; Celery failure alerting
- Frontend Lighthouse score ≥ 90; bundle analysis complete
- Staged rollout to 5 beta customer organizations

### Exit Criteria
- [ ] Pen test report: no high-severity findings
- [ ] `k6` load test: p95 < 200 ms at 50 concurrent users
- [ ] `/health` endpoint returns DB + Redis + worker status
- [ ] 5xx error rate alert triggers correctly in staging
- [ ] 5 beta customers onboarded and active

### Blocked By
- M7 (all features must be complete before hardening)

---

## M9 — General Availability
**Target:** End of Week 22 · Phase 7 (weeks 3–5)

### Delivers
- All Phase 1–7 acceptance criteria passing against the production environment
- Automated daily DB backup with tested restore procedure (point-in-time recovery)
- Complete runbook: org suspension, support grant creation, feature flag rollout, incident response
- `API.md` published to developer docs site
- "Build your first workflow in 10 minutes" onboarding guide
- Production secrets rotated from development values; WAF enabled; TLS configured
- General availability announcement

### Exit Criteria
- [ ] All M0–M8 exit criteria pass on the production environment
- [ ] DB restore drill completed successfully
- [ ] Production `ENCRYPTION_KEY` and `JWT_SECRET_KEY` differ from dev/staging
- [ ] On-call runbook reviewed and signed off by ≥ 2 engineers
- [ ] Platform audit log `DELETE` permission revoked from `app_user` in production DB
- [ ] Zero open critical or high bugs in the issue tracker

### Blocked By
- M8

---

## Summary Table

| # | Milestone | Week | Phase | Key Deliverable |
|---|-----------|------|-------|-----------------|
| M0 | Dev Environment | 1 | 1 | Full stack runs locally; CI green |
| M1 | Auth & Security | 2 | 1 | Login, tokens, rate limiting |
| M2 | Organizations & RBAC | 5 | 2 | Multi-tenant orgs, invitations, API keys |
| M3 | Workflow Builder | 7 | 3 | Visual editor, node types, publish + versioning |
| M4 | Execution Engine | 9 | 3 | Async DAG runner, Celery tasks, retry |
| M5 | AI Features | 12 | 4 | RAG, document indexing, AI nodes |
| M6 | Platform Admin | 14 | 5 | Internal dashboard, support grants, audit log |
| M7 | Real-Time & Analytics | 17 | 6 | WebSocket feed, notifications, analytics |
| M8 | Beta Launch | 19 | 7 | Pen tested, load tested, 5 beta customers |
| M9 | General Availability | 22 | 7 | Production-ready, documented, launched |
