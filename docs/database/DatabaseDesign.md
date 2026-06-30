# Database Design Document
# AI Business Process Automation Platform

| Field | Value |
|-------|-------|
| Version | 1.1.0 |
| Status | Approved |
| Date | 2026-06-30 |
| Author | Architecture Team |
| References | docs/SRS.md §10, docs/architecture/ARCHITECTURE.md §8, §10.5 |

---

## Table of Contents

1. [Overview](#1-overview)
2. [Entity Relationship Diagram](#2-entity-relationship-diagram)
3. [Schema — Auth Domain](#3-schema--auth-domain)
4. [Schema — Organization Domain](#4-schema--organization-domain)
5. [Schema — Workflow Domain](#5-schema--workflow-domain)
6. [Schema — Execution Domain](#6-schema--execution-domain)
7. [Schema — AI & Files Domain](#7-schema--ai--files-domain)
8. [Schema — Platform Domain](#8-schema--platform-domain)
9. [Complete Index Strategy](#9-complete-index-strategy)
10. [pgvector Configuration](#10-pgvector-configuration)
11. [Constraints & Integrity Rules](#11-constraints--integrity-rules)
12. [Common Query Patterns](#12-common-query-patterns)
13. [Migrations Strategy](#13-migrations-strategy)
14. [Partitioning Strategy](#14-partitioning-strategy)
15. [Redis Schema](#15-redis-schema)
16. [Object Storage Layout](#16-object-storage-layout)
17. [Seed Data](#17-seed-data)
18. [Backup & Recovery](#18-backup--recovery)

---

## 1. Overview

### 1.1 Database Engine

| Property | Value |
|----------|-------|
| Engine | PostgreSQL 16 |
| Extensions | `pgvector`, `uuid-ossp`, `pg_trgm`, `btree_gin` |
| Encoding | UTF-8 |
| Collation | `en_US.UTF-8` |
| Timezone | UTC (all timestamps stored in UTC) |

### 1.2 Extensions Setup

```sql
-- Run once on database creation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";     -- UUID generation
CREATE EXTENSION IF NOT EXISTS "pgvector";       -- Vector similarity search
CREATE EXTENSION IF NOT EXISTS "pg_trgm";        -- Trigram text search
CREATE EXTENSION IF NOT EXISTS "btree_gin";      -- GIN indexes on scalar types
```

### 1.3 Design Principles

1. **Every primary key is a UUID.** Generated server-side via `gen_random_uuid()`. Prevents sequential ID enumeration attacks and supports future multi-region data merging.
2. **All timestamps in UTC with timezone.** Stored as `TIMESTAMPTZ`. Application converts to user timezone at display time.
3. **Tenant isolation via `organization_id`.** Every table with organization-scoped data carries `organization_id NOT NULL`. The application layer always filters by this column — no exceptions.
4. **Soft deletes for user-facing entities.** `documents` and `workflows` use `deleted_at TIMESTAMPTZ` rather than hard deletes to preserve audit trails and allow recovery.
5. **JSONB for flexible configuration.** Node `config`, workflow `settings`, and `metadata` columns use JSONB. This avoids wide sparse tables for configuration data that varies per entity type.
6. **Append-only audit and usage logs.** `audit_logs` and `ai_usage_logs` are never updated or deleted. Partitioning manages their size.
7. **No application-level sequences.** `version_number` uses a subquery max + 1 pattern inside a transaction, not a global sequence, to scope version numbers per workflow.

### 1.4 Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Tables | `snake_case`, plural | `workflow_runs` |
| Columns | `snake_case` | `organization_id` |
| Primary keys | `id` | `id UUID PK` |
| Foreign keys | `{referenced_table_singular}_id` | `workflow_id` |
| Indexes | `idx_{table}_{columns}` | `idx_workflows_org_status` |
| Unique indexes | `uq_{table}_{columns}` | `uq_users_email` |
| Check constraints | `chk_{table}_{rule}` | `chk_workflow_runs_status` |
| Timestamps | `{event}_at` | `created_at`, `deleted_at` |

---

## 2. Entity Relationship Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                         AUTH DOMAIN                                   │
│                                                                       │
│  ┌─────────┐     ┌──────────────────┐     ┌─────────────────────┐   │
│  │  users  │────<│  oauth_accounts  │     │ email_verification_  │   │
│  │         │     └──────────────────┘     │      tokens         │   │
│  │         │────<│ password_reset_  │     └─────────────────────┘   │
│  │         │     │     tokens       │────<                           │
│  └────┬────┘     └──────────────────┘                               │
└───────│──────────────────────────────────────────────────────────────┘
        │
┌───────│──────────────────────────────────────────────────────────────┐
│       │               ORGANIZATION DOMAIN                             │
│       │                                                               │
│  ┌────┴──────────┐   ┌─────────────┐   ┌───────────────┐           │
│  │  org_members  │>──│organizations│──<│  departments   │           │
│  └───────────────┘   │             │   └───────────────┘           │
│                       │             │──<│  invitations   │           │
│  user_notification_  │             │   └───────────────┘           │
│  preferences ────────│             │──<│    api_keys    │           │
│                       │             │   └───────────────┘           │
│                       │             │──<│  integrations  │           │
└───────────────────────│─────────────────────────────────────────────┘
                        │
┌───────────────────────│─────────────────────────────────────────────┐
│                        │         WORKFLOW DOMAIN                      │
│                        │                                              │
│                   ┌────┴─────┐    ┌──────────────────┐              │
│                   │workflows │──<─│ workflow_versions │              │
│                   │          │    │                  │──<─┐          │
│                   └────┬─────┘    └──────────────────┘    │          │
│                        │                              workflow_nodes  │
│                        │                              workflow_edges  │
└────────────────────────│────────────────────────────────────────────┘
                         │
┌────────────────────────│────────────────────────────────────────────┐
│                         │        EXECUTION DOMAIN                     │
│                         │                                             │
│                    ┌────┴──────────┐    ┌─────────────────┐         │
│                    │ workflow_runs  │──<─│ execution_logs  │         │
│                    │ (parent_run_id│    └─────────────────┘         │
│                    │  self-ref)    │──<─┐                            │
│                    └───────────────┘    │ ai_usage_logs              │
└─────────────────────────────────────────────────────────────────────┘
                         │
┌────────────────────────│────────────────────────────────────────────┐
│                         │      AI & FILES DOMAIN                      │
│                         │                                             │
│              ┌──────────┴──┐    ┌───────────────────┐               │
│              │  documents  │──<─│  document_chunks  │               │
│              │             │    │  (VECTOR(1536))   │               │
│              └─────────────┘    └───────────────────┘               │
└─────────────────────────────────────────────────────────────────────┘
                         │
┌────────────────────────│────────────────────────────────────────────┐
│                         │      ORG CROSS-CUTTING DOMAIN               │
│                         │                                             │
│              notifications (user_id + org_id)                        │
│              audit_logs  (user_id + org_id, append-only)             │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                   PLATFORM ADMIN DOMAIN                               │
│                   (AutoFlow team infrastructure — no org_id)          │
│                                                                       │
│  ┌───────────────────┐   ┌──────────────────────┐                   │
│  │  platform_users   │──<│ support_access_grants │                   │
│  │  (AutoFlow staff) │   │ (TTL 24h per org)     │                   │
│  └───────────────────┘   └──────────────────────┘                   │
│                                                                       │
│  ┌────────────────┐   ┌──────────────────────┐                      │
│  │ support_tickets│   │   feature_flags       │                      │
│  │ (customer →    │   │   (platform toggles)  │                      │
│  │  AutoFlow)     │   └──────────────────────┘                      │
│  └────────────────┘                                                  │
│                                                                       │
│  platform_audit_logs  (platform-level audit, append-only)            │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.1 Table Count Summary

| Domain | Tables |
|--------|--------|
| Auth | 4 (`users`, `oauth_accounts`, `email_verification_tokens`, `password_reset_tokens`) |
| Organization | 5 (`organizations`, `org_members`, `departments`, `invitations`, `user_notification_preferences`) |
| Workflow | 4 (`workflows`, `workflow_versions`, `workflow_nodes`, `workflow_edges`) |
| Execution | 2 (`workflow_runs`, `execution_logs`) |
| AI & Files | 4 (`documents`, `document_chunks`, `ai_usage_logs`, `integrations`) |
| Org Cross-Cutting | 3 (`api_keys`, `notifications`, `audit_logs`) |
| Platform Admin | 5 (`platform_users`, `support_access_grants`, `support_tickets`, `feature_flags`, `platform_audit_logs`) |
| **Total** | **27 tables** |

> **Scope distinction:** Every table in the first 6 domains carries an `organization_id` and belongs to a customer tenant. The Platform Admin domain has no `organization_id` — it belongs to AutoFlow's own operational infrastructure and is only accessible via platform-scoped JWTs (see ARCHITECTURE.md §10.5).

---

## 3. Schema — Auth Domain

### 3.1 `users`

Central identity table. One row per unique person regardless of how many organizations they belong to.

```sql
CREATE TABLE users (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    email             VARCHAR(255) NOT NULL,
    hashed_password   VARCHAR(255),            -- NULL for OAuth-only accounts
    full_name         VARCHAR(255) NOT NULL,
    avatar_url        TEXT,
    is_verified       BOOLEAN     NOT NULL DEFAULT FALSE,
    is_active         BOOLEAN     NOT NULL DEFAULT TRUE,
    tos_accepted_at   TIMESTAMPTZ,             -- Terms of Service acceptance timestamp
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX uq_users_email ON users (LOWER(email));
CREATE INDEX idx_users_is_active ON users (is_active) WHERE is_active = TRUE;
```

**Column notes:**

| Column | Notes |
|--------|-------|
| `email` | Stored in original case; unique index uses `LOWER(email)` for case-insensitive lookup |
| `hashed_password` | bcrypt hash (cost 12). NULL when user authenticated exclusively via OAuth |
| `is_verified` | Set to TRUE when the user clicks the email verification link |
| `is_active` | Set to FALSE on account deletion (soft disable). Blocked from login immediately |
| `tos_accepted_at` | Required for GDPR compliance — records when ToS was accepted (RC-005) |

---

### 3.2 `oauth_accounts`

Links a platform user account to one or more external OAuth provider identities.

```sql
CREATE TABLE oauth_accounts (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider            VARCHAR(50) NOT NULL,   -- 'google', 'microsoft'
    provider_user_id    VARCHAR(255) NOT NULL,
    provider_email      VARCHAR(255),
    access_token        TEXT,                   -- AES-256 encrypted
    refresh_token       TEXT,                   -- AES-256 encrypted
    token_expires_at    TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_oauth_provider_user UNIQUE (provider, provider_user_id),
    CONSTRAINT chk_oauth_provider CHECK (provider IN ('google', 'microsoft'))
);

CREATE INDEX idx_oauth_accounts_user_id ON oauth_accounts (user_id);
```

**Column notes:**

| Column | Notes |
|--------|-------|
| `provider_user_id` | The OAuth provider's stable user ID (e.g., Google `sub` claim) |
| `provider_email` | Email returned by the provider — may differ from `users.email` if user changed it |
| `access_token` | Short-lived OAuth access token, AES-256 encrypted at rest |
| `refresh_token` | Long-lived OAuth refresh token, AES-256 encrypted at rest |

---

### 3.3 `email_verification_tokens`

One-time tokens sent when a user registers or requests email re-verification.

```sql
CREATE TABLE email_verification_tokens (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(255) NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ,                   -- NULL until consumed
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_email_verification_token UNIQUE (token_hash)
);

CREATE INDEX idx_email_verification_user_id ON email_verification_tokens (user_id);
```

**Flow:** Application generates a random 32-byte token → SHA-256 hashes it → stores hash → sends plaintext in email link. On verification, application hashes the incoming token and looks up the hash. `used_at` is set on first use; subsequent calls with the same token are rejected.

---

### 3.4 `password_reset_tokens`

One-time tokens sent when a user requests a password reset. Valid for 1 hour.

```sql
CREATE TABLE password_reset_tokens (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(255) NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,          -- NOW() + INTERVAL '1 hour'
    used_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_password_reset_token UNIQUE (token_hash)
);

CREATE INDEX idx_password_reset_user_id ON password_reset_tokens (user_id);
```

**Security note:** Only one active (unused, unexpired) reset token per user should be enforced at the application layer — when a new reset is requested, the previous token is marked used. This prevents token accumulation.

---

## 4. Schema — Organization Domain

### 4.1 `organizations`

Top-level tenant container. All other organization-scoped data references this table.

```sql
CREATE TABLE organizations (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name                VARCHAR(255) NOT NULL,
    slug                VARCHAR(100) NOT NULL,
    plan                VARCHAR(50)  NOT NULL DEFAULT 'free',
    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,
    settings            JSONB       NOT NULL DEFAULT '{}',
    storage_used_bytes  BIGINT      NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_organizations_slug UNIQUE (slug),
    CONSTRAINT chk_organizations_plan CHECK (plan IN ('free', 'pro', 'enterprise')),
    CONSTRAINT chk_organizations_storage CHECK (storage_used_bytes >= 0)
);

CREATE INDEX idx_organizations_slug ON organizations (slug);
CREATE INDEX idx_organizations_active ON organizations (is_active) WHERE is_active = TRUE;
```

**`settings` JSONB structure:**
```json
{
  "timezone": "America/New_York",
  "language": "en",
  "logo_url": "https://...",
  "ai_budget_usd_monthly": 100.00,
  "max_workflow_executions_monthly": 10000,
  "max_storage_bytes": 5368709120
}
```

---

### 4.2 `org_members`

Membership join table. Defines a user's role within a specific organization.

```sql
CREATE TABLE org_members (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id         UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role            VARCHAR(50) NOT NULL,
    department_id   UUID        REFERENCES departments(id) ON DELETE SET NULL,
    joined_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_org_members_org_user UNIQUE (organization_id, user_id),
    CONSTRAINT chk_org_members_role CHECK (
        role IN ('owner', 'admin', 'manager', 'analyst', 'employee', 'viewer')
    )
);

CREATE INDEX idx_org_members_user_id ON org_members (user_id);
CREATE INDEX idx_org_members_org_role ON org_members (organization_id, role);
```

**Business rules enforced at application layer:**
- Only one member with `role = 'owner'` per organization at any time
- Owner cannot change their own role without first transferring ownership
- An organization must always have exactly one owner

---

### 4.3 `departments`

Optional grouping of users within an organization. Used to scope workflows and filter analytics.

```sql
CREATE TABLE departments (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_departments_org_name UNIQUE (organization_id, name)
);

CREATE INDEX idx_departments_org_id ON departments (organization_id);
```

---

### 4.4 `invitations`

Pending invitations to join an organization. Expire after 48 hours.

```sql
CREATE TABLE invitations (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    invited_by      UUID        NOT NULL REFERENCES users(id),
    email           VARCHAR(255) NOT NULL,
    role            VARCHAR(50) NOT NULL,
    token_hash      VARCHAR(255) NOT NULL,
    expires_at      TIMESTAMPTZ NOT NULL,      -- NOW() + INTERVAL '48 hours'
    accepted_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_invitations_token UNIQUE (token_hash),
    CONSTRAINT chk_invitations_role CHECK (
        role IN ('admin', 'manager', 'analyst', 'employee', 'viewer')
    )
);

CREATE INDEX idx_invitations_org_email ON invitations (organization_id, email);
CREATE INDEX idx_invitations_expires ON invitations (expires_at)
    WHERE accepted_at IS NULL;
```

**Note:** Only one pending invitation per `(organization_id, email)` pair should be active at once — enforced at application layer. New invitations invalidate previous ones for the same email+org combination.

---

### 4.5 `user_notification_preferences`

Per-user, per-organization notification settings. Created with defaults on first login to an organization.

```sql
CREATE TABLE user_notification_preferences (
    id                          UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                     UUID    NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id             UUID    NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email_on_workflow_failure   BOOLEAN NOT NULL DEFAULT TRUE,
    email_on_workflow_success   BOOLEAN NOT NULL DEFAULT FALSE,
    email_on_invitation         BOOLEAN NOT NULL DEFAULT TRUE,
    email_on_weekly_report      BOOLEAN NOT NULL DEFAULT TRUE,
    inapp_on_workflow_failure   BOOLEAN NOT NULL DEFAULT TRUE,
    inapp_on_workflow_success   BOOLEAN NOT NULL DEFAULT TRUE,
    inapp_on_mention            BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_notif_prefs_user_org UNIQUE (user_id, organization_id)
);

CREATE INDEX idx_notif_prefs_user_id ON user_notification_preferences (user_id);
```

---

## 5. Schema — Workflow Domain

### 5.1 `workflows`

Master workflow record. Holds identity and status. Actual graph definition lives in `workflow_versions`.

```sql
CREATE TABLE workflows (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id   UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    created_by        UUID        NOT NULL REFERENCES users(id),
    name              VARCHAR(255) NOT NULL,
    description       TEXT,
    status            VARCHAR(50) NOT NULL DEFAULT 'draft',
    active_version_id UUID,                   -- FK added via ALTER after workflow_versions
    tags              JSONB       NOT NULL DEFAULT '[]',
    deleted_at        TIMESTAMPTZ,            -- soft delete
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_workflows_status CHECK (status IN ('draft', 'published', 'archived'))
);

CREATE INDEX idx_workflows_org_status
    ON workflows (organization_id, status)
    WHERE deleted_at IS NULL;

CREATE INDEX idx_workflows_org_created
    ON workflows (organization_id, created_at DESC)
    WHERE deleted_at IS NULL;

-- Added after workflow_versions table is created:
ALTER TABLE workflows
    ADD CONSTRAINT fk_workflows_active_version
    FOREIGN KEY (active_version_id)
    REFERENCES workflow_versions(id)
    ON DELETE SET NULL
    DEFERRABLE INITIALLY DEFERRED;
```

**`tags` JSONB structure:** `["finance", "invoice-processing", "automated"]`

---

### 5.2 `workflow_versions`

Immutable snapshot of a workflow graph at the time of publishing. Each publish creates a new version.

```sql
CREATE TABLE workflow_versions (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id     UUID        NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    version_number  INTEGER     NOT NULL,
    published_by    UUID        NOT NULL REFERENCES users(id),
    published_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    definition      JSONB       NOT NULL,      -- full graph: nodes + edges + configs
    change_summary  TEXT,                      -- optional human-readable description of changes

    CONSTRAINT uq_workflow_versions_num UNIQUE (workflow_id, version_number),
    CONSTRAINT chk_version_number_positive CHECK (version_number >= 1)
);

CREATE INDEX idx_workflow_versions_workflow_id
    ON workflow_versions (workflow_id, version_number DESC);
```

**`definition` JSONB structure:**
```json
{
  "nodes": [
    {
      "id": "node-uuid",
      "type": "trigger.webhook",
      "label": "Customer Invoice Received",
      "position": {"x": 100, "y": 200},
      "config": {"path": "/invoice", "method": "POST"}
    }
  ],
  "edges": [
    {
      "id": "edge-uuid",
      "source": "node-uuid-1",
      "target": "node-uuid-2",
      "sourceHandle": "output",
      "targetHandle": "input"
    }
  ]
}
```

**Version number assignment** (inside a transaction to prevent race conditions):
```sql
INSERT INTO workflow_versions (workflow_id, version_number, ...)
SELECT :workflow_id,
       COALESCE(MAX(version_number), 0) + 1,
       ...
FROM workflow_versions
WHERE workflow_id = :workflow_id;
```

---

### 5.3 `workflow_nodes`

Individual nodes within a published workflow version. Denormalized from the `definition` JSONB for efficient execution log foreign key references.

```sql
CREATE TABLE workflow_nodes (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_version_id UUID        NOT NULL REFERENCES workflow_versions(id) ON DELETE CASCADE,
    node_type           VARCHAR(100) NOT NULL,
    label               VARCHAR(255),
    position_x          FLOAT       NOT NULL DEFAULT 0,
    position_y          FLOAT       NOT NULL DEFAULT 0,
    config              JSONB       NOT NULL DEFAULT '{}'
);

CREATE INDEX idx_workflow_nodes_version_id ON workflow_nodes (workflow_version_id);
CREATE INDEX idx_workflow_nodes_type ON workflow_nodes (node_type);
```

**Registered `node_type` values:**

| Category | Values |
|----------|--------|
| Triggers | `trigger.manual`, `trigger.schedule`, `trigger.webhook`, `trigger.email` |
| Actions | `action.http`, `action.email`, `action.condition`, `action.delay`, `action.db_write` |
| AI | `ai.extraction`, `ai.classification`, `ai.summarization`, `ai.prompt`, `ai.rag`, `ai.multi_agent` |

---

### 5.4 `workflow_edges`

Directed connections between nodes. Defines the execution order and branching logic.

```sql
CREATE TABLE workflow_edges (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_version_id UUID        NOT NULL REFERENCES workflow_versions(id) ON DELETE CASCADE,
    source_node_id      UUID        NOT NULL REFERENCES workflow_nodes(id) ON DELETE CASCADE,
    target_node_id      UUID        NOT NULL REFERENCES workflow_nodes(id) ON DELETE CASCADE,
    source_handle       VARCHAR(50) NOT NULL DEFAULT 'output',
    target_handle       VARCHAR(50) NOT NULL DEFAULT 'input',

    CONSTRAINT chk_workflow_edges_no_self_loop
        CHECK (source_node_id <> target_node_id)
);

CREATE INDEX idx_workflow_edges_version_id ON workflow_edges (workflow_version_id);
CREATE INDEX idx_workflow_edges_source ON workflow_edges (source_node_id);
CREATE INDEX idx_workflow_edges_target ON workflow_edges (target_node_id);
```

**`source_handle` values for condition nodes:** `'true'`, `'false'`, `'default'`

---

## 6. Schema — Execution Domain

### 6.1 `workflow_runs`

One record per workflow execution. The top-level container for a single run.

```sql
CREATE TABLE workflow_runs (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    workflow_id         UUID        NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    workflow_version_id UUID        NOT NULL REFERENCES workflow_versions(id),
    triggered_by        UUID        REFERENCES users(id) ON DELETE SET NULL,
    trigger_type        VARCHAR(50) NOT NULL,
    status              VARCHAR(50) NOT NULL DEFAULT 'pending',
    input_data          JSONB       NOT NULL DEFAULT '{}',
    output_data         JSONB,
    error_message       TEXT,
    parent_run_id       UUID        REFERENCES workflow_runs(id) ON DELETE SET NULL,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,

    CONSTRAINT chk_workflow_runs_trigger CHECK (
        trigger_type IN ('manual', 'schedule', 'webhook', 'api')
    ),
    CONSTRAINT chk_workflow_runs_status CHECK (
        status IN ('pending', 'running', 'completed', 'failed', 'cancelled')
    )
);

-- Primary dashboard query: list runs for an org sorted by recency
CREATE INDEX idx_workflow_runs_org_status_started
    ON workflow_runs (organization_id, status, started_at DESC);

-- Per-workflow run history
CREATE INDEX idx_workflow_runs_workflow_id
    ON workflow_runs (workflow_id, started_at DESC);

-- Retry chain lookup
CREATE INDEX idx_workflow_runs_parent_run_id
    ON workflow_runs (parent_run_id)
    WHERE parent_run_id IS NOT NULL;
```

**`parent_run_id` usage:** When a user triggers "Retry from Failed Node", the system creates a new `workflow_run` with `parent_run_id` pointing to the original failed run. The engine loads the parent run's completed `execution_logs` to reconstruct `node_outputs`, skipping already-completed nodes and preventing duplicate side effects.

---

### 6.2 `execution_logs`

One record per node execution attempt within a workflow run. High write-volume table — candidate for partitioning at scale.

```sql
CREATE TABLE execution_logs (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id UUID        NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    node_id         UUID        NOT NULL REFERENCES workflow_nodes(id),
    status          VARCHAR(50) NOT NULL DEFAULT 'pending',
    attempt_number  INTEGER     NOT NULL DEFAULT 1,
    input_data      JSONB,
    output_data     JSONB,
    error_message   TEXT,
    error_type      VARCHAR(100),              -- e.g., 'ExternalServiceError', 'TimeoutError'
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    duration_ms     INTEGER,

    CONSTRAINT chk_execution_logs_status CHECK (
        status IN ('pending', 'running', 'completed', 'failed', 'skipped')
    ),
    CONSTRAINT chk_execution_logs_attempt CHECK (attempt_number >= 1),
    CONSTRAINT chk_execution_logs_duration CHECK (
        duration_ms IS NULL OR duration_ms >= 0
    )
);

-- Primary access: all logs for a specific run
CREATE INDEX idx_execution_logs_run_id
    ON execution_logs (workflow_run_id);

-- Secondary: find all logs for a specific node (analytics, debugging)
CREATE INDEX idx_execution_logs_node_id
    ON execution_logs (node_id, started_at DESC);

-- Failed node analysis
CREATE INDEX idx_execution_logs_failed
    ON execution_logs (node_id, attempt_number)
    WHERE status = 'failed';
```

---

## 7. Schema — AI & Files Domain

### 7.1 `documents`

Metadata for all uploaded files. Binary content is stored in object storage, never in the database.

```sql
CREATE TABLE documents (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    uploaded_by     UUID        NOT NULL REFERENCES users(id),
    name            VARCHAR(500) NOT NULL,
    mime_type       VARCHAR(100) NOT NULL,
    size_bytes      BIGINT      NOT NULL,
    storage_key     TEXT        NOT NULL,       -- S3 object key
    metadata        JSONB       NOT NULL DEFAULT '{}',
    is_indexed      BOOLEAN     NOT NULL DEFAULT FALSE,
    deleted_at      TIMESTAMPTZ,               -- soft delete
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_documents_storage_key UNIQUE (storage_key),
    CONSTRAINT chk_documents_size CHECK (size_bytes > 0)
);

CREATE INDEX idx_documents_org_created
    ON documents (organization_id, created_at DESC)
    WHERE deleted_at IS NULL;

CREATE INDEX idx_documents_org_indexed
    ON documents (organization_id, is_indexed)
    WHERE deleted_at IS NULL;

-- Trigram index for name search
CREATE INDEX idx_documents_name_trgm
    ON documents USING GIN (name gin_trgm_ops)
    WHERE deleted_at IS NULL;
```

**`metadata` JSONB structure:**
```json
{
  "page_count": 12,
  "word_count": 4500,
  "language": "en",
  "extracted_at": "2026-06-30T10:00:00Z",
  "ocr_applied": false
}
```

**On soft delete:** Set `deleted_at = NOW()`. The storage object is deleted asynchronously by a Celery task. The `storage_key` unique constraint prevents re-upload to the same key path after deletion.

---

### 7.2 `document_chunks`

Text chunks with vector embeddings for RAG retrieval. This is the highest-cardinality table — expect 100–1000 rows per document.

```sql
CREATE TABLE document_chunks (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID        NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    organization_id UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    chunk_index     INTEGER     NOT NULL,
    content         TEXT        NOT NULL,
    embedding       VECTOR(1536),              -- pgvector; NULL until indexed
    metadata        JSONB       NOT NULL DEFAULT '{}',

    CONSTRAINT uq_document_chunks_doc_idx UNIQUE (document_id, chunk_index),
    CONSTRAINT chk_document_chunks_idx CHECK (chunk_index >= 0)
);

-- pgvector HNSW index for cosine similarity (see Section 10)
CREATE INDEX idx_document_chunks_embedding
    ON document_chunks USING HNSW (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Tenant-scoped chunk lookup (used before vector search to filter by org)
CREATE INDEX idx_document_chunks_org_id
    ON document_chunks (organization_id);
```

**`metadata` JSONB structure:**
```json
{
  "page_number": 3,
  "section": "Terms and Conditions",
  "char_start": 1500,
  "char_end": 3000,
  "token_count": 487
}
```

---

### 7.3 `ai_usage_logs`

Append-only log of every LLM API call. Used for cost tracking, analytics, and budget enforcement.

```sql
CREATE TABLE ai_usage_logs (
    id                  UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID           NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    workflow_run_id     UUID           REFERENCES workflow_runs(id) ON DELETE SET NULL,
    node_id             UUID           REFERENCES workflow_nodes(id) ON DELETE SET NULL,
    provider            VARCHAR(50)    NOT NULL,
    model               VARCHAR(100)   NOT NULL,
    operation           VARCHAR(50)    NOT NULL,
    prompt_tokens       INTEGER        NOT NULL DEFAULT 0,
    completion_tokens   INTEGER        NOT NULL DEFAULT 0,
    total_tokens        INTEGER        NOT NULL DEFAULT 0,
    estimated_cost_usd  NUMERIC(10,6)  NOT NULL DEFAULT 0,
    latency_ms          INTEGER        NOT NULL,
    created_at          TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_ai_usage_provider CHECK (
        provider IN ('openai', 'anthropic', 'ollama')
    ),
    CONSTRAINT chk_ai_usage_operation CHECK (
        operation IN ('chat', 'embed', 'classify', 'extract', 'summarize', 'rag', 'agent')
    ),
    CONSTRAINT chk_ai_usage_tokens CHECK (
        prompt_tokens >= 0 AND completion_tokens >= 0 AND total_tokens >= 0
    ),
    CONSTRAINT chk_ai_usage_latency CHECK (latency_ms >= 0)
);

-- Monthly cost aggregation (analytics dashboard)
CREATE INDEX idx_ai_usage_org_created
    ON ai_usage_logs (organization_id, created_at DESC);

-- Per-workflow cost breakdown
CREATE INDEX idx_ai_usage_run_id
    ON ai_usage_logs (workflow_run_id)
    WHERE workflow_run_id IS NOT NULL;

-- Model-level usage reports
CREATE INDEX idx_ai_usage_org_model
    ON ai_usage_logs (organization_id, model, created_at DESC);
```

---

### 7.4 `integrations`

Stores configured connections to external services (Gmail, Slack, Google Drive). Credentials are AES-256 encrypted.

```sql
CREATE TABLE integrations (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    created_by          UUID        NOT NULL REFERENCES users(id),
    provider            VARCHAR(100) NOT NULL,
    name                VARCHAR(255) NOT NULL,
    status              VARCHAR(50) NOT NULL DEFAULT 'active',
    credentials         JSONB       NOT NULL DEFAULT '{}',  -- all values AES-256 encrypted
    config              JSONB       NOT NULL DEFAULT '{}',
    last_verified_at    TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_integrations_org_provider_name
        UNIQUE (organization_id, provider, name),
    CONSTRAINT chk_integrations_provider CHECK (
        provider IN ('gmail', 'google_drive', 'slack', 'microsoft_teams',
                     'outlook', 'salesforce', 'hubspot', 'custom_http')
    ),
    CONSTRAINT chk_integrations_status CHECK (
        status IN ('active', 'inactive', 'error')
    )
);

CREATE INDEX idx_integrations_org_id ON integrations (organization_id, status);
```

**`credentials` JSONB structure (all string values are AES-256 encrypted before storage):**
```json
{
  "access_token":  "<encrypted>",
  "refresh_token": "<encrypted>",
  "client_id":     "<encrypted>",
  "webhook_secret": "<encrypted>"
}
```

---

## 8. Schema — Platform Domain

This section covers two distinct sub-domains:

- **Sections 8.1–8.3** — Org-level cross-cutting tables (`api_keys`, `notifications`, `audit_logs`). These carry `organization_id` and are accessed by both org users and platform admins.
- **Sections 8.4–8.8** — Platform Admin tables (`platform_users`, `support_access_grants`, `support_tickets`, `feature_flags`, `platform_audit_logs`). No `organization_id` — these belong to AutoFlow's own operational infrastructure and require a platform-scoped JWT.

### 8.1 `api_keys`

API keys for programmatic platform access. Plaintext is never stored — only a bcrypt hash.

```sql
CREATE TABLE api_keys (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    created_by      UUID        NOT NULL REFERENCES users(id),
    label           VARCHAR(255) NOT NULL,
    key_hash        VARCHAR(255) NOT NULL,          -- bcrypt hash of full key
    key_prefix      VARCHAR(12)  NOT NULL,          -- first 8 chars, shown in UI
    scopes          JSONB        NOT NULL DEFAULT '[]',
    last_used_at    TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,
    revoked_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Non-revoked key lookup (primary auth path)
CREATE INDEX idx_api_keys_org_active
    ON api_keys (organization_id)
    WHERE revoked_at IS NULL;
```

**`scopes` JSONB structure:** `["workflow:read", "workflow:execute", "document:read", "document:write"]`

**Supported scope values:**

| Scope | Access Granted |
|-------|---------------|
| `workflow:read` | List and view workflows and their versions |
| `workflow:execute` | Trigger workflow executions |
| `workflow:write` | Create and edit workflows |
| `document:read` | List and download documents |
| `document:write` | Upload and delete documents |
| `analytics:read` | View analytics dashboards |
| `admin:*` | Full administrative access |

---

### 8.2 `notifications`

In-app notification records delivered to individual users.

```sql
CREATE TABLE notifications (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id         UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type            VARCHAR(100) NOT NULL,
    title           VARCHAR(500) NOT NULL,
    body            TEXT,
    metadata        JSONB       NOT NULL DEFAULT '{}',
    is_read         BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Notification feed (primary access pattern)
CREATE INDEX idx_notifications_user_unread
    ON notifications (user_id, created_at DESC)
    WHERE is_read = FALSE;

CREATE INDEX idx_notifications_user_all
    ON notifications (user_id, created_at DESC);
```

**`type` values:**

| Type | Trigger |
|------|---------|
| `workflow.failed` | A workflow run exhausted all retries |
| `workflow.completed` | A workflow run completed successfully |
| `invitation.received` | User was invited to an organization |
| `member.joined` | New member accepted an invitation |
| `ai.budget_warning` | AI token usage exceeds 80% of monthly budget |
| `system.maintenance` | Planned downtime notification |

**`metadata` JSONB structure:**
```json
{
  "workflow_id":  "uuid",
  "workflow_name": "Invoice Processing",
  "run_id":       "uuid",
  "error_node":   "uuid"
}
```

---

### 8.3 `audit_logs`

Immutable, append-only record of all state-changing user actions. Never updated or deleted.

```sql
CREATE TABLE audit_logs (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID        NOT NULL REFERENCES organizations(id),
    user_id         UUID        REFERENCES users(id) ON DELETE SET NULL,
    action          VARCHAR(255) NOT NULL,
    resource_type   VARCHAR(100) NOT NULL,
    resource_id     UUID,
    ip_address      INET,
    user_agent      TEXT,
    metadata        JSONB       NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()

    -- NO foreign key to organizations with CASCADE — audit logs must survive org deletion
    -- NO UPDATE, NO DELETE — enforced at application layer and DB role permissions
);

-- Primary audit trail access: org + time
CREATE INDEX idx_audit_logs_org_created
    ON audit_logs (organization_id, created_at DESC);

-- Resource-specific audit trail
CREATE INDEX idx_audit_logs_resource
    ON audit_logs (resource_type, resource_id, created_at DESC);
```

**`action` naming convention:** `{domain}.{verb}` — e.g., `workflow.published`, `member.invited`, `api_key.revoked`, `document.deleted`

**`metadata` JSONB structure:**
```json
{
  "before": { "role": "employee" },
  "after":  { "role": "manager" },
  "reason": "Promoted by admin"
}
```

**Database-level write protection** (applied to the `app_user` role used by the API):
```sql
REVOKE UPDATE, DELETE ON audit_logs FROM app_user;
REVOKE UPDATE, DELETE ON ai_usage_logs FROM app_user;
REVOKE UPDATE, DELETE ON platform_audit_logs FROM app_user;
```

---

### 8.4 `platform_users`

AutoFlow team members (employees). Completely separate from the customer-facing `users` table. A platform user never appears in `org_members`.

```sql
CREATE TABLE platform_users (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255) NOT NULL,
    role            VARCHAR(50)  NOT NULL,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_platform_users_role CHECK (
        role IN ('super_admin', 'platform_admin', 'support_engineer',
                 'devops_engineer', 'billing_manager')
    )
);

CREATE UNIQUE INDEX uq_platform_users_email ON platform_users (LOWER(email));
CREATE INDEX idx_platform_users_role ON platform_users (role) WHERE is_active = TRUE;
```

**Column notes:**

| Column | Notes |
|--------|-------|
| `role` | Enforced by CHECK constraint; maps to `require_platform_role()` dependency in FastAPI |
| `hashed_password` | bcrypt cost 12; platform users always use password auth (no OAuth for internal staff) |
| `is_active` | Set to FALSE on offboarding; blocks login immediately without deleting records |

**Role capabilities summary (see ARCHITECTURE.md §10.5 for full table):**

| Role | Can Suspend Orgs | Can View Customer Data | Can Manage Billing | Can View System Logs |
|------|:-:|:-:|:-:|:-:|
| `super_admin` | ✓ | ✓ | ✓ | ✓ |
| `platform_admin` | ✓ | ✓ | ✓ | ✓ |
| `support_engineer` | — | With grant only | — | — |
| `devops_engineer` | — | — | — | ✓ |
| `billing_manager` | — | — | ✓ | — |

---

### 8.5 `support_access_grants`

Temporary, time-limited grants that allow a support engineer to read a specific customer org's data. Required before a support engineer can access any `/platform/organizations/{org_id}/*` endpoint.

```sql
CREATE TABLE support_access_grants (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_user_id    UUID        NOT NULL REFERENCES platform_users(id) ON DELETE CASCADE,
    organization_id     UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    granted_by          UUID        NOT NULL REFERENCES platform_users(id),
    reason              TEXT        NOT NULL,
    expires_at          TIMESTAMPTZ NOT NULL,    -- created_at + INTERVAL '24 hours' (max)
    revoked_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_support_grants_expiry  CHECK (expires_at > created_at),
    CONSTRAINT chk_support_grants_max_ttl CHECK (expires_at <= created_at + INTERVAL '24 hours')
);

-- Active grant lookup (checked on every request to /platform/organizations/{org_id}/*)
CREATE INDEX idx_support_grants_user_org
    ON support_access_grants (platform_user_id, organization_id)
    WHERE revoked_at IS NULL;

-- Expired grant cleanup (Celery Beat daily task)
CREATE INDEX idx_support_grants_expires
    ON support_access_grants (expires_at)
    WHERE revoked_at IS NULL;
```

**Lifecycle:**
1. A `support_engineer` submits a reason → `platform_admin` or `super_admin` calls `POST /platform/support-grants`
2. Grant row created with `expires_at = NOW() + 24h`
3. Every request to a customer org endpoint checks: `EXISTS(SELECT 1 FROM support_access_grants WHERE platform_user_id = :uid AND organization_id = :org_id AND revoked_at IS NULL AND expires_at > NOW())`
4. Grant expires automatically; a `super_admin` can revoke early by setting `revoked_at`
5. All access during the grant window is recorded in `platform_audit_logs`

---

### 8.6 `support_tickets`

Customer-submitted support requests visible to support engineers in the Platform Dashboard.

```sql
CREATE TABLE support_tickets (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID        NOT NULL REFERENCES organizations(id) ON DELETE SET NULL,
    submitted_by    UUID        REFERENCES users(id) ON DELETE SET NULL,
    assigned_to     UUID        REFERENCES platform_users(id) ON DELETE SET NULL,
    subject         VARCHAR(500) NOT NULL,
    body            TEXT         NOT NULL,
    status          VARCHAR(50)  NOT NULL DEFAULT 'open',
    priority        VARCHAR(50)  NOT NULL DEFAULT 'normal',
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_support_tickets_status CHECK (
        status IN ('open', 'in_progress', 'resolved', 'closed')
    ),
    CONSTRAINT chk_support_tickets_priority CHECK (
        priority IN ('low', 'normal', 'high', 'critical')
    )
);

-- Support engineer queue: open tickets sorted by priority then age
CREATE INDEX idx_support_tickets_open
    ON support_tickets (priority DESC, created_at ASC)
    WHERE status IN ('open', 'in_progress');

-- Per-org ticket history
CREATE INDEX idx_support_tickets_org_id
    ON support_tickets (organization_id, created_at DESC);

-- Assigned engineer workload
CREATE INDEX idx_support_tickets_assigned
    ON support_tickets (assigned_to, status)
    WHERE assigned_to IS NOT NULL;
```

---

### 8.7 `feature_flags`

Platform-level toggles controlled by platform admins. Used to gate features for all orgs, a percentage rollout, or specific org overrides.

```sql
CREATE TABLE feature_flags (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL,
    description     TEXT,
    is_enabled      BOOLEAN      NOT NULL DEFAULT FALSE,
    rollout_pct     INTEGER      NOT NULL DEFAULT 0,        -- 0–100: % of orgs enabled
    target_orgs     UUID[]       NOT NULL DEFAULT '{}',     -- explicit org-level overrides
    updated_by      UUID         REFERENCES platform_users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_feature_flags_name   UNIQUE (name),
    CONSTRAINT chk_feature_flags_pct   CHECK (rollout_pct BETWEEN 0 AND 100)
);

-- Fast flag lookup by name (hot path — checked on some API requests)
CREATE UNIQUE INDEX uq_feature_flags_name_lower ON feature_flags (LOWER(name));
```

**Evaluation logic (application layer):**
```python
def is_flag_enabled(flag: FeatureFlag, org_id: UUID) -> bool:
    if not flag.is_enabled:
        return False
    if org_id in flag.target_orgs:   # explicit override
        return True
    # Deterministic rollout: hash org_id to 0-99
    return int(hashlib.md5(org_id.bytes).hexdigest(), 16) % 100 < flag.rollout_pct
```

---

### 8.8 `platform_audit_logs`

Immutable, append-only record of all actions taken by platform users (AutoFlow team). Separate from `audit_logs` (which tracks org user actions). Survives deletion of both platform users and customer organizations.

```sql
CREATE TABLE platform_audit_logs (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_user_id    UUID        REFERENCES platform_users(id) ON DELETE SET NULL,
    action              VARCHAR(255) NOT NULL,
    resource_type       VARCHAR(100) NOT NULL,
    resource_id         UUID,
    organization_id     UUID        REFERENCES organizations(id) ON DELETE SET NULL,
    ip_address          INET,
    metadata            JSONB       NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()

    -- NO CASCADE anywhere — records must survive deletion of either party
    -- NO UPDATE, NO DELETE — enforced by DB role: REVOKE UPDATE, DELETE ON platform_audit_logs FROM app_user
);

-- Primary access: time-sorted platform activity log
CREATE INDEX idx_platform_audit_created
    ON platform_audit_logs (created_at DESC);

-- Filter by acting platform user
CREATE INDEX idx_platform_audit_user
    ON platform_audit_logs (platform_user_id, created_at DESC);

-- Filter by affected org (e.g., "all platform actions taken against Org A")
CREATE INDEX idx_platform_audit_org
    ON platform_audit_logs (organization_id, created_at DESC)
    WHERE organization_id IS NOT NULL;
```

**`action` naming convention (platform scope):** `platform.{domain}.{verb}` — e.g., `platform.org.suspended`, `platform.support_grant.created`, `platform.feature_flag.toggled`, `platform.subscription.changed`

**`metadata` example — org suspension:**
```json
{
  "reason": "Non-payment after 30-day grace period",
  "previous_status": "active",
  "new_status": "suspended",
  "plan": "pro"
}
```

---

## 9. Complete Index Strategy

### 9.1 All Indexes

| Table | Index Name | Type | Columns | Condition | Purpose |
|-------|-----------|------|---------|-----------|---------|
| `users` | `uq_users_email` | UNIQUE BTREE | `LOWER(email)` | — | Case-insensitive email login lookup |
| `users` | `idx_users_is_active` | BTREE | `is_active` | `WHERE is_active = TRUE` | Active user filter |
| `oauth_accounts` | `uq_oauth_provider_user` | UNIQUE BTREE | `(provider, provider_user_id)` | — | OAuth identity dedup |
| `oauth_accounts` | `idx_oauth_accounts_user_id` | BTREE | `user_id` | — | Load user's OAuth accounts |
| `email_verification_tokens` | `uq_email_verification_token` | UNIQUE BTREE | `token_hash` | — | Token lookup on verification |
| `email_verification_tokens` | `idx_email_verification_user_id` | BTREE | `user_id` | — | Invalidate prior tokens |
| `password_reset_tokens` | `uq_password_reset_token` | UNIQUE BTREE | `token_hash` | — | Token lookup on reset |
| `password_reset_tokens` | `idx_password_reset_user_id` | BTREE | `user_id` | — | Invalidate prior tokens |
| `organizations` | `uq_organizations_slug` | UNIQUE BTREE | `slug` | — | Slug uniqueness |
| `organizations` | `idx_organizations_active` | BTREE | `is_active` | `WHERE is_active = TRUE` | Active org check |
| `org_members` | `uq_org_members_org_user` | UNIQUE BTREE | `(organization_id, user_id)` | — | One membership per user per org |
| `org_members` | `idx_org_members_user_id` | BTREE | `user_id` | — | Load user's organizations |
| `org_members` | `idx_org_members_org_role` | BTREE | `(organization_id, role)` | — | Load all admins/owners of an org |
| `departments` | `uq_departments_org_name` | UNIQUE BTREE | `(organization_id, name)` | — | Unique dept name per org |
| `departments` | `idx_departments_org_id` | BTREE | `organization_id` | — | List org departments |
| `invitations` | `uq_invitations_token` | UNIQUE BTREE | `token_hash` | — | Token lookup on accept |
| `invitations` | `idx_invitations_org_email` | BTREE | `(organization_id, email)` | — | Check pending invite |
| `invitations` | `idx_invitations_expires` | BTREE | `expires_at` | `WHERE accepted_at IS NULL` | Expired invite cleanup |
| `user_notification_preferences` | `uq_notif_prefs_user_org` | UNIQUE BTREE | `(user_id, organization_id)` | — | One pref row per user per org |
| `workflows` | `idx_workflows_org_status` | BTREE | `(organization_id, status)` | `WHERE deleted_at IS NULL` | Workflow list by status |
| `workflows` | `idx_workflows_org_created` | BTREE | `(organization_id, created_at DESC)` | `WHERE deleted_at IS NULL` | Recent workflows list |
| `workflow_versions` | `uq_workflow_versions_num` | UNIQUE BTREE | `(workflow_id, version_number)` | — | Version number dedup |
| `workflow_versions` | `idx_workflow_versions_workflow_id` | BTREE | `(workflow_id, version_number DESC)` | — | Version history list |
| `workflow_nodes` | `idx_workflow_nodes_version_id` | BTREE | `workflow_version_id` | — | Load all nodes for a version |
| `workflow_nodes` | `idx_workflow_nodes_type` | BTREE | `node_type` | — | Analytics by node type |
| `workflow_edges` | `idx_workflow_edges_version_id` | BTREE | `workflow_version_id` | — | Load all edges for a version |
| `workflow_edges` | `idx_workflow_edges_source` | BTREE | `source_node_id` | — | Outgoing edges per node |
| `workflow_edges` | `idx_workflow_edges_target` | BTREE | `target_node_id` | — | Incoming edges per node |
| `workflow_runs` | `idx_workflow_runs_org_status_started` | BTREE | `(organization_id, status, started_at DESC)` | — | Dashboard run list |
| `workflow_runs` | `idx_workflow_runs_workflow_id` | BTREE | `(workflow_id, started_at DESC)` | — | Per-workflow run history |
| `workflow_runs` | `idx_workflow_runs_parent_run_id` | BTREE | `parent_run_id` | `WHERE parent_run_id IS NOT NULL` | Retry chain lookup |
| `execution_logs` | `idx_execution_logs_run_id` | BTREE | `workflow_run_id` | — | All logs for a run |
| `execution_logs` | `idx_execution_logs_node_id` | BTREE | `(node_id, started_at DESC)` | — | Per-node log history |
| `execution_logs` | `idx_execution_logs_failed` | BTREE | `(node_id, attempt_number)` | `WHERE status = 'failed'` | Failed node analysis |
| `documents` | `idx_documents_org_created` | BTREE | `(organization_id, created_at DESC)` | `WHERE deleted_at IS NULL` | Document library list |
| `documents` | `idx_documents_org_indexed` | BTREE | `(organization_id, is_indexed)` | `WHERE deleted_at IS NULL` | RAG indexing queue |
| `documents` | `idx_documents_name_trgm` | GIN (trgm) | `name` | `WHERE deleted_at IS NULL` | Full-text name search |
| `document_chunks` | `uq_document_chunks_doc_idx` | UNIQUE BTREE | `(document_id, chunk_index)` | — | Chunk dedup on re-index |
| `document_chunks` | `idx_document_chunks_embedding` | HNSW | `embedding vector_cosine_ops` | — | Cosine similarity search |
| `document_chunks` | `idx_document_chunks_org_id` | BTREE | `organization_id` | — | Tenant pre-filter before vector search |
| `ai_usage_logs` | `idx_ai_usage_org_created` | BTREE | `(organization_id, created_at DESC)` | — | Monthly cost aggregation |
| `ai_usage_logs` | `idx_ai_usage_run_id` | BTREE | `workflow_run_id` | `WHERE workflow_run_id IS NOT NULL` | Per-run cost breakdown |
| `ai_usage_logs` | `idx_ai_usage_org_model` | BTREE | `(organization_id, model, created_at DESC)` | — | Model-level usage reports |
| `integrations` | `idx_integrations_org_id` | BTREE | `(organization_id, status)` | — | Active integrations list |
| `api_keys` | `idx_api_keys_org_active` | BTREE | `organization_id` | `WHERE revoked_at IS NULL` | API key auth lookup |
| `notifications` | `idx_notifications_user_unread` | BTREE | `(user_id, created_at DESC)` | `WHERE is_read = FALSE` | Notification badge count |
| `notifications` | `idx_notifications_user_all` | BTREE | `(user_id, created_at DESC)` | — | Full notification feed |
| `audit_logs` | `idx_audit_logs_org_created` | BTREE | `(organization_id, created_at DESC)` | — | Audit trail with pagination |
| `audit_logs` | `idx_audit_logs_resource` | BTREE | `(resource_type, resource_id, created_at DESC)` | — | Resource audit trail |
| `platform_users` | `uq_platform_users_email` | UNIQUE BTREE | `LOWER(email)` | — | Case-insensitive platform login |
| `platform_users` | `idx_platform_users_role` | BTREE | `role` | `WHERE is_active = TRUE` | List active engineers by role |
| `support_access_grants` | `idx_support_grants_user_org` | BTREE | `(platform_user_id, organization_id)` | `WHERE revoked_at IS NULL` | Active grant check per request |
| `support_access_grants` | `idx_support_grants_expires` | BTREE | `expires_at` | `WHERE revoked_at IS NULL` | Expired grant cleanup |
| `support_tickets` | `idx_support_tickets_open` | BTREE | `(priority DESC, created_at ASC)` | `WHERE status IN ('open', 'in_progress')` | Support engineer queue |
| `support_tickets` | `idx_support_tickets_org_id` | BTREE | `(organization_id, created_at DESC)` | — | Per-org ticket history |
| `support_tickets` | `idx_support_tickets_assigned` | BTREE | `(assigned_to, status)` | `WHERE assigned_to IS NOT NULL` | Engineer workload view |
| `feature_flags` | `uq_feature_flags_name_lower` | UNIQUE BTREE | `LOWER(name)` | — | Flag lookup by name (hot path) |
| `platform_audit_logs` | `idx_platform_audit_created` | BTREE | `created_at DESC` | — | Chronological platform activity |
| `platform_audit_logs` | `idx_platform_audit_user` | BTREE | `(platform_user_id, created_at DESC)` | — | Per-engineer action history |
| `platform_audit_logs` | `idx_platform_audit_org` | BTREE | `(organization_id, created_at DESC)` | `WHERE organization_id IS NOT NULL` | Actions taken against an org |

### 9.2 Index Maintenance

```sql
-- Reindex bloated indexes (run during low-traffic window)
REINDEX INDEX CONCURRENTLY idx_execution_logs_run_id;

-- Check index bloat (run weekly via monitoring)
SELECT indexname, pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
ORDER BY pg_relation_size(indexrelid) DESC;
```

---

## 10. pgvector Configuration

### 10.1 Embedding Dimensions

| Provider | Model | Dimensions | Notes |
|----------|-------|-----------|-------|
| OpenAI | `text-embedding-3-small` | 1536 | Default; best quality/cost ratio |
| OpenAI | `text-embedding-3-large` | 3072 | Higher accuracy, 2× storage cost |
| Local | `all-MiniLM-L6-v2` | 384 | No API cost; lower accuracy |

The `embedding VECTOR(1536)` column in `document_chunks` matches the default OpenAI model. If switching to a local model (384 dimensions), a migration must change the column type and drop/recreate the HNSW index.

### 10.2 HNSW Index Parameters

```sql
CREATE INDEX idx_document_chunks_embedding
    ON document_chunks
    USING HNSW (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

| Parameter | Value | Effect |
|-----------|-------|--------|
| `m` | 16 | Connections per node in the graph. Higher = better recall, more memory |
| `ef_construction` | 64 | Build-time search width. Higher = better index quality, slower build |

**At query time**, the `ef_search` parameter controls recall vs. speed trade-off:
```sql
SET hnsw.ef_search = 100;   -- default is 40; increase for better recall
SELECT content, 1 - (embedding <=> :query_vec) AS score
FROM document_chunks
WHERE organization_id = :org_id
ORDER BY embedding <=> :query_vec
LIMIT 5;
```

### 10.3 Similarity Threshold

Chunks with cosine similarity < 0.75 are excluded from RAG context. This threshold is applied in application code (not SQL) to allow per-query tuning without index changes:

```python
chunks = [c for c in raw_results if c.score >= config.similarity_threshold]
```

### 10.4 Scaling Considerations

| Chunk Count | Recommendation |
|-------------|---------------|
| < 1M | Current HNSW index is sufficient |
| 1M – 10M | Add a partial HNSW index per high-volume organization |
| > 10M | Evaluate migration to dedicated vector DB (Qdrant, Weaviate); `RAGRetriever` interface does not change |

---

## 11. Constraints & Integrity Rules

### 11.1 Check Constraints Summary

| Table | Constraint | Rule |
|-------|-----------|------|
| `organizations` | `chk_organizations_plan` | `plan IN ('free', 'pro', 'enterprise')` |
| `organizations` | `chk_organizations_storage` | `storage_used_bytes >= 0` |
| `org_members` | `chk_org_members_role` | `role IN ('owner', 'admin', 'manager', 'analyst', 'employee', 'viewer')` |
| `invitations` | `chk_invitations_role` | `role IN ('admin', 'manager', 'analyst', 'employee', 'viewer')` |
| `oauth_accounts` | `chk_oauth_provider` | `provider IN ('google', 'microsoft')` |
| `workflows` | `chk_workflows_status` | `status IN ('draft', 'published', 'archived')` |
| `workflow_versions` | `chk_version_number_positive` | `version_number >= 1` |
| `workflow_edges` | `chk_workflow_edges_no_self_loop` | `source_node_id <> target_node_id` |
| `workflow_runs` | `chk_workflow_runs_trigger` | `trigger_type IN ('manual', 'schedule', 'webhook', 'api')` |
| `workflow_runs` | `chk_workflow_runs_status` | `status IN ('pending', 'running', 'completed', 'failed', 'cancelled')` |
| `execution_logs` | `chk_execution_logs_status` | `status IN ('pending', 'running', 'completed', 'failed', 'skipped')` |
| `execution_logs` | `chk_execution_logs_attempt` | `attempt_number >= 1` |
| `execution_logs` | `chk_execution_logs_duration` | `duration_ms IS NULL OR duration_ms >= 0` |
| `documents` | `chk_documents_size` | `size_bytes > 0` |
| `document_chunks` | `chk_document_chunks_idx` | `chunk_index >= 0` |
| `ai_usage_logs` | `chk_ai_usage_provider` | `provider IN ('openai', 'anthropic', 'ollama')` |
| `ai_usage_logs` | `chk_ai_usage_operation` | `operation IN ('chat', 'embed', 'classify', 'extract', 'summarize', 'rag', 'agent')` |
| `ai_usage_logs` | `chk_ai_usage_tokens` | `prompt_tokens >= 0 AND completion_tokens >= 0` |
| `ai_usage_logs` | `chk_ai_usage_latency` | `latency_ms >= 0` |
| `integrations` | `chk_integrations_status` | `status IN ('active', 'inactive', 'error')` |
| `platform_users` | `chk_platform_users_role` | `role IN ('super_admin', 'platform_admin', 'support_engineer', 'devops_engineer', 'billing_manager')` |
| `support_access_grants` | `chk_support_grants_expiry` | `expires_at > created_at` |
| `support_access_grants` | `chk_support_grants_max_ttl` | `expires_at <= created_at + INTERVAL '24 hours'` |
| `support_tickets` | `chk_support_tickets_status` | `status IN ('open', 'in_progress', 'resolved', 'closed')` |
| `support_tickets` | `chk_support_tickets_priority` | `priority IN ('low', 'normal', 'high', 'critical')` |
| `feature_flags` | `chk_feature_flags_pct` | `rollout_pct BETWEEN 0 AND 100` |

### 11.2 Foreign Key Cascade Rules

| Relationship | On Parent Delete |
|-------------|-----------------|
| `users` → `oauth_accounts` | CASCADE (OAuth account deleted with user) |
| `users` → `email_verification_tokens` | CASCADE |
| `users` → `password_reset_tokens` | CASCADE |
| `organizations` → `org_members` | CASCADE |
| `organizations` → `departments` | CASCADE |
| `organizations` → `invitations` | CASCADE |
| `organizations` → `workflows` | CASCADE |
| `organizations` → `documents` | CASCADE |
| `organizations` → `document_chunks` | CASCADE |
| `organizations` → `api_keys` | CASCADE |
| `organizations` → `notifications` | CASCADE |
| `organizations` → `integrations` | CASCADE |
| `organizations` → `ai_usage_logs` | CASCADE (acceptable — org data gone) |
| `organizations` → `audit_logs` | **NO CASCADE** — audit records survive org deletion |
| `users` → `org_members` | CASCADE |
| `users` → `notifications` | CASCADE |
| `users` → `audit_logs` | SET NULL — audit entry preserved, user link nulled |
| `users` → `workflow_runs.triggered_by` | SET NULL — run preserved, triggerer link nulled |
| `workflows` → `workflow_versions` | CASCADE |
| `workflow_versions` → `workflow_nodes` | CASCADE |
| `workflow_versions` → `workflow_edges` | CASCADE |
| `workflow_runs` → `execution_logs` | CASCADE |
| `documents` → `document_chunks` | CASCADE |
| `workflow_runs` → `ai_usage_logs` | SET NULL (usage log preserved) |
| `workflow_runs` → `workflow_runs.parent_run_id` | SET NULL (self-referential) |
| `departments` → `org_members.department_id` | SET NULL |
| `workflows` → `workflow_versions.active_version_id` | SET NULL (deferred FK) |
| `platform_users` → `support_access_grants.platform_user_id` | CASCADE |
| `platform_users` → `support_access_grants.granted_by` | RESTRICT (cannot delete granter while active grants exist) |
| `platform_users` → `support_tickets.assigned_to` | SET NULL |
| `platform_users` → `feature_flags.updated_by` | SET NULL |
| `platform_users` → `platform_audit_logs.platform_user_id` | SET NULL (audit preserved) |
| `organizations` → `support_access_grants.organization_id` | CASCADE |
| `organizations` → `support_tickets.organization_id` | SET NULL (ticket preserved after org deletion) |
| `organizations` → `platform_audit_logs.organization_id` | SET NULL (audit preserved) |
| `users` → `support_tickets.submitted_by` | SET NULL (ticket preserved after user deletion) |

### 11.3 Application-Layer Rules (Not Enforced by DB)

| Rule | Where Enforced |
|------|---------------|
| Exactly one `owner` per organization | `org_service.create_org()`, `org_service.update_role()` |
| No active password reset + verification tokens overlap | `auth_service.request_reset()` |
| `version_number` assigned inside a serializable transaction | `workflow_service.publish()` |
| `storage_used_bytes` updated on upload/delete | `file_service.upload()`, `file_service.delete()` |
| Invitation dedup: one pending invite per (org, email) | `org_service.invite_member()` |
| Audit logs are never modified | DB role permissions (`REVOKE UPDATE, DELETE`) |
| `platform_audit_logs` are never modified | DB role permissions (`REVOKE UPDATE, DELETE`) |
| Support access grant TTL max 24h | `chk_support_grants_max_ttl` CHECK constraint + `platform_service.create_support_grant()` |
| Only `super_admin` or `platform_admin` can create support grants | `require_platform_role("super_admin", "platform_admin")` dependency |
| `support_engineer` needs an active grant before reading any org data | `platform/dependencies.py: check_support_grant()` |
| Platform users and org users are in separate tables and cannot be confused | JWT `scope` claim ("platform" vs "org"); separate auth dependency chains |
| Org users can never be granted a platform role | No cross-table FK; `PlatformUser` and `User` are distinct models |

---

## 12. Common Query Patterns

### Q1 — Dashboard: Recent workflow runs for an org

```sql
-- Uses: idx_workflow_runs_org_status_started
SELECT wr.id, wr.status, wr.trigger_type, wr.started_at, wr.completed_at,
       w.name AS workflow_name
FROM workflow_runs wr
JOIN workflows w ON w.id = wr.workflow_id
WHERE wr.organization_id = :org_id
ORDER BY wr.started_at DESC
LIMIT 20 OFFSET :offset;
```

### Q2 — Execution log: All node logs for a run

```sql
-- Uses: idx_execution_logs_run_id
SELECT el.*, wn.node_type, wn.label
FROM execution_logs el
JOIN workflow_nodes wn ON wn.id = el.node_id
WHERE el.workflow_run_id = :run_id
ORDER BY el.started_at ASC;
```

### Q3 — RAG: Find top-5 similar chunks within an org

```sql
-- Uses: idx_document_chunks_embedding (HNSW) + idx_document_chunks_org_id
-- ef_search set per session before this query
SET hnsw.ef_search = 100;

SELECT dc.content, dc.metadata, d.name AS document_name,
       1 - (dc.embedding <=> :query_embedding) AS similarity_score
FROM document_chunks dc
JOIN documents d ON d.id = dc.document_id
WHERE dc.organization_id = :org_id
  AND d.deleted_at IS NULL
ORDER BY dc.embedding <=> :query_embedding
LIMIT 5;
```

### Q4 — Analytics: Execution counts by status for current month

```sql
-- Uses: idx_workflow_runs_org_status_started
SELECT status, COUNT(*) AS count
FROM workflow_runs
WHERE organization_id = :org_id
  AND started_at >= DATE_TRUNC('month', NOW())
GROUP BY status;
```

### Q5 — Analytics: AI token usage by model this month

```sql
-- Uses: idx_ai_usage_org_model
SELECT model, provider,
       SUM(prompt_tokens)     AS total_prompt_tokens,
       SUM(completion_tokens) AS total_completion_tokens,
       SUM(estimated_cost_usd) AS total_cost_usd
FROM ai_usage_logs
WHERE organization_id = :org_id
  AND created_at >= DATE_TRUNC('month', NOW())
GROUP BY model, provider
ORDER BY total_cost_usd DESC;
```

### Q6 — Notifications: Unread count + latest 20 for a user

```sql
-- Uses: idx_notifications_user_unread, idx_notifications_user_all
SELECT COUNT(*) FROM notifications
WHERE user_id = :user_id AND is_read = FALSE;

SELECT id, type, title, body, metadata, created_at, is_read
FROM notifications
WHERE user_id = :user_id
ORDER BY created_at DESC
LIMIT 20;
```

### Q7 — Auth: Load user + membership by email

```sql
-- Uses: uq_users_email + idx_org_members_user_id
SELECT u.*, om.role, om.organization_id, o.plan, o.is_active AS org_active
FROM users u
JOIN org_members om ON om.user_id = u.id
JOIN organizations o ON o.id = om.organization_id
WHERE LOWER(u.email) = LOWER(:email)
  AND u.is_active = TRUE
  AND om.organization_id = :org_id;
```

### Q8 — API key authentication

```sql
-- Uses: idx_api_keys_org_active
-- Application iterates and bcrypt.verify() against each — result cached in Redis
SELECT id, organization_id, key_hash, scopes, expires_at
FROM api_keys
WHERE revoked_at IS NULL
  AND (expires_at IS NULL OR expires_at > NOW());
```

### Q9 — Top failing nodes across an org (analytics)

```sql
-- Uses: idx_execution_logs_failed + idx_workflow_nodes_version_id
SELECT wn.node_type, wn.label, COUNT(*) AS failure_count,
       MODE() WITHIN GROUP (ORDER BY el.error_type) AS most_common_error
FROM execution_logs el
JOIN workflow_nodes wn ON wn.id = el.node_id
JOIN workflow_runs wr ON wr.id = el.workflow_run_id
WHERE wr.organization_id = :org_id
  AND el.status = 'failed'
  AND el.started_at >= NOW() - INTERVAL '30 days'
GROUP BY wn.id, wn.node_type, wn.label
ORDER BY failure_count DESC
LIMIT 10;
```

### Q10 — Audit log with pagination

```sql
-- Uses: idx_audit_logs_org_created
SELECT al.*, u.full_name AS user_name, u.email AS user_email
FROM audit_logs al
LEFT JOIN users u ON u.id = al.user_id
WHERE al.organization_id = :org_id
ORDER BY al.created_at DESC
LIMIT 50 OFFSET :offset;
```

### Q11 — Platform Dashboard: All organizations summary

```sql
-- Platform Admin: list all customer orgs with key health metrics
-- Uses: idx_organizations_active + subqueries
SELECT o.id, o.name, o.slug, o.plan, o.is_active,
       o.created_at,
       o.storage_used_bytes,
       (SELECT COUNT(*) FROM org_members om WHERE om.organization_id = o.id)     AS member_count,
       (SELECT COUNT(*) FROM workflows w WHERE w.organization_id = o.id
                                           AND w.deleted_at IS NULL)              AS workflow_count,
       (SELECT MAX(wr.started_at) FROM workflow_runs wr
        WHERE wr.organization_id = o.id)                                          AS last_run_at,
       (SELECT SUM(aul.estimated_cost_usd)
        FROM ai_usage_logs aul
        WHERE aul.organization_id = o.id
          AND aul.created_at >= DATE_TRUNC('month', NOW()))                       AS ai_cost_this_month
FROM organizations o
ORDER BY o.created_at DESC
LIMIT 50 OFFSET :offset;
```

### Q12 — Platform: Check active support grant before granting data access

```sql
-- Uses: idx_support_grants_user_org
-- Called in platform/dependencies.py check_support_grant()
SELECT 1
FROM support_access_grants
WHERE platform_user_id = :platform_user_id
  AND organization_id  = :org_id
  AND revoked_at IS NULL
  AND expires_at > NOW()
LIMIT 1;
```

### Q13 — Platform: Open support ticket queue for an engineer

```sql
-- Uses: idx_support_tickets_open + idx_support_tickets_assigned
SELECT st.*, o.name AS org_name, pu.full_name AS assigned_to_name
FROM support_tickets st
LEFT JOIN organizations o  ON o.id  = st.organization_id
LEFT JOIN platform_users pu ON pu.id = st.assigned_to
WHERE st.status IN ('open', 'in_progress')
  AND (:assigned_to IS NULL OR st.assigned_to = :assigned_to)
ORDER BY
    CASE st.priority
        WHEN 'critical' THEN 1
        WHEN 'high'     THEN 2
        WHEN 'normal'   THEN 3
        WHEN 'low'      THEN 4
    END,
    st.created_at ASC
LIMIT 25 OFFSET :offset;
```

### Q14 — Platform: All actions taken against a specific org

```sql
-- Uses: idx_platform_audit_org
-- Useful during incident investigation: what did the AutoFlow team do to this org?
SELECT pal.*, pu.full_name AS actor_name, pu.role AS actor_role
FROM platform_audit_logs pal
LEFT JOIN platform_users pu ON pu.id = pal.platform_user_id
WHERE pal.organization_id = :org_id
ORDER BY pal.created_at DESC
LIMIT 50 OFFSET :offset;
```

### Q15 — Platform: Feature flag evaluation for an org

```sql
-- Uses: uq_feature_flags_name_lower
SELECT is_enabled, rollout_pct, target_orgs
FROM feature_flags
WHERE LOWER(name) = LOWER(:flag_name);
-- Deterministic rollout evaluated in application (see §8.7)
```

---

## 13. Migrations Strategy

### 13.1 Tooling

All schema changes are managed through **Alembic** with async support via `alembic[asyncpg]`.

```
backend/
  alembic/
    versions/                    # Auto-generated migration files
      0001_initial_schema.py
      0002_add_workflow_tags.py
    env.py                       # Alembic environment config
    script.py.mako               # Migration file template
  alembic.ini                    # Alembic config (points to env.py)
```

### 13.2 Alembic env.py Configuration

```python
# alembic/env.py
from app.core.config import settings
from app.core.database import Base

# Import all models so Alembic can detect them
from app.modules.auth.models import *
from app.modules.organizations.models import *
from app.modules.workflows.models import *
from app.modules.execution.models import *
from app.modules.ai.models import *
from app.modules.files.models import *
from app.modules.notifications.models import *
from app.modules.analytics.models import *
from app.modules.platform.models import *    # platform_users, support_access_grants,
                                             # support_tickets, feature_flags, platform_audit_logs

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
target_metadata = Base.metadata
```

### 13.3 Naming Convention Configuration

```python
# app/core/database.py
from sqlalchemy import MetaData

NAMING_CONVENTION = {
    "ix":  "idx_%(table_name)s_%(column_0_name)s",
    "uq":  "uq_%(table_name)s_%(column_0_N_name)s",
    "ck":  "chk_%(table_name)s_%(constraint_name)s",
    "fk":  "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk":  "pk_%(table_name)s",
}

Base = declarative_base(metadata=MetaData(naming_convention=NAMING_CONVENTION))
```

### 13.4 Migration Workflow

```bash
# 1. Make model changes in SQLAlchemy models

# 2. Auto-generate migration
alembic revision --autogenerate -m "add_workflow_tags_column"

# 3. Review the generated file in alembic/versions/
# Always inspect: autogenerate misses index changes, custom constraints

# 4. Apply to development database
alembic upgrade head

# 5. Rollback if needed
alembic downgrade -1

# 6. Check current revision
alembic current

# 7. View migration history
alembic history --verbose
```

### 13.5 Migration File Convention

```python
# alembic/versions/0003_add_parent_run_id.py
"""Add parent_run_id to workflow_runs for retry chain tracking

Revision ID: a1b2c3d4e5f6
Revises: 9f8e7d6c5b4a
Create Date: 2026-07-01 10:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = '9f8e7d6c5b4a'

def upgrade() -> None:
    op.add_column('workflow_runs',
        sa.Column('parent_run_id', sa.UUID(), nullable=True)
    )
    op.create_foreign_key(
        'fk_workflow_runs_parent_run_id',
        'workflow_runs', 'workflow_runs',
        ['parent_run_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index(
        'idx_workflow_runs_parent_run_id',
        'workflow_runs', ['parent_run_id'],
        postgresql_where=sa.text('parent_run_id IS NOT NULL')
    )

def downgrade() -> None:
    op.drop_index('idx_workflow_runs_parent_run_id', table_name='workflow_runs')
    op.drop_constraint('fk_workflow_runs_parent_run_id', 'workflow_runs')
    op.drop_column('workflow_runs', 'parent_run_id')
```

### 13.6 Zero-Downtime Migration Rules

| Change Type | Strategy |
|------------|---------|
| Add nullable column | Safe — add directly, backfill in background |
| Add NOT NULL column | Add as nullable → backfill → add NOT NULL constraint |
| Add index | Use `CREATE INDEX CONCURRENTLY` (not blocking) |
| Drop column | Remove from application code first, then run migration in next release |
| Rename column | Add new column → dual-write → migrate reads → drop old column |
| Change column type | Add new column → backfill → swap → drop old |

```python
# Always use CONCURRENTLY for index creation in production migrations
op.execute("CREATE INDEX CONCURRENTLY idx_name ON table (column)")
```

---

## 14. Partitioning Strategy

High-volume append-only tables are partitioned by month to keep query performance stable as data grows. Partitioning is introduced when the table exceeds ~10M rows.

### 14.1 `execution_logs` — Range Partitioning by Month

```sql
-- Convert to partitioned table (done via migration, non-disruptive with pg_partman)
CREATE TABLE execution_logs (
    -- ... same columns ...
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (started_at);

-- Monthly partitions (auto-created by pg_partman or migration)
CREATE TABLE execution_logs_2026_06
    PARTITION OF execution_logs
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

CREATE TABLE execution_logs_2026_07
    PARTITION OF execution_logs
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
```

**Retention policy:** Partitions older than 12 months are detached and archived to cold storage. Detaching a partition is instant and does not lock the parent table.

### 14.2 `audit_logs` — Range Partitioning by Month

```sql
CREATE TABLE audit_logs (
    -- ... same columns ...
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);
```

**Retention policy:** Audit logs are retained for a minimum of 2 years per compliance requirement (RC-002). Partitions older than 24 months are moved to a read-only archive schema, not deleted.

### 14.3 `ai_usage_logs` — Range Partitioning by Month

```sql
CREATE TABLE ai_usage_logs (
    -- ... same columns ...
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);
```

**Retention policy:** Retained for 13 months (13 monthly partitions active at any time) to support year-over-year cost comparisons. Older data archived to cold storage.

### 14.4 Partition Management

```sql
-- pg_partman extension handles automatic partition creation
CREATE EXTENSION IF NOT EXISTS pg_partman;

SELECT partman.create_parent(
    p_parent_table => 'public.execution_logs',
    p_control => 'started_at',
    p_type => 'range',
    p_interval => 'monthly',
    p_premake => 3            -- pre-create 3 future months
);

-- Run maintenance job weekly (via Celery Beat):
SELECT partman.run_maintenance(p_analyze := FALSE);
```

---

## 15. Redis Schema

### 15.1 Configuration

```
maxmemory          4gb
maxmemory-policy   allkeys-lru     # Evict least-recently-used keys under memory pressure
appendonly         yes              # AOF persistence for durability
appendfsync        everysec         # Balance durability vs. performance
```

### 15.2 Key Patterns

| Key Pattern | Type | Value | TTL | Purpose |
|-------------|------|-------|-----|---------|
| `session:{user_id}:{session_id}` | STRING | bcrypt hash of refresh token | 7 days | Refresh token validation |
| `rate:auth:{ip}` | STRING | request count | 15 minutes | Auth endpoint rate limiting |
| `rate:api:{api_key_id}` | STRING | request count | 1 minute | API key rate limiting |
| `rate:webhook:{workflow_id}` | STRING | request count | 1 minute | Webhook receiver rate limiting |
| `api_key_cache:{org_id}` | STRING | JSON array of key hashes | 60 seconds | API key auth lookup cache |
| `run:status:{run_id}` | STRING | JSON status + timestamps | 1 hour | Live execution status cache |
| `ws:org:{org_id}` | PUBSUB | — | None (in-memory) | WebSocket event broadcasting |
| `cache:analytics:{org_id}:{date_key}` | STRING | Serialized query result | 5 minutes | Analytics dashboard cache |
| `cache:workflow:{workflow_id}` | STRING | Serialized workflow + version | 30 seconds | Hot workflow config cache |
| `redbeat:*` | HASH/ZSET | Celery Beat schedule entries | None | Dynamic cron schedules |
| `celery:*` | — | Celery broker/backend keys | Varies | Task queue and result backend |

### 15.3 Session Key Structure

```
session:{user_id}:{session_id}
  Value: "$2b$12$..." (bcrypt hash of the refresh token)
  TTL: 604800 (7 days)

On refresh:
  1. DEL session:{user_id}:{old_session_id}
  2. SET session:{user_id}:{new_session_id} {new_hash} EX 604800

On logout:
  DEL session:{user_id}:{session_id}

On admin revoke all sessions:
  SCAN for session:{user_id}:* → DEL all matches
```

### 15.4 Analytics Cache Key Convention

```
cache:analytics:{org_id}:{metric}:{date_bucket}

Examples:
  cache:analytics:org-uuid:execution_counts:2026-06
  cache:analytics:org-uuid:ai_cost:2026-06
  cache:analytics:org-uuid:top_workflows:2026-06-30
```

---

## 16. Object Storage Layout

### 16.1 Bucket Structure

```
{bucket-name}/
│
├── {organization_id}/
│   │
│   ├── documents/
│   │   └── {document_id}/
│   │       └── {original_filename}     # e.g., invoice-2026-06.pdf
│   │
│   ├── generated/
│   │   └── {workflow_run_id}/
│   │       └── {filename}              # e.g., summary_report.md
│   │
│   └── exports/
│       └── {export_id}/
│           └── {export_filename}       # e.g., workflow_export.json
│
└── platform/
    └── avatars/
        └── {user_id}/
            └── avatar.{ext}            # e.g., avatar.webp
```

**`storage_key` in the `documents` table** stores the full path: `{org_id}/documents/{doc_id}/{filename}`

### 16.2 Presigned URL Configuration

| Operation | Expiry | Notes |
|-----------|--------|-------|
| GET (download) | 15 minutes | Generated on demand per request |
| PUT (upload) | 5 minutes | Frontend uploads directly to storage, not via API |
| DELETE | — | Performed server-side only, never client-side |

### 16.3 Lifecycle Rules

```json
{
  "Rules": [
    {
      "ID": "abort-incomplete-multipart",
      "Status": "Enabled",
      "AbortIncompleteMultipartUpload": { "DaysAfterInitiation": 1 }
    },
    {
      "ID": "transition-old-exports",
      "Filter": { "Prefix": "*/exports/" },
      "Status": "Enabled",
      "Transitions": [
        { "Days": 30, "StorageClass": "STANDARD_IA" }
      ]
    }
  ]
}
```

### 16.4 MIME Type Allowlist

Only the following MIME types are accepted for upload:

| Extension | MIME Type |
|-----------|----------|
| `.pdf` | `application/pdf` |
| `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| `.xlsx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` |
| `.csv` | `text/csv` |
| `.png` | `image/png` |
| `.jpg` / `.jpeg` | `image/jpeg` |

MIME type is validated server-side by reading the file's magic bytes — not by trusting the `Content-Type` header.

---

## 17. Seed Data

The following data is inserted during initial deployment via an Alembic migration or a dedicated `seed.py` script.

### 17.1 Customer Users — No Seed Accounts

Customer users are created via the registration flow only. There are no default org user accounts. The first registered user creates their organization and is assigned the `owner` role.

### 17.1a Platform Admin — Bootstrap via CLI

The first `super_admin` cannot be created via the API (there is no registration flow for platform users — that would be a security hole). It is seeded once at deployment time via a one-shot CLI command:

```bash
# Run once during initial deployment
python -m app.modules.platform.cli create_super_admin \
    --email "admin@autoflow.ai" \
    --full-name "AutoFlow Admin" \
    --password "$INITIAL_SUPER_ADMIN_PASSWORD"
```

This inserts a row into `platform_users` with `role = 'super_admin'`. Subsequent platform users are created by the super admin via the Platform Dashboard (`POST /api/v1/platform/users`). The CLI command is disabled after first use (guarded by checking `COUNT(*) = 0` in `platform_users`).

### 17.2 Schema Validation Data

The following are used for CHECK constraint validation and are defined in the schema, not as table rows:

**Organization scope (customer tenants):**
- Valid org member roles: `['owner', 'admin', 'manager', 'analyst', 'employee', 'viewer']`
- Valid invitation roles (owner is never invited): `['admin', 'manager', 'analyst', 'employee', 'viewer']`

**Platform scope (AutoFlow staff):**
- Valid platform user roles: `['super_admin', 'platform_admin', 'support_engineer', 'devops_engineer', 'billing_manager']`

**Shared:**
- Valid plans: `['free', 'pro', 'enterprise']`
- Valid trigger types: `['manual', 'schedule', 'webhook', 'api']`
- Valid run statuses: `['pending', 'running', 'completed', 'failed', 'cancelled']`
- Valid support ticket statuses: `['open', 'in_progress', 'resolved', 'closed']`

### 17.3 Default Organization Settings

When an organization is created, `settings` is initialized with these defaults:

```python
DEFAULT_ORG_SETTINGS = {
    "timezone": "UTC",
    "language": "en",
    "logo_url": None,
    "ai_budget_usd_monthly": None,          # None = no budget limit
    "max_workflow_executions_monthly": None, # None = no execution limit
    "max_storage_bytes": 5_368_709_120,      # 5 GB default
}
```

### 17.4 Default Notification Preferences

When a user joins an organization (via invitation or creation), a `user_notification_preferences` row is created with all defaults:

```python
DEFAULT_NOTIFICATION_PREFERENCES = {
    "email_on_workflow_failure":  True,
    "email_on_workflow_success":  False,
    "email_on_invitation":        True,
    "email_on_weekly_report":     True,
    "inapp_on_workflow_failure":  True,
    "inapp_on_workflow_success":  True,
    "inapp_on_mention":           True,
}
```

---

## 18. Backup & Recovery

### 18.1 PostgreSQL Backup Strategy

**Continuous WAL archiving + daily base backups** using `pgBackRest` or AWS RDS automated backups.

| Backup Type | Frequency | Retention |
|-------------|-----------|-----------|
| Full base backup | Daily (2:00 AM UTC) | 7 days |
| WAL archive (continuous) | Every completed WAL segment (~16 MB) | 7 days |
| Monthly snapshot | 1st of each month | 12 months |

**Point-in-Time Recovery (PITR):** With continuous WAL archiving, the database can be restored to any second within the retention window.

```bash
# Restore to a specific point in time (pgBackRest)
pgbackrest --stanza=main --type=time \
  "--target=2026-06-30 14:35:00 UTC" restore
```

### 18.2 Recovery Time Objectives

| Scenario | RTO | RPO |
|----------|-----|-----|
| Primary instance failure (failover to standby) | < 60 seconds | < 30 seconds |
| Accidental data deletion (PITR) | < 30 minutes | 0 (point-in-time) |
| Full database corruption | < 2 hours | < 1 day (last base backup) |
| Datacenter failure | < 4 hours | < 1 hour (cross-region replica) |

### 18.3 Redis Persistence

Redis is configured with:
- **AOF (Append-Only File)**: `appendfsync everysec` — at most 1 second of data loss on crash
- **RDB snapshot**: Every 15 minutes if ≥ 100 keys changed

Redis data loss only affects caching and active sessions. No business-critical state lives exclusively in Redis. On Redis restart:
- Active user sessions are lost (users must re-login)
- Workflow run status cache is rebuilt from PostgreSQL on next read
- WebSocket subscriptions are re-established by clients on reconnect

### 18.4 Object Storage (S3/MinIO)

| Feature | Configuration |
|---------|--------------|
| Versioning | Enabled on the documents bucket |
| Cross-region replication | Enabled in production (primary → replica bucket) |
| Object deletion | Delete markers used (true deletion requires explicit delete-marker removal) |
| Retention policy | User-uploaded documents: indefinite until explicit deletion |
| Generated artifacts | 90-day lifecycle rule for `generated/` prefix |

### 18.5 Backup Verification

Backups are tested monthly via an automated process:

```bash
# Monthly backup verification (Celery scheduled task)
1. Restore last nightly backup to an isolated test instance
2. Run pg_restore integrity check
3. Execute 5 key queries (count tables, verify FK consistency)
4. Log result + notify platform team
5. Destroy test instance
```

---

*End of Database Design Document v1.1.0*

*All schema changes must go through an Alembic migration. Direct DDL changes to production are prohibited. This document is updated alongside migrations.*

*v1.1.0 changes: Added Platform Admin Domain (5 new tables: `platform_users`, `support_access_grants`, `support_tickets`, `feature_flags`, `platform_audit_logs`). Clarified org cross-cutting vs. platform-level scope distinction. Added platform admin query patterns Q11–Q15. Updated seed data and Alembic imports to include platform module. See ARCHITECTURE.md §10.5 for role hierarchy and RBAC design.*
