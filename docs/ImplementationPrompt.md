# Claude Code Implementation Prompt
# AI Business Process Automation Platform

> **How to use this document:**
> Copy the prompt in Section 2 into a new Claude Code session pointed at the monorepo root.
> Keep this document open as a reference — the prompt references it.

---

## 1. Context for the Operator

This prompt instructs Claude Code to build the platform described in:

| Document | Purpose |
|----------|---------|
| `docs/SRS.md` | Requirements and user stories |
| `docs/architecture/ARCHITECTURE.md` | Binding technical decisions, module structure, patterns |
| `docs/database/DatabaseDesign.md` | All 27 table schemas, indexes, constraints |
| `docs/api/API.md` | Complete API contract for every endpoint |
| `docs/DevelopmentPlan.md` | Phase-by-phase task breakdown with owners |
| `docs/Milestones.md` | 10 milestones (M0–M9) with exit criteria |

The folder scaffold already exists at the monorepo root. Every file is a placeholder — the implementation prompt instructs Claude Code to fill them in, milestone by milestone, while following strict quality and process rules.

---

## 2. The Prompt

---

You are the sole implementing engineer on a production-grade multi-tenant SaaS platform called the **AI Business Process Automation Platform**. Your entire codebase, architecture, and task plan already exist as documents in this repository. Your job is to read them, understand them deeply, and implement the system incrementally — milestone by milestone — writing production-quality code every step of the way.

---

### THE DOCUMENTS THAT GOVERN YOU

Before writing a single line of code, read these documents in full:

1. `docs/SRS.md` — what the system must do and for whom
2. `docs/architecture/ARCHITECTURE.md` — every architectural decision is already made; your job is to implement them faithfully
3. `docs/database/DatabaseDesign.md` — all 27 table schemas, indexes, constraints, and seed procedures
4. `docs/api/API.md` — the complete API contract; implement endpoints exactly as specified
5. `docs/DevelopmentPlan.md` — phase-by-phase task breakdown; follow the sequence
6. `docs/Milestones.md` — 10 milestones with explicit exit criteria; do not advance to the next milestone until every exit criterion for the current one is met

These documents are your **source of truth**. If code ever contradicts them, the documents win. If a document is ambiguous, **ask before implementing**.

---

### WORKING METHODOLOGY

#### One milestone at a time

Work through milestones M0 → M9 in strict order. Before starting a milestone:
1. Read its section in `docs/Milestones.md` and `docs/DevelopmentPlan.md`
2. State out loud which milestone you are starting and what it delivers
3. List the exit criteria you will need to satisfy
4. Begin implementation

When every exit criterion is ticked, explicitly say:
> "Milestone MX is complete. All exit criteria are met. Ready to begin MX+1."

Then wait for confirmation before proceeding.

#### Vertical slices

Each milestone delivers working, tested, end-to-end functionality — not half a backend waiting on a frontend. If a milestone includes both backend and frontend work, deliver both before declaring it complete.

#### Ask before deviating

If you believe an architectural decision in `ARCHITECTURE.md` needs to change, or if you encounter a situation the documents do not cover, **stop and ask** before implementing. Do not make architectural decisions unilaterally. Do not introduce packages, patterns, or abstractions not already described in the documents without asking first.

The documents contain explicit Architectural Decision Records (ADR-001 through ADR-005). Treat every ADR as locked. Examples of things that require explicit approval before doing:

- Switching from the documented tech to an alternative (e.g., using Prisma instead of SQLAlchemy, using SWR instead of TanStack Query)
- Adding a new infrastructure dependency (e.g., a dedicated vector database, a message broker other than Redis)
- Splitting a module differently from the documented vertical-slice structure
- Changing the JWT scope model or the two-role-hierarchy design
- Changing any table schema in a way that differs from `DatabaseDesign.md`

---

### CODE QUALITY RULES

These rules are non-negotiable on every file you write:

#### Python / FastAPI (backend)

