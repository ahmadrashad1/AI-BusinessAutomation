# Software Architecture Document
# AI Business Process Automation Platform

| Field | Value |
|-------|-------|
| Version | 1.0.0 |
| Status | Approved |
| Date | 2026-06-30 |
| Author | Architecture Team |
| SRS Reference | docs/SRS.md v1.0.0 |

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Architectural Decisions](#2-architectural-decisions)
3. [Monorepo Directory Structure](#3-monorepo-directory-structure)
4. [Frontend Architecture](#4-frontend-architecture)
5. [Backend Architecture](#5-backend-architecture)
6. [Workflow Execution Architecture](#6-workflow-execution-architecture)
7. [AI Architecture](#7-ai-architecture)
8. [Data Architecture](#8-data-architecture)
9. [Real-Time Architecture](#9-real-time-architecture)
10. [Security Architecture](#10-security-architecture)
11. [Infrastructure Architecture](#11-infrastructure-architecture)
12. [Inter-Component Communication](#12-inter-component-communication)
13. [Error Handling Strategy](#13-error-handling-strategy)
14. [Testing Architecture](#14-testing-architecture)
15. [Component Dependency Map](#15-component-dependency-map)

> **Section 10.5** documents the full role hierarchy (Platform vs. Organization scope).
> **Section 14.3–14.5** contain expanded security, RBAC, and complete flow test cases.

---

## 1. Architecture Overview

### 1.1 System Context

The platform is a multi-tenant SaaS application. Every tenant (organization) is fully isolated at the data layer. Multiple users within an organization collaborate on shared workflows, documents, and automation runs.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            External World                                │
│                                                                          │
│   Browser Users          External Systems          LLM Providers         │
│   (employees,            (ERPs, CRMs,              (OpenAI,              │
│    analysts,              webhooks, APIs)            Anthropic,           │
│    managers)                                         Ollama)              │
└──────────┬───────────────────────┬─────────────────────────┬────────────┘
           │ HTTPS / WSS           │ HTTPS (webhooks)         │ HTTPS
           ▼                       ▼                          │
┌──────────────────────────────────────────────────────────────────────┐
│                         Platform Boundary                             │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                  Nginx (Reverse Proxy)                          │  │
│  │       SSL Termination · Routing · Connection Rate Limiting      │  │
│  └──────────┬────────────────────────────┬────────────────────────┘  │
│             │ /api/*  /ws/*               │ /*                        │
│             ▼                             ▼                           │
│  ┌──────────────────────┐    ┌──────────────────────────┐            │
│  │  FastAPI Application  │    │  Next.js Frontend         │            │
│  │  (stateless, N        │    │  (SSR + static assets)    │            │
│  │   instances)          │    │                           │            │
│  └──────────┬───────────┘    └──────────────────────────┘            │
│             │                                                          │
│    ┌────────┼──────────────────────┐                                  │
│    ▼        ▼                      ▼                                  │
│  ┌──────┐ ┌─────────────────┐ ┌───────────┐                          │
│  │ PG   │ │ Redis           │ │ MinIO/S3  │                          │
│  │ (DB) │ │ (queue+cache    │ │ (object   │                          │
│  │      │ │  +pub/sub)      │ │  storage) │                          │
│  └──────┘ └────────┬────────┘ └───────────┘                          │
│                    │                                                   │
│                    ▼                                                   │
│         ┌──────────────────────┐                                      │
│         │  Celery Workers       │ ──────────────────────► LLM APIs   │
│         │  (AI · execution ·    │                                      │
│         │   email · scheduled)  │                                      │
│         └──────────────────────┘                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 1.2 Six Core Responsibilities

| Component | Responsibility |
|-----------|---------------|
| **Next.js** | Render UI, manage client state, relay API calls, stream WebSocket events |
| **FastAPI** | Validate requests, enforce auth/authz/tenancy, orchestrate service calls, return fast responses |
| **Celery Workers** | Execute workflows, run AI pipelines, send emails, run scheduled jobs |
| **PostgreSQL** | Durable storage for all structured data + vector embeddings |
| **Redis** | Task queue, refresh token sessions, analytics cache, WebSocket pub/sub |
| **MinIO / S3** | Durable storage for all binary files (PDFs, images, generated documents) |

### 1.3 Key Architectural Principles

1. **API layer never blocks.** Any operation that could take > 300ms is dispatched to Celery. The API acknowledges with a run ID and status is pushed via WebSocket.
2. **Stateless API.** No in-process session state. Horizontal scaling is add-more-instances.
3. **Tenant isolation at the query layer.** Every SQLAlchemy query receives `organization_id` from the request context middleware — not from the route handler.
4. **Plugin-based node architecture.** New workflow node types are registered via a decorator. The execution engine has zero knowledge of specific node types.
5. **LLM-provider agnostic.** All AI calls go through a `ModelProvider` protocol. Switching providers requires only an environment variable change.
6. **Redis is ephemeral.** No business-critical state lives only in Redis. Redis loss causes degraded UX (slower, no WebSocket), not data loss.

---

## 2. Architectural Decisions

### ADR-001: Modular Monolith over Microservices

**Decision:** Single FastAPI application with domain-centric module boundaries. Celery workers share the same codebase.

**Reasoning:** The MVP targets 100 organizations and 5,000 users. The operational overhead of service mesh, inter-service auth, distributed tracing, and network failure handling is unjustified at this scale. The module boundaries defined here are the future microservice boundaries — splitting is a deployment change, not a redesign.

**Consequence:** Modules must not import from each other's internals. Cross-module communication goes through service interfaces or shared models defined in `core/`.

---

### ADR-002: Domain-Centric Vertical Slices over Horizontal Layers

**Decision:** Each module owns its own `models.py`, `schemas.py`, `service.py`, and `router.py`.

**Reasoning:** Horizontal layers (`models/`, `services/`, `schemas/`) require jumping across 4 directories to understand one feature. Vertical slices keep all code for a domain co-located. The SRS has 9 clearly bounded domains — they map directly to modules.

**Consequence:** Global `models/` and `services/` directories do not exist. Shared database primitives (Base class, session factory) live in `core/database.py`.

---

### ADR-003: Celery + Redis over FastAPI Background Tasks

**Decision:** All async work uses Celery with Redis as broker, not FastAPI's `BackgroundTasks`.

**Reasoning:** FastAPI `BackgroundTasks` run in the same process as the request — they block request workers, are lost on pod restart, and cannot be distributed across multiple machines. Celery tasks are durable (persisted in Redis until acknowledged), retriable, distributable, and monitorable via Flower.

**Consequence:** All work that needs retry logic, scheduling, or more than ~100ms of execution time is a Celery task.

---

### ADR-004: pgvector over a Dedicated Vector Database

**Decision:** Embeddings are stored in PostgreSQL using the `pgvector` extension.

**Reasoning:** At MVP and Phase 2 scale (millions of document chunks), pgvector with an HNSW index is faster than a round-trip to a separate Qdrant or Pinecone service. It eliminates one more infrastructure component to operate and keeps RAG retrieval in the same transaction as the metadata query.

**Consequence:** Re-evaluate at ~100M chunks or when cosine search latency exceeds 50ms P95. Migration to a dedicated vector DB is mechanical — the `RAGRetriever` interface does not change.

---

### ADR-005: Monorepo

**Decision:** Frontend, backend, infrastructure, and documentation in one git repository.

**Reasoning:** API contract changes and their corresponding UI changes land in a single atomic commit. CI/CD is simpler. No version pinning across repos for a two-layer app.

**Consequence:** CI jobs are scoped by path — frontend changes do not trigger backend tests and vice versa.

---

## 3. Monorepo Directory Structure

```
ai-business-automation/
│
├── frontend/                          # Next.js 14 (App Router)
│   ├── src/
│   │   ├── app/
│   │   │   ├── (auth)/               # Public route group
│   │   │   │   ├── login/
│   │   │   │   │   └── page.tsx
│   │   │   │   ├── register/
│   │   │   │   │   └── page.tsx
│   │   │   │   ├── verify-email/
│   │   │   │   │   └── page.tsx
│   │   │   │   └── reset-password/
│   │   │   │       └── page.tsx
│   │   │   ├── (dashboard)/          # Customer Dashboard (Organization users)
│   │   │   │   ├── layout.tsx        # Auth guard + org context provider
│   │   │   │   ├── page.tsx          # Dashboard home
│   │   │   │   ├── workflows/
│   │   │   │   │   ├── page.tsx      # Workflow list
│   │   │   │   │   └── [id]/
│   │   │   │   │       ├── page.tsx  # Workflow detail + run history
│   │   │   │   │       └── builder/
│   │   │   │   │           └── page.tsx  # Canvas editor (React Flow)
│   │   │   │   ├── executions/
│   │   │   │   │   ├── page.tsx      # All runs across workflows
│   │   │   │   │   └── [runId]/
│   │   │   │   │       └── page.tsx  # Run detail + node logs
│   │   │   │   ├── documents/
│   │   │   │   │   └── page.tsx
│   │   │   │   ├── knowledge-base/
│   │   │   │   │   └── page.tsx      # RAG Q&A interface
│   │   │   │   ├── analytics/
│   │   │   │   │   └── page.tsx
│   │   │   │   └── settings/
│   │   │   │       ├── layout.tsx    # Settings sidebar
│   │   │   │       ├── profile/
│   │   │   │       ├── organization/
│   │   │   │       ├── members/
│   │   │   │       ├── departments/
│   │   │   │       ├── api-keys/
│   │   │   │       └── integrations/
│   │   │   │
│   │   │   ├── (platform-admin)/     # Platform Dashboard (AutoFlow team only)
│   │   │   │   ├── layout.tsx        # Platform role guard — org users redirected to /dashboard
│   │   │   │   ├── page.tsx          # Overview: uptime, queue depth, revenue KPIs
│   │   │   │   ├── organizations/
│   │   │   │   │   ├── page.tsx      # All tenants: plan, user count, status
│   │   │   │   │   └── [orgId]/
│   │   │   │   │       └── page.tsx  # Tenant detail: members, usage, suspend/reinstate
│   │   │   │   ├── subscriptions/
│   │   │   │   │   └── page.tsx      # Subscription & billing management
│   │   │   │   ├── system/
│   │   │   │   │   ├── page.tsx      # Worker queues, DB health, Redis stats, storage
│   │   │   │   │   └── logs/
│   │   │   │   │       └── page.tsx  # System log viewer with filter + search
│   │   │   │   └── support/
│   │   │   │       └── page.tsx      # Support ticket queue + feature flags
│   │   │   ├── api/                  # Next.js API routes
│   │   │   │   └── auth/
│   │   │   │       └── callback/
│   │   │   │           └── route.ts  # Google OAuth callback handler
│   │   │   ├── layout.tsx            # Root layout (fonts, providers)
│   │   │   └── globals.css
│   │   ├── components/
│   │   │   ├── ui/                   # shadcn/ui component re-exports
│   │   │   ├── workflow-builder/
│   │   │   │   ├── Canvas.tsx        # React Flow wrapper
│   │   │   │   ├── NodePalette.tsx   # Draggable node sidebar
│   │   │   │   ├── NodeConfigPanel.tsx # Right-side config form
│   │   │   │   ├── Toolbar.tsx       # Save / Publish / Undo buttons
│   │   │   │   └── nodes/            # React Flow custom node components
│   │   │   │       ├── TriggerNode.tsx
│   │   │   │       ├── ActionNode.tsx
│   │   │   │       ├── AINode.tsx
│   │   │   │       └── ConditionNode.tsx
│   │   │   ├── execution/
│   │   │   │   ├── RunStatusBadge.tsx
│   │   │   │   ├── NodeLogRow.tsx
│   │   │   │   └── LiveExecutionOverlay.tsx  # WebSocket-driven live status
│   │   │   ├── notifications/
│   │   │   │   ├── NotificationBell.tsx
│   │   │   │   └── NotificationFeed.tsx
│   │   │   └── shared/
│   │   │       ├── OrgSwitcher.tsx
│   │   │       ├── PermissionGate.tsx  # Role-based render guard
│   │   │       └── DataTable.tsx
│   │   ├── lib/
│   │   │   ├── api/                  # API client layer
│   │   │   │   ├── client.ts         # Axios instance + interceptors
│   │   │   │   ├── auth.ts           # login, register, refresh, logout
│   │   │   │   ├── workflows.ts      # CRUD + publish + versions
│   │   │   │   ├── executions.ts     # trigger, cancel, retry, logs
│   │   │   │   ├── documents.ts      # upload, list, delete
│   │   │   │   ├── analytics.ts
│   │   │   │   ├── organizations.ts
│   │   │   │   └── ai.ts             # RAG query, workflow generate
│   │   │   ├── stores/               # Zustand stores (client state only)
│   │   │   │   ├── auth.store.ts     # user, org, access token (in memory)
│   │   │   │   ├── builder.store.ts  # nodes, edges, history (undo/redo)
│   │   │   │   └── notifications.store.ts
│   │   │   ├── hooks/
│   │   │   │   ├── useWebSocket.ts   # Singleton WS connection + event dispatch
│   │   │   │   ├── usePermission.ts  # Check current user role
│   │   │   │   └── useOrg.ts         # Current org context
│   │   │   ├── query/                # TanStack Query keys + hooks
│   │   │   │   ├── keys.ts           # Centralized query key factory
│   │   │   │   ├── useWorkflows.ts
│   │   │   │   ├── useExecutions.ts
│   │   │   │   └── useAnalytics.ts
│   │   │   └── utils/
│   │   │       ├── cn.ts             # tailwind-merge utility
│   │   │       ├── format.ts         # date, duration, file size formatters
│   │   │       └── graph.ts          # topological sort for canvas validation
│   │   └── types/
│   │       ├── api.ts                # API response shapes (mirrors backend schemas)
│   │       ├── workflow.ts           # Node, Edge, WorkflowGraph types
│   │       └── auth.ts
│   ├── public/
│   ├── package.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   └── tsconfig.json
│
├── backend/
│   ├── app/
│   │   ├── main.py                   # FastAPI app factory + lifespan
│   │   ├── core/                     # Cross-cutting infrastructure
│   │   │   ├── config.py             # Pydantic Settings (reads env vars)
│   │   │   ├── database.py           # SQLAlchemy engine, session factory, Base
│   │   │   ├── redis.py              # Redis client factory
│   │   │   ├── storage.py            # S3/MinIO client wrapper
│   │   │   ├── security.py           # JWT encode/decode, bcrypt, AES-256
│   │   │   ├── middleware.py         # Tenant context, request logging
│   │   │   ├── rate_limit.py         # Redis-backed rate limiter
│   │   │   └── exceptions.py         # HTTP exception classes + handlers
│   │   ├── modules/
│   │   │   │
│   │   │   ├── auth/
│   │   │   │   ├── models.py         # User, OAuthAccount, PasswordResetToken
│   │   │   │   ├── schemas.py        # RegisterRequest, LoginResponse, TokenPair
│   │   │   │   ├── service.py        # register, login, refresh, logout, reset
│   │   │   │   ├── router.py         # POST /auth/register, /auth/login, etc.
│   │   │   │   └── dependencies.py   # get_current_user, require_verified
│   │   │   │
│   │   │   ├── organizations/
│   │   │   │   ├── models.py         # Organization, OrgMember, Department, Invitation
│   │   │   │   ├── schemas.py
│   │   │   │   ├── service.py        # create_org, invite_member, accept_invite, update_role
│   │   │   │   └── router.py         # /orgs, /orgs/{id}/members, /invitations
│   │   │   │
│   │   │   ├── workflows/
│   │   │   │   ├── models.py         # Workflow, WorkflowVersion, WorkflowNode, WorkflowEdge
│   │   │   │   ├── schemas.py
│   │   │   │   ├── service.py        # CRUD, publish, revert, duplicate
│   │   │   │   ├── router.py         # /workflows, /workflows/{id}/publish
│   │   │   │   ├── validator.py      # validate_graph() before publish
│   │   │   │   └── nodes/            # Node type plugin registry
│   │   │   │       ├── registry.py   # NODE_REGISTRY dict + @register_node decorator
│   │   │   │       ├── base.py       # BaseNode ABC + ExecutionContext dataclass
│   │   │   │       ├── triggers/
│   │   │   │       │   ├── manual.py       # trigger.manual
│   │   │   │       │   ├── schedule.py     # trigger.schedule
│   │   │   │       │   ├── webhook.py      # trigger.webhook
│   │   │   │       │   └── email.py        # trigger.email
│   │   │   │       ├── actions/
│   │   │   │       │   ├── http_request.py # action.http
│   │   │   │       │   ├── send_email.py   # action.email
│   │   │   │       │   ├── condition.py    # action.condition
│   │   │   │       │   ├── delay.py        # action.delay
│   │   │   │       │   └── db_write.py     # action.db_write
│   │   │   │       └── ai/
│   │   │   │           ├── extraction.py       # ai.extraction
│   │   │   │           ├── classification.py   # ai.classification
│   │   │   │           ├── summarization.py    # ai.summarization
│   │   │   │           ├── prompt.py           # ai.prompt
│   │   │   │           ├── rag.py              # ai.rag
│   │   │   │           └── multi_agent.py      # ai.multi_agent
│   │   │   │
│   │   │   ├── execution/
│   │   │   │   ├── models.py         # WorkflowRun, ExecutionLog
│   │   │   │   ├── schemas.py
│   │   │   │   ├── service.py        # trigger_run, cancel_run, retry_from_node
│   │   │   │   ├── router.py         # /runs, /runs/{id}, /runs/{id}/retry
│   │   │   │   ├── engine.py         # WorkflowEngine: topological sort + node dispatch
│   │   │   │   └── scheduler.py      # Celery Beat schedule CRUD for cron triggers
│   │   │   │
│   │   │   ├── ai/
│   │   │   │   ├── providers/
│   │   │   │   │   ├── base.py       # ModelProvider Protocol
│   │   │   │   │   ├── openai.py     # OpenAIProvider
│   │   │   │   │   ├── anthropic.py  # AnthropicProvider
│   │   │   │   │   └── factory.py    # get_provider() reads LLM_PROVIDER env
│   │   │   │   ├── chains/
│   │   │   │   │   ├── extraction.py      # LangChain extraction chain
│   │   │   │   │   ├── classification.py  # LangChain classification chain
│   │   │   │   │   └── summarization.py   # LangChain map-reduce chain
│   │   │   │   ├── rag/
│   │   │   │   │   ├── indexer.py    # parse → chunk → embed → store in pgvector
│   │   │   │   │   └── retriever.py  # embed query → cosine search → LLM answer
│   │   │   │   ├── agents/
│   │   │   │   │   └── graph.py      # LangGraph StateGraph definition
│   │   │   │   ├── ocr.py            # Tesseract / AWS Textract abstraction
│   │   │   │   ├── usage.py          # log_ai_usage() helper
│   │   │   │   ├── schemas.py
│   │   │   │   └── router.py         # /ai/query (RAG), /ai/generate-workflow
│   │   │   │
│   │   │   ├── files/
│   │   │   │   ├── models.py         # Document, DocumentChunk
│   │   │   │   ├── schemas.py
│   │   │   │   ├── service.py        # upload, get_download_url, delete
│   │   │   │   └── router.py         # /documents (multipart upload, list, delete)
│   │   │   │
│   │   │   ├── notifications/
│   │   │   │   ├── models.py         # Notification
│   │   │   │   ├── schemas.py
│   │   │   │   ├── service.py        # create_notification, mark_read
│   │   │   │   ├── router.py         # /notifications, WebSocket /ws
│   │   │   │   ├── email.py          # send_email() via SMTP/SendGrid
│   │   │   │   └── websocket.py      # ConnectionManager + Redis subscriber
│   │   │   │
│   │   │   ├── analytics/
│   │   │   │   ├── models.py         # AIUsageLog (read model)
│   │   │   │   ├── schemas.py
│   │   │   │   ├── service.py        # aggregate queries with Redis cache
│   │   │   │   └── router.py         # /analytics/dashboard, /analytics/ai-usage
│   │   │   │
│   │   │   └── platform/             # Platform Admin module (AutoFlow team only)
│   │   │       ├── models.py         # PlatformUser, PlatformRole, SupportTicket, FeatureFlag
│   │   │       ├── schemas.py        # OrgSummary, SystemHealth, TicketCreate
│   │   │       ├── service.py        # suspend_org, reinstate_org, grant_support_access,
│   │   │       │                     # list_all_orgs, get_system_health, toggle_feature_flag
│   │   │       ├── router.py         # /platform/* — all require platform role
│   │   │       └── dependencies.py   # require_platform_role(), get_platform_user()
│   │   │
│   │   └── api/
│   │       ├── v1/
│   │       │   └── router.py         # Mounts all module routers under /api/v1
│   │       └── webhooks/
│   │           └── router.py         # /webhooks/{workflow_id} — inbound triggers
│   │
│   ├── worker/
│   │   ├── celery_app.py             # Celery app factory (imports from app.core.config)
│   │   └── tasks/
│   │       ├── workflow_execution.py # execute_workflow_task(run_id)
│   │       ├── ai_processing.py      # document_extraction_task, rag_index_task
│   │       ├── notifications.py      # send_email_task
│   │       └── scheduled.py         # Celery Beat periodic tasks
│   │
│   ├── alembic/
│   │   ├── versions/                 # Auto-generated migration files
│   │   ├── env.py
│   │   └── alembic.ini
│   │
│   ├── tests/
│   │   ├── unit/
│   │   │   ├── test_auth_service.py
│   │   │   ├── test_workflow_engine.py
│   │   │   ├── test_graph_validator.py
│   │   │   ├── test_node_registry.py
│   │   │   └── test_ai_chains.py
│   │   ├── integration/
│   │   │   ├── test_auth_api.py
│   │   │   ├── test_workflow_api.py
│   │   │   ├── test_execution_flow.py
│   │   │   └── test_tenant_isolation.py
│   │   └── conftest.py              # DB fixtures, test client, org + user factories
│   │
│   ├── pyproject.toml
│   ├── Dockerfile                   # FastAPI app image
│   └── Dockerfile.worker            # Celery worker image
│
├── infra/
│   ├── nginx/
│   │   ├── nginx.conf               # Main Nginx config
│   │   └── conf.d/
│   │       └── default.conf         # Upstream proxy rules + SSL
│   └── docker/
│       └── .env.example             # Template for all env vars
│
├── docs/
│   ├── SRS.md
│   └── architecture/
│       └── ARCHITECTURE.md          # This document
│
├── .github/
│   └── workflows/
│       ├── ci.yml                   # Lint + test on every PR
│       └── deploy.yml               # Build + push + deploy on merge to main
│
├── docker-compose.yml               # Full local dev stack
├── docker-compose.prod.yml          # Production overrides
└── .env.example                     # Root env template
```

---

## 4. Frontend Architecture

### 4.1 Route Structure

Next.js App Router uses **route groups** for layout separation:

| Route Group | Layout | Purpose |
|-------------|--------|---------|
| `(auth)` | Minimal (no sidebar) | Login, register, verify email, reset password |
| `(dashboard)` | Full app shell + auth guard | All authenticated pages |

The `(dashboard)/layout.tsx` is the auth boundary — it reads the access token from the Zustand auth store, and redirects to `/login` if absent. It also establishes the organization context by loading the current user's org membership.

### 4.2 State Management Strategy

Two stores handle two fundamentally different types of state:

**Zustand stores** (client-only, synchronous, in-memory):

```
auth.store.ts
  ├── currentUser: User | null
  ├── currentOrg: Organization | null
  ├── accessToken: string | null     ← never persisted to localStorage
  └── actions: login(), logout(), switchOrg(), setToken()

builder.store.ts
  ├── nodes: Node[]
  ├── edges: Edge[]
  ├── history: HistoryEntry[]        ← undo/redo stack (max 20)
  ├── isDirty: boolean
  └── actions: addNode(), updateNode(), undo(), redo(), reset()

notifications.store.ts
  ├── notifications: Notification[]
  ├── unreadCount: number
  └── actions: addNotification(), markRead(), markAllRead()
```

**TanStack Query** (server state, cache, background refetch):
- All API data (workflows, runs, documents, analytics, members)
- Centralized query keys in `lib/query/keys.ts` prevent cache collisions
- WebSocket events invalidate specific query keys to trigger background refetch

### 4.3 API Client Layer

```
lib/api/client.ts
  Axios instance
    Request interceptor:
      → attach Authorization: Bearer {accessToken} from Zustand store
    Response interceptor:
      → on 401: call /auth/refresh → update token in store → retry original request
      → on 403: redirect to unauthorized page
      → on 5xx: surface error to TanStack Query error boundary
```

All domain-specific API modules (`workflows.ts`, `executions.ts`) import from `client.ts`. They export typed async functions, not raw Axios calls. TanStack Query hooks wrap these functions.

### 4.4 Workflow Builder State

The canvas has its own Zustand slice because it is high-frequency (drag events, edge connections) and must not trigger React Query re-renders:

```
builder.store.ts flow:
  User drags node onto canvas
    → addNode() appends to nodes[]
    → pushHistory() captures previous state
    → isDirty = true

  User clicks Save
    → service.saveWorkflow(nodes, edges) called
    → isDirty = false

  User presses Ctrl+Z
    → undo() pops history, restores nodes/edges
    → (max 20 history entries, oldest discarded)
```

React Flow's `onNodesChange` and `onEdgesChange` are wired to the Zustand store mutations, not to local `useState`.

### 4.5 WebSocket Integration

A singleton WebSocket connection is established when the user enters the `(dashboard)` route group and torn down on logout:

```
useWebSocket.ts
  connect(orgId):
    ws = new WebSocket(`wss://api/ws?token=${accessToken}`)
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      dispatch(msg)     ← routes to the right handler
    }

  dispatch(msg):
    if msg.type == "run.status_changed":
      → invalidate query key ["executions", msg.run_id]
      → notifications.store.addNotification(...)
    if msg.type == "node.completed":
      → update builder.store node status overlay
    if msg.type == "notification.new":
      → notifications.store.addNotification(...)
```

---

## 5. Backend Architecture

### 5.1 FastAPI Application Factory

```python
# app/main.py
def create_app() -> FastAPI:
    app = FastAPI(title="AI BPA Platform", version="1.0.0")

    # Middleware (registered in reverse — first registered = outermost)
    app.add_middleware(TenantContextMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(CORSMiddleware, ...)

    # Exception handlers
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # Routers
    app.include_router(api_v1_router, prefix="/api/v1")
    app.include_router(webhook_router, prefix="/webhooks")
    app.include_router(websocket_router)  # /ws

    # Lifespan: connect DB pool, Redis, register scheduled tasks
    app.router.lifespan_context = lifespan

    return app
```

### 5.2 Module Internal Structure

Every module follows the same four-file contract:

```
module/
  models.py    SQLAlchemy ORM models. Import Base from core/database.py.
               No business logic. No imports from other modules.

  schemas.py   Pydantic v2 models for request/response.
               Named as: {Entity}Create, {Entity}Update, {Entity}Response.
               No SQLAlchemy imports.

  service.py   Business logic. Accepts db: AsyncSession as a parameter.
               Returns Pydantic schemas or raises AppException.
               May import from core/ and from other modules' schemas only.

  router.py    FastAPI router. Depends on service functions via DI.
               Handles HTTP concerns: status codes, response models, path params.
               No business logic.
```

**Cross-module dependency rule:** Modules may import each other's *schemas* (for response composition) but never each other's *models* or *services*. This keeps module boundaries clean and enables future extraction into separate services.

### 5.3 Core Layer

```
core/
  config.py       Pydantic BaseSettings. Reads all env vars. Single source of truth.
                  Imported by everything. No other module imports from config.py.

  database.py     SQLAlchemy async engine. AsyncSessionLocal factory.
                  Base declarative class. get_db() dependency function.

  redis.py        Async Redis client (redis.asyncio). get_redis() dependency.

  storage.py      Boto3 S3 client wrapper. upload_file(), get_presigned_url(),
                  delete_file(). Abstracts MinIO vs S3 via S3_ENDPOINT_URL.

  security.py     create_access_token(), decode_access_token(), hash_password(),
                  verify_password(), encrypt_secret(), decrypt_secret().

  middleware.py   TenantContextMiddleware: reads org_id from JWT claims,
                  stores in request.state.organization_id.
                  RequestLoggingMiddleware: assigns request_id, logs start/end.

  rate_limit.py   RateLimiter: Redis sliding window. Applied as a FastAPI
                  dependency on specific route groups.

  exceptions.py   AppException base class with HTTP status + error code.
                  Subclasses: NotFoundError, ForbiddenError, ConflictError,
                  UnprocessableError, ExternalServiceError.
```

### 5.4 Dependency Injection Chain

FastAPI dependencies compose into a clean auth → authz → context chain:

```
get_db()                          → AsyncSession
get_redis()                       → Redis
get_current_user(db, token)       → User (validates JWT, loads user from DB)
get_current_member(user, org_id)  → OrgMember (loads org membership + role)
require_role("admin")(member)     → OrgMember (raises 403 if role insufficient)
```

A typical protected endpoint:

```python
@router.post("/workflows")
async def create_workflow(
    body: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
    member: OrgMember = Depends(require_role("analyst")),
):
    return await workflow_service.create(db, member.organization_id, member.user_id, body)
```

The `organization_id` never comes from the request body — always from the authenticated member's context.

### 5.5 Node Plugin Registry

The execution engine is fully decoupled from node types via a decorator-based registry:

```python
# workflows/nodes/registry.py
NODE_REGISTRY: dict[str, type[BaseNode]] = {}

def register_node(node_type: str):
    def decorator(cls: type[BaseNode]) -> type[BaseNode]:
        NODE_REGISTRY[node_type] = cls
        return cls
    return decorator

def get_node_handler(node_type: str) -> BaseNode:
    if node_type not in NODE_REGISTRY:
        raise UnprocessableError(f"Unknown node type: {node_type}")
    return NODE_REGISTRY[node_type]()
```

```python
# workflows/nodes/base.py
@dataclass
class ExecutionContext:
    run_id: UUID
    organization_id: UUID
    trigger_payload: dict
    node_outputs: dict[str, dict]   # node_id → output from prior nodes
    db: AsyncSession
    storage: StorageClient

class BaseNode(ABC):
    @abstractmethod
    async def execute(
        self,
        input_data: dict,
        config: dict,
        context: ExecutionContext,
    ) -> dict:
        """Return output dict passed to downstream nodes."""
```

```python
# workflows/nodes/actions/http_request.py
@register_node("action.http")
class HTTPRequestNode(BaseNode):
    async def execute(self, input_data: dict, config: dict, context: ExecutionContext) -> dict:
        response = await httpx.AsyncClient().request(
            method=config["method"],
            url=config["url"],
            headers=config.get("headers", {}),
            json=input_data,
            timeout=config.get("timeout_seconds", 30),
        )
        return {"status_code": response.status_code, "body": response.json()}
```

Registrations happen at module import time. The `main.py` lifespan imports all node modules to trigger registration before the server accepts requests.

---

## 6. Workflow Execution Architecture

### 6.1 Trigger → Execution Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ TRIGGER LAYER (FastAPI, < 200ms)                                 │
│                                                                   │
│  POST /api/v1/runs (manual)                                       │
│  POST /webhooks/{workflow_id} (webhook)                           │
│  Celery Beat fires (schedule)                                     │
│              │                                                    │
│              ▼                                                    │
│  1. Validate workflow is published                                │
│  2. Create WorkflowRun (status=pending, input_data=payload)       │
│  3. Enqueue execute_workflow_task(run_id) → Celery               │
│  4. Return {run_id, status: "pending"} immediately               │
└──────────────────────────┬──────────────────────────────────────┘
                           │ task queue (Redis)
┌──────────────────────────▼──────────────────────────────────────┐
│ EXECUTION LAYER (Celery Worker, async)                            │
│                                                                   │
│  execute_workflow_task(run_id):                                   │
│    1. Load WorkflowRun + WorkflowVersion from DB                  │
│    2. Update status → running; publish WS event                  │
│    3. Build ExecutionContext (run_id, org_id, trigger_payload)    │
│    4. Call WorkflowEngine.execute(version, context)              │
│                                                                   │
│  WorkflowEngine.execute():                                        │
│    nodes = topological_sort(version.nodes, version.edges)        │
│    for node in nodes:                                            │
│      input = resolve_input(node, context.node_outputs)           │
│      log = create_execution_log(run_id, node.id, status=running)│
│      publish WS: {type: "node.started", node_id, run_id}        │
│      try:                                                        │
│        output = await node_handler.execute(input, config, ctx)  │
│        update log: status=completed, output=output               │
│        context.node_outputs[node.id] = output                   │
│        publish WS: {type: "node.completed", node_id, output}    │
│      except NodeExecutionError as e:                             │
│        update log: status=failed, error=str(e)                   │
│        publish WS: {type: "node.failed", node_id, error}        │
│        raise → Celery retry                                      │
│                                                                   │
│    Update WorkflowRun: status=completed                          │
│    publish WS: {type: "run.completed", run_id}                   │
└──────────────────────────────────────────────────────────────────┘
```

### 6.2 Input Resolution

Each node's input is built from the outputs of its upstream nodes. For nodes with a single upstream parent, the input is the parent's full output dict. For condition branches, only the output of the branch's entry node is passed. This is resolved by the engine before dispatching to the node handler:

```python
def resolve_input(node: WorkflowNode, node_outputs: dict[str, dict]) -> dict:
    upstream_node_ids = get_upstream_nodes(node)
    if len(upstream_node_ids) == 1:
        return node_outputs.get(upstream_node_ids[0], {})
    # Merge multiple upstream outputs (for future parallel branches)
    merged = {}
    for uid in upstream_node_ids:
        merged.update(node_outputs.get(uid, {}))
    return merged
```

### 6.3 Retry Strategy

```
Node fails
  └── Celery catches exception
        └── attempt_number < max_retries (default 3)?
              ├── YES → retry with delay = 2^attempt × 10 seconds
              │         (10s → 20s → 40s)
              └── NO  → mark ExecutionLog failed
                        mark WorkflowRun failed
                        create Notification (workflow.failed)
                        send email if configured
```

Celery task configuration:
```python
@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    autoretry_for=(NodeExecutionError, ExternalServiceError),
    retry_backoff=True,
    retry_backoff_max=120,
)
def execute_workflow_task(self, run_id: str): ...
```

### 6.4 Manual Retry from Failed Node

When a user clicks "Retry from failed node":
1. Load the `WorkflowRun` and all `ExecutionLog` entries
2. Build `node_outputs` from all `ExecutionLog` entries with `status=completed`
3. Create a new `WorkflowRun` (with `parent_run_id` reference) starting from the failed node
4. Enqueue Celery task with the pre-loaded `node_outputs` so already-completed nodes are skipped

This prevents double side-effects (e.g., ERP updated twice).

### 6.5 Scheduled Workflows

Scheduled triggers use **Celery Beat with `celery-redbeat`** — a Redis-backed dynamic scheduler that requires no restart when schedules change:

```python
# execution/scheduler.py
from redbeat import RedBeatSchedulerEntry
from worker.celery_app import celery_app

def create_schedule(workflow_id: UUID, cron_expr: str):
    """Called when a workflow with a schedule trigger is published."""
    entry = RedBeatSchedulerEntry(
        name=f"workflow-{workflow_id}",
        task="worker.tasks.scheduled.trigger_scheduled_workflow",
        schedule=crontab(*parse_cron(cron_expr)),
        kwargs={"workflow_id": str(workflow_id)},
        app=celery_app,
    )
    entry.save()

def delete_schedule(workflow_id: UUID):
    """Called when a scheduled workflow is archived or its trigger is changed."""
    entry = RedBeatSchedulerEntry.from_key(
        f"redbeat:workflow-{workflow_id}", app=celery_app
    )
    entry.delete()
```

`redbeat` stores schedule entries in Redis under `redbeat:*` keys. Celery Beat polls Redis at the configured tick interval (default: 5 seconds). Publishing or archiving a workflow updates Redis immediately — no worker restart needed.

---

## 7. AI Architecture

### 7.1 AI Request Flow

All AI work is dispatched asynchronously from the workflow execution engine. AI nodes do not run in the FastAPI process.

```
WorkflowEngine encounters ai.extraction node
  │
  └── node_handler.execute() called (inside Celery worker)
        │
        ▼
  AINodeDispatcher.dispatch(node_type, input, config, context)
        │
        ├── Fetches file from S3 if input contains file_id
        ├── Runs OCR if mime_type is image or scanned PDF
        ├── Routes to appropriate chain/retriever/graph
        ├── Calls LLM via ModelProvider
        ├── Validates output with Pydantic
        ├── Calls log_ai_usage(provider, model, tokens, latency, context)
        └── Returns structured output dict
```

### 7.2 Model Provider Abstraction

```python
# ai/providers/base.py
from typing import Protocol, runtime_checkable

@runtime_checkable
class ModelProvider(Protocol):
    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.0,
        response_format: dict | None = None,
    ) -> tuple[str, UsageStats]: ...

    async def embed(self, text: str) -> list[float]: ...

@dataclass
class UsageStats:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
```

```python
# ai/providers/factory.py
def get_provider(settings: Settings) -> ModelProvider:
    match settings.LLM_PROVIDER:
        case "openai":    return OpenAIProvider(api_key=settings.OPENAI_API_KEY)
        case "anthropic": return AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY)
        case "ollama":    return OllamaProvider(base_url=settings.OLLAMA_BASE_URL)
        case _: raise ValueError(f"Unknown LLM_PROVIDER: {settings.LLM_PROVIDER}")
```

The provider is injected into chains and retrievers via constructor parameter — no global singleton. This makes unit testing trivially easy (inject a mock provider).

### 7.3 Intelligent Document Processing Chain

```
Input: {file_id, extraction_schema, confidence_threshold}
  │
  ▼ Fetch file from S3 (StorageClient)
  │
  ▼ Detect file type
    ├── PDF (text-based)  → PyMuPDF text extraction
    ├── PDF (scanned)     → Tesseract OCR
    ├── DOCX              → python-docx
    ├── XLSX              → openpyxl
    └── Image             → Tesseract OCR
  │
  ▼ Chunk text (if > 8000 tokens) → token-aware splitter
  │
  ▼ LangChain extraction chain:
    system_prompt = build_extraction_prompt(extraction_schema)
    response = await provider.chat(
        messages=[system_prompt, {"role": "user", "content": document_text}],
        response_format={"type": "json_object"},
    )
  │
  ▼ Pydantic validates response against extraction_schema
  │
  ▼ Assign confidence scores per field (LLM self-reports or heuristic)
  │
  ▼ Flag fields below confidence_threshold for human review
  │
Output: {extracted_fields: dict, confidence: dict, flagged_fields: list}
```

### 7.4 RAG Pipeline

**Indexing** (runs when a document is uploaded and marked for RAG indexing):

```
Document uploaded → rag_index_task(document_id) enqueued
  │
  ▼ Fetch document text (OCR/parse as above)
  ▼ Chunk: 512 tokens, 50-token overlap (LangChain RecursiveCharacterTextSplitter)
  ▼ For each chunk:
      embedding = await provider.embed(chunk.text)
      INSERT INTO document_chunks (document_id, org_id, chunk_index, content, embedding)
  ▼ UPDATE documents SET is_indexed = true
```

**Retrieval** (runs at query time, inside Celery worker or FastAPI for low-latency Q&A endpoint):

```
Query: "What is our maternity leave policy?"
  │
  ▼ embed query → vector[1536]
  ▼ pgvector cosine similarity search:
      SELECT content, metadata, 1 - (embedding <=> :query_vec) AS score
      FROM document_chunks
      WHERE organization_id = :org_id
        AND (1 - (embedding <=> :query_vec)) > 0.75
      ORDER BY score DESC
      LIMIT 5
  │
  ▼ Build context prompt:
      [System: "Answer using only the provided documents. Cite sources."]
      [User: query + retrieved chunks with source labels]
  ▼ provider.chat(messages) → grounded answer with citations
Output: {answer, sources: [{document_name, chunk_index, score}]}
```

### 7.5 Multi-Agent Graph (LangGraph)

```python
# ai/agents/graph.py
from langgraph.graph import StateGraph, END
from typing import TypedDict

class AgentState(TypedDict):
    task: str
    document_text: str | None
    extracted_data: dict | None
    validation_result: dict | None
    final_report: str | None
    error: str | None
    iteration_count: int

def build_multi_agent_graph(config: MultiAgentConfig) -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("coordinator",        coordinator_node)
    graph.add_node("document_reader",    document_reader_node)
    graph.add_node("knowledge_retriever",knowledge_retriever_node)
    graph.add_node("validator",          validator_node)
    graph.add_node("report_generator",   report_generator_node)

    graph.set_entry_point("coordinator")

    graph.add_conditional_edges("coordinator", route_from_coordinator, {
        "document_reader":     "document_reader",
        "knowledge_retriever": "knowledge_retriever",
        "validator":           "validator",
        "report_generator":    "report_generator",
        "end":                 END,
    })
    # Each agent returns to coordinator after completing its task
    graph.add_edge("document_reader",     "coordinator")
    graph.add_edge("knowledge_retriever", "coordinator")
    graph.add_edge("report_generator",    END)

    # Optional human-in-the-loop: interrupt after validator
    if config.require_human_approval:
        graph.add_edge("validator", "__interrupt__")
    else:
        graph.add_edge("validator", "coordinator")

    return graph.compile()
```

Max iterations are enforced inside `coordinator_node` by checking `state["iteration_count"]` against the configured maximum. Exceeding the limit transitions to an error state.

### 7.6 AI Token Usage Logging

Every LLM call is wrapped by a logging helper:

```python
# ai/usage.py
async def log_ai_usage(
    db: AsyncSession,
    context: ExecutionContext,
    provider: str,
    model: str,
    operation: str,
    usage: UsageStats,
    latency_ms: int,
):
    estimated_cost = calculate_cost(provider, model, usage)
    await db.execute(
        insert(AIUsageLog).values(
            organization_id=context.organization_id,
            workflow_run_id=context.run_id,
            provider=provider,
            model=model,
            operation=operation,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            estimated_cost_usd=estimated_cost,
            latency_ms=latency_ms,
        )
    )
```

---

## 8. Data Architecture

### 8.1 PostgreSQL Connection Strategy

The FastAPI application uses an **async connection pool** (SQLAlchemy + asyncpg):

```python
# core/database.py
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=20,           # 20 persistent connections per API instance
    max_overflow=10,        # 10 extra connections under burst load
    pool_pre_ping=True,     # Validate connection before use (handles failover)
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

The Celery worker uses **sync SQLAlchemy** with a smaller pool (workers are already parallel processes, not coroutines).

### 8.2 Tenant Isolation Pattern

The `TenantContextMiddleware` extracts `organization_id` from the JWT and stores it in `request.state`. The service layer always passes this value explicitly to DB queries — it is never read from the request inside a service function:

```python
# middleware.py — extracts and stores
async def dispatch(self, request: Request, call_next):
    token = extract_bearer_token(request)
    if token:
        claims = decode_access_token(token)
        request.state.organization_id = claims.get("org_id")
    return await call_next(request)

# workflows/service.py — always scoped
async def list_workflows(db: AsyncSession, organization_id: UUID) -> list[WorkflowResponse]:
    result = await db.execute(
        select(Workflow)
        .where(Workflow.organization_id == organization_id)
        .order_by(Workflow.created_at.desc())
    )
    return [WorkflowResponse.model_validate(w) for w in result.scalars()]
```

### 8.3 pgvector Index Configuration

The HNSW index on `document_chunks.embedding` is configured for cosine distance:

```sql
CREATE INDEX document_chunks_embedding_idx
  ON document_chunks
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);
```

- `m = 16`: number of bidirectional links per node (higher = better recall, more memory)
- `ef_construction = 64`: build-time search width (higher = better index quality, slower build)

Re-evaluate at 10M+ chunks. At that scale, filter-then-search (filter by `organization_id` first, then cosine search) may require a partial index per organization or migration to a dedicated vector DB.

### 8.4 Object Storage Layout

Files are stored under a keyed path that prevents enumeration and enforces organization scoping:

```
bucket/
  {organization_id}/
    documents/
      {document_id}/{original_filename}
    generated/
      {workflow_run_id}/{filename}
    avatars/
      {user_id}/avatar.{ext}
```

The `storage_key` column in the `documents` table stores the full path. Pre-signed URLs are generated on demand with a 15-minute expiry — the path is never exposed directly to clients.

### 8.5 Redis Key Namespace

```
session:{user_id}:{session_id}         → refresh token hash       TTL: 7d
rate:auth:{ip}                         → request count            TTL: 15m
rate:api:{api_key_id}                  → request count            TTL: 1m
run:status:{run_id}                    → current run status       TTL: 1h
ws:org:{org_id}                        → pub/sub channel          no TTL
cache:analytics:{org_id}:{date_key}    → serialized query result  TTL: 5m
celery:*                               → Celery broker/backend     varies
```

All keys are namespaced by concern. The `ws:org:{org_id}` channel is a Redis Pub/Sub channel, not a stored key — it has no TTL.

---

## 9. Real-Time Architecture

### 9.1 WebSocket Connection Lifecycle

```
Browser                FastAPI Instance          Redis
  │                          │                     │
  │── WS connect /ws ────────►                     │
  │   (token in query param)  │                     │
  │                           │ subscribe to        │
  │                           │ ws:org:{org_id} ───►│
  │                           │                     │
  │◄──── connected ───────────│                     │
  │                           │                     │
  ...  (workflow runs, AI tasks, events) ...
  │                           │◄── PUBLISH ─────────│
  │                           │    {type, data}      │
  │◄──── WS message ──────────│                     │
  │                           │                     │
  │── WS close ───────────────►                     │
  │                           │ unsubscribe ────────►│
```

### 9.2 WebSocket Connection Manager

```python
# notifications/websocket.py
class ConnectionManager:
    def __init__(self):
        # org_id → set of WebSocket connections
        self._connections: dict[UUID, set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, org_id: UUID):
        await websocket.accept()
        self._connections[org_id].add(websocket)

    def disconnect(self, websocket: WebSocket, org_id: UUID):
        self._connections[org_id].discard(websocket)

    async def broadcast_to_org(self, org_id: UUID, message: dict):
        dead = set()
        for ws in self._connections.get(org_id, set()):
            try:
                await ws.send_json(message)
            except WebSocketDisconnect:
                dead.add(ws)
        self._connections[org_id] -= dead

manager = ConnectionManager()
```

### 9.3 Redis Pub/Sub Subscriber

Each FastAPI instance runs a background task (started in the lifespan) that subscribes to all organization channels and routes messages to the local `ConnectionManager`:

```python
# notifications/websocket.py
async def redis_subscriber(redis: Redis):
    pubsub = redis.pubsub()
    await pubsub.psubscribe("ws:org:*")   # wildcard — subscribe to all org channels
    async for message in pubsub.listen():
        if message["type"] == "pmessage":
            channel: str = message["channel"]          # "ws:org:{org_id}"
            org_id = UUID(channel.split(":")[-1])
            data = json.loads(message["data"])
            await manager.broadcast_to_org(org_id, data)
```

### 9.4 Publishing Events from Workers

Celery workers publish events to Redis after each significant state change:

```python
# worker/tasks/workflow_execution.py
def publish_event(org_id: UUID, event: dict):
    redis_client.publish(f"ws:org:{org_id}", json.dumps(event))

# Called after each node completion:
publish_event(context.organization_id, {
    "type": "node.completed",
    "run_id": str(context.run_id),
    "node_id": str(node.id),
    "status": "completed",
    "output_preview": truncate(output, 500),
})
```

### 9.5 WebSocket Message Types

| Type | Trigger | Payload |
|------|---------|---------|
| `run.started` | WorkflowRun status → running | `{run_id, workflow_id}` |
| `node.started` | Node execution begins | `{run_id, node_id}` |
| `node.completed` | Node execution succeeds | `{run_id, node_id, output_preview}` |
| `node.failed` | Node execution fails | `{run_id, node_id, error}` |
| `run.completed` | WorkflowRun status → completed | `{run_id, duration_ms}` |
| `run.failed` | WorkflowRun status → failed | `{run_id, error}` |
| `notification.new` | Any new Notification created | `{id, type, title, body}` |

---

## 10. Security Architecture

### 10.1 Authentication Flow

```
POST /api/v1/auth/login {email, password}
  │
  ▼ Rate limit check (5 req / 15min per IP)
  ▼ Load user by email
  ▼ verify_password(plain, hashed)  ← bcrypt, cost=12
  ▼ Check is_verified == true
  ▼ Create session_id (UUID)
  ▼ access_token  = JWT {user_id, org_id, session_id, exp: +15min}
  ▼ refresh_token = opaque UUID stored as bcrypt hash in Redis
    Key: session:{user_id}:{session_id}
    Value: bcrypt(refresh_token)
    TTL: 7 days
  ▼ Return access_token in body, refresh_token in HttpOnly cookie
```

```
POST /api/v1/auth/refresh
  │ (refresh token sent automatically via cookie)
  ▼ Read session_id from refresh token (JWT-encoded reference)
  ▼ Load Redis key: session:{user_id}:{session_id}
  ▼ bcrypt verify(incoming_token, stored_hash)
  ▼ Delete old Redis key (rotation: old token immediately invalid)
  ▼ Issue new access_token + new refresh_token
  ▼ Store new refresh_token hash in Redis
```

### 10.2 API Key Authentication

```
Incoming request: Authorization: Bearer bpa_sk_xxxxxxxxxxxx
  │
  ▼ Identify as API key (prefix "bpa_sk_")
  ▼ Load all non-revoked api_keys for all organizations
    (small set, cached in Redis for 60s)
  ▼ For each candidate: bcrypt.verify(incoming, key_hash)
    (early-exit on first match)
  ▼ Check key is not expired (expires_at)
  ▼ Check key is not revoked (revoked_at)
  ▼ Verify requested endpoint is within key's scopes
  ▼ Load organization from key record
  ▼ Inject organization_id into request.state
  ▼ Update last_used_at (background task, non-blocking)
```

### 10.3 Request Security Middleware Stack

Every request passes through this stack in order (outermost to innermost):

```
1. Nginx                     SSL termination, HSTS, HTTP→HTTPS redirect
                             Connection-level rate limit (nginx limit_req)

2. CORSMiddleware            Restrict origins to known frontend domains

3. RequestLoggingMiddleware  Assign request_id, log method/path/IP, log response

4. RateLimitMiddleware       Redis sliding window per (IP, endpoint_category)
                             Returns 429 on breach

5. Auth resolution           Extract + validate JWT or API key
                             Populate request.state.user_id, .org_id, .role
                             Returns 401 if invalid, 403 if insufficient role

6. TenantContextMiddleware   Confirm organization_id is set
                             Verify org is active (not suspended/deleted)

7. Route handler             Business logic (role already verified by Depends)

8. AuditLogMiddleware        On state-changing methods (POST/PUT/PATCH/DELETE):
   (post-response)           Write async audit log entry (fire-and-forget)
```

### 10.4 Secret Storage

```python
# core/security.py
from cryptography.fernet import Fernet

def encrypt_secret(plaintext: str, key: bytes) -> str:
    """AES-128 in CBC mode via Fernet. Used for OAuth tokens, third-party API keys."""
    f = Fernet(key)
    return f.encrypt(plaintext.encode()).decode()

def decrypt_secret(ciphertext: str, key: bytes) -> str:
    f = Fernet(key)
    return f.decrypt(ciphertext.encode()).decode()
```

The encryption key (`ENCRYPTION_KEY`) is a 32-byte URL-safe base64 string set as an environment variable. In production, it is fetched from HashiCorp Vault at startup and never written to disk or logs.

### 10.5 Role Hierarchy and RBAC

The platform has two completely separate role scopes. A user holds roles in exactly one scope — never both. This is enforced at the token level: the JWT claim `scope` is either `"platform"` or `"org"`.

```
┌─────────────────────────────────────────────────────────────────┐
│                      AutoFlow AI Platform                        │
│                                                                  │
│   PLATFORM SCOPE                    ORGANIZATION SCOPE           │
│   (AutoFlow employees)              (Customer companies)         │
│                                                                  │
│   Super Admin                       Organization Owner           │
│   Platform Admin                    Organization Admin           │
│   Support Engineer                  Manager                      │
│   DevOps Engineer                   Analyst                      │
│   Billing Manager                   Employee                     │
│                                     Viewer                       │
└─────────────────────────────────────────────────────────────────┘
```

#### Platform Roles (AutoFlow team)

| Role | Responsibilities | Cannot Do |
|------|-----------------|-----------|
| **Super Admin** | All platform actions; manage other platform users; toggle feature flags | — |
| **Platform Admin** | Manage subscriptions, suspend/reinstate orgs, view platform health, manage billing, view system logs, monitor AI usage | Edit customer workflows without explicit support grant |
| **Support Engineer** | View any org's data (read-only), grant temporary support access to a specific org for up to 24h | Suspend orgs, manage billing, access system logs |
| **DevOps Engineer** | Monitor worker queues, view DB health, Redis stats, deploy new versions | Access customer data, manage subscriptions |
| **Billing Manager** | View and manage subscriptions, revenue, invoices | Access customer data, system logs |

#### Organization Roles (Customer companies)

| Role | Responsibilities | Cannot Do |
|------|-----------------|-----------|
| **Organization Owner** | All org actions; delete the organization; transfer ownership | Access other organizations |
| **Organization Admin** | Invite/remove users, assign roles, create workflows, manage integrations, configure API keys, manage documents, view audit logs, configure AI models, manage departments | Delete the organization |
| **Manager** | Create and run workflows, view execution history, manage documents in their department | Invite users, manage integrations, configure API keys |
| **Analyst** | Create and run workflows, view execution history, query knowledge base | Manage users, manage integrations |
| **Employee** | Trigger existing published workflows, view own run history | Create or edit workflows |
| **Viewer** | Read-only: view workflows, execution history, analytics | Trigger workflows, create anything |

#### Tenant Isolation Guarantee

Company A can never read or write Company B's data. This is enforced at three independent layers:

1. **JWT claim layer** — `org_id` is embedded in the token; a user cannot claim a different org.
2. **Middleware layer** — `TenantContextMiddleware` sets `request.state.organization_id` from the verified JWT. Route handlers never accept `org_id` from the request body.
3. **Query layer** — every service function receives `organization_id` as a parameter and includes it in every `WHERE` clause. There is no "list all" query that bypasses this filter.

Platform users accessing a customer org's data must have an explicit `SupportAccessGrant` row (created by a Support Engineer, TTL 24h). Without it, `/api/v1/orgs/{org_id}/*` returns 403 even for platform users.

#### Backend RBAC Dependencies

Two separate dependency chains enforce the two scopes:

```python
# platform/dependencies.py
async def get_platform_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> PlatformUser:
    claims = decode_access_token(token)
    if claims.get("scope") != "platform":
        raise ForbiddenError("Platform access required")
    return await db.get(PlatformUser, claims["user_id"])

def require_platform_role(*roles: str):
    async def dependency(user: PlatformUser = Depends(get_platform_user)) -> PlatformUser:
        if user.role not in roles:
            raise ForbiddenError(f"Requires one of: {roles}")
        return user
    return dependency

# auth/dependencies.py (existing, updated)
def require_org_role(*roles: str):
    async def dependency(member: OrgMember = Depends(get_current_member)) -> OrgMember:
        # Role hierarchy: owner > admin > manager > analyst > employee > viewer
        ROLE_RANK = {"owner": 6, "admin": 5, "manager": 4, "analyst": 3, "employee": 2, "viewer": 1}
        min_rank = min(ROLE_RANK[r] for r in roles)
        if ROLE_RANK.get(member.role, 0) < min_rank:
            raise ForbiddenError(f"Requires one of: {roles}")
        return member
    return dependency
```

#### Platform vs. Organization Endpoint Separation

```
/api/v1/platform/*     → require_platform_role(...)   — AutoFlow team only
/api/v1/orgs/*         → require_org_role(...)         — customer org members only
/api/v1/workflows/*    → require_org_role("analyst")   — minimum analyst rank
/api/v1/settings/*     → require_org_role("admin")     — minimum admin rank
```

A platform user hitting `/api/v1/workflows/` gets 403. A customer org admin hitting `/api/v1/platform/organizations` gets 403. The two namespaces are mutually exclusive.

---

## 11. Infrastructure Architecture

### 11.1 Docker Compose (Development)

```yaml
# docker-compose.yml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: bpa_dev
      POSTGRES_USER: bpa
      POSTGRES_PASSWORD: bpa_dev_password
    volumes:
      - pg_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - minio_data:/data
    ports:
      - "9000:9000"   # S3 API
      - "9001:9001"   # MinIO Console

  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - ./backend:/app
    env_file: .env
    ports:
      - "8000:8000"
    depends_on: [db, redis, minio]

  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.worker
    command: celery -A worker.celery_app worker --loglevel=info --concurrency=4
    volumes:
      - ./backend:/app
    env_file: .env
    depends_on: [db, redis, minio]

  beat:
    build:
      context: ./backend
      dockerfile: Dockerfile.worker
    command: celery -A worker.celery_app beat --loglevel=info
    env_file: .env
    depends_on: [redis]

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    command: npm run dev
    volumes:
      - ./frontend:/app
      - /app/node_modules
    ports:
      - "3000:3000"

  flower:
    build:
      context: ./backend
      dockerfile: Dockerfile.worker
    command: celery -A worker.celery_app flower --port=5555
    env_file: .env
    ports:
      - "5555:5555"   # Celery task monitor UI
    depends_on: [redis]

  nginx:
    image: nginx:alpine
    volumes:
      - ./infra/nginx/conf.d:/etc/nginx/conf.d
    ports:
      - "80:80"
    depends_on: [api, frontend]
```

### 11.2 Nginx Configuration

```nginx
# infra/nginx/conf.d/default.conf
upstream api {
    server api:8000;
}

upstream frontend {
    server frontend:3000;
}

server {
    listen 80;

    # WebSocket upgrade
    map $http_upgrade $connection_upgrade {
        default upgrade;
        ''      close;
    }

    # API requests
    location /api/ {
        proxy_pass http://api;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Request-ID      $request_id;
    }

    # WebSocket
    location /ws {
        proxy_pass http://api;
        proxy_http_version 1.1;
        proxy_set_header Upgrade    $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_read_timeout 3600s;
    }

    # Webhook receivers
    location /webhooks/ {
        proxy_pass http://api;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # All other requests → Next.js
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
    }
}
```

### 11.3 CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
name: CI

on:
  pull_request:
    branches: [main]

jobs:
  backend-lint:
    if: contains(github.event.pull_request.changed_files, 'backend/')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install ruff mypy
      - run: ruff check backend/
      - run: mypy backend/app

  backend-test:
    needs: backend-lint
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env: { POSTGRES_PASSWORD: test, POSTGRES_DB: bpa_test }
      redis:
        image: redis:7-alpine
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r backend/requirements.txt
      - run: pytest backend/tests/ --cov=app --cov-report=xml --cov-fail-under=80

  frontend-lint:
    if: contains(github.event.pull_request.changed_files, 'frontend/')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: cd frontend && npm ci
      - run: cd frontend && npm run lint
      - run: cd frontend && npx tsc --noEmit

  frontend-test:
    needs: frontend-lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: cd frontend && npm ci && npm test -- --coverage
```

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build + push API image
        run: |
          docker build -t ghcr.io/${{ github.repository }}/api:${{ github.sha }} ./backend
          docker push ghcr.io/${{ github.repository }}/api:${{ github.sha }}
      - name: Build + push Worker image
        run: |
          docker build -f backend/Dockerfile.worker \
            -t ghcr.io/${{ github.repository }}/worker:${{ github.sha }} ./backend
          docker push ghcr.io/${{ github.repository }}/worker:${{ github.sha }}
      - name: Build + push Frontend image
        run: |
          docker build -t ghcr.io/${{ github.repository }}/frontend:${{ github.sha }} ./frontend
          docker push ghcr.io/${{ github.repository }}/frontend:${{ github.sha }}

  deploy-staging:
    needs: build-and-push
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - name: Deploy to staging
        run: |
          ssh deploy@$STAGING_HOST "
            docker pull ghcr.io/${{ github.repository }}/api:${{ github.sha }} &&
            docker pull ghcr.io/${{ github.repository }}/worker:${{ github.sha }} &&
            docker pull ghcr.io/${{ github.repository }}/frontend:${{ github.sha }} &&
            docker compose -f docker-compose.prod.yml up -d --no-deps api worker frontend
          "

  deploy-production:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment: production          # requires manual approval in GitHub
    steps:
      - name: Deploy to production (rolling)
        run: |
          ssh deploy@$PROD_HOST "docker compose -f docker-compose.prod.yml up -d --no-deps \
            --scale api=2 --scale worker=4 api worker frontend"
```

### 11.4 Scaling Playbook

| Signal | Action |
|--------|--------|
| API P95 latency > 400ms | Add FastAPI instances (`--scale api=N`) |
| Celery queue depth > 500 | Add worker instances (`--scale worker=N`) |
| DB read latency > 100ms | Add PostgreSQL read replica; route analytics queries to replica |
| Redis memory > 80% | Increase Redis instance size; evaluate Redis Cluster |
| pgvector cosine search > 50ms P95 | Increase HNSW `ef_search`; evaluate per-org partial indexes |

---

## 12. Inter-Component Communication

### 12.1 Communication Matrix

| From → To | Protocol | Auth | Sync/Async |
|-----------|----------|------|-----------|
| Browser → Nginx | HTTPS / WSS | JWT cookie | Sync |
| Nginx → FastAPI | HTTP (internal) | — | Sync |
| Nginx → Next.js | HTTP (internal) | — | Sync |
| FastAPI → PostgreSQL | asyncpg | DB credentials | Sync (async pool) |
| FastAPI → Redis | redis.asyncio | — | Sync (async) |
| FastAPI → MinIO/S3 | HTTPS | Access key | Sync (async) |
| FastAPI → Celery | Redis (enqueue) | — | Async (fire-and-forget) |
| Celery → PostgreSQL | psycopg2 | DB credentials | Sync |
| Celery → Redis | redis-py | — | Sync |
| Celery → MinIO/S3 | HTTPS | Access key | Sync |
| Celery → LLM APIs | HTTPS | API key | Sync (with timeout) |
| Celery → Redis pub/sub | redis-py publish | — | Sync |
| FastAPI → Redis pub/sub | redis.asyncio subscribe | — | Async |
| FastAPI → Browser | WebSocket | JWT | Async (push) |

### 12.2 API Versioning

All routes are prefixed `/api/v1/`. When breaking changes are required:
- New routes are added under `/api/v2/`
- `/api/v1/` endpoints are maintained with deprecation headers for one release cycle
- The frontend always targets the latest version

---

## 13. Error Handling Strategy

### 13.1 Error Classification

| Layer | Error Type | Handling |
|-------|-----------|---------|
| FastAPI router | `RequestValidationError` | 422 with field-level detail |
| Service layer | `AppException` subclass | Mapped to HTTP status by exception handler |
| Node execution | `NodeExecutionError` | Celery retry → eventual `ExecutionLog` failure entry |
| External API | `httpx.TimeoutException` | Raised as `ExternalServiceError` → retry |
| LLM provider | `RateLimitError` / timeout | Raised as `ExternalServiceError` → retry with longer backoff |
| Database | `IntegrityError` | Caught in service, raised as `ConflictError` (409) |
| Database | `OperationalError` | Propagated to Celery → retry (transient DB failure) |

### 13.2 Error Response Format

All API errors return a consistent JSON body:

```json
{
  "error": {
    "code": "WORKFLOW_NOT_FOUND",
    "message": "Workflow f3a1... does not exist or you do not have access.",
    "request_id": "req_abc123",
    "details": {}
  }
}
```

### 13.3 Celery Error Propagation

```
Node raises exception
  └── WorkflowEngine catches it
        └── Updates ExecutionLog: status=failed, error_message=str(e)
              └── Publishes WS event: {type: "node.failed", error}
                    └── Re-raises to Celery task
                          └── Celery retries (exponential backoff)
                                └── On max retries exceeded:
                                      └── Updates WorkflowRun: status=failed
                                            └── Calls create_notification()
                                                  └── Calls send_email_task() if configured
```

---

## 14. Testing Architecture

### 14.1 Test Pyramid

```
                    ┌──────────────┐
                    │  E2E Tests   │  (Playwright — UI + API together)
                    │  (minimal)   │  Test the 3 most critical user journeys
                    └──────┬───────┘
               ┌───────────┴────────────┐
               │   Integration Tests    │  Real DB + Redis in Docker
               │   (~30% of tests)      │  Test API endpoints end-to-end
               └───────────┬────────────┘
          ┌─────────────────┴──────────────────┐
          │          Unit Tests                 │  Mock DB + external services
          │          (~70% of tests)            │  Test service logic + node handlers
          └─────────────────────────────────────┘
```

### 14.2 Key Test Fixtures

```python
# tests/conftest.py
@pytest.fixture
async def db():
    """Async DB session against a test database. Rolls back after each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        yield session
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
def org_factory(db):
    """Creates an organization + owner user."""
    async def _factory(name="Test Org") -> tuple[Organization, User, str]:
        org = Organization(name=name, slug=slugify(name), plan="free")
        user = User(email=f"{slug}@test.com", hashed_password=hash_password("pw"))
        db.add_all([org, user])
        await db.commit()
        member = OrgMember(organization_id=org.id, user_id=user.id, role="owner")
        db.add(member)
        await db.commit()
        token = create_access_token({"user_id": str(user.id), "org_id": str(org.id)})
        return org, user, token
    return _factory

@pytest.fixture
def client(db):
    """FastAPI test client with DB override."""
    app.dependency_overrides[get_db] = lambda: db
    return AsyncClient(app=app, base_url="http://test")
```

### 14.3 Critical Test Cases

| Area | Test |
|------|------|
| Tenant isolation | User from Org A cannot read Org B's workflows via any API endpoint |
| Auth | Expired access token returns 401; valid refresh token returns new token pair |
| Workflow engine | Condition node routes to correct branch; failed node retried with backoff |
| Node registry | Unregistered node type raises clear error; new node type registered via decorator works |
| RAG | Query returns chunks only from querying organization's documents |
| AI token logging | Every LLM call results in an `ai_usage_log` row with correct token counts |
| File access | Pre-signed URL expires; file from another org returns 403 |

---

## 15. Component Dependency Map

```
                            core/
                        (no module imports)
                             │
              ┌──────────────┼──────────────────────┐
              │              │                        │
           auth/        organizations/            files/
              │              │                        │
              └──────────────┼────────────────────────┘
                             │
                         workflows/
                        (nodes/registry)
                             │
                         execution/
                        (engine.py)
                             │
                   ┌─────────┼──────────┐
                   │                    │
                  ai/              notifications/
              (providers/          (websocket.py
               chains/              email.py)
               rag/
               agents/)
                             │
                         analytics/
                      (read-only queries,
                       no write operations)
```

**Rule:** Arrows point downward only. Lower modules never import from higher modules. `analytics/` imports execution and AI schemas for aggregation queries but does not call their services. `execution/engine.py` imports from `workflows/nodes/registry` but not from `workflows/service.py`.

---

*End of Architecture Document v1.0.0*

*All architectural decisions recorded here are binding. Changes require a new ADR entry and version increment. This document is the authoritative reference for implementation.*
