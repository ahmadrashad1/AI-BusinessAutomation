# Software Requirements Specification (SRS)
# AI Business Process Automation Platform

| Field | Value |
|-------|-------|
| Version | 1.0.0 |
| Status | Draft |
| Date | 2026-06-29 |
| Author | Architecture Team |
| Classification | Internal |

---

## Table of Contents

1. [Vision](#1-vision)
2. [Functional Requirements](#2-functional-requirements)
3. [Non-Functional Requirements](#3-non-functional-requirements)
4. [User Roles](#4-user-roles)
5. [User Stories](#5-user-stories)
6. [Use Cases](#6-use-cases)
7. [System Constraints](#7-system-constraints)
8. [Tech Stack](#8-tech-stack)
9. [Security](#9-security)
10. [Database Requirements](#10-database-requirements)
11. [AI Requirements](#11-ai-requirements)
12. [Deployment](#12-deployment)
13. [Future Roadmap](#13-future-roadmap)

---

## 1. Vision

### 1.1 Problem Statement

Organizations of all sizes spend thousands of hours every month on repetitive manual processes. Employees read emails, extract data from invoices, copy information between systems, update CRMs, route support tickets, and generate reports — all by hand. These processes are slow, error-prone, and expensive.

The core problem is disconnected tooling. A typical organization operates across email, spreadsheets, CRM systems, ERPs, document storage platforms, and messaging tools — none of which communicate with each other. Employees become the integration layer, manually transferring information between systems throughout the day.

**Before this platform:**
```
Customer sends invoice email
        ↓ Employee reads email
        ↓ Downloads attachment
        ↓ Opens invoice manually
        ↓ Transcribes data into ERP
        ↓ Sends confirmation email
        ↓ Notifies finance team via Slack
```

**After this platform:**
```
Customer sends invoice email
        ↓ Workflow triggered automatically
        ↓ AI extracts structured invoice data
        ↓ ERP updated via API
        ↓ Finance team notified automatically
        ↓ Customer receives confirmation email
```

### 1.2 Product Overview

The AI Business Process Automation Platform is a multi-tenant SaaS product that enables organizations to design, execute, monitor, and optimize automated business workflows using AI agents and visual workflow tooling.

The platform combines:

- **Visual Workflow Builder** — drag-and-drop interface to compose automation pipelines
- **AI Processing Engine** — document extraction, classification, summarization, and decision support
- **Integration Hub** — connections to email, CRM, ERP, cloud storage, and messaging tools
- **Execution Engine** — reliable, observable, retryable workflow execution with scheduling
- **Analytics Dashboard** — real-time visibility into workflow performance and AI usage

### 1.3 Value Proposition

| Stakeholder | Value Delivered |
|-------------|----------------|
| Organization Owner | Reduce operational headcount costs, increase throughput without hiring |
| Operations Teams | Eliminate repetitive data entry and manual routing tasks |
| Managers | Real-time visibility into process performance and bottlenecks |
| IT / Developers | Extensible platform with API access and custom integration support |
| Finance Teams | Faster invoice processing, accurate ERP data, audit trails |

### 1.4 Target Market

- **Primary:** Small to medium-sized businesses (50–500 employees) with high-volume repetitive processes
- **Secondary:** Enterprise departments within larger organizations (HR, Finance, Legal, Procurement, Customer Support)
- **Geography:** Initially English-speaking markets; internationalization planned for Phase 3

### 1.5 Success Metrics

| Metric | MVP Target | 12-Month Target |
|--------|-----------|----------------|
| Organizations onboarded | 50 | 1,000 |
| Workflow executions / month | 10,000 | 1,000,000 |
| Average time saved per workflow | 15 min | 15 min |
| Workflow success rate | ≥ 95% | ≥ 98% |
| AI extraction accuracy | ≥ 90% | ≥ 95% |
| P95 API response time | < 500ms | < 300ms |

---

## 2. Functional Requirements

### Priority Legend

| Code | Meaning |
|------|---------|
| **M** | Must Have — core MVP, no launch without this |
| **S** | Should Have — important, ship in first iteration after MVP |
| **C** | Could Have — valuable, schedule when capacity permits |
| **W** | Won't Have (now) — explicitly deferred to future roadmap |

---

### 2.1 Authentication & Session Management

| ID | Priority | Requirement |
|----|----------|-------------|
| FR-AUTH-001 | M | Users can register with email and password |
| FR-AUTH-002 | M | Users can log in with email and password |
| FR-AUTH-003 | M | System issues JWT access tokens (15-minute expiry) and refresh tokens (7-day expiry) |
| FR-AUTH-004 | M | System silently refreshes access tokens using refresh tokens |
| FR-AUTH-005 | M | Users can log out, invalidating their refresh token |
| FR-AUTH-006 | M | System sends email verification on registration; unverified accounts cannot access the platform |
| FR-AUTH-007 | M | Users can request a password reset via email link (token valid for 1 hour) |
| FR-AUTH-008 | S | Users can authenticate via Google OAuth 2.0 |
| FR-AUTH-009 | S | Users can manage active sessions and revoke individual sessions |
| FR-AUTH-010 | C | Users can authenticate via Microsoft OAuth 2.0 |
| FR-AUTH-011 | C | System supports multi-factor authentication (TOTP) |

---

### 2.2 Organization Management

| ID | Priority | Requirement |
|----|----------|-------------|
| FR-ORG-001 | M | A user can create an organization and becomes its Owner |
| FR-ORG-002 | M | Organization Owner can invite users by email |
| FR-ORG-003 | M | Invited users receive an email with an invitation link (valid for 48 hours) |
| FR-ORG-004 | M | Organization Owner can assign roles to members (Owner, Admin, Manager, Business Analyst, Employee, Viewer) |
| FR-ORG-005 | M | Organization Owner can remove members from the organization |
| FR-ORG-006 | M | Each user can belong to multiple organizations and switch between them |
| FR-ORG-007 | M | Organization data is strictly isolated — no cross-tenant data access |
| FR-ORG-008 | S | Admins can create departments within the organization |
| FR-ORG-009 | S | Users can be assigned to one or more departments |
| FR-ORG-010 | S | Admins can configure organization-level settings (name, logo, timezone, language) |
| FR-ORG-011 | C | Organization Owner can view a billing dashboard and manage subscription tier |
| FR-ORG-012 | C | System enforces usage limits per subscription tier (workflow count, AI token usage, storage) |

---

### 2.3 Workflow Builder

| ID | Priority | Requirement |
|----|----------|-------------|
| FR-WF-001 | M | Business Analysts and Admins can create new workflows |
| FR-WF-002 | M | Workflow Builder provides a visual drag-and-drop canvas (React Flow) |
| FR-WF-003 | M | Users can add nodes to the canvas from a categorized node palette |
| FR-WF-004 | M | Users can connect nodes with directed edges to define execution order |
| FR-WF-005 | M | Users can configure each node via a side-panel properties form |
| FR-WF-006 | M | System supports the following trigger node types: Manual, Schedule (cron), Webhook, API Call, Email Received |
| FR-WF-007 | M | System supports the following action node types: Send Email, HTTP Request, Database Write, Delay, Condition/Branch |
| FR-WF-008 | M | System supports the following AI node types: Document Extraction, Text Classification, Summarization, AI Prompt |
| FR-WF-009 | M | Users can save a workflow as a draft |
| FR-WF-010 | M | Users can publish a workflow to make it executable |
| FR-WF-011 | M | System versions workflows — each publish creates a new version; prior versions are retained |
| FR-WF-012 | M | Users can revert to a previous workflow version |
| FR-WF-013 | S | Users can duplicate an existing workflow |
| FR-WF-014 | S | Users can export a workflow definition as JSON |
| FR-WF-015 | S | Users can import a workflow definition from JSON |
| FR-WF-016 | S | Workflow Builder validates the graph before publishing (no orphan nodes, required fields completed) |
| FR-WF-017 | S | Users can add human-readable labels and descriptions to nodes |
| FR-WF-018 | C | System provides a library of workflow templates that users can clone and customize |
| FR-WF-019 | C | Users can describe a workflow in natural language and the AI generates a draft workflow graph |
| FR-WF-020 | C | Workflow Builder supports sub-workflows (reusable workflow blocks) |

---

### 2.4 Workflow Execution Engine

| ID | Priority | Requirement |
|----|----------|-------------|
| FR-EXE-001 | M | Users can manually trigger execution of a published workflow |
| FR-EXE-002 | M | System executes scheduled workflows at the configured cron interval |
| FR-EXE-003 | M | System executes workflows via incoming webhook HTTP requests |
| FR-EXE-004 | M | System executes workflows via authenticated API calls |
| FR-EXE-005 | M | Each workflow execution creates a unique workflow run record |
| FR-EXE-006 | M | System executes workflow nodes sequentially in topological order |
| FR-EXE-007 | M | System evaluates Condition nodes and routes execution to the appropriate branch |
| FR-EXE-008 | M | Each node execution produces a structured output passed as input to the next node |
| FR-EXE-009 | M | Long-running AI tasks execute asynchronously via a task queue (Celery/Redis) |
| FR-EXE-010 | M | System records the status of each workflow run: Pending, Running, Completed, Failed, Cancelled |
| FR-EXE-011 | M | System logs each node execution: status, input, output, duration, timestamps |
| FR-EXE-012 | M | Failed workflow steps are automatically retried up to a configurable maximum (default: 3) |
| FR-EXE-013 | M | System supports configurable retry delay with exponential backoff |
| FR-EXE-014 | S | Users can manually retry a failed workflow run from the last failed node |
| FR-EXE-015 | S | Users can cancel a running workflow execution |
| FR-EXE-016 | S | System emits real-time execution status updates via WebSocket |
| FR-EXE-017 | S | Workflow execution supports passing input data as a JSON payload at trigger time |
| FR-EXE-018 | C | System supports parallel node execution for independent branches |
| FR-EXE-019 | C | System supports workflow execution timeouts configurable per workflow |

---

### 2.5 Workflow Monitoring

| ID | Priority | Requirement |
|----|----------|-------------|
| FR-MON-001 | M | Users can view a list of all workflow runs with status, trigger, and timestamps |
| FR-MON-002 | M | Users can view the detailed execution log of a specific workflow run |
| FR-MON-003 | M | Execution log shows each node's status, input data, output data, duration, and error message |
| FR-MON-004 | M | Users can filter workflow runs by status, date range, and workflow name |
| FR-MON-005 | S | System displays execution history paginated with search |
| FR-MON-006 | S | System highlights failed nodes visually on the workflow canvas |
| FR-MON-007 | S | Users receive in-app notifications when a workflow run fails |
| FR-MON-008 | C | Users can set alert thresholds (e.g., failure rate > 10%) and receive email alerts |

---

### 2.6 File Management

| ID | Priority | Requirement |
|----|----------|-------------|
| FR-FILE-001 | M | Users can upload files: PDF, DOCX, XLSX, CSV, PNG, JPEG |
| FR-FILE-002 | M | Files are stored in S3-compatible object storage (MinIO in dev, S3 in prod) |
| FR-FILE-003 | M | System generates a secure, time-limited pre-signed URL for file download |
| FR-FILE-004 | M | File metadata (name, size, type, owner, upload date) is recorded in the database |
| FR-FILE-005 | M | Files are scoped to the organization — users cannot access files from other organizations |
| FR-FILE-006 | S | Users can delete files; deletion removes both the database record and the object in storage |
| FR-FILE-007 | S | System enforces per-organization storage quotas based on subscription tier |
| FR-FILE-008 | C | Users can organize files into folders |
| FR-FILE-009 | C | System retains file version history when a file is re-uploaded with the same name |

---

### 2.7 Notifications

| ID | Priority | Requirement |
|----|----------|-------------|
| FR-NOT-001 | M | System generates in-app notifications for workflow failures, invitations, and system alerts |
| FR-NOT-002 | M | Users can view their notification feed with read/unread status |
| FR-NOT-003 | M | System sends transactional emails (verification, password reset, invitations, workflow alerts) |
| FR-NOT-004 | S | System delivers real-time notifications to the client via WebSocket |
| FR-NOT-005 | S | Users can configure notification preferences (email on/off per event type) |
| FR-NOT-006 | C | Workflow action nodes can send notifications to Slack channels via webhook |
| FR-NOT-007 | C | Workflow action nodes can send notifications to Microsoft Teams channels |
| FR-NOT-008 | C | System supports outbound webhook delivery for external notification consumers |

---

### 2.8 Analytics Dashboard

| ID | Priority | Requirement |
|----|----------|-------------|
| FR-ANA-001 | M | Dashboard displays total workflow executions, success count, and failure count |
| FR-ANA-002 | M | Dashboard displays AI token usage (total, by workflow, by model) |
| FR-ANA-003 | M | Dashboard displays average workflow execution time |
| FR-ANA-004 | M | Dashboard displays most-executed workflows |
| FR-ANA-005 | S | Dashboard displays time-series charts for executions and failures over time |
| FR-ANA-006 | S | Managers can view per-user activity (executions triggered, documents processed) |
| FR-ANA-007 | S | Dashboard displays top failure reasons and failing workflow nodes |
| FR-ANA-008 | C | System generates weekly summary reports emailed to Owners and Managers |
| FR-ANA-009 | C | AI Decision Support surfaces workflow optimization recommendations based on execution history |
| FR-ANA-010 | W | Custom report builder for user-defined analytics queries |

---

### 2.9 API & Integrations

| ID | Priority | Requirement |
|----|----------|-------------|
| FR-API-001 | M | System exposes a RESTful API for all platform operations |
| FR-API-002 | M | API is versioned (e.g., `/api/v1/`) |
| FR-API-003 | M | Admins can generate, rotate, and revoke API keys for programmatic access |
| FR-API-004 | M | API key access is scoped to specific permissions |
| FR-API-005 | S | System provides OpenAPI (Swagger) documentation for all endpoints |
| FR-API-006 | S | System supports incoming webhook receivers as workflow triggers |
| FR-API-007 | C | Workflow nodes can make outbound HTTP requests to arbitrary REST APIs with configurable auth (Bearer, Basic, API Key) |
| FR-API-008 | C | Platform provides a Gmail integration (read emails, send emails) via OAuth |
| FR-API-009 | C | Platform provides a Google Drive integration (upload, download, list files) |
| FR-API-010 | C | Platform provides a Slack integration (send messages to channels) |
| FR-API-011 | W | Platform provides a Salesforce CRM integration |
| FR-API-012 | W | Platform provides a HubSpot CRM integration |
| FR-API-013 | W | Platform provides an SAP ERP integration |

---

## 3. Non-Functional Requirements

### 3.1 Performance

| ID | Requirement |
|----|-------------|
| NFR-PERF-001 | API endpoints return responses within 300ms at P95 under normal load |
| NFR-PERF-002 | Workflow trigger acknowledgement (not completion) returns within 200ms |
| NFR-PERF-003 | Simple workflow executions (no AI nodes) complete within 5 seconds |
| NFR-PERF-004 | AI document extraction completes within 30 seconds for documents up to 50 pages |
| NFR-PERF-005 | Dashboard analytics queries return within 2 seconds |
| NFR-PERF-006 | File uploads up to 50MB complete without timeout |
| NFR-PERF-007 | WebSocket notifications are delivered within 1 second of the triggering event |

### 3.2 Scalability

| ID | Requirement |
|----|-------------|
| NFR-SCALE-001 | The API layer scales horizontally; no session state is stored on the API server |
| NFR-SCALE-002 | The Celery worker pool scales independently of the API layer |
| NFR-SCALE-003 | The system handles 1,000 concurrent API requests without degradation |
| NFR-SCALE-004 | The task queue supports 10,000 queued workflow executions without data loss |
| NFR-SCALE-005 | Database read traffic is offloaded to read replicas as volume grows |
| NFR-SCALE-006 | Object storage is unbounded in capacity (S3-compatible) |

### 3.3 Availability & Reliability

| ID | Requirement |
|----|-------------|
| NFR-AVAIL-001 | System targets 99.9% uptime (< 8.7 hours downtime/year) in production |
| NFR-AVAIL-002 | Scheduled workflow executions are retried automatically if the worker is temporarily unavailable |
| NFR-AVAIL-003 | Database is deployed with automatic failover (primary + standby) |
| NFR-AVAIL-004 | Redis is deployed in cluster mode with replication |
| NFR-AVAIL-005 | All failed workflow executions are recorded; no execution is silently dropped |
| NFR-AVAIL-006 | System gracefully degrades if the LLM provider is unavailable — AI nodes fail with a clear error rather than hanging |

### 3.4 Security

| ID | Requirement |
|----|-------------|
| NFR-SEC-001 | All data in transit is encrypted via TLS 1.2+ |
| NFR-SEC-002 | All sensitive data at rest (passwords, API keys, OAuth tokens) is encrypted |
| NFR-SEC-003 | Passwords are hashed using bcrypt with a minimum cost factor of 12 |
| NFR-SEC-004 | JWT secrets are rotated without downtime |
| NFR-SEC-005 | API keys are stored as bcrypt hashes; the plaintext value is shown only once at creation |
| NFR-SEC-006 | All user actions affecting organization data are recorded in an immutable audit log |
| NFR-SEC-007 | Every database query is scoped to the authenticated user's organization_id |
| NFR-SEC-008 | File access requires a valid, time-limited pre-signed URL tied to the organization |
| NFR-SEC-009 | Rate limiting is applied to authentication endpoints (5 failed attempts → 15-minute lockout) |
| NFR-SEC-010 | Input validation is applied to all API endpoints; raw user input is never interpolated into SQL or shell commands |

### 3.5 Maintainability

| ID | Requirement |
|----|-------------|
| NFR-MAINT-001 | All database schema changes are managed through versioned Alembic migrations |
| NFR-MAINT-002 | Backend code achieves ≥ 80% test coverage on business logic |
| NFR-MAINT-003 | Workflow node types are implemented as a plugin architecture — new node types can be added without modifying the execution engine |
| NFR-MAINT-004 | All services emit structured JSON logs with request IDs for distributed tracing |
| NFR-MAINT-005 | Environment-specific configuration is managed via environment variables, never hardcoded |

### 3.6 Usability

| ID | Requirement |
|----|-------------|
| NFR-USE-001 | A non-technical user can build and publish a simple 3-node workflow within 15 minutes without documentation |
| NFR-USE-002 | The UI displays clear, actionable error messages for all failure states |
| NFR-USE-003 | The workflow canvas supports undo/redo for the last 20 actions |
| NFR-USE-004 | The platform is accessible on modern browsers: Chrome, Firefox, Edge, Safari (last 2 major versions) |
| NFR-USE-005 | The UI is responsive and functional on tablet-sized screens (≥ 768px) |

---

## 4. User Roles

### 4.1 Role Overview

The platform uses Role-Based Access Control (RBAC). Each user within an organization is assigned exactly one role. Roles are hierarchical — higher roles inherit the permissions of lower roles.

```
Owner
  └── Admin
        └── Manager
              └── Business Analyst
                    └── Employee
                          └── Viewer
```

### 4.2 Role Definitions

#### Owner
The organization creator. Unique per organization (only one active Owner at a time).

**Responsibilities:**
- Full control over the organization
- Manage subscription and billing
- Transfer ownership
- Delete the organization

#### Admin
Designated by the Owner to manage day-to-day operations.

**Responsibilities:**
- Invite and remove users
- Assign and change roles
- Configure integrations and API keys
- Manage departments
- Access all organization data and workflows

#### Manager
Team leads and department heads who oversee operations.

**Responsibilities:**
- Monitor workflow execution and KPIs
- Review AI-generated outputs before they trigger external actions
- Approve workflow publishing
- View analytics dashboards and reports
- Read-only access to audit logs

#### Business Analyst
The primary workflow designer.

**Responsibilities:**
- Create, edit, and publish workflows
- Design AI prompts and configure AI nodes
- Configure integrations within workflows
- Monitor workflow performance
- Manage document templates

#### Employee
Operational team member who uses automated workflows day-to-day.

**Responsibilities:**
- Manually trigger assigned workflows
- Upload documents for processing
- View results of workflows they triggered
- Receive notifications related to their work

#### Viewer
Read-only access for stakeholders who need visibility but not participation.

**Responsibilities:**
- View workflow definitions (not edit)
- View execution history and status
- View analytics dashboards

### 4.3 Permission Matrix

| Feature | Viewer | Employee | Business Analyst | Manager | Admin | Owner |
|---------|--------|----------|-----------------|---------|-------|-------|
| View workflows | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Create/edit workflows | ✗ | ✗ | ✓ | ✓ | ✓ | ✓ |
| Publish workflows | ✗ | ✗ | ✓ | ✓ | ✓ | ✓ |
| Delete workflows | ✗ | ✗ | ✓ | ✓ | ✓ | ✓ |
| Trigger workflows manually | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ |
| View execution history | ✓ | Own only | ✓ | ✓ | ✓ | ✓ |
| Retry failed executions | ✗ | ✗ | ✓ | ✓ | ✓ | ✓ |
| Upload documents | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Manage integrations | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |
| Manage API keys | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |
| Invite users | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |
| Manage roles | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |
| View analytics | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ |
| View audit logs | ✗ | ✗ | ✗ | ✓ | ✓ | ✓ |
| Manage billing | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ |
| Delete organization | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ |

---

## 5. User Stories

### Epic 1: Authentication & Onboarding

| ID | Role | Story | Acceptance Criteria |
|----|------|-------|---------------------|
| US-001 | New User | As a new user, I want to register with my email and password so that I can access the platform | Registration form validates email format and password strength; verification email sent; unverified users cannot log in |
| US-002 | Registered User | As a registered user, I want to log in so that I can access my organization's workflows | Successful login returns access and refresh tokens; failed login shows error without leaking whether email exists |
| US-003 | User | As a user, I want to reset my password via email so that I can regain access if I forget it | Reset link expires in 1 hour; link is single-use; password updated successfully on form submission |
| US-004 | User | As a user, I want to log in with Google so that I don't need a separate password for this platform | OAuth flow completes; account linked to Google email; user lands on dashboard |
| US-005 | User | As a user, I want to manage my active sessions so that I can revoke access from devices I no longer use | Session list shows device, location, last active; individual sessions can be revoked |

### Epic 2: Organization Management

| ID | Role | Story | Acceptance Criteria |
|----|------|-------|---------------------|
| US-006 | New User | As a new user, I want to create an organization so that my team can collaborate on automation | Organization created with user as Owner; organization slug generated; team can be invited immediately |
| US-007 | Owner/Admin | As an admin, I want to invite team members by email so that they can access the platform | Invitation email sent; recipient can accept and is added to the organization with the assigned role; invitations expire after 48 hours |
| US-008 | Owner | As an organization owner, I want to assign roles to team members so that each person has appropriate access | Role dropdown shown for each member; changes take effect immediately; Owner cannot demote themselves without transferring ownership |
| US-009 | User | As a user, I want to switch between organizations I belong to so that I can work across clients | Organization switcher in nav; switching loads the selected organization's context |
| US-010 | Admin | As an admin, I want to create departments so that I can organize workflows and users by team | Department created; users can be assigned to departments; workflows can be scoped to departments |

### Epic 3: Workflow Building

| ID | Role | Story | Acceptance Criteria |
|----|------|-------|---------------------|
| US-011 | Business Analyst | As a business analyst, I want to drag and drop nodes onto a canvas so that I can visually design automation workflows | Node palette shows categorized nodes; nodes snap to grid; connections can be drawn between output and input ports |
| US-012 | Business Analyst | As a business analyst, I want to configure each node's properties so that the workflow behaves correctly | Clicking a node opens a properties panel; required fields are validated; configuration is saved on blur or confirmation |
| US-013 | Business Analyst | As a business analyst, I want to save a workflow as a draft so that I can continue editing it later | Draft saved with auto-save every 30 seconds; manual save available; draft not executable until published |
| US-014 | Business Analyst | As a business analyst, I want to publish a workflow so that it can be executed | Validation runs before publish; errors are shown inline; successful publish increments version number |
| US-015 | Business Analyst | As a business analyst, I want to revert to a previous workflow version so that I can undo a bad change | Version history list shows timestamp and author of each version; selected version loads in canvas for review before restoring |
| US-016 | Business Analyst | As a business analyst, I want to describe a workflow in plain English and have the AI generate a draft so that I can automate faster | Natural language input field; AI generates a valid node graph; user reviews and edits before publishing |

### Epic 4: Workflow Execution & Monitoring

| ID | Role | Story | Acceptance Criteria |
|----|------|-------|---------------------|
| US-017 | Employee | As an employee, I want to manually trigger a workflow so that I can start an automation on demand | Trigger button shown on published workflows; optional input payload form; execution starts and status is visible immediately |
| US-018 | Business Analyst | As a business analyst, I want to schedule a workflow to run daily at 9am so that reports are generated automatically | Cron expression or friendly scheduler UI; next run time shown; schedule survives redeployment |
| US-019 | Manager | As a manager, I want to see the real-time execution status of a running workflow so that I know if it's proceeding correctly | Live status updates via WebSocket; each node shows Pending/Running/Complete/Failed; no manual refresh required |
| US-020 | Manager | As a manager, I want to see the full execution log of a completed workflow run so that I can diagnose failures | Log shows each node: start time, duration, input data, output data, error message if failed |
| US-021 | Business Analyst | As a business analyst, I want to retry a failed workflow from the failed step so that I don't need to restart the entire run | Retry button on failed runs; execution resumes from failed node; prior successful node outputs are preserved |

### Epic 5: AI Features

| ID | Role | Story | Acceptance Criteria |
|----|------|-------|---------------------|
| US-022 | Employee | As an employee, I want to upload an invoice and have the AI extract the vendor name, amount, due date, and line items automatically | AI returns structured JSON; extraction confidence score shown; user can review and correct before saving |
| US-023 | Business Analyst | As a business analyst, I want to classify incoming emails by type (complaint, inquiry, invoice) so that they are routed to the correct workflow | Classification node configured with categories; AI returns label and confidence score; condition nodes route based on label |
| US-024 | Employee | As an employee, I want to ask questions about our internal documents and get accurate answers so that I can find policy information quickly | RAG system retrieves relevant document chunks; answer includes source references; response grounded in document content |
| US-025 | Manager | As a manager, I want the AI to generate a weekly workflow performance report so that I have an executive summary without manual effort | Report generated as structured document; includes execution counts, success rates, top failures, trending metrics |
| US-026 | Business Analyst | As a business analyst, I want to configure a multi-agent workflow where one agent reads a document and another validates the extracted data so that complex tasks are handled reliably | LangGraph-based multi-agent node; agents defined with roles and tools; inter-agent communication via shared state |

### Epic 6: Files & Documents

| ID | Role | Story | Acceptance Criteria |
|----|------|-------|---------------------|
| US-027 | Employee | As an employee, I want to upload a PDF contract so that the AI can process it | File picker accepts PDF, DOCX, XLSX, CSV, PNG, JPEG; upload progress shown; file appears in document library immediately |
| US-028 | Employee | As an employee, I want to download a processed document so that I can share it | Pre-signed URL generated on demand; download begins without exposing permanent storage URL; link expires after 15 minutes |

### Epic 7: Analytics

| ID | Role | Story | Acceptance Criteria |
|----|------|-------|---------------------|
| US-029 | Owner | As an organization owner, I want to see total AI token usage so that I can manage costs | Token usage shown by model, by workflow, and by date range; current month total prominently displayed |
| US-030 | Manager | As a manager, I want to see which workflows fail most often so that I can prioritize fixes | Failure rate table sorted by count; failure reasons aggregated; links to individual failed runs |

---

## 6. Use Cases

### UC-001: Invoice Processing Workflow

**Actor:** Employee (trigger), AI Extraction Node, ERP System (external)

**Preconditions:**
- User is authenticated and has Employee role or above
- An invoice processing workflow is published
- ERP integration is configured

**Main Flow:**
1. Customer sends invoice to monitored email address
2. Email Trigger node fires; email metadata and attachment are passed to the next node
3. File Download node retrieves the PDF attachment from the email
4. AI Document Extraction node receives the PDF; sends to OCR + LLM pipeline
5. LLM extracts: Vendor Name, Invoice Number, Invoice Date, Due Date, Line Items, Total Amount, Tax
6. Condition node validates that all required fields are present
7. HTTP Request node sends structured data to ERP via REST API
8. Send Email node sends confirmation to the customer
9. Slack Notification node notifies the Finance channel
10. Workflow run is marked Complete; execution log is recorded

**Alternate Flow — Missing Fields:**
- At step 6, if required fields are missing, workflow branches to a human review node
- Manager receives in-app notification with the partial extraction for manual completion
- After manual completion, execution resumes at step 7

**Postconditions:**
- ERP updated with invoice data
- Customer received confirmation
- Finance team notified
- Full execution log available for audit

---

### UC-002: User Invites a Team Member

**Actor:** Admin or Owner

**Preconditions:**
- Actor is authenticated and has Admin or Owner role
- Invited email is not already a member of the organization

**Main Flow:**
1. Admin navigates to Organization Settings → Members
2. Admin enters the invitee's email address and selects a role
3. System creates an invitation record with a signed token (48-hour expiry)
4. System sends an invitation email to the invitee
5. Invitee clicks the link and is prompted to register (if no account) or log in
6. On acceptance, a membership record is created linking the user to the organization with the assigned role
7. Invitee is redirected to the organization dashboard

**Alternate Flow — Invitee Already Has Account:**
- At step 5, if the email matches an existing account, user logs in normally
- Invitation is automatically accepted and membership created

**Alternate Flow — Expired Invitation:**
- At step 5, if the token is expired, user sees an error
- Admin must send a new invitation

**Postconditions:**
- New member record exists in the organization
- New member can log in and access the platform with the assigned role
- Audit log records the invitation and acceptance

---

### UC-003: Business Analyst Builds and Publishes a Workflow

**Actor:** Business Analyst

**Preconditions:**
- User is authenticated with Business Analyst role or above
- User belongs to an organization

**Main Flow:**
1. Business Analyst navigates to Workflows → New Workflow
2. User enters workflow name and description
3. User drags a trigger node (e.g., Webhook) onto the canvas from the node palette
4. User configures the trigger: sets the webhook path
5. User drags an AI Document Extraction node and connects it to the trigger
6. User configures the extraction node: selects document field, defines expected fields
7. User drags a Condition node; connects to extraction node output
8. User configures the condition: checks if `confidence_score > 0.8`
9. User drags a Database Write node for the True branch and a Human Review node for the False branch
10. User saves the workflow (auto-save and manual save)
11. User clicks Publish
12. System validates the graph: no orphan nodes, all required fields complete
13. System saves the workflow as version 1 and marks it Active
14. System generates a unique webhook URL for the workflow

**Alternate Flow — Validation Failure:**
- At step 12, if validation fails, system highlights the failing node and shows a descriptive error message
- User corrects the issue and re-publishes

**Postconditions:**
- Workflow version 1 is published and executable
- Webhook URL is available for external systems to call
- Workflow appears in the published workflows list

---

### UC-004: Employee Queries Internal Documents (RAG)

**Actor:** Employee

**Preconditions:**
- User is authenticated with Employee role or above
- Company documents have been uploaded and indexed (embeddings stored in pgvector)

**Main Flow:**
1. Employee navigates to the AI Assistant / Knowledge Base section
2. Employee types a question: "What is our maternity leave policy?"
3. System embeds the query using the same embedding model used for indexing
4. System performs a cosine similarity search against the pgvector index for the organization's documents
5. Top K relevant chunks are retrieved with their source document references
6. LLM receives the query and the retrieved chunks; generates a grounded answer
7. Response is displayed with inline citations linking to the source documents
8. Employee can follow the citation link to view the source document

**Alternate Flow — No Relevant Documents Found:**
- At step 4, if similarity scores are below a threshold, the system responds: "I couldn't find relevant information in your documents. You may want to upload the relevant policy document."

**Postconditions:**
- Employee has an accurate answer grounded in company documents
- No hallucinated content — all claims reference retrieved chunks

---

### UC-005: Workflow Execution Fails and is Retried

**Actor:** Celery Worker (automated), Business Analyst (manual retry)

**Preconditions:**
- A workflow is running
- A node encounters an error (e.g., external API returns 500)

**Main Flow:**
1. Node execution returns an error
2. Celery worker catches the exception; records the node execution as Failed with error details
3. Worker checks the retry count against the maximum (default: 3)
4. Worker schedules a retry with exponential backoff (e.g., 2^attempt × 10 seconds)
5. If retry succeeds, execution continues to the next node
6. If all retries are exhausted, the workflow run is marked Failed
7. System sends an in-app notification to the workflow owner
8. Business Analyst views the execution log and identifies the failing node
9. Business Analyst clicks "Retry from Failed Node"
10. System re-executes from the failed node with the same input data from the previous successful node

**Postconditions:**
- If retry succeeds: workflow run marked Complete; no duplicate side effects from already-succeeded nodes
- If retries exhausted: full error context recorded; manual retry available

---

### UC-006: Admin Manages API Keys

**Actor:** Admin

**Preconditions:**
- User is authenticated with Admin or Owner role

**Main Flow:**
1. Admin navigates to Settings → API Keys
2. Admin clicks "Generate New API Key"
3. Admin enters a label and selects scopes (e.g., workflow:execute, document:read)
4. System generates a cryptographically random API key
5. System stores a bcrypt hash of the key in the database
6. System displays the plaintext key to the Admin once — with a prominent warning to copy it now
7. Admin copies the key and configures it in the external system
8. For subsequent API calls, the external system sends the key in the Authorization header
9. System hashes the incoming key and compares against stored hashes for the organization

**Alternate Flow — Rotating a Key:**
- Admin generates a new key with the same scopes
- Old key continues to work until Admin explicitly revokes it
- Admin updates the external system with the new key, then revokes the old key

**Postconditions:**
- Plaintext key is never stored
- External systems can authenticate with the API key
- Key can be revoked instantly, immediately blocking further access

---

### UC-007: AI Workflow Agent Generates a Draft Workflow

**Actor:** Business Analyst

**Preconditions:**
- User is authenticated with Business Analyst role or above
- AI Workflow Agent feature is enabled for the organization

**Main Flow:**
1. Business Analyst opens the Workflow Builder
2. Business Analyst clicks "Generate with AI"
3. Business Analyst types: "When a customer emails an invoice, extract the data, update our ERP, and notify the finance team on Slack"
4. System sends the description to the LLM with a schema describing available node types and their configuration
5. LLM returns a JSON workflow graph with nodes, edges, and partial configurations
6. System deserializes the graph and renders it on the canvas
7. Business Analyst reviews the generated nodes — the trigger is set to Email Received, an AI Extraction node follows, then an HTTP Request node targeting the ERP, and a Slack Notification node
8. Business Analyst fills in the ERP endpoint URL and Slack channel name
9. Business Analyst publishes the workflow

**Postconditions:**
- Draft workflow created in seconds vs. minutes of manual building
- Business Analyst retains full control; AI is a starting point, not the final decision

---

### UC-008: Multi-Agent Document Validation

**Actor:** Business Analyst (configuration), Celery Worker (execution)

**Preconditions:**
- A multi-agent workflow node is configured with a Coordinator, Document Reader, Validator, and Report Generator agent
- A purchase order document is uploaded

**Main Flow:**
1. Workflow is triggered with a PDF purchase order as input
2. Coordinator Agent receives the task and delegates to Document Reader Agent
3. Document Reader Agent uses OCR + LLM to extract line items, vendor, totals from the PDF
4. Coordinator passes extracted data to Validator Agent
5. Validator Agent checks: quantities are positive, totals match line item sum, vendor exists in approved vendor list (queried from database)
6. If validation passes, Coordinator passes data to Report Generator Agent
7. Report Generator creates a structured approval summary document
8. Summary is saved to file storage; link is passed as workflow output
9. Manager receives notification with a link to the approval summary

**Postconditions:**
- Purchase order validated without human data entry
- Validation result and reasoning recorded in execution log
- Manager has a structured summary to approve or reject

---

## 7. System Constraints

### 7.1 Technical Constraints

| ID | Constraint |
|----|-----------|
| TC-001 | All long-running operations (AI inference, file processing, external API calls) must execute asynchronously via the task queue to avoid blocking API request threads |
| TC-002 | The database schema must include `organization_id` on all tenant-specific tables; the application layer must enforce this filter on every query |
| TC-003 | LLM inference calls must include request timeouts (default: 60 seconds) to prevent indefinite blocking of worker threads |
| TC-004 | The workflow node architecture must be extensible — new node types are registered via a plugin registry, not by modifying the execution engine core |
| TC-005 | File content must never be stored in the relational database — only metadata; binary content lives in object storage |
| TC-006 | Redis is used exclusively for ephemeral state (task queues, caching, WebSocket channels) — Redis data loss must not corrupt workflow state |
| TC-007 | The system must function correctly with the LLM provider abstracted behind a configurable interface — switching between OpenAI, Anthropic, and local LLMs must not require code changes |

### 7.2 Business Constraints

| ID | Constraint |
|----|-----------|
| BC-001 | AI-generated outputs that trigger irreversible external actions (ERP updates, payment processing) must be reviewable by a human before execution, unless the workflow is explicitly configured for fully autonomous operation |
| BC-002 | Usage limits (API calls, AI tokens, storage) are enforced per organization per subscription tier |
| BC-003 | The platform must not store or process data in a manner that violates the organization's data residency requirements |
| BC-004 | All LLM provider API keys are organization-specific — the platform operator does not share a single API key across tenants |

### 7.3 Regulatory & Compliance Constraints

| ID | Constraint |
|----|-----------|
| RC-001 | User passwords must never be stored in plaintext or reversibly encrypted |
| RC-002 | An immutable audit trail must record all actions that modify organization data, workflows, users, or permissions |
| RC-003 | Users must be able to request deletion of their personal data (right to erasure) — the system must support account deletion with data anonymization |
| RC-004 | The platform must support GDPR-compliant data export for an organization's data upon request |
| RC-005 | Terms of Service and Privacy Policy acceptance must be recorded at registration with a timestamp |

### 7.4 Integration Constraints

| ID | Constraint |
|----|-----------|
| IC-001 | External integration credentials (OAuth tokens, API keys for third-party services) are encrypted at rest using AES-256 |
| IC-002 | Outbound HTTP requests from workflow nodes must respect configurable timeout and retry limits to prevent cascading failures |
| IC-003 | Webhook receivers must validate request signatures (HMAC-SHA256) before triggering workflow execution |

---

## 8. Tech Stack

### 8.1 Frontend

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Framework | Next.js 14 (App Router) | SSR/SSG support, React ecosystem, built-in routing, excellent TypeScript support |
| Language | TypeScript | Type safety, better IDE support, reduces runtime errors |
| Styling | Tailwind CSS | Utility-first, consistent design system, fast iteration |
| Component Library | shadcn/ui | Accessible, unstyled components built on Radix UI, composable |
| Workflow Canvas | React Flow | Purpose-built for node graph editors; handles pan, zoom, edge routing |
| State Management | Zustand | Lightweight, minimal boilerplate for client state |
| Server State | TanStack Query (React Query) | Caching, background refetch, optimistic updates for API data |
| Forms | React Hook Form + Zod | Performant form handling with schema-based validation |
| Real-time | Native WebSocket / Socket.io client | Live execution status updates |
| HTTP Client | Axios | Request/response interceptors for auth token refresh |

### 8.2 Backend

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Framework | FastAPI | High performance, async-native, automatic OpenAPI docs, Python ecosystem |
| Language | Python 3.11+ | Strong AI/ML library ecosystem, async support, type hints |
| ORM | SQLAlchemy 2.0 | Mature, expressive, supports async queries |
| Migrations | Alembic | Versioned schema migrations tightly integrated with SQLAlchemy |
| Task Queue | Celery + Redis | Battle-tested for distributed async tasks; supports retries, scheduling, monitoring |
| WebSockets | FastAPI WebSocket / Redis Pub/Sub | Real-time push to connected clients via Redis channels |
| Validation | Pydantic v2 | Fast schema validation, serialization, settings management |
| Email | SendGrid / SMTP | Transactional email delivery |
| Testing | pytest + pytest-asyncio | Async-compatible test suite |

### 8.3 AI & ML

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| LLM Orchestration | LangChain | Chains, tools, document loaders, memory abstractions |
| Multi-Agent | LangGraph | Stateful agent graphs, cycle support, human-in-the-loop |
| LLM Providers | OpenAI GPT-4o, Anthropic Claude (configurable) | Best-in-class capability; provider-agnostic via abstraction layer |
| Embeddings | OpenAI text-embedding-3-small / Sentence Transformers | Semantic search for RAG; local option available |
| Vector Store | pgvector (PostgreSQL extension) | Keeps embeddings co-located with relational data; no separate vector DB required at scale |
| OCR | Tesseract / AWS Textract (configurable) | Text extraction from scanned PDFs and images |
| Document Parsing | PyMuPDF, python-docx, openpyxl | Parse PDF, Word, and Excel without cloud dependency |

### 8.4 Data Storage

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Primary Database | PostgreSQL 16 | Mature, ACID-compliant, supports pgvector, JSON columns, full-text search |
| Cache & Queue Broker | Redis 7 | In-memory speed for caching and Celery task broker |
| Object Storage | MinIO (dev) / AWS S3 (prod) | S3-compatible API; unlimited file storage; pre-signed URL support |

### 8.5 Infrastructure & DevOps

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Containerization | Docker + Docker Compose | Consistent local dev environment; prod parity |
| Reverse Proxy / Load Balancer | Nginx | SSL termination, static file serving, upstream routing |
| CI/CD | GitHub Actions | Integrated with repository; supports parallel jobs, secrets management |
| Container Registry | GitHub Container Registry / Docker Hub | Store and version Docker images |
| Monitoring | Prometheus + Grafana (planned) | Metrics collection and visualization |
| Logging | Structured JSON logs → ELK Stack / CloudWatch | Centralized, searchable log aggregation |
| Secrets Management | Environment variables + HashiCorp Vault (prod) | No secrets in code; rotation without redeployment |

---

## 9. Security

### 9.1 Authentication

The platform uses JWT-based stateless authentication with short-lived access tokens and longer-lived refresh tokens.

| Token | Lifetime | Storage | Transmission |
|-------|---------|---------|-------------|
| Access Token | 15 minutes | Memory only (JS variable) | Authorization: Bearer header |
| Refresh Token | 7 days | HttpOnly, Secure, SameSite=Strict cookie | Cookie header (automatic) |

**Token Rotation:** On each refresh, the old refresh token is invalidated and a new one is issued (refresh token rotation). This limits the window for token theft exploitation.

**Invalidation:** Refresh tokens are stored in Redis with the user's session ID. Logout or admin revocation deletes the Redis entry, immediately invalidating the session.

### 9.2 Authorization (RBAC)

- Every API endpoint is decorated with a required permission scope
- The authenticated user's role is resolved from the database on each request
- Role resolution always includes the `organization_id` from the JWT claims — users cannot access other organizations' data even with valid tokens
- Permission checks happen in a middleware layer before business logic executes

### 9.3 Multi-Tenant Data Isolation

- Every table with tenant-specific data includes an `organization_id` foreign key
- SQLAlchemy query middleware automatically appends `WHERE organization_id = :current_org` to all queries
- Integration tests verify that users cannot retrieve data from a different organization via any API endpoint
- No cross-tenant joins are permitted in application code

### 9.4 Secrets & Key Management

| Secret Type | Storage Method |
|-------------|---------------|
| User passwords | bcrypt hash (cost factor 12) |
| JWT signing secret | Environment variable; not in database |
| Platform API keys | bcrypt hash; plaintext shown once |
| Third-party OAuth tokens | AES-256 encrypted column in database |
| Third-party API keys (user-provided) | AES-256 encrypted column in database |
| Encryption master key | Environment variable / Vault |

### 9.5 Transport Security

- All production traffic over HTTPS (TLS 1.2 minimum, TLS 1.3 preferred)
- HSTS header enforced on all responses
- HTTP to HTTPS redirect enforced at the Nginx layer
- Internal service communication (API ↔ DB, API ↔ Redis) runs within a private network segment

### 9.6 Input Validation & Injection Prevention

- All API request bodies are validated against Pydantic schemas before processing
- SQLAlchemy ORM with parameterized queries — no raw SQL string interpolation
- File upload validation: MIME type checked server-side (not just extension); files are stored in isolated paths per organization
- HTML output in the frontend uses React's automatic XSS escaping — `dangerouslySetInnerHTML` is forbidden
- Webhook payloads are validated with HMAC-SHA256 signatures before triggering execution

### 9.7 Rate Limiting

| Endpoint Category | Limit |
|-------------------|-------|
| Auth (login, register, password reset) | 5 requests / 15 minutes per IP |
| API (general) | 1,000 requests / minute per API key |
| AI endpoints | Configurable per organization tier |
| Webhook receivers | 100 requests / minute per webhook |

### 9.8 Audit Logging

Every state-changing action writes an audit log entry:

```
{
  "event_id": "uuid",
  "organization_id": "uuid",
  "user_id": "uuid",
  "action": "workflow.published",
  "resource_type": "workflow",
  "resource_id": "uuid",
  "ip_address": "x.x.x.x",
  "user_agent": "...",
  "timestamp": "ISO 8601",
  "metadata": { ... }
}
```

Audit logs are append-only — no update or delete operations on audit records. Retained for minimum 2 years.

---

## 10. Database Requirements

### 10.1 Database Engine

PostgreSQL 16 with the following extensions:
- `pgvector` — vector similarity search for RAG embeddings
- `uuid-ossp` — UUID generation for primary keys
- `pg_trgm` — trigram indexing for full-text search on workflow names and document metadata

### 10.2 Schema Overview

```
organizations ──┬── users (through org_members)
                ├── workflows ──── workflow_versions
                │                      └── workflow_nodes
                │                      └── workflow_edges
                ├── workflow_runs ──── execution_logs
                ├── documents ──── document_chunks (embeddings)
                ├── api_keys
                ├── notifications
                ├── audit_logs
                ├── integrations
                └── departments
```

### 10.3 Core Table Definitions

#### `organizations`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| name | VARCHAR(255) | |
| slug | VARCHAR(100) UNIQUE | URL-safe identifier |
| plan | VARCHAR(50) | free, pro, enterprise |
| settings | JSONB | org-level configuration |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

#### `users`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| email | VARCHAR(255) UNIQUE | |
| hashed_password | VARCHAR(255) | nullable for OAuth-only users |
| full_name | VARCHAR(255) | |
| avatar_url | TEXT | |
| is_verified | BOOLEAN | default false |
| is_active | BOOLEAN | default true |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

#### `org_members`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → organizations | |
| user_id | UUID FK → users | |
| role | VARCHAR(50) | owner, admin, manager, analyst, employee, viewer |
| department_id | UUID FK → departments | nullable |
| joined_at | TIMESTAMPTZ | |
| UNIQUE | (organization_id, user_id) | one membership per org per user |

#### `invitations`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → organizations | |
| invited_by | UUID FK → users | |
| email | VARCHAR(255) | |
| role | VARCHAR(50) | |
| token | VARCHAR(255) UNIQUE | signed, hashed |
| expires_at | TIMESTAMPTZ | |
| accepted_at | TIMESTAMPTZ | nullable |

#### `departments`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → organizations | |
| name | VARCHAR(255) | |
| created_at | TIMESTAMPTZ | |

#### `workflows`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → organizations | |
| created_by | UUID FK → users | |
| name | VARCHAR(255) | |
| description | TEXT | |
| status | VARCHAR(50) | draft, published, archived |
| active_version_id | UUID FK → workflow_versions | nullable |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

#### `workflow_versions`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| workflow_id | UUID FK → workflows | |
| version_number | INTEGER | auto-incremented per workflow |
| published_by | UUID FK → users | |
| published_at | TIMESTAMPTZ | |
| definition | JSONB | full graph snapshot (nodes + edges + config) |

#### `workflow_nodes`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| workflow_version_id | UUID FK → workflow_versions | |
| node_type | VARCHAR(100) | trigger.webhook, ai.extraction, action.http, etc. |
| label | VARCHAR(255) | |
| position_x | FLOAT | canvas position |
| position_y | FLOAT | canvas position |
| config | JSONB | node-specific configuration |

#### `workflow_edges`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| workflow_version_id | UUID FK → workflow_versions | |
| source_node_id | UUID FK → workflow_nodes | |
| target_node_id | UUID FK → workflow_nodes | |
| source_handle | VARCHAR(50) | e.g., "true", "false", "output" |
| target_handle | VARCHAR(50) | |

#### `workflow_runs`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → organizations | |
| workflow_id | UUID FK → workflows | |
| workflow_version_id | UUID FK → workflow_versions | |
| triggered_by | UUID FK → users | nullable for scheduled/webhook |
| trigger_type | VARCHAR(50) | manual, schedule, webhook, api |
| status | VARCHAR(50) | pending, running, completed, failed, cancelled |
| input_data | JSONB | trigger payload |
| output_data | JSONB | final node output |
| started_at | TIMESTAMPTZ | |
| completed_at | TIMESTAMPTZ | nullable |
| error_message | TEXT | nullable |

#### `execution_logs`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| workflow_run_id | UUID FK → workflow_runs | |
| node_id | UUID FK → workflow_nodes | |
| status | VARCHAR(50) | pending, running, completed, failed, skipped |
| attempt_number | INTEGER | 1-based |
| input_data | JSONB | |
| output_data | JSONB | |
| error_message | TEXT | nullable |
| started_at | TIMESTAMPTZ | |
| completed_at | TIMESTAMPTZ | nullable |
| duration_ms | INTEGER | |

#### `documents`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → organizations | |
| uploaded_by | UUID FK → users | |
| name | VARCHAR(500) | |
| mime_type | VARCHAR(100) | |
| size_bytes | BIGINT | |
| storage_key | TEXT | S3 object key |
| metadata | JSONB | extracted metadata |
| is_indexed | BOOLEAN | whether chunked and embedded |
| created_at | TIMESTAMPTZ | |

#### `document_chunks`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| document_id | UUID FK → documents | |
| organization_id | UUID FK → organizations | |
| chunk_index | INTEGER | |
| content | TEXT | raw text of the chunk |
| embedding | VECTOR(1536) | pgvector embedding |
| metadata | JSONB | page number, section, etc. |

#### `api_keys`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → organizations | |
| created_by | UUID FK → users | |
| label | VARCHAR(255) | |
| key_hash | VARCHAR(255) | bcrypt hash |
| key_prefix | VARCHAR(10) | first 8 chars shown in UI (e.g., `bpa_sk_x`) |
| scopes | JSONB | list of allowed permission scopes |
| last_used_at | TIMESTAMPTZ | nullable |
| expires_at | TIMESTAMPTZ | nullable |
| revoked_at | TIMESTAMPTZ | nullable |
| created_at | TIMESTAMPTZ | |

#### `notifications`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → organizations | |
| user_id | UUID FK → users | |
| type | VARCHAR(100) | workflow.failed, invitation.received, etc. |
| title | VARCHAR(500) | |
| body | TEXT | |
| metadata | JSONB | links, resource IDs |
| is_read | BOOLEAN | default false |
| created_at | TIMESTAMPTZ | |

#### `audit_logs`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → organizations | |
| user_id | UUID FK → users | nullable (system events) |
| action | VARCHAR(255) | e.g., workflow.published, member.invited |
| resource_type | VARCHAR(100) | |
| resource_id | UUID | |
| ip_address | INET | |
| user_agent | TEXT | |
| metadata | JSONB | before/after state for updates |
| created_at | TIMESTAMPTZ | append-only |

#### `ai_usage_logs`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → organizations | |
| workflow_run_id | UUID FK → workflow_runs | nullable (manual AI calls) |
| node_id | UUID FK → workflow_nodes | nullable |
| provider | VARCHAR(50) | openai, anthropic, ollama |
| model | VARCHAR(100) | e.g., gpt-4o, claude-sonnet-4-6 |
| operation | VARCHAR(50) | chat, embed, classify, extract |
| prompt_tokens | INTEGER | |
| completion_tokens | INTEGER | |
| total_tokens | INTEGER | |
| estimated_cost_usd | NUMERIC(10,6) | calculated at log time from current pricing |
| latency_ms | INTEGER | |
| created_at | TIMESTAMPTZ | |

### 10.4 Indexing Strategy

| Table | Index | Purpose |
|-------|-------|---------|
| org_members | (organization_id, user_id) UNIQUE | Membership lookup |
| workflows | (organization_id, status) | Filter workflows by org and status |
| workflow_runs | (organization_id, status, created_at DESC) | Dashboard and monitoring queries |
| execution_logs | (workflow_run_id) | Fetch all logs for a run |
| documents | (organization_id, created_at DESC) | Document library listing |
| document_chunks | HNSW index on embedding (pgvector) | Fast approximate nearest-neighbor search |
| notifications | (user_id, is_read, created_at DESC) | Notification feed |
| audit_logs | (organization_id, created_at DESC) | Audit trail paging |

### 10.5 Redis Usage

| Key Pattern | Purpose | TTL |
|-------------|---------|-----|
| `session:{user_id}:{session_id}` | Refresh token validity | 7 days |
| `rate_limit:auth:{ip}` | Authentication rate limiting | 15 minutes |
| `workflow_run:{run_id}:status` | Live execution status cache | 1 hour |
| `ws:channel:{organization_id}` | WebSocket pub/sub channel | None (in-memory) |
| `celery:*` | Celery task broker and result backend | Per-task TTL |
| `cache:analytics:{org_id}:{date}` | Analytics query cache | 5 minutes |

---

## 11. AI Requirements

### 11.1 AI Architecture Overview

The AI layer is built on LangChain for single-agent chains and LangGraph for multi-agent stateful workflows. The LLM provider is abstracted behind a configurable interface — switching between OpenAI, Anthropic Claude, or self-hosted models requires only an environment variable change.

```
Workflow Execution Engine
        │
        ▼
AI Node Dispatcher (LangChain)
        │
   ┌────┴────────────────┬──────────────────┬──────────────┐
   ▼                     ▼                  ▼              ▼
Document              Text              RAG             Multi-Agent
Extraction           Processing         Query           Orchestrator
(IDP Chain)          (Classify/         (pgvector +     (LangGraph)
                      Summarize)         LLM)
```

### 11.2 Intelligent Document Processing (IDP)

**Purpose:** Extract structured data from unstructured documents (PDFs, images, Word docs).

**Pipeline:**
1. File retrieved from object storage
2. OCR applied if the document is image-based or a scanned PDF (Tesseract / AWS Textract)
3. Text chunked and passed to the extraction LLM with a user-defined schema
4. LLM returns a JSON object conforming to the schema with a confidence score per field
5. Extracted data is validated against the schema using Pydantic
6. Low-confidence fields are flagged for human review

**AI Requirements:**
- Model: GPT-4o or Claude claude-sonnet-4-6 (configurable)
- Max document size: 50MB; max pages processed per call: 100 (chunked if larger)
- Confidence threshold: configurable per workflow (default: 0.8)
- Output: Validated JSON matching the user-defined extraction schema

### 11.3 Text Classification

**Purpose:** Classify unstructured text (emails, support tickets, documents) into user-defined categories.

**Pipeline:**
1. Input text is sent to the LLM with category definitions from the node configuration
2. LLM returns the predicted category and a confidence score
3. Result is passed to downstream Condition nodes for routing

**AI Requirements:**
- Model: GPT-4o-mini or Claude Haiku (cost-optimized for high-volume classification)
- Latency target: < 5 seconds per classification
- Output: `{ "category": "invoice", "confidence": 0.96, "reasoning": "..." }`

### 11.4 Text Summarization

**Purpose:** Generate concise summaries of long documents, email threads, or meeting notes.

**Pipeline:**
1. Input text is chunked using token-aware splitter if it exceeds context window
2. Map-reduce summarization applied for long documents
3. Final summary returned as plain text or structured format

**AI Requirements:**
- Supports Map-Reduce and Refine summarization strategies
- Configurable summary length (brief / standard / detailed)
- Model: GPT-4o or Claude claude-sonnet-4-6

### 11.5 RAG (Retrieval-Augmented Generation)

**Purpose:** Allow employees to query internal company documents and get accurate, grounded answers.

**Pipeline:**
1. Documents are uploaded and parsed into text chunks (512 token chunks, 50 token overlap)
2. Each chunk is embedded using `text-embedding-3-small` (1536 dimensions)
3. Embeddings are stored in `document_chunks` table with pgvector
4. At query time, the question is embedded using the same model
5. Cosine similarity search retrieves top-K relevant chunks (K=5 default, configurable)
6. Retrieved chunks and the user question are passed to the LLM as context
7. LLM generates a grounded answer with citations

**AI Requirements:**
- Embedding model: `text-embedding-3-small` (OpenAI) or `all-MiniLM-L6-v2` (local Sentence Transformers)
- Vector dimensions: 1536 (OpenAI) or 384 (local)
- Similarity threshold: 0.75 (chunks below this threshold are excluded)
- Maximum context: Top 5 chunks passed to LLM
- Citation format: Answer includes `[Source: Document Name, Page N]` references

### 11.6 AI Workflow Agent (Natural Language → Workflow)

**Purpose:** Accept a plain English description of a workflow and generate a valid workflow graph.

**Implementation:**
- System prompt includes the complete node type schema as JSON Schema
- LangChain structured output parser enforces the workflow graph format
- Generated graph is deserialized and rendered on the React Flow canvas
- User reviews and modifies before publishing — no automatic publishing

**AI Requirements:**
- Model: GPT-4o or Claude Opus (higher reasoning capability required)
- Output format: JSON conforming to workflow graph schema
- Validation: Pydantic validates the generated graph; invalid graphs return an error with explanation

### 11.7 Multi-Agent Automation (LangGraph)

**Purpose:** Enable complex tasks that require multiple specialized AI agents collaborating.

**Architecture (LangGraph):**
```python
StateGraph:
  Nodes:
    - coordinator: routes tasks to appropriate agents
    - document_reader: OCR + extraction
    - knowledge_retriever: RAG query
    - validator: checks extracted data against rules
    - report_generator: formats final output
  Edges:
    - coordinator → document_reader
    - document_reader → coordinator (with extracted data)
    - coordinator → validator
    - validator → coordinator (with validation result)
    - coordinator → report_generator
    - report_generator → END
  State:
    - shared TypedDict passed between all nodes
```

**AI Requirements:**
- Framework: LangGraph 0.2+
- State: Typed shared state dictionary passed between agents
- Human-in-the-loop: Optional interrupt point after validator for manager approval
- Max iterations: Configurable per workflow (default: 10 to prevent infinite loops)
- Agent tools: File read, database query, HTTP request, web search (configurable per agent)

### 11.8 AI Report Generation

**Purpose:** Generate periodic workflow performance reports and executive summaries.

**Inputs:**
- Aggregated execution metrics from the analytics service
- Optionally: sample execution logs for context

**Outputs:**
- Markdown report with sections: Summary, Key Metrics, Top Performing Workflows, Problem Areas, Recommendations
- Can be rendered as PDF and attached to notification emails

### 11.9 AI Token Management

| Metric | Tracked Per |
|--------|------------|
| Prompt tokens | Organization, workflow, model, date |
| Completion tokens | Organization, workflow, model, date |
| Total cost estimate | Organization, month |
| Requests | Organization, workflow, node type |

Token usage is logged to the `ai_usage_logs` table after each LLM call. Budget alerts notify Owners when monthly usage exceeds configurable thresholds.

### 11.10 Model Abstraction Layer

All LLM calls go through a `ModelProvider` interface:

```python
class ModelProvider(Protocol):
    def chat(self, messages: list[Message], **kwargs) -> str: ...
    def embed(self, text: str) -> list[float]: ...

# Implementations:
class OpenAIProvider(ModelProvider): ...
class AnthropicProvider(ModelProvider): ...
class LocalOllamaProvider(ModelProvider): ...
```

The active provider is configured via `LLM_PROVIDER` environment variable. No AI feature code references a specific provider directly.

---

## 12. Deployment

### 12.1 Environment Tiers

| Environment | Purpose | Infrastructure |
|-------------|---------|---------------|
| Development | Local developer machines | Docker Compose |
| Staging | Pre-production testing | Cloud VM or Railway/Render |
| Production | Live customer traffic | Cloud (AWS/GCP/Azure/DigitalOcean) |

### 12.2 Production Architecture

```
Internet
    │
    ▼
┌──────────────────────────────────────────┐
│            Nginx (Load Balancer)          │
│   SSL Termination │ Static File Serving   │
└───────────┬──────────────────┬───────────┘
            │                  │
            ▼                  ▼
┌─────────────────┐   ┌─────────────────────┐
│  Next.js        │   │  FastAPI             │
│  Frontend       │   │  (2+ instances)      │
│  (Static/SSR)   │   │  Port 8000           │
└─────────────────┘   └────────┬────────────┘
                               │
              ┌────────────────┼───────────────────┐
              ▼                ▼                   ▼
   ┌──────────────┐  ┌────────────────┐  ┌───────────────┐
   │  PostgreSQL  │  │   Redis        │  │   MinIO / S3  │
   │  Primary     │  │   (Queue +     │  │   Object      │
   │  + Standby   │  │    Cache +     │  │   Storage     │
   │  (Port 5432) │  │    PubSub)     │  │               │
   └──────────────┘  └────────────────┘  └───────────────┘
                               │
              ┌────────────────┘
              ▼
   ┌──────────────────────────┐
   │   Celery Workers          │
   │   (AI + Background Tasks) │
   │   (N instances, auto-     │
   │    scale based on queue)  │
   └──────────────────────────┘
              │
              ▼
   ┌──────────────────────────┐
   │   LLM Providers           │
   │   OpenAI / Anthropic API  │
   └──────────────────────────┘
```

### 12.3 Docker Compose (Development)

Services defined in `docker-compose.yml`:

| Service | Image | Ports |
|---------|-------|-------|
| `db` | postgres:16 | 5432 |
| `redis` | redis:7-alpine | 6379 |
| `minio` | minio/minio | 9000, 9001 |
| `api` | Custom (FastAPI) | 8000 |
| `worker` | Custom (Celery) | — |
| `frontend` | Custom (Next.js) | 3000 |
| `nginx` | nginx:alpine | 80, 443 |

### 12.4 CI/CD Pipeline (GitHub Actions)

```
Push to feature branch
        │
        ▼
┌─────────────────┐
│  lint + typecheck│  (ruff, mypy, ESLint, tsc)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Unit Tests      │  (pytest, Jest)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Integration     │  (pytest with real DB + Redis in Docker)
│  Tests           │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Build Docker    │
│  Images          │
└────────┬────────┘
         │
     PR Merge to main
         │
         ▼
┌─────────────────┐
│  Push to         │
│  Container       │
│  Registry        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Deploy to       │
│  Staging         │
└────────┬────────┘
         │
    Manual approval
         │
         ▼
┌─────────────────┐
│  Deploy to       │
│  Production      │
│  (rolling update)│
└─────────────────┘
```

### 12.5 Environment Variables

| Variable | Component | Description |
|----------|-----------|-------------|
| `DATABASE_URL` | API, Worker | PostgreSQL connection string |
| `REDIS_URL` | API, Worker | Redis connection string |
| `SECRET_KEY` | API | JWT signing secret (min 32 chars) |
| `ENCRYPTION_KEY` | API | AES-256 key for encrypting stored credentials |
| `S3_ENDPOINT_URL` | API, Worker | MinIO or S3 endpoint |
| `S3_BUCKET_NAME` | API, Worker | Object storage bucket |
| `AWS_ACCESS_KEY_ID` | API, Worker | S3/MinIO access key |
| `AWS_SECRET_ACCESS_KEY` | API, Worker | S3/MinIO secret key |
| `OPENAI_API_KEY` | Worker | OpenAI API key (platform default) |
| `ANTHROPIC_API_KEY` | Worker | Anthropic API key (platform default) |
| `LLM_PROVIDER` | Worker | `openai` / `anthropic` / `ollama` |
| `SMTP_HOST` | API | Email delivery host |
| `SMTP_PORT` | API | Email delivery port |
| `SMTP_USER` | API | Email SMTP username |
| `SMTP_PASSWORD` | API | Email SMTP password |
| `FRONTEND_URL` | API | Used in email links (e.g., `https://app.example.com`) |
| `GOOGLE_CLIENT_ID` | API | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | API | Google OAuth client secret |
| `CELERY_BROKER_URL` | Worker | Redis URL for Celery broker |
| `CELERY_RESULT_BACKEND` | Worker | Redis URL for result storage |

### 12.6 Scaling Strategy

| Component | Scaling Approach |
|-----------|-----------------|
| FastAPI | Horizontal — add stateless instances behind Nginx |
| Celery Workers | Horizontal — scale based on Redis queue depth |
| PostgreSQL | Vertical first; add read replicas for read-heavy queries |
| Redis | Redis Cluster for horizontal scaling |
| Object Storage | Inherently scalable (S3 / MinIO distributed mode) |
| Next.js Frontend | Served as static assets via CDN (Cloudfront / Cloudflare) |

---

## 13. Future Roadmap

### Phase 1 — MVP (Months 1–4)

Core platform that proves the value proposition end-to-end.

**Deliverables:**
- [ ] Email/password authentication with JWT and refresh tokens
- [ ] Google OAuth
- [ ] Organization creation, member invitations, RBAC
- [ ] Visual workflow builder (React Flow) with core node types
- [ ] Workflow versioning (save, publish, revert)
- [ ] Trigger types: Manual, Schedule, Webhook
- [ ] AI nodes: Document Extraction, Text Classification, AI Prompt
- [ ] File upload and storage (PDF, DOCX, XLSX, CSV, images)
- [ ] Asynchronous workflow execution via Celery
- [ ] Retry logic with exponential backoff
- [ ] Execution monitoring (status, logs per node)
- [ ] In-app and email notifications
- [ ] Basic analytics dashboard (execution counts, success rate, AI token usage)
- [ ] REST API with API key authentication
- [ ] OpenAPI documentation
- [ ] Docker Compose development environment
- [ ] GitHub Actions CI/CD pipeline

### Phase 2 — Growth (Months 5–8)

Expand AI capabilities, integrations, and team features.

**Deliverables:**
- [ ] RAG knowledge base (document indexing + natural language Q&A)
- [ ] Text summarization node
- [ ] AI Workflow Agent (natural language → workflow draft)
- [ ] Multi-agent workflows with LangGraph
- [ ] Human-in-the-loop review step for AI outputs
- [ ] Real-time execution updates via WebSocket
- [ ] Gmail integration (trigger on email received, send email action)
- [ ] Google Drive integration (upload, download, list)
- [ ] Slack integration (send message action)
- [ ] Workflow templates library
- [ ] Workflow import/export (JSON)
- [ ] Departments and department-scoped workflows
- [ ] Advanced analytics: time-series charts, per-user activity, failure analysis
- [ ] AI-generated weekly reports
- [ ] Subscription billing (Stripe integration)
- [ ] Usage quotas enforcement per tier
- [ ] Staging environment deployment

### Phase 3 — Scale (Months 9–18)

Enterprise readiness, additional integrations, and platform extensibility.

**Deliverables:**
- [ ] Microsoft OAuth (Teams, Outlook, OneDrive integration)
- [ ] Salesforce CRM integration
- [ ] HubSpot CRM integration
- [ ] SAP ERP connector
- [ ] Custom REST API node (generic HTTP action with auth configuration)
- [ ] Plugin / custom node SDK for developer extensibility
- [ ] Sub-workflows (reusable workflow blocks)
- [ ] Parallel branch execution in workflow engine
- [ ] Advanced RBAC: custom roles, field-level permissions
- [ ] Multi-language UI (i18n)
- [ ] Data residency controls (EU/US region selection)
- [ ] SOC 2 Type II compliance audit
- [ ] GDPR data export and right-to-erasure tooling
- [ ] SSO / SAML 2.0 for enterprise identity providers
- [ ] Kubernetes Helm chart for self-hosted deployment
- [ ] Prometheus + Grafana observability stack
- [ ] AI decision support: bottleneck detection, automation opportunity suggestions
- [ ] Custom report builder
- [ ] White-label offering for resellers

### Long-Term Vision (18+ Months)

- Marketplace for community-contributed workflow templates and custom nodes
- Voice-activated workflow triggering
- Mobile application for workflow monitoring and approvals
- Predictive analytics: forecast workflow failures before they occur
- Industry-specific solution packages (Legal, Healthcare, Finance, HR)
- On-premise / air-gapped deployment for regulated industries

---

*End of Software Requirements Specification v1.0.0*

*This document is a living specification. Changes are tracked in git history. All material changes require a version increment and review by the Architecture Team.*
