# API Design Document
# AI Business Process Automation Platform

| Field | Value |
|-------|-------|
| Version | 1.0.0 |
| Status | Approved |
| Date | 2026-06-30 |
| Author | Architecture Team |
| References | docs/architecture/ARCHITECTURE.md §5, §10, docs/database/DatabaseDesign.md |

---

## Table of Contents

1. [API Conventions](#1-api-conventions)
2. [Authentication & Authorization](#2-authentication--authorization)
3. [Error Reference](#3-error-reference)
4. [Rate Limits](#4-rate-limits)
5. [Auth Endpoints](#5-auth-endpoints)
6. [Organization Endpoints](#6-organization-endpoints)
7. [Workflow Endpoints](#7-workflow-endpoints)
8. [Execution Endpoints](#8-execution-endpoints)
9. [Document Endpoints](#9-document-endpoints)
10. [AI Endpoints](#10-ai-endpoints)
11. [Integration Endpoints](#11-integration-endpoints)
12. [Notification Endpoints](#12-notification-endpoints)
13. [Analytics Endpoints](#13-analytics-endpoints)
14. [Platform Admin Endpoints](#14-platform-admin-endpoints)
15. [Webhook Receiver](#15-webhook-receiver)
16. [WebSocket Protocol](#16-websocket-protocol)

---

## 1. API Conventions

### 1.1 Base URL

```
Production:  https://api.autoflow.ai/api/v1
Staging:     https://staging-api.autoflow.ai/api/v1
Development: http://localhost:8000/api/v1
```

### 1.2 Versioning

All routes carry the `/api/v1/` prefix. When breaking changes are required, new routes ship under `/api/v2/` while `/api/v1/` is maintained with `Deprecation` response headers for one release cycle.

### 1.3 Request Format

- All request bodies are `application/json` unless the endpoint accepts file uploads (`multipart/form-data`)
- All timestamps in request bodies must be **ISO 8601 UTC** — e.g., `"2026-06-30T14:00:00Z"`
- UUIDs must be lowercase hyphenated format — e.g., `"a1b2c3d4-e5f6-..."`

### 1.4 Response Format

All successful responses return `application/json`. Collections return a paginated envelope:

```json
{
  "items": [...],
  "total": 142,
  "page": 1,
  "page_size": 20,
  "has_next": true
}
```

Single-resource responses return the resource object directly (no envelope).

### 1.5 Pagination

Pagination is cursor-free — it uses page + page_size query parameters.

| Parameter | Type | Default | Max | Description |
|-----------|------|---------|-----|-------------|
| `page` | integer | `1` | — | 1-based page number |
| `page_size` | integer | `20` | `100` | Items per page |

### 1.6 Tenant Isolation Rule

`organization_id` is **never** accepted in a request body. It is always derived from the authenticated user's JWT claims. Any attempt to inject an `organization_id` in the body is silently ignored. This is enforced at the dependency injection layer — not per-route.

### 1.7 Soft Delete Behavior

Endpoints that soft-delete (`workflows`, `documents`) return `204 No Content` immediately. The resource disappears from all list and get endpoints. The underlying DB row is not deleted — `deleted_at` is set.

### 1.8 Audit Logging

Every `POST`, `PATCH`, `PUT`, and `DELETE` request automatically writes an entry to `audit_logs` (org scope) or `platform_audit_logs` (platform scope) after the response is sent. This is handled by `AuditLogMiddleware` — routes do not need to call audit functions manually.

---

## 2. Authentication & Authorization

### 2.1 JWT Authentication (Browser / Dashboard)

The standard auth flow for browser users:

```
1. POST /api/v1/auth/login → returns access_token (body) + refresh_token (HttpOnly cookie)
2. All subsequent requests: Authorization: Bearer {access_token}
3. On 401 → POST /api/v1/auth/refresh (cookie sent automatically) → new access_token
4. On logout → POST /api/v1/auth/logout → cookie cleared, Redis session deleted
```

**Access token claims:**
```json
{
  "user_id": "uuid",
  "org_id":  "uuid",
  "session_id": "uuid",
  "role": "analyst",
  "scope": "org",
  "exp": 1751289600
}
```

**Platform staff JWT claims** (scope differs):
```json
{
  "user_id": "uuid",
  "scope": "platform",
  "role": "support_engineer",
  "exp": 1751289600
}
```

Access tokens expire in **15 minutes**. Refresh tokens expire in **7 days** and rotate on every use (replay attack prevention — see ARCHITECTURE.md §10.1).

### 2.2 API Key Authentication (Programmatic / Integrations)

```
Authorization: Bearer bpa_sk_xxxxxxxxxxxxxxxxxxxx
```

API keys are identified by the `bpa_sk_` prefix. They carry scopes that restrict which endpoints they can call. An API key with only `workflow:read` cannot trigger a run. Scope validation happens after bcrypt verification.

**Supported scopes:**

| Scope | Endpoints Accessible |
|-------|---------------------|
| `workflow:read` | GET /workflows, GET /workflows/{id} |
| `workflow:write` | POST/PATCH /workflows, POST /workflows/{id}/publish |
| `workflow:execute` | POST /runs |
| `document:read` | GET /documents, GET /documents/{id}/download-url |
| `document:write` | POST /documents, DELETE /documents/{id} |
| `analytics:read` | GET /analytics/* |
| `admin:*` | All org endpoints |

API key requests do not carry a `user_id` — `triggered_by` in `workflow_runs` will be `NULL` for API-triggered runs.

### 2.3 Role Requirements Notation

Throughout this document, required minimum role is shown as:

- `[org: analyst+]` — org-scoped JWT; minimum rank is `analyst` (analyst, manager, admin, owner all qualify)
- `[org: admin+]` — minimum `admin` rank
- `[org: owner]` — only the organization owner
- `[platform: platform_admin+]` — platform-scoped JWT; `platform_admin` or `super_admin`
- `[platform: any]` — any platform-scoped JWT
- `[api: workflow:execute]` — API key with this scope also accepted
- `[public]` — no authentication required

**Org role rank order:** owner (6) > admin (5) > manager (4) > analyst (3) > employee (2) > viewer (1)

**Existence leakage rule:** When an org user requests a resource that belongs to a different organization, the response is **404 Not Found**, never 403 Forbidden — the existence of the resource is not confirmed.

---

## 3. Error Reference

### 3.1 Error Response Shape

All errors return a consistent JSON body regardless of status code:

```json
{
  "error": {
    "code": "WORKFLOW_NOT_FOUND",
    "message": "Workflow f3a1c2d4... does not exist or you do not have access.",
    "request_id": "req_7x9kLmP2",
    "details": {}
  }
}
```

| Field | Description |
|-------|-------------|
| `code` | Machine-readable error code. Stable across versions — safe to branch on in client code |
| `message` | Human-readable message. May change; do not parse |
| `request_id` | Correlates to server logs. Always include in bug reports |
| `details` | Structured extra data — e.g., field-level validation errors |

**Validation error `details` example (422):**
```json
{
  "details": {
    "fields": [
      { "field": "name", "message": "Field required" },
      { "field": "nodes", "message": "At least one trigger node is required" }
    ]
  }
}
```

### 3.2 Error Code Reference

| HTTP | Code | When |
|------|------|------|
| 400 | `BAD_REQUEST` | Malformed JSON or missing required field caught outside Pydantic |
| 401 | `MISSING_TOKEN` | No Authorization header and no refresh cookie |
| 401 | `TOKEN_EXPIRED` | JWT `exp` claim is in the past |
| 401 | `INVALID_TOKEN` | JWT signature invalid, tampered, or wrong secret |
| 401 | `REFRESH_TOKEN_REUSED` | Replay attack — refresh token already rotated |
| 401 | `REFRESH_TOKEN_EXPIRED` | Refresh token TTL (7 days) exceeded |
| 401 | `EMAIL_NOT_VERIFIED` | Login attempt with unverified email |
| 401 | `ACCOUNT_DISABLED` | `users.is_active = FALSE` |
| 401 | `ORG_SUSPENDED` | `organizations.is_active = FALSE` |
| 401 | `API_KEY_INVALID` | Key not found, revoked, or expired |
| 401 | `API_KEY_SCOPE_DENIED` | Key exists but lacks the required scope |
| 403 | `FORBIDDEN` | Authenticated but insufficient role for this action |
| 403 | `PLATFORM_ACCESS_REQUIRED` | Org-scoped token used on a platform endpoint |
| 403 | `SUPPORT_GRANT_REQUIRED` | Support engineer has no active grant for this org |
| 404 | `NOT_FOUND` | Resource does not exist or belongs to another org |
| 409 | `CONFLICT` | Unique constraint violation (e.g., duplicate org slug, duplicate workflow name) |
| 422 | `VALIDATION_ERROR` | Pydantic validation failed — see `details.fields` |
| 422 | `INVALID_GRAPH` | Workflow graph failed structural validation before publish |
| 429 | `RATE_LIMITED` | Too many requests — see `Retry-After` header |
| 500 | `INTERNAL_ERROR` | Unexpected server error |
| 502 | `EXTERNAL_SERVICE_ERROR` | Upstream LLM or integration API failed |
| 503 | `SERVICE_UNAVAILABLE` | Worker queue overloaded or DB connection exhausted |

---

## 4. Rate Limits

| Endpoint Group | Limit | Window | Key |
|---------------|-------|--------|-----|
| `POST /auth/login` | 5 requests | 15 minutes | Per IP |
| `POST /auth/register` | 3 requests | 1 hour | Per IP |
| `POST /auth/forgot-password` | 3 requests | 1 hour | Per IP |
| `POST /auth/refresh` | 30 requests | 15 minutes | Per user_id |
| `POST /runs` (manual trigger) | 100 requests | 1 minute | Per org |
| `POST /webhooks/{id}` | 60 requests | 1 minute | Per workflow |
| `POST /ai/query` | 30 requests | 1 minute | Per org |
| `POST /documents` (upload) | 20 requests | 1 minute | Per org |
| All other `/api/v1/*` | 300 requests | 1 minute | Per (user_id or api_key_id) |
| All `/api/v1/platform/*` | 120 requests | 1 minute | Per platform_user_id |

On limit breach the response is `429 Too Many Requests` with:
```
Retry-After: 47
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1751289600
```

---

## 5. Auth Endpoints

### POST /auth/register

Create a new user account. If an `invite_token` is provided, the user is immediately joined to the invitation's organization.

**Auth:** `[public]`

**Request:**
```json
{
  "email": "alice@acme.com",
  "password": "SecurePass123!",
  "full_name": "Alice Chen",
  "invite_token": "a1b2c3..."    // optional — from invitation email
}
```

**Password rules:** minimum 8 characters, at least one uppercase, one lowercase, one digit.

**Response `201 Created`:**
```json
{
  "id": "uuid",
  "email": "alice@acme.com",
  "full_name": "Alice Chen",
  "is_verified": false,
  "created_at": "2026-06-30T10:00:00Z"
}
```

**Notes:**
- A verification email is sent immediately (async Celery task)
- If `invite_token` is valid, `is_verified` is set to `true` (invited users are pre-verified)
- `409 CONFLICT` if email already registered

---

### POST /auth/login

Authenticate with email and password.

**Auth:** `[public]`

**Request:**
```json
{
  "email": "alice@acme.com",
  "password": "SecurePass123!",
  "org_id": "uuid"   // optional — if user belongs to multiple orgs, selects which org to scope the token to
}
```

**Response `200 OK`:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 900,
  "user": {
    "id": "uuid",
    "email": "alice@acme.com",
    "full_name": "Alice Chen",
    "is_verified": true
  },
  "organization": {
    "id": "uuid",
    "name": "Acme Corp",
    "slug": "acme-corp",
    "plan": "pro"
  },
  "role": "analyst"
}
```

**Set-Cookie (HttpOnly, Secure, SameSite=Strict):**
```
refresh_token=<opaque-uuid>; HttpOnly; Secure; SameSite=Strict; Max-Age=604800; Path=/api/v1/auth/refresh
```

**Notes:**
- If user belongs to multiple orgs and `org_id` is omitted, returns `200` with `organizations` array and no token — client must re-call with an `org_id`
- `401 EMAIL_NOT_VERIFIED` if `is_verified = false`
- `401 ACCOUNT_DISABLED` if `is_active = false`
- `401 ORG_SUSPENDED` if the selected org is suspended

---

### POST /auth/refresh

Rotate the refresh token and issue a new access token. The old refresh token is immediately invalidated.

**Auth:** `[public]` (refresh token in HttpOnly cookie — sent automatically)

**Request:** No body

**Response `200 OK`:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 900
}
```

New `Set-Cookie` with rotated refresh token.

**Notes:**
- `401 REFRESH_TOKEN_REUSED` if this token was already used (replay attack detection)
- The Redis session key is atomically deleted + re-created in a single transaction

---

### POST /auth/logout

Invalidate the current session. Clears the refresh token from Redis.

**Auth:** `[org: viewer+]`

**Request:** No body

**Response `204 No Content`**

`Set-Cookie: refresh_token=; Max-Age=0` (clears cookie)

---

### GET /auth/me

Return the current user's profile and org membership.

**Auth:** `[org: viewer+]`

**Response `200 OK`:**
```json
{
  "user": {
    "id": "uuid",
    "email": "alice@acme.com",
    "full_name": "Alice Chen",
    "avatar_url": "https://...",
    "is_verified": true,
    "created_at": "2026-01-15T09:00:00Z"
  },
  "organization": {
    "id": "uuid",
    "name": "Acme Corp",
    "slug": "acme-corp",
    "plan": "pro",
    "settings": { ... }
  },
  "role": "analyst",
  "department": { "id": "uuid", "name": "Finance" }
}
```

---

### POST /auth/verify-email

Verify a user's email address using the token from the verification email.

**Auth:** `[public]`

**Request:**
```json
{ "token": "plaintext-token-from-email" }
```

**Response `200 OK`:**
```json
{ "message": "Email verified successfully." }
```

**Notes:**
- Token is single-use — `used_at` set on first consumption
- `404 NOT_FOUND` if token does not exist or is already used
- `422 VALIDATION_ERROR` if token is expired (`expires_at` in the past)

---

### POST /auth/resend-verification

Resend the verification email.

**Auth:** `[public]`

**Request:**
```json
{ "email": "alice@acme.com" }
```

**Response `204 No Content`** (always — no confirmation whether email exists, to prevent enumeration)

---

### POST /auth/forgot-password

Request a password reset email.

**Auth:** `[public]`

**Request:**
```json
{ "email": "alice@acme.com" }
```

**Response `204 No Content`** (always — no confirmation whether email exists)

---

### POST /auth/reset-password

Set a new password using the reset token from email.

**Auth:** `[public]`

**Request:**
```json
{
  "token": "plaintext-token-from-email",
  "new_password": "NewSecurePass456!"
}
```

**Response `200 OK`:**
```json
{ "message": "Password reset successfully. Please log in." }
```

**Notes:**
- All active sessions for this user are invalidated (all Redis `session:{user_id}:*` keys deleted)
- Token is single-use

---

### GET /auth/google

Initiate Google OAuth flow. Redirects to Google's consent screen.

**Auth:** `[public]`

**Query params:** `?redirect_uri=https://app.autoflow.ai/dashboard`

**Response `302 Redirect`** → Google OAuth URL

---

### GET /auth/google/callback

Handle Google OAuth callback. Handled by Next.js API route `/api/auth/callback/route.ts`, which exchanges the code with the FastAPI backend.

**Auth:** `[public]`

**Query params:** `?code=...&state=...`

**Response `302 Redirect`** → Frontend dashboard (with access token set in memory via postMessage)

---

## 6. Organization Endpoints

### POST /orgs

Create a new organization. The calling user becomes the `owner`.

**Auth:** `[org: viewer+]` (any authenticated user can create an org)

**Request:**
```json
{
  "name": "Acme Corp",
  "slug": "acme-corp"   // optional — auto-generated from name if omitted
}
```

**Response `201 Created`:**
```json
{
  "id": "uuid",
  "name": "Acme Corp",
  "slug": "acme-corp",
  "plan": "free",
  "is_active": true,
  "settings": { "timezone": "UTC", "language": "en", "max_storage_bytes": 5368709120 },
  "created_at": "2026-06-30T10:00:00Z"
}
```

**Notes:**
- `409 CONFLICT` if slug already taken
- A new access token is issued (background) scoping the user to this org

---

### GET /orgs/{org_id}

Get organization details.

**Auth:** `[org: viewer+]`

**Response `200 OK`:**
```json
{
  "id": "uuid",
  "name": "Acme Corp",
  "slug": "acme-corp",
  "plan": "pro",
  "is_active": true,
  "storage_used_bytes": 214748364,
  "settings": {
    "timezone": "America/New_York",
    "language": "en",
    "logo_url": "https://...",
    "ai_budget_usd_monthly": 500.00,
    "max_workflow_executions_monthly": 50000,
    "max_storage_bytes": 10737418240
  },
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-06-30T10:00:00Z"
}
```

---

### PATCH /orgs/{org_id}

Update organization name or settings.

**Auth:** `[org: admin+]`

**Request (all fields optional):**
```json
{
  "name": "Acme Corporation",
  "settings": {
    "timezone": "Europe/London",
    "ai_budget_usd_monthly": 1000.00
  }
}
```

**Response `200 OK`:** Updated organization object

---

### DELETE /orgs/{org_id}

Permanently delete the organization and all its data. This is irreversible.

**Auth:** `[org: owner]`

**Request:**
```json
{ "confirmation": "acme-corp" }
```

The `confirmation` field must match the organization's slug exactly.

**Response `204 No Content`**

**Notes:**
- All workflows, runs, documents, members, and integrations are cascade-deleted
- `audit_logs` rows are retained (no cascade — see DatabaseDesign.md §11.2)
- A Celery task deletes all S3 objects for this org asynchronously

---

### GET /orgs/{org_id}/members

List all members of an organization.

**Auth:** `[org: viewer+]`

**Query params:** `?page=1&page_size=20&role=analyst&department_id=uuid`

**Response `200 OK`:**
```json
{
  "items": [
    {
      "user_id": "uuid",
      "email": "alice@acme.com",
      "full_name": "Alice Chen",
      "avatar_url": "https://...",
      "role": "analyst",
      "department": { "id": "uuid", "name": "Finance" },
      "joined_at": "2026-02-01T09:00:00Z"
    }
  ],
  "total": 34,
  "page": 1,
  "page_size": 20,
  "has_next": true
}
```

---

### PATCH /orgs/{org_id}/members/{user_id}

Change a member's role or department assignment.

**Auth:** `[org: admin+]`

**Request:**
```json
{
  "role": "manager",
  "department_id": "uuid"   // optional
}
```

**Response `200 OK`:** Updated member object

**Notes:**
- `403 FORBIDDEN` if the caller tries to change the owner's role without being the owner
- `403 FORBIDDEN` if the caller tries to assign a role equal to or higher than their own
- The `owner` role cannot be assigned via this endpoint — use `POST /orgs/{id}/transfer-ownership`

---

### DELETE /orgs/{org_id}/members/{user_id}

Remove a member from the organization.

**Auth:** `[org: admin+]`

**Response `204 No Content`**

**Notes:**
- `403 FORBIDDEN` if trying to remove the owner
- The user's `users` record is not deleted — only the `org_members` row

---

### POST /orgs/{org_id}/transfer-ownership

Transfer the `owner` role to another member.

**Auth:** `[org: owner]`

**Request:**
```json
{ "new_owner_user_id": "uuid" }
```

**Response `200 OK`:**
```json
{ "message": "Ownership transferred. Your role is now admin." }
```

---

### POST /orgs/{org_id}/invitations

Invite a user to the organization by email.

**Auth:** `[org: admin+]`

**Request:**
```json
{
  "email": "bob@acme.com",
  "role": "analyst",
  "department_id": "uuid"   // optional
}
```

**Response `201 Created`:**
```json
{
  "id": "uuid",
  "email": "bob@acme.com",
  "role": "analyst",
  "expires_at": "2026-07-02T10:00:00Z",
  "created_at": "2026-06-30T10:00:00Z"
}
```

**Notes:**
- An email with the invitation link is sent asynchronously
- `409 CONFLICT` if a pending (unexpired) invitation already exists for this email+org
- Inviting an `owner` role is not permitted (`422 VALIDATION_ERROR`)

---

### GET /orgs/{org_id}/invitations

List pending (unexpired, unaccepted) invitations.

**Auth:** `[org: admin+]`

**Response `200 OK`:**
```json
{
  "items": [
    {
      "id": "uuid",
      "email": "bob@acme.com",
      "role": "analyst",
      "invited_by": { "user_id": "uuid", "full_name": "Alice Chen" },
      "expires_at": "2026-07-02T10:00:00Z",
      "created_at": "2026-06-30T10:00:00Z"
    }
  ],
  "total": 3,
  "page": 1,
  "page_size": 20,
  "has_next": false
}
```

---

### DELETE /orgs/{org_id}/invitations/{invitation_id}

Revoke a pending invitation before it is accepted.

**Auth:** `[org: admin+]`

**Response `204 No Content`**

---

### POST /invitations/accept

Accept an invitation using the token from the email link. Can be called without an existing session — the user may need to register first.

**Auth:** `[public]`

**Request:**
```json
{ "token": "plaintext-invitation-token" }
```

**Response `200 OK`:**
```json
{
  "organization": { "id": "uuid", "name": "Acme Corp" },
  "role": "analyst",
  "message": "You have joined Acme Corp as analyst."
}
```

**Notes:**
- `404 NOT_FOUND` if token is invalid or expired
- `409 CONFLICT` if the user is already a member of this org
- If the calling user's email does not match the invitation email, returns `403 FORBIDDEN`

---

### GET /orgs/{org_id}/departments

List departments in the organization.

**Auth:** `[org: viewer+]`

**Response `200 OK`:**
```json
{
  "items": [
    { "id": "uuid", "name": "Finance", "member_count": 12 },
    { "id": "uuid", "name": "HR", "member_count": 5 }
  ],
  "total": 4
}
```

---

### POST /orgs/{org_id}/departments

Create a department.

**Auth:** `[org: admin+]`

**Request:**
```json
{ "name": "Engineering" }
```

**Response `201 Created`:**
```json
{ "id": "uuid", "name": "Engineering", "created_at": "2026-06-30T10:00:00Z" }
```

---

### PATCH /orgs/{org_id}/departments/{dept_id}

Rename a department.

**Auth:** `[org: admin+]`

**Request:** `{ "name": "Software Engineering" }`

**Response `200 OK`:** Updated department object

---

### DELETE /orgs/{org_id}/departments/{dept_id}

Delete a department. Members assigned to it have their `department_id` set to NULL.

**Auth:** `[org: admin+]`

**Response `204 No Content`**

---

### GET /orgs/{org_id}/api-keys

List all API keys for the organization. Key values are never returned — only metadata.

**Auth:** `[org: admin+]`

**Response `200 OK`:**
```json
{
  "items": [
    {
      "id": "uuid",
      "label": "Production Webhook Key",
      "key_prefix": "bpa_sk_a1",
      "scopes": ["workflow:execute", "document:read"],
      "last_used_at": "2026-06-29T18:30:00Z",
      "expires_at": null,
      "revoked_at": null,
      "created_at": "2026-01-15T09:00:00Z"
    }
  ],
  "total": 3
}
```

---

### POST /orgs/{org_id}/api-keys

Create a new API key. The full key value is returned **once only** — it cannot be retrieved again.

**Auth:** `[org: admin+]`

**Request:**
```json
{
  "label": "CI/CD Pipeline Key",
  "scopes": ["workflow:execute", "workflow:read"],
  "expires_at": "2027-01-01T00:00:00Z"   // optional
}
```

**Response `201 Created`:**
```json
{
  "id": "uuid",
  "label": "CI/CD Pipeline Key",
  "key": "bpa_sk_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
  "key_prefix": "bpa_sk_a1",
  "scopes": ["workflow:execute", "workflow:read"],
  "expires_at": "2027-01-01T00:00:00Z",
  "created_at": "2026-06-30T10:00:00Z"
}
```

**Notes:**
- The `key` field is returned only in this response. Store it immediately.
- The backend stores only `bcrypt(key)` — the plaintext is not persisted

---

### DELETE /orgs/{org_id}/api-keys/{key_id}

Revoke an API key. Immediately prevents further use.

**Auth:** `[org: admin+]`

**Response `204 No Content`**

---

## 7. Workflow Endpoints

### GET /workflows

List all non-deleted workflows in the organization.

**Auth:** `[org: viewer+]` `[api: workflow:read]`

**Query params:**

| Param | Type | Description |
|-------|------|-------------|
| `status` | string | Filter by `draft`, `published`, `archived` |
| `search` | string | Full-text search on `name` |
| `tag` | string | Filter by tag value |
| `created_by` | uuid | Filter by creator user_id |
| `page` | integer | Default `1` |
| `page_size` | integer | Default `20`, max `100` |

**Response `200 OK`:**
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "Invoice Processing",
      "description": "Extracts and validates invoices from email",
      "status": "published",
      "tags": ["finance", "automated"],
      "active_version_number": 3,
      "created_by": { "user_id": "uuid", "full_name": "Alice Chen" },
      "last_run_at": "2026-06-30T09:45:00Z",
      "created_at": "2026-03-01T10:00:00Z",
      "updated_at": "2026-06-15T14:00:00Z"
    }
  ],
  "total": 27,
  "page": 1,
  "page_size": 20,
  "has_next": true
}
```

---

### POST /workflows

Create a new draft workflow.

**Auth:** `[org: analyst+]` `[api: workflow:write]`

**Request:**
```json
{
  "name": "Invoice Processing",
  "description": "Extracts and validates invoices from email",
  "tags": ["finance"]
}
```

**Response `201 Created`:**
```json
{
  "id": "uuid",
  "name": "Invoice Processing",
  "description": "Extracts and validates invoices from email",
  "status": "draft",
  "tags": ["finance"],
  "active_version_id": null,
  "created_by": { "user_id": "uuid", "full_name": "Alice Chen" },
  "created_at": "2026-06-30T10:00:00Z"
}
```

---

### GET /workflows/{workflow_id}

Get a workflow with its current active version graph.

**Auth:** `[org: viewer+]` `[api: workflow:read]`

**Response `200 OK`:**
```json
{
  "id": "uuid",
  "name": "Invoice Processing",
  "description": "...",
  "status": "published",
  "tags": ["finance"],
  "active_version": {
    "id": "uuid",
    "version_number": 3,
    "published_by": { "user_id": "uuid", "full_name": "Alice Chen" },
    "published_at": "2026-06-15T14:00:00Z",
    "change_summary": "Added email notification on failure",
    "definition": {
      "nodes": [ { "id": "n1", "type": "trigger.webhook", "label": "Invoice In", "position": {"x": 100, "y": 200}, "config": {} } ],
      "edges": [ { "id": "e1", "source": "n1", "target": "n2", "sourceHandle": "output", "targetHandle": "input" } ]
    }
  },
  "created_at": "2026-03-01T10:00:00Z",
  "updated_at": "2026-06-15T14:00:00Z"
}
```

---

### PATCH /workflows/{workflow_id}

Update workflow metadata or draft graph.

**Auth:** `[org: analyst+]` `[api: workflow:write]`

**Request (all fields optional):**
```json
{
  "name": "Invoice Processing v2",
  "description": "Updated description",
  "tags": ["finance", "invoice"],
  "definition": {
    "nodes": [...],
    "edges": [...]
  }
}
```

**Response `200 OK`:** Updated workflow object

**Notes:**
- `definition` can only be updated while `status = 'draft'`. Updating the definition of a published workflow automatically creates a new draft — it does not modify the published version.

---

### DELETE /workflows/{workflow_id}

Soft-delete a workflow. Immediately hides it from all list/get endpoints.

**Auth:** `[org: admin+]` `[api: workflow:write]`

**Response `204 No Content`**

**Notes:**
- In-progress runs (`status = 'running'`) are not cancelled automatically — they will complete or fail
- The workflow cannot be re-activated after deletion

---

### POST /workflows/{workflow_id}/publish

Validate and publish the current draft as a new version.

**Auth:** `[org: analyst+]` `[api: workflow:write]`

**Request (optional):**
```json
{ "change_summary": "Added retry logic to HTTP request node" }
```

**Response `200 OK`:**
```json
{
  "id": "uuid",
  "status": "published",
  "active_version": {
    "id": "uuid",
    "version_number": 4,
    "published_at": "2026-06-30T11:00:00Z"
  }
}
```

**Validation rules enforced before publish:**
- At least one trigger node (`trigger.*`)
- No orphaned nodes (every non-trigger node has at least one incoming edge)
- No cycles in the graph
- All registered node types (unknown types fail with `422 INVALID_GRAPH`)
- `condition` nodes must have both `true` and `false` outgoing edges

**Error response `422 INVALID_GRAPH`:**
```json
{
  "error": {
    "code": "INVALID_GRAPH",
    "message": "Workflow graph failed validation.",
    "details": {
      "errors": [
        { "node_id": "n3", "message": "Condition node missing 'false' branch" },
        { "node_id": "n5", "message": "Orphaned node — no incoming edges" }
      ]
    }
  }
}
```

---

### POST /workflows/{workflow_id}/duplicate

Create a copy of the workflow as a new draft.

**Auth:** `[org: analyst+]`

**Request (optional):**
```json
{ "name": "Invoice Processing (Copy)" }
```

**Response `201 Created`:** New workflow object (draft status, no active version)

---

### GET /workflows/{workflow_id}/versions

List all published versions of a workflow.

**Auth:** `[org: viewer+]`

**Response `200 OK`:**
```json
{
  "items": [
    {
      "id": "uuid",
      "version_number": 3,
      "published_by": { "user_id": "uuid", "full_name": "Alice Chen" },
      "published_at": "2026-06-15T14:00:00Z",
      "change_summary": "Added email notification on failure"
    }
  ],
  "total": 3
}
```

---

### GET /workflows/{workflow_id}/versions/{version_number}

Get a specific version's full graph definition.

**Auth:** `[org: viewer+]`

**Response `200 OK`:** Version object including full `definition` JSONB

---

### POST /workflows/{workflow_id}/revert/{version_number}

Revert the active version to a previously published version. Creates a new version record (does not overwrite history).

**Auth:** `[org: admin+]`

**Request (optional):**
```json
{ "change_summary": "Reverted to v2 — v3 caused errors" }
```

**Response `200 OK`:** Updated workflow with new `active_version` (version_number = old_max + 1, definition copied from target version)

---

### POST /workflows/{workflow_id}/archive

Archive a published workflow. Prevents new runs. Existing run history is preserved.

**Auth:** `[org: admin+]`

**Response `200 OK`:** Workflow with `status: "archived"`

---

## 8. Execution Endpoints

### POST /runs

Trigger a manual workflow run.

**Auth:** `[org: employee+]` `[api: workflow:execute]`

**Request:**
```json
{
  "workflow_id": "uuid",
  "input_data": {
    "invoice_url": "https://...",
    "sender_email": "vendor@example.com"
  }
}
```

**Response `202 Accepted`:**
```json
{
  "run_id": "uuid",
  "workflow_id": "uuid",
  "status": "pending",
  "trigger_type": "manual",
  "started_at": "2026-06-30T11:00:00Z"
}
```

**Notes:**
- Returns `202` immediately — execution is async (Celery)
- `404 NOT_FOUND` if workflow does not exist or belongs to another org
- `422 VALIDATION_ERROR` if workflow is `draft` or `archived` (must be `published`)
- WebSocket events will stream execution progress — see Section 16

---

### GET /runs

List workflow runs for the organization.

**Auth:** `[org: viewer+]`

**Query params:**

| Param | Type | Description |
|-------|------|-------------|
| `workflow_id` | uuid | Filter by specific workflow |
| `status` | string | `pending`, `running`, `completed`, `failed`, `cancelled` |
| `trigger_type` | string | `manual`, `schedule`, `webhook`, `api` |
| `triggered_by` | uuid | Filter by user who triggered |
| `from_date` | ISO 8601 | `started_at` range start |
| `to_date` | ISO 8601 | `started_at` range end |
| `page` | integer | Default `1` |
| `page_size` | integer | Default `20`, max `100` |

**Response `200 OK`:**
```json
{
  "items": [
    {
      "run_id": "uuid",
      "workflow_id": "uuid",
      "workflow_name": "Invoice Processing",
      "status": "completed",
      "trigger_type": "webhook",
      "triggered_by": { "user_id": null, "label": "Webhook" },
      "started_at": "2026-06-30T09:45:00Z",
      "completed_at": "2026-06-30T09:45:12Z",
      "duration_ms": 12450,
      "parent_run_id": null
    }
  ],
  "total": 1847,
  "page": 1,
  "page_size": 20,
  "has_next": true
}
```

---

### GET /runs/{run_id}

Get a single run's status and summary.

**Auth:** `[org: viewer+]`

**Response `200 OK`:**
```json
{
  "run_id": "uuid",
  "workflow_id": "uuid",
  "workflow_version_id": "uuid",
  "status": "failed",
  "trigger_type": "manual",
  "triggered_by": { "user_id": "uuid", "full_name": "Alice Chen" },
  "input_data": { "invoice_url": "https://..." },
  "output_data": null,
  "error_message": "HTTP request to ERP timed out after 30s",
  "started_at": "2026-06-30T09:45:00Z",
  "completed_at": "2026-06-30T09:45:32Z",
  "duration_ms": 32000,
  "parent_run_id": null,
  "retry_run_ids": ["uuid"]
}
```

---

### GET /runs/{run_id}/logs

Get per-node execution logs for a run.

**Auth:** `[org: viewer+]`

**Response `200 OK`:**
```json
{
  "run_id": "uuid",
  "logs": [
    {
      "log_id": "uuid",
      "node_id": "n1",
      "node_type": "trigger.webhook",
      "node_label": "Invoice In",
      "status": "completed",
      "attempt_number": 1,
      "input_data": { "body": { "invoice_id": "INV-001" } },
      "output_data": { "invoice_id": "INV-001", "amount": 4500.00 },
      "error_message": null,
      "error_type": null,
      "started_at": "2026-06-30T09:45:00Z",
      "completed_at": "2026-06-30T09:45:00Z",
      "duration_ms": 45
    },
    {
      "log_id": "uuid",
      "node_id": "n3",
      "node_type": "action.http",
      "node_label": "Post to ERP",
      "status": "failed",
      "attempt_number": 3,
      "error_message": "HTTP request to ERP timed out after 30s",
      "error_type": "ExternalServiceError",
      "started_at": "2026-06-30T09:45:10Z",
      "completed_at": "2026-06-30T09:45:32Z",
      "duration_ms": 30001
    }
  ]
}
```

---

### POST /runs/{run_id}/cancel

Cancel a pending or running workflow run.

**Auth:** `[org: analyst+]`

**Request:** No body

**Response `200 OK`:**
```json
{ "run_id": "uuid", "status": "cancelled" }
```

**Notes:**
- If the run is already `completed` or `failed`, returns `409 CONFLICT`
- Cancellation is best-effort — a node currently executing may complete before the signal is received

---

### POST /runs/{run_id}/retry

Retry a failed run from the failed node. Skips nodes that already completed successfully.

**Auth:** `[org: analyst+]`

**Request:** No body

**Response `202 Accepted`:**
```json
{
  "run_id": "uuid",   // NEW run_id for the retry run
  "parent_run_id": "uuid",
  "status": "pending",
  "message": "Retry run created. Skipping 2 already-completed nodes."
}
```

**Notes:**
- Only valid if the original run has `status = 'failed'`
- Returns `409 CONFLICT` if the run has no failed nodes
- The retry run references `parent_run_id` and re-uses completed node outputs from the parent

---

## 9. Document Endpoints

### GET /documents

List documents in the organization.

**Auth:** `[org: viewer+]` `[api: document:read]`

**Query params:**

| Param | Type | Description |
|-------|------|-------------|
| `search` | string | Trigram search on filename |
| `mime_type` | string | Filter by MIME type |
| `is_indexed` | boolean | Filter by RAG indexing status |
| `page` | integer | Default `1` |
| `page_size` | integer | Default `20`, max `100` |

**Response `200 OK`:**
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "Q2-Employee-Handbook.pdf",
      "mime_type": "application/pdf",
      "size_bytes": 2457600,
      "is_indexed": true,
      "uploaded_by": { "user_id": "uuid", "full_name": "Alice Chen" },
      "metadata": { "page_count": 48, "language": "en" },
      "created_at": "2026-05-01T10:00:00Z"
    }
  ],
  "total": 142,
  "page": 1,
  "page_size": 20,
  "has_next": true
}
```

---

### POST /documents/upload-url

Get a presigned S3/MinIO PUT URL for direct browser-to-storage upload. The client uploads the file directly to storage, then calls `POST /documents` to register it.

**Auth:** `[org: analyst+]` `[api: document:write]`

**Request:**
```json
{
  "filename": "Q2-Employee-Handbook.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 2457600
}
```

**Response `200 OK`:**
```json
{
  "upload_url": "https://minio.internal/bpa-bucket/org-uuid/documents/doc-uuid/Q2-Employee-Handbook.pdf?X-Amz-Signature=...",
  "storage_key": "org-uuid/documents/doc-uuid/Q2-Employee-Handbook.pdf",
  "expires_at": "2026-06-30T10:05:00Z"
}
```

**Notes:**
- Presigned PUT URL expires in 5 minutes
- Only allowed MIME types accepted — see DatabaseDesign.md §16.4
- `413` if `size_bytes` exceeds org's remaining storage quota

---

### POST /documents

Register a document after successful upload to storage.

**Auth:** `[org: analyst+]` `[api: document:write]`

**Request:**
```json
{
  "name": "Q2-Employee-Handbook.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 2457600,
  "storage_key": "org-uuid/documents/doc-uuid/Q2-Employee-Handbook.pdf",
  "index_for_rag": true
}
```

**Response `201 Created`:**
```json
{
  "id": "uuid",
  "name": "Q2-Employee-Handbook.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 2457600,
  "is_indexed": false,
  "indexing_status": "queued",
  "created_at": "2026-06-30T10:01:00Z"
}
```

**Notes:**
- If `index_for_rag: true`, a `rag_index_task` is enqueued immediately
- `422 VALIDATION_ERROR` if the `storage_key` path does not begin with the org's UUID (tampering prevention)

---

### GET /documents/{document_id}

Get document metadata.

**Auth:** `[org: viewer+]` `[api: document:read]`

**Response `200 OK`:** Full document object including `metadata` JSONB

---

### GET /documents/{document_id}/download-url

Get a presigned GET URL to download the document.

**Auth:** `[org: viewer+]` `[api: document:read]`

**Response `200 OK`:**
```json
{
  "download_url": "https://minio.internal/bpa-bucket/...?X-Amz-Signature=...",
  "expires_at": "2026-06-30T10:15:00Z"
}
```

URL expires in 15 minutes.

---

### DELETE /documents/{document_id}

Soft-delete a document. Queues async S3 deletion via Celery.

**Auth:** `[org: analyst+]` `[api: document:write]`

**Response `204 No Content`**

**Notes:**
- Document disappears from list/get immediately
- `document_chunks` rows are cascade-deleted synchronously
- S3 object is deleted asynchronously

---

### POST /documents/{document_id}/index

(Re-)trigger RAG indexing for a document.

**Auth:** `[org: analyst+]`

**Response `202 Accepted`:**
```json
{ "document_id": "uuid", "indexing_status": "queued" }
```

---

## 10. AI Endpoints

### POST /ai/query

Submit a natural-language question against the organization's indexed documents (RAG).

**Auth:** `[org: viewer+]`

**Request:**
```json
{
  "question": "What is our parental leave policy?",
  "document_ids": ["uuid", "uuid"],   // optional — scope to specific documents
  "similarity_threshold": 0.75,        // optional — default 0.75
  "max_sources": 5                     // optional — default 5
}
```

**Response `200 OK`:**
```json
{
  "question": "What is our parental leave policy?",
  "answer": "Employees are entitled to 16 weeks of paid parental leave...",
  "sources": [
    {
      "document_id": "uuid",
      "document_name": "Employee-Handbook-2026.pdf",
      "chunk_index": 14,
      "excerpt": "...16 weeks of fully paid parental leave is available to all...",
      "similarity_score": 0.921
    }
  ],
  "model": "gpt-4o",
  "tokens_used": 1847,
  "latency_ms": 1230
}
```

**Notes:**
- Query only searches chunks where `organization_id` matches the caller's org — cross-org leakage is structurally impossible
- If no relevant documents found, `answer` states this clearly and `sources` is `[]`
- Token usage is logged to `ai_usage_logs`

---

### POST /ai/generate-workflow

Use AI to generate a workflow graph from a natural-language description.

**Auth:** `[org: analyst+]`

**Request:**
```json
{
  "description": "When an email arrives with an invoice attachment, extract the invoice data, validate the total against our ERP, and send a Slack notification with the result.",
  "trigger_type": "trigger.email"   // optional hint
}
```

**Response `200 OK`:**
```json
{
  "workflow_draft": {
    "name": "Invoice Email Processing",
    "description": "AI-generated workflow",
    "definition": {
      "nodes": [...],
      "edges": [...]
    }
  },
  "explanation": "I created a 4-node workflow: email trigger → extraction → HTTP validation → Slack notification.",
  "tokens_used": 3210
}
```

**Notes:**
- The returned `workflow_draft` is not persisted — the client must call `POST /workflows` to save it
- The generated graph may require manual review before publishing

---

## 11. Integration Endpoints

### GET /integrations

List configured integrations for the organization.

**Auth:** `[org: admin+]`

**Response `200 OK`:**
```json
{
  "items": [
    {
      "id": "uuid",
      "provider": "gmail",
      "name": "Company Gmail",
      "status": "active",
      "last_verified_at": "2026-06-30T06:00:00Z",
      "created_at": "2026-01-15T09:00:00Z"
    }
  ],
  "total": 3
}
```

**Notes:** `credentials` JSONB is never returned — only status and metadata

---

### POST /integrations

Create a new integration. Credentials are AES-256 encrypted before storage.

**Auth:** `[org: admin+]`

**Request:**
```json
{
  "provider": "slack",
  "name": "Engineering Slack",
  "credentials": {
    "webhook_url": "https://hooks.slack.com/services/...",
    "bot_token": "xoxb-..."
  },
  "config": {
    "default_channel": "#alerts"
  }
}
```

**Response `201 Created`:**
```json
{
  "id": "uuid",
  "provider": "slack",
  "name": "Engineering Slack",
  "status": "active",
  "config": { "default_channel": "#alerts" },
  "created_at": "2026-06-30T10:00:00Z"
}
```

---

### PATCH /integrations/{integration_id}

Update integration name, credentials, or config.

**Auth:** `[org: admin+]`

**Request (all fields optional):**
```json
{
  "name": "Engineering Slack (Updated)",
  "credentials": { "bot_token": "xoxb-new-token" },
  "config": { "default_channel": "#engineering" }
}
```

**Response `200 OK`:** Updated integration object (no credentials in response)

---

### POST /integrations/{integration_id}/verify

Test the integration connection and update `last_verified_at`.

**Auth:** `[org: admin+]`

**Response `200 OK`:**
```json
{
  "status": "active",
  "verified_at": "2026-06-30T11:00:00Z",
  "message": "Connection successful."
}
```

`status` becomes `"error"` if the test fails, with `message` describing the failure.

---

### DELETE /integrations/{integration_id}

Delete an integration. Active workflows referencing this integration will fail on next run.

**Auth:** `[org: admin+]`

**Response `204 No Content`**

---

## 12. Notification Endpoints

### GET /notifications

Get the current user's notification feed.

**Auth:** `[org: viewer+]`

**Query params:** `?is_read=false&page=1&page_size=20`

**Response `200 OK`:**
```json
{
  "items": [
    {
      "id": "uuid",
      "type": "workflow.failed",
      "title": "Invoice Processing failed",
      "body": "Node 'Post to ERP' failed after 3 retries.",
      "metadata": {
        "workflow_id": "uuid",
        "workflow_name": "Invoice Processing",
        "run_id": "uuid"
      },
      "is_read": false,
      "created_at": "2026-06-30T09:45:32Z"
    }
  ],
  "total": 14,
  "unread_count": 5,
  "page": 1,
  "page_size": 20,
  "has_next": false
}
```

---

### PATCH /notifications/{notification_id}/read

Mark a single notification as read.

**Auth:** `[org: viewer+]`

**Response `200 OK`:** `{ "id": "uuid", "is_read": true }`

---

### POST /notifications/read-all

Mark all notifications for the current user as read.

**Auth:** `[org: viewer+]`

**Response `200 OK`:** `{ "marked_read": 14 }`

---

### GET /me/notification-preferences

Get the current user's notification preferences for their current org.

**Auth:** `[org: viewer+]`

**Response `200 OK`:**
```json
{
  "email_on_workflow_failure": true,
  "email_on_workflow_success": false,
  "email_on_invitation": true,
  "email_on_weekly_report": true,
  "inapp_on_workflow_failure": true,
  "inapp_on_workflow_success": true,
  "inapp_on_mention": true
}
```

---

### PATCH /me/notification-preferences

Update notification preferences.

**Auth:** `[org: viewer+]`

**Request (all fields optional):**
```json
{
  "email_on_workflow_success": true,
  "email_on_weekly_report": false
}
```

**Response `200 OK`:** Full updated preferences object

---

## 13. Analytics Endpoints

### GET /analytics/dashboard

Get the main dashboard statistics for the current org.

**Auth:** `[org: viewer+]`

**Query params:** `?period=30d` (supported: `7d`, `30d`, `90d`, `12m`)

**Response `200 OK`:**
```json
{
  "period": "30d",
  "executions": {
    "total": 4821,
    "completed": 4650,
    "failed": 171,
    "success_rate_pct": 96.5,
    "avg_duration_ms": 8430,
    "trend_pct": 12.3
  },
  "ai_usage": {
    "total_tokens": 18430000,
    "total_cost_usd": 147.28,
    "budget_usd": 500.00,
    "budget_used_pct": 29.5
  },
  "storage": {
    "used_bytes": 214748364,
    "max_bytes": 10737418240,
    "used_pct": 2.0,
    "document_count": 142
  },
  "top_workflows": [
    {
      "workflow_id": "uuid",
      "name": "Invoice Processing",
      "run_count": 1847,
      "failure_count": 23,
      "avg_duration_ms": 12450
    }
  ],
  "cached_at": "2026-06-30T10:00:00Z"
}
```

**Notes:** Results are cached in Redis for 5 minutes (`cache:analytics:{org_id}:dashboard:{date_key}`)

---

### GET /analytics/executions

Detailed execution statistics.

**Auth:** `[org: viewer+]`

**Query params:** `?period=30d&workflow_id=uuid&group_by=day`

**Response `200 OK`:**
```json
{
  "period": "30d",
  "group_by": "day",
  "series": [
    { "date": "2026-06-01", "completed": 142, "failed": 5, "avg_duration_ms": 8200 },
    { "date": "2026-06-02", "completed": 167, "failed": 3, "avg_duration_ms": 7900 }
  ],
  "by_trigger_type": {
    "manual": 312, "webhook": 3841, "schedule": 668, "api": 0
  },
  "top_failing_nodes": [
    {
      "node_type": "action.http",
      "node_label": "Post to ERP",
      "failure_count": 89,
      "most_common_error": "ExternalServiceError"
    }
  ]
}
```

---

### GET /analytics/ai-usage

AI token and cost breakdown.

**Auth:** `[org: viewer+]`

**Query params:** `?period=30d`

**Response `200 OK`:**
```json
{
  "period": "30d",
  "total_cost_usd": 147.28,
  "by_model": [
    { "provider": "openai", "model": "gpt-4o", "total_tokens": 14200000, "cost_usd": 118.40 },
    { "provider": "openai", "model": "text-embedding-3-small", "total_tokens": 4230000, "cost_usd": 28.88 }
  ],
  "by_operation": [
    { "operation": "extract", "total_tokens": 9800000, "cost_usd": 82.00 },
    { "operation": "embed", "total_tokens": 4230000, "cost_usd": 28.88 },
    { "operation": "rag", "total_tokens": 2400000, "cost_usd": 20.10 }
  ],
  "daily_series": [
    { "date": "2026-06-01", "cost_usd": 4.82, "total_tokens": 578400 }
  ]
}
```

---

## 14. Platform Admin Endpoints

All endpoints in this section require a **platform-scoped JWT** (`scope: "platform"`). An org-scoped token returns `403 PLATFORM_ACCESS_REQUIRED` regardless of the org user's role.

### GET /platform/organizations

List all customer organizations across the entire platform.

**Auth:** `[platform: any]`

**Query params:** `?plan=pro&is_active=true&search=acme&page=1&page_size=50`

**Response `200 OK`:**
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "Acme Corp",
      "slug": "acme-corp",
      "plan": "pro",
      "is_active": true,
      "member_count": 34,
      "workflow_count": 27,
      "storage_used_bytes": 214748364,
      "ai_cost_this_month_usd": 147.28,
      "last_run_at": "2026-06-30T09:45:00Z",
      "created_at": "2026-01-01T00:00:00Z"
    }
  ],
  "total": 847,
  "page": 1,
  "page_size": 50,
  "has_next": true
}
```

---

### GET /platform/organizations/{org_id}

Get detailed information about a specific organization.

**Auth:** `[platform: any]`

Support engineers additionally require an active `support_access_grant` for this `org_id`. See §14.12.

**Response `200 OK`:** Full org object + members list + recent runs summary + AI usage summary

---

### POST /platform/organizations/{org_id}/suspend

Suspend an organization. All logins for org users return `401 ORG_SUSPENDED` immediately.

**Auth:** `[platform: platform_admin+]`

**Request:**
```json
{ "reason": "Non-payment after 30-day grace period" }
```

**Response `200 OK`:**
```json
{
  "id": "uuid",
  "is_active": false,
  "suspended_at": "2026-06-30T12:00:00Z",
  "suspended_by": "uuid",
  "reason": "Non-payment after 30-day grace period"
}
```

**Notes:**
- In-progress Celery runs are not interrupted — they will complete or fail naturally
- New run triggers are rejected with `401 ORG_SUSPENDED`
- Action recorded in `platform_audit_logs` with `action: "platform.org.suspended"`

---

### POST /platform/organizations/{org_id}/reinstate

Reinstate a suspended organization.

**Auth:** `[platform: platform_admin+]`

**Request:**
```json
{ "reason": "Payment received" }
```

**Response `200 OK`:** Org object with `is_active: true`

---

### GET /platform/organizations/{org_id}/members

View an organization's member list. For support investigation only.

**Auth:** `[platform: support_engineer+]` + active support access grant required

**Response `200 OK`:** Same shape as `GET /orgs/{org_id}/members`

---

### GET /platform/users

List all platform users (AutoFlow team members).

**Auth:** `[platform: platform_admin+]`

**Response `200 OK`:**
```json
{
  "items": [
    {
      "id": "uuid",
      "email": "alice@autoflow.ai",
      "full_name": "Alice Chen",
      "role": "platform_admin",
      "is_active": true,
      "created_at": "2026-01-01T00:00:00Z"
    }
  ],
  "total": 8
}
```

---

### POST /platform/users

Create a new platform user (onboard an AutoFlow team member).

**Auth:** `[platform: super_admin]`

**Request:**
```json
{
  "email": "bob@autoflow.ai",
  "full_name": "Bob Kim",
  "role": "support_engineer",
  "temporary_password": "TempPass123!"
}
```

**Response `201 Created`:** Platform user object

---

### PATCH /platform/users/{platform_user_id}

Update a platform user's role or active status.

**Auth:** `[platform: super_admin]`

**Request (all fields optional):**
```json
{
  "role": "platform_admin",
  "is_active": false
}
```

**Response `200 OK`:** Updated platform user object

**Notes:**
- Setting `is_active: false` immediately blocks that user's platform sessions
- A `super_admin` cannot demote themselves (must transfer to another super_admin first)

---

### GET /platform/support-grants

List all active support access grants.

**Auth:** `[platform: platform_admin+]`

**Response `200 OK`:**
```json
{
  "items": [
    {
      "id": "uuid",
      "platform_user": { "id": "uuid", "full_name": "Bob Kim", "role": "support_engineer" },
      "organization": { "id": "uuid", "name": "Acme Corp" },
      "granted_by": { "id": "uuid", "full_name": "Alice Chen" },
      "reason": "Customer reported data extraction failure — Ticket #4821",
      "expires_at": "2026-07-01T12:00:00Z",
      "created_at": "2026-06-30T12:00:00Z"
    }
  ],
  "total": 2
}
```

---

### POST /platform/support-grants

Grant a support engineer temporary read access to a customer org.

**Auth:** `[platform: platform_admin+]`

**Request:**
```json
{
  "platform_user_id": "uuid",
  "organization_id": "uuid",
  "reason": "Customer reported data extraction failure — Ticket #4821",
  "duration_hours": 8   // 1–24, default 24
}
```

**Response `201 Created`:**
```json
{
  "id": "uuid",
  "expires_at": "2026-06-30T20:00:00Z",
  "message": "Bob Kim now has read access to Acme Corp until 20:00 UTC."
}
```

---

### DELETE /platform/support-grants/{grant_id}

Revoke an active support grant early.

**Auth:** `[platform: platform_admin+]`

**Response `204 No Content`**

---

### GET /platform/support-tickets

List customer support tickets.

**Auth:** `[platform: support_engineer+]`

**Query params:** `?status=open&priority=critical&assigned_to=uuid&page=1&page_size=25`

**Response `200 OK`:**
```json
{
  "items": [
    {
      "id": "uuid",
      "organization": { "id": "uuid", "name": "Acme Corp" },
      "submitted_by": { "user_id": "uuid", "email": "alice@acme.com" },
      "assigned_to": { "id": "uuid", "full_name": "Bob Kim" },
      "subject": "Workflow execution stuck in 'running' state",
      "status": "in_progress",
      "priority": "high",
      "created_at": "2026-06-30T08:00:00Z",
      "updated_at": "2026-06-30T09:30:00Z"
    }
  ],
  "total": 14,
  "page": 1,
  "page_size": 25,
  "has_next": false
}
```

---

### PATCH /platform/support-tickets/{ticket_id}

Update a support ticket status, priority, or assignee.

**Auth:** `[platform: support_engineer+]`

**Request (all fields optional):**
```json
{
  "status": "resolved",
  "priority": "normal",
  "assigned_to": "uuid"
}
```

**Response `200 OK`:** Updated ticket object

---

### GET /platform/feature-flags

List all feature flags.

**Auth:** `[platform: platform_admin+]`

**Response `200 OK`:**
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "multi_agent_workflows",
      "description": "Enable LangGraph multi-agent node type",
      "is_enabled": true,
      "rollout_pct": 25,
      "target_orgs": ["uuid"],
      "updated_by": { "id": "uuid", "full_name": "Alice Chen" },
      "updated_at": "2026-06-28T14:00:00Z"
    }
  ],
  "total": 12
}
```

---

### PATCH /platform/feature-flags/{flag_id}

Update a feature flag's enabled state, rollout percentage, or org overrides.

**Auth:** `[platform: super_admin]`

**Request (all fields optional):**
```json
{
  "is_enabled": true,
  "rollout_pct": 50,
  "target_orgs": ["uuid-acme", "uuid-globex"]
}
```

**Response `200 OK`:** Updated feature flag object

---

### GET /platform/system/health

Get real-time system health metrics for the DevOps dashboard.

**Auth:** `[platform: devops_engineer+]`

**Response `200 OK`:**
```json
{
  "api": {
    "instances": 2,
    "p95_latency_ms": 187,
    "requests_per_minute": 340
  },
  "celery": {
    "active_workers": 4,
    "queue_depth": 23,
    "tasks_per_minute": 84
  },
  "database": {
    "connection_pool_used": 14,
    "connection_pool_max": 40,
    "p95_query_latency_ms": 12,
    "replication_lag_ms": 0
  },
  "redis": {
    "memory_used_mb": 512,
    "memory_max_mb": 4096,
    "used_pct": 12.5,
    "connected_clients": 28
  },
  "storage": {
    "total_used_gb": 384,
    "bucket_object_count": 28471
  },
  "checked_at": "2026-06-30T12:00:00Z"
}
```

---

### GET /platform/audit-logs

View the platform-level audit trail (actions taken by AutoFlow team members).

**Auth:** `[platform: platform_admin+]`

**Query params:** `?platform_user_id=uuid&org_id=uuid&action=platform.org.suspended&from_date=...&page=1&page_size=50`

**Response `200 OK`:**
```json
{
  "items": [
    {
      "id": "uuid",
      "actor": { "id": "uuid", "full_name": "Alice Chen", "role": "platform_admin" },
      "action": "platform.org.suspended",
      "resource_type": "organization",
      "resource_id": "uuid",
      "organization": { "id": "uuid", "name": "Acme Corp" },
      "ip_address": "203.0.113.42",
      "metadata": {
        "reason": "Non-payment after 30-day grace period",
        "previous_status": "active"
      },
      "created_at": "2026-06-30T12:00:00Z"
    }
  ],
  "total": 214,
  "page": 1,
  "page_size": 50,
  "has_next": true
}
```

---

## 15. Webhook Receiver

### POST /webhooks/{workflow_id}

Receive an inbound webhook trigger for a published workflow. No user auth — the `workflow_id` in the path acts as the routing key. HMAC signature verification is applied if the workflow's trigger config includes a `webhook_secret`.

**Auth:** `[public]` (HMAC optional per workflow config)

**Path:** `/webhooks/{workflow_id}` (note: no `/api/v1/` prefix)

**Headers (when secret is configured):**
```
X-Autoflow-Signature: sha256=<hmac-hex>
X-Autoflow-Timestamp: 1751289600
```

**Request:** Any JSON body — passed as `trigger_payload` to the workflow run

**Response `202 Accepted`:**
```json
{ "run_id": "uuid", "status": "pending" }
```

**Response `404 Not Found`:** Workflow does not exist or is not published

**Response `401 Unauthorized`:** HMAC signature invalid or timestamp more than 5 minutes old

**Notes:**
- Rate limited to 60 requests/minute per workflow
- A webhook-triggered run has `trigger_type = 'webhook'` and `triggered_by = NULL`
- HMAC validation: `HMAC-SHA256(secret, f"{timestamp}.{raw_request_body}")`

---

## 16. WebSocket Protocol

### Connection

```
wss://api.autoflow.ai/ws?token={access_token}
```

The access token is passed as a query parameter (not a header — WebSocket browsers cannot set custom headers). The token is validated on connection establishment; an invalid token closes the connection immediately with code `4001`.

One WebSocket connection per browser session. The connection is established when the user enters the `(dashboard)` route group and torn down on logout.

### Message Format

All messages from server → client are JSON:

```json
{
  "type": "run.status_changed",
  "data": { ... },
  "timestamp": "2026-06-30T09:45:12Z"
}
```

### Server → Client Message Types

| Type | When Fired | `data` Shape |
|------|-----------|--------------|
| `run.started` | WorkflowRun status → `running` | `{ run_id, workflow_id, workflow_name }` |
| `node.started` | Node execution begins | `{ run_id, node_id, node_type, node_label }` |
| `node.completed` | Node execution succeeds | `{ run_id, node_id, output_preview: string (truncated 500 chars) }` |
| `node.failed` | Node execution fails | `{ run_id, node_id, error_message, attempt_number }` |
| `run.completed` | WorkflowRun status → `completed` | `{ run_id, duration_ms }` |
| `run.failed` | WorkflowRun status → `failed` | `{ run_id, error_message }` |
| `run.cancelled` | WorkflowRun manually cancelled | `{ run_id }` |
| `notification.new` | Any new Notification created for this user | `{ id, type, title, body }` |
| `ping` | Server keepalive (every 30s) | `{}` |

### Client → Server Message Types

Clients only send one message type:

```json
{ "type": "pong" }
```

Sent in response to `ping`. If the server does not receive `pong` within 10 seconds after sending `ping`, the connection is closed with code `1001 Going Away`.

### Tenant Isolation

The WebSocket connection subscribes to the Redis pub/sub channel `ws:org:{org_id}` derived from the JWT's `org_id` claim. Events for other organizations are structurally unreachable — the channel is org-scoped at the publish layer.

### Reconnection

If the connection is lost (network interruption, server restart), the frontend reconnects with exponential backoff: 1s → 2s → 4s → 8s → max 30s. On reconnect, the client calls `GET /runs` and `GET /notifications` to catch up on any events missed during the disconnection window.

---

*End of API Design Document v1.0.0*

*This document is the authoritative API contract. All endpoint signatures are stable within v1. Changes to request/response shapes require a version increment and backward-compatible transition period. Implementation must match this document exactly — discrepancies are bugs in the implementation, not the spec.*