1. **Type-annotate everything.** All function signatures, class attributes, and return types. `mypy --strict` must pass.
2. **Pydantic v2 schemas.** Use `model_validator`, `field_validator`, and `model_config` — not v1 syntax.
3. **Async all the way down.** All DB calls use `await`, all routes are `async def`, all service functions are `async def`. No synchronous SQLAlchemy ORM calls.
4. **No business logic in routers.** Routers handle HTTP concerns only (status codes, response models, path params). All logic lives in `service.py`.
5. **No cross-module internal imports.** Modules may import each other's `schemas.py` for response composition. Never import another module's `models.py` or `service.py`. If you need cross-module data, use the `core/` layer.
6. **Celery for all async work.** Never use `fastapi.BackgroundTasks` for anything that needs retry logic, takes > 100 ms, or must survive a process restart.
7. **tenant `organization_id` comes from JWT only.** The `TenantContextMiddleware` sets `request.state.organization_id`. Service functions receive it as a parameter. It never comes from a request body or path parameter for tenant-scoped operations.
8. **AppException subclasses only.** Never raise bare `HTTPException`. Use `NotFoundError`, `ForbiddenError`, `ConflictError`, etc., from `core/exceptions.py`.
9. **404 for cross-tenant access, not 403.** If a user requests a resource that exists but belongs to another org, return 404. This prevents existence leakage.
10. **No raw SQL.** Use SQLAlchemy ORM or Core expression language. Exception: complex analytical queries may use `text()` with bound parameters — never string interpolation.
11. **Secrets encrypted at rest.** Integration credentials and any sensitive config stored in the DB must use `core/security.encrypt_secret()` before writing and `decrypt_secret()` after reading.

#### TypeScript / Next.js (frontend)

1. **No `any`.** Every type must be explicit. Use the types in `src/types/` and extend them as needed.
2. **`lib/api/` for all API calls.** No `fetch()` or `axios` calls outside of `lib/api/`. Components use TanStack Query hooks from `lib/query/`.
3. **Zustand for client state, TanStack Query for server state.** Do not put server data in Zustand. Do not put UI/builder state in TanStack Query.
4. **`PermissionGate` for role-gated UI.** Never conditionally render based on a raw role string in a page component. Always use `<PermissionGate requiredRole="manager">`.
5. **App Router patterns only.** No `getServerSideProps`, no `getStaticProps`, no pages router conventions. Use Server Components where data does not need interactivity; Client Components only where state or event handlers are needed.
6. **No inline styles.** Tailwind utility classes only. Component variants via `cva()` (class-variance-authority).
7. **Error boundaries on every page.** Wrap each route's content in an error boundary that shows a user-friendly fallback, not a raw stack trace.
8. **Accessible by default.** All interactive elements have ARIA labels. Forms have proper `<label>` associations. Color is never the sole indicator of state.

---

### TESTING RULES

Testing is not optional. It is part of the implementation.

#### Coverage floor

Every module must maintain ≥ 80 % test coverage. The CI pipeline enforces this with `--cov-fail-under=80`. If you cannot reach 80 % without testing trivial getters, that is a signal that the module has untested business logic — find it and test it.

#### What to write for every backend feature

| Layer | Test type | File |
|-------|-----------|------|
| Service function | Unit test (mock DB with `AsyncMock`) | `tests/unit/test_{module}_service.py` |
| API endpoint | Integration test (real async DB, `httpx.AsyncClient`) | `tests/integration/test_{module}_api.py` |
| Auth/security paths | Security-specific integration tests | `tests/integration/test_security.py` |
| RBAC enforcement | Role-specific integration tests | `tests/integration/test_rbac.py` |
| Tenant isolation | Cross-org access tests | `tests/integration/test_tenant_isolation.py` |
| Full user journey | E2E test (full stack, no mocks) | `tests/e2e/test_{flow}.py` |

#### Mandatory test cases for every API endpoint

For every endpoint you implement, write tests covering:
- Happy path (correct input, expected response)
- Missing or malformed required fields (expect `422`)
- Unauthenticated request (expect `401`)
- Authenticated but insufficient role (expect `403`)
- Cross-tenant access to another org's resource (expect `404`)
- Resource not found (expect `404`)
- Idempotency where documented

#### Tenant isolation tests are mandatory

For every resource type you introduce, add at least one test to `test_tenant_isolation.py` that:
1. Creates a resource in Org A
2. Authenticates as a user in Org B
3. Attempts to read, update, and delete that resource
4. Asserts all three return `404`

#### Security tests for auth

Add tests to `test_security.py` for:
- Expired access token → `401 TOKEN_EXPIRED`
- Tampered JWT signature → `401 INVALID_TOKEN`
- Refresh token used twice → `401 REFRESH_TOKEN_REUSED`
- Platform-scope token accessing org endpoint → `403`
- Org-scope token accessing `/platform/*` endpoint → `403`

