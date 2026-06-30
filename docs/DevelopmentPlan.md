# Development Plan
# AI Business Process Automation Platform

| Field | Value |
|-------|-------|
| Version | 1.0.0 |
| Status | Active |
| Date | 2026-06-30 |
| Author | Engineering Team |
| References | docs/architecture/ARCHITECTURE.md v1.0.0 · docs/database/DatabaseDesign.md v1.1.0 · docs/api/API.md v1.0.0 |

---

## Table of Contents

1. [Overview](#1-overview)
2. [Guiding Principles](#2-guiding-principles)
3. [Team Structure](#3-team-structure)
4. [Phase Overview](#4-phase-overview)
5. [Phase 1 — Foundation](#5-phase-1--foundation)
6. [Phase 2 — Core Platform](#6-phase-2--core-platform)
7. [Phase 3 — Workflow Engine & Node System](#7-phase-3--workflow-engine--node-system)
8. [Phase 4 — AI Features](#8-phase-4--ai-features)
9. [Phase 5 — Platform Admin](#9-phase-5--platform-admin)
10. [Phase 6 — Analytics, Notifications & Real-Time](#10-phase-6--analytics-notifications--real-time)
11. [Phase 7 — Production Hardening](#11-phase-7--production-hardening)
12. [Milestone Summary](#12-milestone-summary)
13. [Dependency Graph](#13-dependency-graph)
14. [Definition of Done](#14-definition-of-done)
15. [Risk Register](#15-risk-register)

---

## 1. Overview

This plan breaks the full platform into seven sequential phases. Each phase delivers a vertical slice of working, tested functionality. No phase begins until the previous phase's acceptance criteria are met.

**Target state after all phases:** A production-ready, multi-tenant SaaS platform where customer organizations build and run AI-powered business workflows, and the AutoFlow operations team manages the platform through a separate admin dashboard.

**Estimated total duration:** 22 weeks (5.5 months) for a team of 4–5 engineers.

---

## 2. Guiding Principles

1. **Vertical slices first.** Each sprint delivers end-to-end working functionality, not just backend or just frontend.
2. **No feature without a test.** Every public API endpoint has an integration test. Every service function has a unit test. Coverage floor: 80 %.
3. **Security is never a phase-2 concern.** JWT validation, tenant isolation, and RBAC are implemented in Phase 1 and enforced in every subsequent phase.
4. **API contract first.** Frontend development starts only after the backend endpoint is tested and documented. `API.md` is the source of truth.
5. **Celery for all async work.** No `fastapi.BackgroundTasks` for business logic. All long-running operations are Celery tasks.
6. **Feature flags gate unfinished features.** Incomplete or experimental features are hidden behind the `feature_flags` table rather than commented out.

---

## 3. Team Structure

| Role | Count | Primary Responsibility |
|------|-------|----------------------|
| Backend Engineer | 2 | FastAPI modules, Celery tasks, DB migrations |
| Frontend Engineer | 1–2 | Next.js pages, components, stores, query hooks |
| AI/ML Engineer | 1 | AI providers, RAG pipeline, LangGraph agents |
| DevOps (part-time) | 0.5 | Docker, CI/CD, nginx, environment parity |

Phases 1–2 are backend-heavy. Frontend engineers join at full capacity from Phase 3 onward. The AI/ML engineer joins at Phase 4.

---

## 4. Phase Overview

| Phase | Name | Duration | Milestone |
|-------|------|----------|-----------|
| 1 | Foundation | 2 weeks | Dev environment + Auth API green |
| 2 | Core Platform | 3 weeks | Orgs, members, invitations, API keys working |
| 3 | Workflow Engine & Node System | 4 weeks | Workflows built, published, and executed end-to-end |
| 4 | AI Features | 3 weeks | RAG query + 3 AI node types functioning |
| 5 | Platform Admin | 2 weeks | Platform dashboard + support grants live |
| 6 | Analytics, Notifications & Real-Time | 3 weeks | Live execution feed + dashboard analytics |
| 7 | Production Hardening | 5 weeks | Load-tested, monitored, pen-tested, documented |

---

## 5. Phase 1 — Foundation

**Duration:** 2 weeks  
**Goal:** Every engineer can run the full stack locally. Auth works end-to-end. CI passes.

### 5.1 Infrastructure Setup

| Task | Owner | Notes |
|------|-------|-------|
| Finalize `docker-compose.yml` with all services (Postgres/pgvector, Redis, MinIO, Celery, Flower, Nginx) | DevOps | Use `pgvector/pgvector:pg16` image |
| Write `.env.example` and populate local `.env` | DevOps | All engineers copy and fill in |
| Configure GitHub Actions CI: lint (ruff, mypy, ESLint, tsc) + test (pytest, jest) | DevOps | Fail on coverage < 80 % |
| Enable pgvector, pg_trgm, uuid-ossp extensions in init migration | Backend | One-time Alembic revision |
| Configure Alembic `env.py` — async engine, all model imports | Backend | See DatabaseDesign.md §13.2 |

### 5.2 Backend Core Layer

| Task | Owner | Notes |
|------|-------|-------|
| `core/config.py` — pydantic-settings, all env vars typed | Backend | Fail fast on missing vars at startup |
| `core/database.py` — async SQLAlchemy engine, `get_db` dependency, Base | Backend | |
| `core/redis.py` — connection pool, helper for pub/sub | Backend | |
| `core/security.py` — JWT encode/decode (HS256), bcrypt hash/verify, Fernet encrypt/decrypt | Backend | Two scopes: `"org"` and `"platform"` |
| `core/exceptions.py` — `AppError` base, HTTP exception handlers, standard error envelope | Backend | `{error: {code, message, request_id, details}}` |
| `core/middleware.py` — request ID injection, tenant context from JWT, audit log writer | Backend | `organization_id` never from request body |
| `core/rate_limit.py` — sliding window counter in Redis | Backend | |
| `core/storage.py` — presigned GET (15 min) and PUT (5 min) URL helpers for MinIO/S3 | Backend | |

### 5.3 Auth Module

| Task | Owner | Notes |
|------|-------|-------|
| Migration: `users`, `refresh_tokens`, `email_verifications` tables | Backend | See DatabaseDesign.md §3 |
| `auth/models.py` — SQLAlchemy models | Backend | |
| `auth/schemas.py` — Pydantic v2 request/response schemas | Backend | |
| `auth/service.py` — register, login, refresh, logout, verify-email, forgot/reset-password | Backend | Refresh token rotation on every use |
| `auth/router.py` — 10 endpoints as per API.md §5 | Backend | |
| `auth/dependencies.py` — `get_current_user`, `require_verified_email` | Backend | |
| Google OAuth callback route | Backend | `app/api/auth/callback/route.ts` (Next.js) |

### 5.4 Auth Tests

| Task | Owner |
|------|-------|
| `tests/unit/test_auth_service.py` — register, login, token rotation, password reset flow | Backend |
| `tests/integration/test_auth_api.py` — all 10 auth endpoints, happy path + error cases | Backend |
| `tests/integration/test_security.py` — expired JWT, tampered JWT, refresh replay attack, rate limit on `/auth/login` | Backend |

### 5.5 Frontend Auth Shell

| Task | Owner | Notes |
|------|-------|-------|
| Next.js project bootstrap (`npm create next-app`, Tailwind, shadcn/ui init) | Frontend | |
| `lib/api/client.ts` — axios instance, token interceptor, 401 → refresh → retry | Frontend | |
| `lib/stores/auth.store.ts` — Zustand: user, accessToken, org context | Frontend | |
| `(auth)/login/page.tsx` and `(auth)/register/page.tsx` | Frontend | |
| `(auth)/verify-email/page.tsx` and `(auth)/reset-password/page.tsx` | Frontend | |

### 5.6 Phase 1 Acceptance Criteria

- [ ] `docker-compose up` brings the full stack up in under 2 minutes on a clean machine
- [ ] A user can register, verify email, log in, receive tokens, and log out via Postman
- [ ] Refresh token replay attack returns `401 REFRESH_TOKEN_REUSED`
- [ ] Tampered JWT returns `401 INVALID_TOKEN`
- [ ] Login rate limit triggers after 5 requests in 15 minutes
- [ ] CI pipeline passes (lint + unit + integration tests, ≥ 80 % coverage on auth module)

---

## 6. Phase 2 — Core Platform

**Duration:** 3 weeks  
**Goal:** Organizations exist, members can be invited and managed, API keys work, and role-based access is enforced.

### 6.1 Organizations Module

| Task | Owner | Notes |
|------|-------|-------|
| Migration: `organizations`, `org_members`, `departments`, `org_invitations`, `api_keys` | Backend | See DatabaseDesign.md §2–§4 |
| `organizations/models.py` | Backend | |
| `organizations/service.py` — CRUD org, invite flow (email → accept link), role change, ownership transfer, deactivate | Backend | |
| `organizations/router.py` — 15 endpoints as per API.md §6 | Backend | |
| `require_org_role()` dependency with rank hierarchy (owner=6 … viewer=1) | Backend | See ARCHITECTURE.md §10.5 |
| Tenant isolation enforcement: `organization_id` from JWT context, never from body | Backend | Middleware sets `request.state.org_id` |
| API key authentication path: `bpa_sk_` prefix, bcrypt hash compare, scope check | Backend | Separate dependency `get_api_key_user` |

### 6.2 Tenant Isolation Tests

| Task | Owner |
|------|-------|
| `tests/integration/test_tenant_isolation.py` — user from Org A cannot read, write, or delete Org B resources; cross-org resource access returns 404 (not 403) | Backend |
| `tests/integration/test_rbac.py` — viewer cannot create; manager cannot delete org; owner can transfer ownership | Backend |
| `tests/e2e/test_invitation_flow.py` — full invite → accept → assign role → remove member cycle | Backend |

### 6.3 Frontend Organizations

| Task | Owner | Notes |
|------|-------|-------|
| `lib/api/organizations.ts` — typed fetch functions for all 15 endpoints | Frontend | |
| `lib/query/useOrganizations.ts` — TanStack Query hooks | Frontend | |
| `(dashboard)/settings/members/page.tsx` — member list, invite modal, role dropdown | Frontend | |
| `(dashboard)/settings/organization/page.tsx` — org profile, danger zone | Frontend | |
| `(dashboard)/settings/departments/page.tsx` | Frontend | |
| `(dashboard)/settings/api-keys/page.tsx` — create, list (prefix only), revoke | Frontend | |
| `shared/PermissionGate.tsx` — renders children only when user has required role rank | Frontend | |
| `shared/OrgSwitcher.tsx` — for users who belong to multiple orgs | Frontend | |

### 6.4 Phase 2 Acceptance Criteria

- [ ] Owner creates an org, invites a member by email, member accepts invitation
- [ ] Member role changes are reflected immediately on next API request
- [ ] A Viewer cannot `POST /workflows` (returns `403 INSUFFICIENT_ROLE`)
- [ ] An API key with `workflow:read` scope cannot call `POST /workflows`
- [ ] Cross-org resource lookup returns 404 — not 403
- [ ] Ownership transfer changes owner, demotes previous owner to `admin`

---

## 7. Phase 3 — Workflow Engine & Node System

**Duration:** 4 weeks  
**Goal:** Users can build workflows visually, publish them, trigger executions, and see real-time status.

### 7.1 Workflow Module

| Task | Owner | Notes |
|------|-------|-------|
| Migration: `workflows`, `workflow_versions` | Backend | See DatabaseDesign.md §5 |
| `workflows/models.py` and `workflows/schemas.py` | Backend | |
| `workflows/validator.py` — DAG validation: no cycles, trigger count, connected subgraph, required node fields | Backend | Called at publish time; returns structured error list |
| `workflows/service.py` — CRUD, publish (validate → snapshot version → set active_version_id), duplicate, revert | Backend | |
| `workflows/router.py` — 10 endpoints per API.md §7 | Backend | |

### 7.2 Node Plugin System

| Task | Owner | Notes |
|------|-------|-------|
| `workflows/nodes/base.py` — `BaseNode` ABC: `node_type`, `input_schema`, `output_schema`, `execute(context) → dict` | Backend | |
| `workflows/nodes/registry.py` — `NODE_REGISTRY: dict[str, type[BaseNode]]`, `@register_node` decorator | Backend | |
| Trigger nodes: `manual`, `schedule`, `webhook`, `email` | Backend | `schedule` stores cron string; `webhook` returns trigger URL |
| Action nodes: `http_request`, `send_email`, `condition`, `delay`, `db_write` | Backend | `condition` branches on JSONPath expression |

### 7.3 Execution Engine

| Task | Owner | Notes |
|------|-------|-------|
| Migration: `workflow_runs`, `node_executions` | Backend | See DatabaseDesign.md §6 |
| `execution/engine.py` — async DAG walker: topological sort → execute nodes in parallel where no dependency, pass `output` forward as `input` | Backend | |
| `execution/service.py` — `trigger_run`, `cancel_run`, `retry_from_node` | Backend | `trigger_run` creates `WorkflowRun` row + dispatches `execute_workflow` Celery task |
| `execution/router.py` — 6 endpoints per API.md §8 | Backend | `POST /executions` returns `202 Accepted` with `run_id` |
| `worker/tasks/workflow_execution.py` — `execute_workflow(run_id)` Celery task | Backend | Updates `node_executions` rows; publishes status events to Redis |
| `execution/scheduler.py` — syncs schedule-trigger workflows to celery-redbeat | Backend | Called on workflow publish/unpublish |

### 7.4 Execution Tests

| Task | Owner |
|------|-------|
| `tests/unit/test_graph_validator.py` — cyclic graph, disconnected node, zero triggers, missing required fields | Backend |
| `tests/unit/test_workflow_engine.py` — linear chain, parallel branches, condition branch routing, failed node stops run | Backend |
| `tests/unit/test_node_registry.py` — register, lookup, duplicate registration raises error | Backend |
| `tests/integration/test_workflow_api.py` — CRUD, publish with invalid graph returns 422 with node-level errors | Backend |
| `tests/integration/test_execution_flow.py` — trigger → poll status → assert all node_executions rows created | Backend |
| `tests/e2e/test_workflow_flow.py` — full cycle: create → publish → trigger → poll until `completed` | Backend |

### 7.5 Frontend Workflow Builder

| Task | Owner | Notes |
|------|-------|-------|
| Install `@xyflow/react` (React Flow v12) | Frontend | Canvas library |
| `lib/stores/builder.store.ts` — Zustand: nodes, edges, selection, dirty flag, undo/redo stack | Frontend | |
| `workflow-builder/Canvas.tsx` — React Flow canvas with minimap, controls, snap-to-grid | Frontend | |
| `workflow-builder/NodePalette.tsx` — draggable node types from `NODE_REGISTRY` list endpoint | Frontend | |
| `workflow-builder/NodeConfigPanel.tsx` — right-side panel; renders schema-driven form for selected node | Frontend | |
| `workflow-builder/nodes/` — custom React Flow node components for each category | Frontend | |
| `(dashboard)/workflows/[id]/builder/page.tsx` — loads graph, auto-saves draft, publish button triggers validation | Frontend | |
| `(dashboard)/executions/[runId]/page.tsx` — run detail with node timeline, log lines | Frontend | |
| `lib/api/workflows.ts`, `lib/api/executions.ts`, hooks | Frontend | |

### 7.6 Phase 3 Acceptance Criteria

- [ ] A Manager can create a workflow, add a Manual trigger + HTTP Request action, publish, and trigger a run
- [ ] The execution engine walks all nodes; `node_executions` rows are created for each
- [ ] A failed HTTP Request node sets the run to `failed`; `retry_from_node` re-runs from that node only
- [ ] A cyclic graph is rejected at publish with a descriptive error listing the cycle
- [ ] Schedule-triggered workflow fires at the configured cron time (verify with a 1-minute cron in dev)
- [ ] Workflow version is snapshotted on publish; reverting to a previous version works

---

## 8. Phase 4 — AI Features

**Duration:** 3 weeks  
**Goal:** AI node types function in workflows. Users can upload documents, index them, and run RAG queries.

### 8.1 Files & Document Module

| Task | Owner | Notes |
|------|-------|-------|
| Migration: `documents`, `document_embeddings` (pgvector) | Backend | HNSW index, cosine similarity |
| `files/service.py` — upload-url (presigned PUT), register (metadata row), re-index (enqueue Celery task) | Backend | |
| `files/router.py` — 7 endpoints per API.md §9 | Backend | |
| `worker/tasks/ai_processing.py` — `index_document(doc_id)` task: extract text (PDF→PyMuPDF, DOCX→python-docx, XLSX→openpyxl), chunk, embed, upsert into `document_embeddings` | AI/ML | |
| OCR fallback: `ai/ocr.py` — pytesseract for scanned PDFs | AI/ML | |

### 8.2 AI Provider Layer

| Task | Owner | Notes |
|------|-------|-------|
| `ai/providers/base.py` — `ModelProvider` protocol: `complete(messages) → str`, `embed(text) → list[float]` | AI/ML | |
| `ai/providers/openai.py` and `ai/providers/anthropic.py` | AI/ML | |
| `ai/providers/factory.py` — returns provider instance from `LLM_PROVIDER` env var | AI/ML | |
| `ai/usage.py` — logs token counts to `ai_usage_stats` table per call | AI/ML | |

### 8.3 RAG Pipeline

| Task | Owner | Notes |
|------|-------|-------|
| `ai/rag/retriever.py` — top-K HNSW cosine search scoped to `organization_id` | AI/ML | Never cross-org embedding search |
| `ai/rag/indexer.py` — chunking strategy (512-token chunks, 50-token overlap) | AI/ML | |
| `ai/router.py` — `POST /ai/query` (RAG) and `POST /ai/generate-workflow` | AI/ML | |

### 8.4 AI Node Types

| Task | Owner | Notes |
|------|-------|-------|
| `workflows/nodes/ai/extraction.py` — LLM-powered data extraction from node input | AI/ML | |
| `workflows/nodes/ai/classification.py` — classify text into user-defined categories | AI/ML | |
| `workflows/nodes/ai/summarization.py` | AI/ML | |
| `workflows/nodes/ai/prompt.py` — arbitrary LLM prompt with template variables from prior nodes | AI/ML | |
| `workflows/nodes/ai/rag.py` — RAG retrieval node: query knowledge base, inject context into next node | AI/ML | |
| `workflows/nodes/ai/multi_agent.py` — LangGraph subgraph; runs multi-step agent with tool calls | AI/ML | |
| `ai/chains/` — reusable LangChain expression language chains backing the node types | AI/ML | |

### 8.5 AI Tests

| Task | Owner |
|------|-------|
| `tests/unit/test_ai_chains.py` — mock provider responses, assert extraction schema, classification labels | AI/ML |
| Integration test: upload → index (wait for Celery task) → `POST /ai/query` → assert relevant chunk returned | AI/ML |
| Tenant isolation: RAG query must not return embeddings from a different org | AI/ML |

### 8.6 Frontend AI & Documents

| Task | Owner | Notes |
|------|-------|-------|
| `(dashboard)/documents/page.tsx` — file list, upload button (direct-to-MinIO via presigned PUT URL) | Frontend | |
| `(dashboard)/knowledge-base/page.tsx` — RAG query UI, source citations | Frontend | |
| `lib/api/documents.ts` and `lib/api/ai.ts` | Frontend | |
| AI node config panels in the workflow builder | Frontend | Schema-driven; each AI node exposes prompt template, model picker |

### 8.7 Phase 4 Acceptance Criteria

- [ ] A PDF uploaded via presigned PUT is chunked, embedded, and searchable via `/ai/query` within 30 seconds
- [ ] RAG query never returns results from another organization's documents
- [ ] An Extraction node in a workflow correctly extracts named fields from a JSON input
- [ ] A RAG node passes retrieved context to the next LLM Prompt node
- [ ] Token usage is recorded per call in `ai_usage_stats`
- [ ] OCR fallback correctly extracts text from a scanned-image PDF

---

## 9. Phase 5 — Platform Admin

**Duration:** 2 weeks  
**Goal:** AutoFlow team has a fully functional internal dashboard, separate from the customer dashboard.

### 9.1 Platform Module

| Task | Owner | Notes |
|------|-------|-------|
| Migration: `platform_users`, `support_access_grants`, `support_tickets`, `feature_flags`, `platform_audit_logs` | Backend | See DatabaseDesign.md §8.4–§8.8 |
| `platform/models.py` | Backend | |
| `platform/dependencies.py` — `get_platform_user`, `require_platform_role(*roles)` | Backend | Decodes `scope: "platform"` JWT claim |
| `platform/service.py` — `suspend_org`, `reinstate_org`, `grant_support_access` (max 24h TTL), `revoke_grant`, create/update ticket, toggle feature flag | Backend | |
| `platform/router.py` — 13 endpoints per API.md §14, all under `/platform/*` | Backend | |
| `platform/cli.py` — `create_super_admin` CLI bootstrap (guards with `COUNT(*) = 0`) | Backend | Run once; see DatabaseDesign.md §17.1a |
| All platform actions write to `platform_audit_logs` (immutable — no UPDATE/DELETE) | Backend | |

### 9.2 Support Access Grant Enforcement

| Task | Owner | Notes |
|------|-------|-------|
| `require_support_grant` dependency — checks `support_access_grants` for active, non-expired, non-revoked row | Backend | Used on: `GET /platform/organizations/{org_id}` and member endpoints |
| Test: support engineer without grant cannot read org detail (403 SUPPORT_GRANT_REQUIRED) | Backend | |
| Test: support engineer with expired grant cannot read org detail | Backend | |
| Test: grant created by `platform_admin`, accessed by `support_engineer` — success | Backend | |

### 9.3 Frontend Platform Dashboard

| Task | Owner | Notes |
|------|-------|-------|
| `lib/api/platform.ts` — typed wrappers for all 13 platform endpoints | Frontend | |
| `(platform-admin)/layout.tsx` — platform-scope JWT guard; org users redirected to `/dashboard` | Frontend | |
| `(platform-admin)/page.tsx` — KPI tiles: active orgs, total runs today, queue depth, error rate | Frontend | |
| `(platform-admin)/organizations/page.tsx` — searchable org table with status badges | Frontend | |
| `(platform-admin)/organizations/[orgId]/page.tsx` — org detail, member list (requires active support grant), suspend/reinstate buttons | Frontend | |
| `(platform-admin)/support/page.tsx` — ticket queue, status/priority filters, assignment | Frontend | |
| `(platform-admin)/system/page.tsx` — Postgres pool, Redis memory, Celery queue depths | Frontend | |
| `(platform-admin)/system/logs/page.tsx` — platform audit log, filterable by action and org | Frontend | |
| `components/platform/` — `OrgSummaryCard`, `SystemHealthPanel`, `SupportTicketRow`, `FeatureFlagToggle` | Frontend | |

### 9.4 Phase 5 Acceptance Criteria

- [ ] `python -m app.modules.platform.cli create_super_admin` creates the first platform user; running it twice is rejected
- [ ] Super admin can log in at `/login` (shared auth endpoint, `scope: "platform"` in JWT)
- [ ] Platform admin can view the org list and suspend/reinstate an org
- [ ] Suspended org's users receive `403 ORG_SUSPENDED` on all API calls
- [ ] Support engineer cannot access org detail without an active grant from a platform admin
- [ ] Grant expires after 24 hours; re-accessing after expiry returns `403 SUPPORT_GRANT_REQUIRED`
- [ ] All platform actions appear in audit log; audit log rows cannot be deleted via API

---

## 10. Phase 6 — Analytics, Notifications & Real-Time

**Duration:** 3 weeks  
**Goal:** Users see execution analytics, receive in-app and email notifications, and watch live execution progress over WebSocket.

### 10.1 Analytics Module

| Task | Owner | Notes |
|------|-------|-------|
| Migration: `daily_execution_stats`, `ai_usage_stats` | Backend | See DatabaseDesign.md §8 |
| `worker/tasks/scheduled.py` — nightly `rollup_daily_stats` Celery Beat task: aggregate `workflow_runs` → `daily_execution_stats` | Backend | |
| `analytics/service.py` and `analytics/router.py` — 3 endpoints per API.md §13 | Backend | Dashboard stats, time-series executions, AI usage breakdown |
| Redis cache for dashboard query (5-minute TTL) | Backend | |

### 10.2 Notifications Module

| Task | Owner | Notes |
|------|-------|-------|
| Migration: `notifications`, `notification_preferences` | Backend | |
| `notifications/service.py` — create notification, mark read, mark all read | Backend | |
| `notifications/email.py` — SendGrid transactional email helper (invitation, run failed, password reset) | Backend | |
| `notifications/router.py` — 5 endpoints per API.md §12 | Backend | |
| `worker/tasks/notifications.py` — async email dispatch Celery task | Backend | |

### 10.3 WebSocket Real-Time Feed

| Task | Owner | Notes |
|------|-------|-------|
| `notifications/websocket.py` — WS endpoint at `/ws?token={access_token}`, subscribes to Redis channel `ws:org:{org_id}` | Backend | |
| Execution engine publishes `run.started`, `node.started`, `node.completed`, `node.failed`, `run.completed`, `run.failed`, `run.cancelled` events to Redis | Backend | See API.md §16 |
| `lib/hooks/useWebSocket.ts` — connection manager with exponential backoff reconnect (max 30 s), ping/pong keepalive | Frontend | |
| `execution/LiveExecutionOverlay.tsx` — overlays live node status directly on the builder canvas | Frontend | Green pulse → completed, red → failed |
| `notifications/NotificationBell.tsx` and `NotificationFeed.tsx` — unread count badge, drop-down list | Frontend | Receives `notification.new` WS events |

### 10.4 Frontend Analytics

| Task | Owner | Notes |
|------|-------|-------|
| `(dashboard)/analytics/page.tsx` — KPI tiles, execution time series chart (Recharts), AI token usage breakdown | Frontend | |
| `lib/query/useAnalytics.ts` | Frontend | |

### 10.5 Phase 6 Acceptance Criteria

- [ ] A user triggering a workflow sees node-by-node status updates on the canvas within 500 ms of each node completing
- [ ] WebSocket connection drops are transparently reconnected; in-progress run resumes streaming on reconnect
- [ ] `notification.new` event triggers bell badge increment without a page reload
- [ ] Daily stat rollup produces correct counts (verified against raw `workflow_runs` rows)
- [ ] Analytics dashboard loads in under 1 second (Redis cache hit)
- [ ] Invitation email is delivered within 30 seconds of sending the invite

---

## 11. Phase 7 — Production Hardening

**Duration:** 5 weeks  
**Goal:** Platform is safe, observable, and performant at launch-scale. All launch blockers resolved.

### 11.1 Security Hardening (Week 1)

| Task | Owner | Notes |
|------|-------|-------|
| Internal penetration test: JWT attacks, IDOR, tenant escape, API key brute force | Backend | Use OWASP ZAP + manual |
| HMAC-SHA256 webhook signature validation + 5-minute timestamp replay window | Backend | See API.md §15 |
| Secrets rotation: Fernet key rotation procedure documented and tested | Backend | |
| AES-256/Fernet encryption verified for all `integrations.credentials` rows | Backend | |
| Content-Security-Policy, X-Frame-Options, Referrer-Policy headers on all responses | Backend/DevOps | |
| Dependency vulnerability scan (`pip-audit`, `npm audit`) — zero high-severity findings | DevOps | |
| Secrets never logged: verify middleware strips Authorization headers from access logs | Backend | |

### 11.2 Performance & Load Testing (Week 2)

| Task | Owner | Notes |
|------|-------|-------|
| Baseline load test: 50 concurrent users, each triggering 1 workflow per minute — p95 API response < 200 ms | Backend | Use k6 or Locust |
| Celery worker autoscaling policy documented (concurrency, prefetch multiplier) | DevOps | |
| pgvector HNSW index tuning: `ef_construction`, `m` parameters benchmarked | AI/ML | |
| PostgreSQL slow query log review; add missing indexes | Backend | |
| Redis eviction policy set to `allkeys-lru`; confirm no data loss on eviction | DevOps | |
| Frontend Lighthouse score ≥ 90 for performance on dashboard page | Frontend | |
| Bundle analysis: vendor chunks split; `@xyflow/react` lazy-loaded | Frontend | |

### 11.3 Observability (Week 2–3)

| Task | Owner | Notes |
|------|-------|-------|
| Structured JSON logging (request ID, org ID, duration, status) in FastAPI | Backend | |
| Celery task failure alerting — Flower + Slack webhook on task retry exhaustion | DevOps | |
| Health check endpoint `GET /health` — DB ping, Redis ping, worker queue depth | Backend | Used by Nginx upstream health checks |
| Postgres connection pool metrics exported to Prometheus (via `sqlalchemy_pool_size`, `sqlalchemy_checked_out`) | Backend | |
| Uptime monitor on `/health` endpoint (5-minute polling) | DevOps | PagerDuty or equivalent |
| Error rate alert: trigger if 5xx rate > 1 % over a 5-minute window | DevOps | |

### 11.4 E2E & Regression Test Pass (Week 3)

| Task | Owner | Notes |
|------|-------|-------|
| Complete all e2e test cases in `tests/e2e/` against staging environment | Backend/Frontend | |
| Cross-browser test: Chrome, Firefox, Safari (latest stable) on the builder page | Frontend | |
| Mobile responsive check on dashboard pages (not builder — builder is desktop-only by design) | Frontend | |
| Regression test: verify all Phase 1–6 acceptance criteria still pass | Full team | |

### 11.5 Documentation & Launch Prep (Week 4–5)

| Task | Owner | Notes |
|------|-------|-------|
| `API.md` finalized and published to developer docs site | Backend | |
| Onboarding guide: "Build your first workflow in 10 minutes" | Frontend | |
| `create_super_admin` CLI run in production; credential stored in password manager | DevOps | |
| Production environment checklist: strong secrets, TLS, WAF, automated backups, point-in-time recovery tested | DevOps | |
| Runbook: org suspension, support grant creation, feature flag rollout, incident response | DevOps | |
| Staged rollout plan: 5 beta customers → 20 → general availability | PM | |

### 11.6 Phase 7 Acceptance Criteria

- [ ] Zero high-severity findings in internal penetration test
- [ ] p95 API response time < 200 ms at 50 concurrent users
- [ ] All Phase 1–6 acceptance criteria pass against the staging environment
- [ ] Platform audit log is immutable (direct DB `DELETE` is blocked by `REVOKE DELETE ON platform_audit_logs FROM app_user`)
- [ ] Automated daily DB backup verified with a restore drill
- [ ] Production `ENCRYPTION_KEY` and `JWT_SECRET_KEY` are different from development values
- [ ] On-call runbook reviewed and signed off by at least two engineers

---

## 12. Milestone Summary

```
Week  1-2   Phase 1: Foundation complete
             └─ Auth API green, CI passing, full stack runs locally

Week  3-5   Phase 2: Core Platform complete
             └─ Org/member/invite/API key working, tenant isolation tested

Week  6-9   Phase 3: Workflow Engine complete
             └─ Build → publish → execute → observe working end-to-end

Week 10-12  Phase 4: AI Features complete
             └─ RAG live, 6 AI node types working in workflows

Week 13-14  Phase 5: Platform Admin complete
             └─ Internal dashboard live, support grant flow enforced

Week 15-17  Phase 6: Analytics, Notifications, Real-Time complete
             └─ Live execution feed, analytics dashboard, email notifications

Week 18-22  Phase 7: Production Hardening complete
             └─ Load tested, pen tested, monitored, documented → LAUNCH
```

---

## 13. Dependency Graph

```
Phase 1 (Foundation)
    │
    ├──► Phase 2 (Orgs & Members)
    │         │
    │         ├──► Phase 3 (Workflow Engine)
    │         │         │
    │         │         ├──► Phase 4 (AI Features)
    │         │         │         │
    │         │         │         └──► Phase 6 (Analytics / Notifications / Real-Time)
    │         │         │                   │
    │         │         │                   └──► Phase 7 (Production Hardening)
    │         │         │
    │         │         └──► Phase 6 (execution events → WebSocket)
    │         │
    │         └──► Phase 5 (Platform Admin)   ──────────────────► Phase 7
    │
    └──── CI/CD stays green throughout all phases
```

**Hard sequential dependencies:**
- Phase 2 cannot start until `users` table and JWT auth are complete (Phase 1)
- Phase 3 cannot start until org-scoped auth is complete (Phase 2)
- Phase 4 needs the execution engine to run AI nodes (Phase 3)
- Phase 5 needs `organizations` to exist for suspension/grant logic (Phase 2)
- Phase 6 needs execution events (Phase 3) and analytics tables (Phase 4 for AI usage)
- Phase 7 starts only when Phases 1–6 acceptance criteria are all green

**Parallelism possible:**
- Phase 4 (AI) and Phase 5 (Platform Admin) can run in parallel — they share only read access to the `organizations` table
- Phase 6 front-end work can begin during Phase 3 (WebSocket hook, notification components) while back-end execution engine is being built

---

## 14. Definition of Done

A task is **done** when all of the following are true:

1. **Code merged** to `main` (or protected feature branch) via PR, reviewed by at least one other engineer
2. **Tests written** — unit test for every service function, integration test for every API endpoint changed
3. **Coverage maintained** — `pytest --cov` reports ≥ 80 % on the affected module
4. **CI green** — all lint, type-check, and test jobs pass
5. **API.md updated** — if the endpoint contract changed, the doc is updated in the same PR
6. **Migration reviewed** — every `alembic revision` is reviewed for rollback safety before merging
7. **No secrets in code** — automated secret-scanning check passes (GitHub secret scanning + `detect-secrets`)
8. **Phase acceptance criteria checked** — the criterion the task contributes to is re-verified after merge

---

## 15. Risk Register

| ID | Risk | Probability | Impact | Mitigation |
|----|------|-------------|--------|-----------|
| R1 | LLM provider outage halts AI node executions | Medium | High | `ModelProvider` factory supports fallback provider; circuit breaker in `ai/providers/factory.py`; retryable Celery task |
| R2 | pgvector HNSW index degrades at 10M+ embedding rows | Low | High | Benchmark at 1M rows in Phase 4; partition `document_embeddings` by `organization_id` if needed |
| R3 | Celery task queue backlog under load | Medium | Medium | Separate queues for `execution`, `ai`, `notifications`, `scheduled`; queue depth monitoring alert in Phase 7 |
| R4 | Refresh token replay window race condition | Low | Critical | Refresh token rotation uses a DB transaction with `SELECT FOR UPDATE`; tested in Phase 1 security suite |
| R5 | Cross-tenant data leak via RAG embedding search | Low | Critical | `retriever.py` always filters by `organization_id`; tested explicitly in Phase 4 isolation test |
| R6 | Support engineer accesses customer data without audit trail | Low | High | `platform_audit_logs` written before access granted; table is insert-only by `app_user` |
| R7 | Feature scope creep delays launch | High | Medium | Phases are time-boxed; unstarted features pushed to post-launch backlog, not inserted mid-phase |
| R8 | Frontend bundle size causes slow initial load | Medium | Low | Lazy-load builder canvas; code-split per route group; Lighthouse gate in Phase 7 |
| R9 | MinIO/S3 presigned URL misuse (direct public access) | Low | Medium | PUT URLs expire in 5 min; GET URLs expire in 15 min; bucket is private; URL generation is server-side only |
| R10 | Single `super_admin` account is a single point of failure | Medium | High | CLI creates first account; `super_admin` can promote any `platform_admin` to `super_admin`; procedure documented in runbook |

---

*Document version 1.0.0 — updated to match ARCHITECTURE.md v1.0.0, DatabaseDesign.md v1.1.0, and API.md v1.0.0*