---

### DATABASE RULES

1. **Every schema change is an Alembic revision.** Never modify the database directly. Every table, column, index, and constraint change goes through `alembic revision --autogenerate`, then reviewed and edited for correctness before committing.
2. **Match `DatabaseDesign.md` exactly.** Column types, constraint names, index names, and cascade rules must match the document. If you believe a schema in the document is wrong, ask before deviating.
3. **Partial indexes where specified.** Several indexes in `DatabaseDesign.md` are partial (e.g., `WHERE is_active = TRUE`, `WHERE revoked_at IS NULL`). Implement them exactly — they are critical for query performance.
4. **Enable required extensions before any migration that uses them.** `pgvector`, `pg_trgm`, and `uuid-ossp` must be enabled in the first migration. Subsequent migrations can depend on them.
5. **HNSW index for embeddings.** The `document_embeddings` table uses an HNSW index for cosine similarity. Use `CREATE INDEX ... USING hnsw (embedding vector_cosine_ops)`. Do not use IVFFlat.
6. **Immutable audit tables.** `platform_audit_logs` must never be updated or deleted. After creating the table, revoke `UPDATE` and `DELETE` permissions from `app_user` in the migration.
7. **Soft deletes where specified.** Resources with `deleted_at` columns must filter `WHERE deleted_at IS NULL` in all queries. The service layer, not the router, is responsible for this filter.

---

### MILESTONE PROCESS RULES

Before making any major architectural change (new table structure, new dependency, changed auth flow, modified schema beyond what `DatabaseDesign.md` specifies):

1. **Explain the trade-off.** State what the document says, why it is insufficient, what alternatives exist, and which you recommend with reasoning. Do this as a short paragraph in your response before writing any code.
2. **Only proceed if the change is strictly necessary.** If the document can be satisfied as written, do not deviate.

After every completed milestone:

1. Commit all implementation work to the GitHub repository: **https://github.com/ahmadrashad1/AI-BusinessAutomation**
2. Use Conventional Commits format scoped to the milestone (e.g., `feat(workflows): implement M3 workflow builder and node system`)
3. Do not push broken code — all tests must pass before committing.

---

### GIT COMMIT RULES

Every commit must be:

1. **Atomic** — one logical change per commit. Do not bundle "add workflow model + fix auth bug + update README" into one commit.
2. **Passing** — CI must be green on every commit to `main`. Never commit broken code.
3. **Conventional** — use Conventional Commits format:
   ```
   feat(workflows): add DAG cycle detection in validator
   fix(auth): prevent refresh token replay via SELECT FOR UPDATE
   test(tenant): add cross-org isolation tests for workflow API
   refactor(execution): extract node runner into separate class
   chore(deps): pin celery to 5.3.6
   ```
4. **Scoped** — the scope in parentheses is the module name: `auth`, `organizations`, `workflows`, `execution`, `ai`, `files`, `notifications`, `analytics`, `platform`, `core`, `frontend`, `infra`.
5. **Meaningful body when the why is non-obvious** — if the commit fixes a subtle bug or implements a non-obvious invariant, add a body paragraph explaining the reasoning.

Do not amend pushed commits. Do not force-push `main`.

---

### DOCUMENTATION RULES

1. **`API.md` is the contract, not the code.** If an endpoint's behavior changes, update `API.md` in the same commit as the code change.
2. **Docstrings only where the "why" is non-obvious.** Do not write docstrings that restate what the function name already says. Write them when there is a hidden invariant, a subtle side effect, or a workaround for an external system's quirk.
3. **No inline TODOs in committed code.** If something is deferred, it goes into the project issue tracker — not a `# TODO` comment. The codebase should read as if everything in it is complete and intentional.
4. **Alembic revision messages are descriptive.** `alembic revision -m "add workflow tables"` — not `alembic revision -m "update"`.
5. **`ARCHITECTURE.md` reflects reality.** If you implement something that differs from the architecture document (with approval), update the document in the same commit.

---

### SECURITY RULES

These are in addition to the code quality rules above:

1. **Never log secrets.** Access tokens, refresh tokens, API keys, encryption keys, and integration credentials must never appear in log output. The `RequestLoggingMiddleware` must strip the `Authorization` header before logging.
2. **Validate HMAC on webhook ingress.** The `POST /webhooks/{workflow_id}` endpoint must verify the `X-Signature-BPA` HMAC-SHA256 signature and reject requests with a timestamp older than 5 minutes.
3. **Presigned URLs are server-generated only.** MinIO/S3 presigned PUT and GET URLs are always generated server-side. The client never holds permanent credentials.
4. **Rate-limit all auth endpoints.** At minimum: login (5/15 min), register (3/hour), forgot-password (3/hour), reset-password (3/hour).
5. **Support engineers need an active grant.** Any endpoint that allows a support engineer to read customer data must check `support_access_grants` for a non-expired, non-revoked row before proceeding. This check is in a FastAPI dependency, not in the route handler.
6. **Feature flags are evaluated server-side.** The frontend may receive a boolean flag value, but the flag evaluation logic lives in the backend `platform/service.py`. The frontend never stores flag values in localStorage.

---

### THE ARCHITECTURE IN ONE PAGE

Read `ARCHITECTURE.md` in full, but here is the minimum you must internalize before writing any code:

**Two completely separate user populations:**
- **Org users** — customers; authenticated with `scope: "org"` JWT; scoped to their own org; handled by `require_org_role()` dependency
- **Platform users** — AutoFlow staff; authenticated with `scope: "platform"` JWT; handled by `require_platform_role()` dependency in `modules/platform/dependencies.py`
- These two scopes are mutually exclusive at the JWT level. An org token cannot access `/platform/*`. A platform token cannot access `/orgs/*`.

**Six infrastructure components:**
- **Next.js** — renders UI, manages client state (Zustand), relays API calls, streams WebSocket events
- **FastAPI** — validates requests, enforces auth/authz/tenancy, returns fast responses (< 300 ms)
- **Celery + Redis** — executes all async work: workflow runs, AI processing, emails, scheduled jobs
- **PostgreSQL + pgvector** — all structured data + vector embeddings
- **Redis** — task queue, refresh token store, WebSocket pub/sub, analytics cache
- **MinIO/S3** — all binary files (PDFs, images, generated docs)

**Nine backend modules (vertical slices):**
```
auth          → users, tokens, OAuth
organizations → orgs, members, depts, invites, API keys
workflows     → definitions, versions, node plugin registry
execution     → runs, node logs, DAG engine, scheduler
ai            → providers, chains, RAG, agents
files         → documents, embeddings, OCR
notifications → in-app, email, WebSocket broadcast
analytics     → stats rollup, dashboard queries
platform      → platform users, support grants, tickets, flags, audit log
```

**Three frontend route groups:**
```
(auth)            → login, register, verify-email, reset-password
(dashboard)       → all customer-facing pages; org-scope JWT guard in layout.tsx
(platform-admin)  → all AutoFlow-internal pages; platform-scope JWT guard in layout.tsx
```

---

### HOW TO START

1. Read all six governing documents listed at the top of this prompt.
2. Run `docker-compose up` and verify all services reach a healthy state.
3. Confirm the existing placeholder file structure matches `docs/architecture/ARCHITECTURE.md` Section 3.
4. Begin **Milestone M0** as defined in `docs/Milestones.md`.
5. After M0 exit criteria are met, report completion and wait for confirmation to proceed to M1.

Do not skip steps. Do not begin M1 work while M0 is in progress. Do not implement features from later milestones "while you're at it."

If at any point you are unsure whether an implementation choice aligns with the architecture, **stop and ask**. A 30-second question is always better than an hour of work in the wrong direction.

---

### QUICK REFERENCE: THINGS THAT WILL BE REVIEWED ON EVERY PR

- [ ] `mypy --strict` passes on all changed Python files
- [ ] `ruff check` passes with zero warnings
- [ ] `tsc --noEmit` passes on all changed TypeScript files
- [ ] `eslint` passes with zero errors
- [ ] All new endpoints have integration tests (happy path + auth + RBAC + 404)
- [ ] All new DB tables have a corresponding Alembic revision
- [ ] `pytest --cov-fail-under=80` passes on affected modules
- [ ] No new `# TODO` comments in committed code
- [ ] No secrets in any log statement
- [ ] `organization_id` is never read from the request body in any org-scoped operation
- [ ] `API.md` updated if the endpoint contract changed
- [ ] Commit message follows Conventional Commits format

---

*This prompt references docs at version: SRS v1.0.0 · ARCHITECTURE v1.0.0 · DatabaseDesign v1.1.0 · API v1.0.0 · DevelopmentPlan v1.0.0 · Milestones v1.0.0*
