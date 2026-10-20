# FinTracker Architecture

| Status | Owner | Last reviewed | Applies to |
|---|---|---|---|
| Current | Van Vo | 2026-10-20 | main |

This document describes how FinTracker works at a high-level architecture: which services exist, what each service owns, how they talk to each other, how identity and data isolation work, and how the system is deployed to AWS.

It leaves out how a single service does its job: workflow steps, schemas, prompts and API payloads. Those live in each service's architecture doc and specs (see [Related documents](#11-related-documents)).

**Where does a detail belong?** If changing it touches only one service, it goes in that service's doc. If it touches two or more services, the security model, or the deployment, it goes here.

---

## 1. Overview

**What it does:** FinTracker turns a person's raw financial history into one clear picture. Users upload bank statements (PDF, phone screenshot, or CSV export). FinTracker extracts and categorizes the transactions, tracks spending against budgets, and explains the results with an AI-generated Financial Summary.

**Who it's for and why it matters:** retail users whose money is spread across several banks and cards, often locked in PDFs and exports that don't talk to each other. Today they reconcile it by hand or not at all. FinTracker gives them a single place to see where their money goes and whether they're on budget, without connecting bank credentials, and with an assistant that explains their numbers in plain language.

**Current scope:**
- Statement upload and import. Imported transactions arrive as *pending*; the user approves them before they count toward budgets and reports.
- Tabs: Dashboard, Transactions, Budgets, Statements (uploaded statements and their import status), Reports (including the AI Financial Summary), Accounts, Settings.
- The **Dashboard** is a glance at the current month; **Reports** explains completed periods and trends (D21).

**Status labels:** *Existing* means running today; *Proposed* means designed but not built. Phasing is in the [roadmap](roadmap.md).

---

## 2. Services

| Service | Status | Purpose | Owns | Workload type |
|---|---|---|---|---|
| User profile | Existing | Who the user is and what they're allowed to do | Users, Cognito `sub` → internal `userId` mapping, subscription tier, settings, savings goals, WebSocket connections | Synchronous, high-read, low-write |
| Ledger | Existing (runs locally; AWS deployment planned) | The single source of truth for money; serves the Dashboard tab | Accounts, categories, transactions, budgets and templates, bills, statement records (each linked to a `documentId`) | Synchronous, transactional, strict consistency |
| Data pipeline | Existing | Turns statement files into clean, pending transactions | Import job status, per-bank CSV column mappings | Asynchronous, retry-heavy, compute-intensive |
| Analytics | Existing (refactor) | Turns ledger history into metrics and detected patterns, with deterministic code, for the Reports tab and the Dashboard's spending pace | No data of its own; reads the Ledger's reporting views | Read-only, analytical |
| Document service | Proposed (replaces Upload intake). Statement files first; user documents later | Owns every user file from upload to deletion | Original files and file metadata: `documentId`, owner, type, name, size, hash, scan and upload status | Event-driven, short requests |
| Knowledge | Proposed. System help docs first (current focus); user documents later | Makes documents searchable, safely, per user | Text chunks and embeddings derived from documents, never the original files | Async ingestion plus fast retrieval |
| AI assistant | Proposed (current focus) | Runs chat and every LLM call in the app | Conversations, tool catalog, prompts, LLM cost and audit records, summary cache | Streaming, waits on slow LLM calls |

**Why each service is separate**

- **User profile:** identity is a dependency of every service and the responsibility of none. Owning the internal `userId` here keeps the rest of the system independent of the identity provider.
- **Ledger:** financial records need strict consistency and a narrow, guarded write path. Statement imports enter only through one internal, signed endpoint.
- **Data pipeline:** parsing, deduplication and categorization are messy background work. Keeping them out of the Ledger means a failed or slow import never affects the system of record.
- **Analytics:** analysis across periods (trends, comparisons, detectors) is read-heavy and changes for different reasons than the system of record, so it stays out of the Ledger's code and write path.
- **Document service:** every file needs the same controls on the way in (limits, malware scan), on the way out (ownership check, short-lived link, audit) and at the end (deletion). It stores, scans, routes, serves and deletes files, and never interprets their contents.
- **Knowledge:** it is the single owner of the vector store, so the per-user filter is written once instead of in every caller.
- **AI assistant:** chat depends on Ledger, Analytics, User profile and Knowledge, so it sits at the edge of the dependency graph. It also has a different runtime profile, and keeps all AI risk (prompt injection, model upgrades, evaluation, LLM cost) in one place.

---

## 3. High-level architecture

![FinTracker high-level architecture](images/fintracker-high-level.svg)

**Workflow:**

- Every user request enters through the **gateway**, which verifies the token and attaches the internal `userId`. Chat streams through its own REST API, which runs the same identity authorizer (D19).
- Services never share a database. They talk in two ways only: **internal requests** (blue), when the caller needs an answer now, and **events** (orange), when something happened that others may react to. The internal-request lane lists every caller → target pair.
- The **AI assistant** reaches data only by calling other services as tools. It never reads a database itself.
- **Analytics** is the one service that reads another service's store: only the Ledger's reporting views, and only read-only (D22).
- Files move **directly between the client and file storage**. They never pass through a service.

---

## 4. Concepts of Operation (CONOPS)

The topics follow one request into the system, then the system's life: **Enter → Trust → Flow → Store → Protect → Recover → Observe**. Each topic builds on the one before it.

### 4.1 Enter: how do users and systems get in?

Two kinds of entry exist, and each needs its own trust rule (4.2):

**User entry points:** a person starts the work, and every request carries their token.

| Actor | Entry point | Notes |
|---|---|---|
| End user (web app) | Gateway | All app requests, including the AI summary |
| End user (web app) | Chat streaming API (REST, response streaming) | Long-lived streamed responses; same identity authorizer as the gateway (D19) |
| End user (web app) | File storage, by presigned URL | Upload and download only, after a Document service request |

**System triggers:** something other than a user starts the work, so there is no user token.

| Trigger | Starts work in | Notes |
|---|---|---|
| Scheduler | Ledger, Data pipeline, outbox relay | Monthly budget period close; Ledger outbox relay; bank sync (later phase). Summaries are generated on demand, not precomputed |
| Storage event (file uploaded) | Data pipeline | Starts statement import today; replaced by `UploadAccepted` when the Document service ships |
| CI pipeline | Knowledge | Re-indexes system help docs on merge *(proposed)*; see [Update a help doc](#5-cross-service-flows) |
| Identity provider | User profile | Sign-up confirmation hook creates the internal user |

### 4.2 Trust: who is the caller, and what may they do?

- **User identity:**
  - The client signs in with Cognito (Hosted UI) and sends its access token on every call.
  - The gateway runs the User profile **identity authorizer**. It verifies the token, maps `sub` to the internal `userId`, and attaches the `userId`, subscription tier, timezone and primary currency (D23). Results are cached briefly.
  - Services take identity only from that attached value, never from the request body, query string, path, or an LLM tool argument.
  - No user entry point bypasses the identity authorizer. The chat streaming API runs it too (D19).
- **System triggers:** each runs as its own IAM role, and only the expected source may invoke it. Examples: only Cognito may call the sign-up hook, and only CI's deploy role may write system help docs. A scheduled job that works on many users sets each user's context explicitly, one user at a time; it never reads "all rows" through a bypass.
- **Authorization:** ownership of the resource, plus subscription tier for limits. The tier is attached today but not yet enforced anywhere.
- **Service identity:** a service calls another with a request signed by its own IAM role (SigV4). The receiver checks the caller against an allow-list. A `userId` passed between services is trusted only on such a call.
- **Tenant isolation is enforced in the data layer, not only in handlers:**
  - **Ledger database:** PostgreSQL Row-Level Security on every user-owned table, forced even for the table owner. Every child table carries its own `user_id`, so each policy is a single equality check ([ADR-001](architectural_decision_records/ADR-001-user-id-denormalization.md), [ADR-002](architectural_decision_records/ADR-002-rls-and-ownership-scoped-queries.md)).
  - **How each caller sets the user context:**
    - Ledger: sets `app.current_user_id` before every query and resets it after.
    - Data API callers (Analytics, Knowledge): set it inside the same transaction as the query, because each Data API call is otherwise its own session.
    - Analytics may read only the Ledger's reporting views, which run as the caller (`security_invoker`), so RLS still applies (D22).
    - A session with no user set sees zero rows.
  - **Application layer:** repository queries are scoped by owner as well (`…ByIdAndUserId`).
  - **DynamoDB:** `userId` is the partition key, with `dynamodb:LeadingKeys` where tables are accessed per user.
  - **File storage:** object keys are prefixed with `userId`.
- **Cross-tenant requests return 404, not 403**, so the app never confirms that another user's resource exists.

### 4.3 Flow: how does work move between services?

| | Internal request | Event |
|---|---|---|
| Use when | The caller needs the answer now | Something happened and others may react |
| Mechanism | API Gateway HTTP API with IAM authorization, one per receiving service (D18) | EventBridge bus, with an SQS queue and dead-letter queue per consumer |
| Proves the caller | SigV4 signature plus the caller allow-list | Only the producer's role may publish its event types |
| Carries the user | Verified user context (`userId`, tier, timezone, primary currency) forwarded with the request | `userId` in the event body |

**Default to events.** Internal requests are used only where the diagram shows them: AI assistant tool calls, and the Data pipeline's ownership check and import into the Ledger. User settings travel in the verified context, so no service looks them up at request time (D23).

**AI tools are internal requests.** The AI assistant holds the tool *definitions*; the tool *logic* stays in the service that owns the data. The user is fixed from the authenticated request; no tool takes a user ID the model could choose. Each feature gets its own tool subset.

| Event | Producer | Consumers |
|---|---|---|
| `UploadAccepted(documentId, type)` *(proposed)* | Document service, after the scan passes | Data pipeline (`statement`); Knowledge for user documents *(later)* |
| `StatementDeleted(documentId)` *(proposed)* | Ledger, through its outbox | Document service |
| `DocumentDeleted(documentId)` *(later)* | Document service | Knowledge |
| `UserAccountDeleted(userId)` | User profile | Every service that stores user data |
| `UserDataDeleted(userId, service)` *(proposed)* | Each service, after deleting its share | User profile |

**Delivery is at-least-once, so every consumer is idempotent.** For example, the Ledger skips duplicate import rows by statement and row fingerprint.

**The Ledger publishes through a transactional outbox** ([ADR-009](architectural_decision_records/ADR-009-ledger-event-publishing-outbox.md)):
- The event row is written in the same database transaction as the change, so an event exists if and only if the change committed.
- A relay Lambda outside the VPC publishes pending rows to EventBridge on a configurable schedule (6.1).
- The Ledger itself never calls EventBridge, so it needs no NAT or endpoint in dev.

### 4.4 Store: where does data live, who owns it, and when does it end?

- **One owner per data store.** The only exception is Analytics, which reads the Ledger's reporting views through a read-only role (D22).
- **Stores:**

| Store | Owner | Holds |
|---|---|---|
| Aurora PostgreSQL, `ledger` database | Ledger | Accounts, transactions, budgets, bills, statement records |
| Aurora PostgreSQL, `knowledge` database (pgvector) | Knowledge | Chunks and embeddings |
| DynamoDB, tables per service | User profile, Data pipeline, Document service, AI assistant | Each service's own records |
| S3, quarantine and clean buckets | Document service | Original files, keyed by `userId` |

- **A statement has two owners, split by meaning:**
  - The Document service owns the **file** (bytes, name, type, hash, scan status), identified by `documentId`.
  - The Ledger owns what it **means**: account, period, import status, and the transactions it produced.
  - The Ledger's record stores the `documentId`, never a storage location. Only the Document service knows where a file is.
- **File lifecycle:**
  1. **Upload:** limits are checked first, then the file goes to quarantine by presigned URL.
  2. **Accept:** the file is scanned, moved to the clean bucket, and `UploadAccepted` is published.
  3. **Download:** an ownership check, then a short-lived link to the clean bucket.
  4. **Delete:**
     - A statement's deletion starts in the Ledger, because removing transactions is the consequential part.
     - A user document starts in the Document service *(later)*.
- **Routing rule:** the user chooses the document type at upload. Automatic classification is only a sanity check, so a statement never becomes search text.
- **Account closure and retention** (D15):
  1. **Grace period, 30 days:**
     - The account is disabled and its data hidden, but nothing is deleted yet.
     - The user can reactivate during this window.
  2. **Hard deletion, within 7 days after the grace period ends:**
     - User profile publishes `UserAccountDeleted`. Every service deletes its own share and no one else's, then reports `UserDataDeleted`.
     - The whole process stays under the 45-day response window of state privacy laws.
  3. **Backups and file versions expire on their own schedule:**
     - Aurora backups: 14 days in prod.
     - DynamoDB point-in-time recovery: up to 35 days.
     - S3 noncurrent versions: 7 days.

     This is disclosed in the privacy policy.
  4. **What is kept after deletion:**
     - No financial content: no statements, transactions or documents.
     - Kept: a minimal deletion record (pseudonymous user ID, request date, completion date) for 24 months, as evidence the request was honored.
     - Kept: security audit logs for their normal retention period.
     - Kept later: billing records, once paid plans exist.
  5. **Legal hold:** if FinTracker receives a litigation hold or legal order, deletion for the affected users pauses until it is lifted.
  6. **Inactive accounts:** customer data is disposed of no later than two years after last use, unless still needed for the service (FTC Safeguards Rule).

### 4.5 Protect: what guards the data beyond identity?

- **Encryption:** TLS in transit, and encryption at rest everywhere (D13).
  - **Prod:** customer-managed KMS keys, split by data type (documents, database, key-value tables, logs). Each key policy allows only the owning service's role to decrypt, and CloudTrail records every use.
  - **Dev:** free AWS-managed or default keys while it holds only the owner's data. It switches to customer-managed keys before invited testers arrive (6.1 stage presets).
  - Both kinds give the same encryption strength and CloudTrail logging. A customer-managed key adds a key policy as a second lock and can be disabled.
  - Keys don't separate users from each other; access control does (4.2).
- **Files:**
  - Every upload is scanned before any service processes it.
  - Downloads come only from the clean bucket, after an ownership check, through a link that expires in about 5 minutes and forces a download. Each download is audit-logged.
  - Ownership at ingestion is confirmed with the Ledger, never read from file metadata.
- **AI:**
  - Only the AI assistant calls an LLM. Analytics computes every number with deterministic code.
  - Questions about the user's numbers are answered by Ledger and Analytics tools. Document search is for text only.
  - Retrieved text is treated as data, never as instructions. Tools are read-only by default.
  - Financial Summary: only an allow-listed facts payload reaches the model, and output is validated against the facts.
  - Knowledge filters every search by owner and re-checks each result. Isolation tests run in CI.
- **Privacy:**
  - Account numbers, SSNs and similar identifiers are redacted before chunking and embedding.
  - Embeddings get the same protection and deletion as their source text.
  - A user's documents are used only for that user's chat *(later)*. They are never put in a shared index, and never used for training or evaluation without opt-in.
- **Logging:** raw prompts, retrieved document text and model responses are never written to logs; traces are redacted.

### 4.6 Recover: what happens when something fails?

- **Events:**
  - Each consumer has its own queue and dead-letter queue. A failing consumer retries without affecting others, and dead-lettered messages can be replayed once fixed.
  - Ledger events wait safely in the outbox until the relay runs. A paused or failed relay delays them, but never loses them.
- **Statement import:** Step Functions retries each stage and records job status, so the Statements tab shows a failed import instead of losing it. A CSV import pauses until the user confirms the column mapping.
- **AI:**
  - If the LLM fails or a cost limit is reached, the Financial Summary returns a facts-only fallback with the reason. Cost limits never fail open.
  - Report numbers come from Analytics and render before the AI text, so the Reports tab works without the AI assistant.
- **Isolation of failures:** chat, documents and analytics can be down without affecting the Ledger's read and write paths. The Dashboard keeps working without Analytics; only its spending-pace card fails (D21).
- **Cold resume (dev):** Aurora can take about 15 seconds to resume after auto-pause, or 30 seconds or more after a day. Clients and Data API calls use timeouts above that and retry.
- **Backups and recovery targets** (D16, proposed). RPO is how much recent data can be lost; RTO is how long recovery may take.

| Scenario | Prod RPO | Prod RTO | How | Dev |
|---|---|---|---|---|
| AZ failure | ~0 | under 5 minutes | Aurora reader in a second AZ takes over; Fargate tasks in 2 AZs | Best effort (single AZ) |
| Bad deploy or data corruption | under 5 minutes | under 1 hour | Aurora point-in-time restore (14 days); DynamoDB point-in-time recovery; S3 versioning | 24 hours / best effort (1-day backups) |
| Region outage | 24 hours | 24 hours | Restore from backups copied to a second region *(later, before paying customers)* | Not covered |
| Rebuildable data (embeddings, analytics caches) | n/a | Rebuild | Re-index from source documents; recompute from the Ledger | Same |

### 4.7 Observe: how do we know it works and what it costs?

![FinTracker centralized logging, tracing and audit](images/fintracker-observability.svg)

All logs, metrics, traces and audit events from every service land in CloudWatch, so one console answers "what happened to this request?" across services (D20). Dev runs all of it in the dev account today. Prod later adds a monitoring and log-archive account.

- **One trace ID per request:**
  - The first service a request reaches starts a trace ID. Internal requests pass it in the `traceparent` header, and events carry it in their trace header.
  - Every log line, metric and span includes `service` and `trace_id`. One Logs Insights query on a `trace_id` returns every service's lines for that request.
  - The trace starts in the service, not the gateway: HTTP APIs can't start X-Ray traces. The chat REST API can.
- **How each service emits telemetry:**

  | Signal | Python services | Ledger (Java) | Destination |
  |---|---|---|---|
  | Logs | Powertools Logger, JSON to stdout | Logback JSON encoder to stdout | CloudWatch Logs, one log group per service |
  | Metrics | Powertools Metrics | Micrometer | CloudWatch metrics |
  | Traces | OpenTelemetry (ADOT Lambda layer) | OpenTelemetry Spring Boot starter | X-Ray traces |
  | Trace ID in logs | OpenTelemetry trace context | OpenTelemetry trace context (MDC) | — |

  - Logs go to stdout rather than through an OpenTelemetry log exporter: Lambda ships stdout to CloudWatch with no extra code, and lines already written survive a crash or timeout.
  - The X-Ray SDKs reach end of support in February 2027, so traces use OpenTelemetry, not Powertools Tracer.
- **Audit:**
  - **Application audit events** record who did what to which record: sign-in, statement deleted, file downloaded, account closed, LLM call. Every service writes them through one shared `audit(action, actor, resource, outcome)` helper to the `/fintracker/audit` log group, which is kept longer than operational logs.
  - Service-owned audit records stay where they are, because they're part of features: LLM audit records in the AI assistant, the download audit log in the Document service, and deletion records in User profile. Each also emits an audit event, so all of them can be searched in one place.
  - **AWS account activity:** a CloudTrail trail writes every AWS API call to an S3 bucket.
  - **Prod (later):** audit events and an organization CloudTrail are copied to an S3 archive with Object Lock in a separate log-archive account. Workload accounts can write to it but never read or delete it.
  - Logs, traces and audit events never contain financial values, raw prompts or document text (4.5).
- **Investigating an incident:**
  1. An alarm fires and SNS sends an email or phone push.
  2. The service's dashboard shows when it started and which metric moved.
  3. The trace map shows the failing or slowest hop.
  4. Logs Insights shows every service's lines, and the audit events, for that `trace_id`.
  5. A GitHub issue records the timeline, trace IDs and fix.
- **Performance tuning:** per-service dashboards track latency (median and slowest 1–5% of requests), errors, throttles, Lambda cold starts, Aurora capacity and pauses, and LLM tokens and cost per feature.
- **Cost guards:**
  - AWS Budgets alerts.
  - Per-user and app-wide daily LLM limits.
  - API throttling.
  - In dev, reserved concurrency on the AI Lambda.
- **Deletion tracking:** User profile records `UserDataDeleted` from every service. An alarm fires if hard deletion isn't complete within 7 days after the grace period ends *(proposed)*.
- **Outbox health:** an alarm on the age of the oldest unpublished outbox row, active whenever the relay is enabled.

---

## 5. Cross-service flows

One line per hop between services. The steps inside a service are in that service's doc.

### Upload a bank statement (today)

*Relies on: Enter, Trust, Flow, Store*

1. Client → Ledger: create the statement record (account ownership and duplicate checks) and get an upload URL.
2. Client → S3: upload the file.
3. S3 event → Data pipeline: confirm the owner with the Ledger.
4. Data pipeline → Ledger: one signed import call per statement. Rows arrive as pending.
5. Client polls the Data pipeline's job status; the user approves rows in the Transactions tab.

### Upload a bank statement (with the Document service, proposed)

*Relies on: Enter, Trust, Flow, Store, Protect*

1. Client → Ledger: create the statement record.
2. Client → Document service: get an upload URL for that statement; upload to quarantine.
3. Malware scan → Document service: on pass, move to the clean bucket and publish `UploadAccepted(type=statement)`.
4. Data pipeline consumes the event, confirms the owner with the Ledger, and imports pending rows.

### Download a statement or document *(proposed)*

*Relies on: Trust, Store, Protect, Observe*

1. Client → Document service: request a download for a `documentId`.
2. Document service: check ownership, write an audit record, return a short-lived link.
3. Client → S3: download from the clean bucket.

### Delete a statement *(proposed)*

*Relies on: Trust, Flow, Store*

1. Client → Ledger: delete the statement. In one database transaction, the Ledger removes its transactions and record and writes `StatementDeleted` to its outbox.
2. Outbox relay → EventBridge: publishes the event on its next run.
3. Document service deletes the file and all its versions.

### Delete user document *(later)*

*Relies on: Trust, Flow, Store*

1. Client → Document service: delete the document. It deletes the file and publishes `DocumentDeleted`.
2. Knowledge deletes the chunks and embeddings derived from it.

### Open the Dashboard

*Relies on: Enter, Trust, Recover*

1. Client → gateway: the identity authorizer attaches `userId`, timezone and primary currency.
2. Client → Ledger, in parallel: data-through date and pending count, summary cards, budget alerts, this month's bills, recent transactions. The Ledger resolves the current month in the user's timezone.
3. Client → Analytics: spending pace, loaded separately so a failure affects only that card.

### Open the Financial Summary

*Relies on: Trust, Flow, Protect, Recover*

1. Client → Analytics: periods and facts (numbers render first).
2. Client → AI assistant: summary for the period.
3. AI assistant → Analytics: the facts payload for the authenticated user. The assistant then checks its cache and cost limits, calls the LLM with the facts only, and validates the answer or returns a facts-only fallback.

### Ask the chat a question *(proposed)*

*Relies on: Enter, Trust, Flow, Protect*

1. Client → chat streaming API (identity authorizer) → AI assistant.
2. AI assistant → Knowledge (`retrieve(scope=system)`; `scope=mine` *later*), Ledger and Analytics, as tools. Each call is signed and carries the user.
3. AI assistant → LLM, then streams the answer with sources back to the client.

### Update a help doc *(proposed)*

*Relies on: Enter, Store*

1. A developer merges a doc change in Git.
2. CI (assuming a deploy role through OIDC) → Knowledge's system-docs storage: uploads the changed and deleted files.
3. The storage event starts Knowledge ingestion:
   - Each doc is chunked, embedded and written with `scope = system`.
   - Docs are keyed by path and content hash, so re-running a merge is harmless.
   - The doc's previous chunks are replaced, and deleted docs lose their chunks.

### Delete an account

*Relies on: Trust, Flow, Store, Observe*

1. User closes the account → User profile disables it. The 30-day grace period starts and the user can still reactivate.
2. After the grace period, User profile deletes its records and publishes `UserAccountDeleted`.
3. Every service holding user data deletes its own share:
   - Ledger: its records.
   - Data pipeline: job records and mappings.
   - Document service: every file under the user's prefix, all versions, and its metadata.
   - Knowledge: chunks and embeddings.
   - AI assistant: conversations and summary data.

   *Today only the summary data has a handler.*
4. Each service publishes `UserDataDeleted`. User profile records when all of them have finished: within 7 days, or the alarm fires.

---

## 6. Deployment

### 6.1 Environments and what differs between them

| Environment | AWS account | `profile` | Who uses it |
|---|---|---|---|
| Demo | FinTracker-dev | `dev` | The developer, a test user for multi-tenant checks, and a few invited testers |
| Production | FinTracker-prod | `prod` | Customers |

Demo can hold real statements from invited testers, so it keeps the full security model: Cognito MFA, CloudTrail, backups, malware scanning, RLS and IAM. Experiments belong in local development (SAM, Testcontainers).

**Rule:** `profile` changes capacity, availability, the network perimeter, cost guards and defense-in-depth layers (WAF, key management). It never changes application code, the data access path, or the core security model: identity, IAM, Row-Level Security, encryption, MFA, audit logging and malware scanning are the same in both.

| Setting | `dev` | `prod` |
|---|---|---|
| Aurora capacity | min 0 ACU, auto-pause after 5 min (the minimum), so the DB sleeps soon after the last request | min 0.5 ACU, always on |
| Aurora availability | single writer | writer + reader in 2 AZs, deletion protection |
| Aurora backups | 1 day | 14 days |
| Aurora `idle_session_timeout` | 60 s, so idle Lambda JDBC sessions don't keep the DB awake | default |
| Ledger compute *(planned; runs locally today)* | Lambda in VPC, SnapStart | ECS Fargate, 2 tasks across 2 AZs; API Gateway reaches it through a VPC link to an internal load balancer |
| AI assistant compute | Lambda (response streaming) behind the chat REST API | ECS Fargate, 2 tasks, behind an internal ALB; the chat REST API reaches it through a VPC link |
| VPC egress | none: no NAT, no interface endpoints | NAT gateway + S3/DynamoDB gateway endpoints |
| WAF | off | CloudFront and the chat REST API |
| S3 versioning (document buckets) | off | on; noncurrent versions expire after 7 days |
| DynamoDB point-in-time recovery | off | on |
| Encryption keys | AWS-managed or default keys while dev holds only the owner's data; switch to customer-managed before invited testers (see stage presets) | customer-managed KMS keys |
| Outbox relay schedule | `disabled` by default: events wait in the outbox at no cost. Set `rate(1 minute)` while testing deletions, `rate(1 hour)` when invited testers are active. The relay can also be invoked once by hand. Every run wakes Aurora, so a frequent schedule keeps it awake | `rate(1 minute)` |
| Log retention | 7 days | 90 days |
| Audit log group retention | 1 year | 2 years, plus the immutable archive |
| Trace sampling | every request (stays inside X-Ray's free 100,000 traces a month) | sampled, about 5% plus at least one request a second |
| Monitoring and log archive | the dev account's own CloudWatch and CloudTrail bucket | monitoring account linked to dev and prod; audit events and CloudTrail copied to an S3 archive with Object Lock |
| Cost guards | Budgets at $10/$25, AI Lambda reserved concurrency, per-user daily token cap, API throttle ~10 rps, chat API throttle ~2 rps | Budgets, per-user and app-wide LLM limits, production throttles |
| Cognito sign-up | invite-only (admin-created users) | self sign-up |

**How the setting is applied:** each Terraform environment folder sets `profile = "dev"` or `"prod"`, and modules read one settings map:

```hcl
locals {
  settings = {
    dev  = { aurora_min_acu = 0,   aurora_pause_seconds = 300, aurora_reader = false, ledger_compute = "lambda",  ai_compute = "lambda",  nat = false, waf = false, cmk = false, s3_versioning = false, dynamodb_pitr = false, outbox_relay_schedule = "disabled",        log_days = 7,  audit_log_days = 365, trace_sample_rate = 1.0,  log_archive = false }
    prod = { aurora_min_acu = 0.5, aurora_pause_seconds = null, aurora_reader = true,  ledger_compute = "fargate", ai_compute = "fargate", nat = true,  waf = true,  cmk = true,  s3_versioning = true,  dynamodb_pitr = true,  outbox_relay_schedule = "rate(1 minute)",  log_days = 90, audit_log_days = 731, trace_sample_rate = 0.05, log_archive = true  }
  }[var.profile]

  # One-off overrides for the current stage, e.g. -var 'outbox_relay_schedule=rate(1 minute)' or -var 'cmk=true'
  outbox_relay_schedule = coalesce(var.outbox_relay_schedule, local.settings.outbox_relay_schedule)
  cmk                   = coalesce(var.cmk, local.settings.cmk)
}
```

**Dev stage presets.** Dev changes over time. These are the settings to use at each stage:

| Dev stage | Outbox relay | Encryption keys | Aurora | Cognito | Why |
|---|---|---|---|---|---|
| Solo development (now) | `disabled`; invoke by hand when needed | AWS-managed / default (free) | auto-pause 5 min | invite-only | Lowest idle cost; deletions are rare and only for testing; only the owner's data is at risk |
| Testing deletions or events | `rate(1 minute)`, reverted afterwards | AWS-managed / default | auto-pause 5 min | invite-only | See events within a minute; costs only while it runs |
| Invited testers active | `rate(1 hour)` | **customer-managed** (`cmk = true`), switched *before* the first invite | auto-pause 5 min | invite-only | Real tester data gets the same key controls as prod; deletions complete within an hour; about $4/month for keys plus $3–4/month for hourly Aurora wake-ups |
| Ready for customers | Deploy the `prod` profile | customer-managed | — | self sign-up | Move to prod rather than stretching dev |

**Switching dev to customer-managed keys** takes about an hour while dev holds only the owner's data, mostly waiting on AWS:
1. Snapshot Aurora.
2. Copy the snapshot with the new key.
3. Restore it as a new cluster.
4. Repoint the Ledger and the Data API callers.

Alternatively, recreate the cluster, run the migrations and re-upload statements. Changing the key in Terraform replaces the cluster, so restore from the snapshot or accept an empty database. DynamoDB, S3 and Secrets Manager switch in place.

A new difference between environments needs a key here and a row in the table above. If a difference isn't in both places, it shouldn't exist.

### 6.2 Dev deployment

![FinTracker dev deployment](images/fintracker-aws-dev.svg)

**How it runs**

- CloudFront serves the Angular app. API Gateway runs the identity authorizer and routes to Lambda functions for every service.
- Chat streams through the chat REST API, which runs the identity authorizer and then invokes the AI assistant's Lambda in streaming mode (D19). Junk requests never reach the Lambda, and the stage throttle caps the bill.
- Each service that receives internal requests (Analytics, Ledger, Knowledge, User profile) has its own internal HTTP API with IAM auth, integrated directly with its Lambda (D18). Callers find the URLs in SSM Parameter Store.
- Analytics and Knowledge reach Aurora through the RDS Data API over HTTPS. The Ledger connects over JDBC from inside the VPC, using an IAM database auth token it generates locally.
- Events flow through EventBridge to per-consumer SQS queues. The Data pipeline and Knowledge ingestion run as Step Functions workflows.
- The Ledger writes its events to an outbox table. The relay Lambda, outside the VPC, publishes them when its schedule is enabled.
- Uploads go straight to the S3 quarantine bucket. GuardDuty scans them before anything is processed.

**Key decisions for this environment**

- **Scale to zero.** Aurora auto-pauses and every service runs on Lambda, so idle cost is about $3–15/month plus Bedrock and Textract usage (add about $4 for customer-managed keys once invited testers arrive). The trade-off is cold starts.
- **Only the Ledger and Aurora are in the VPC.** The Ledger needs no NAT or endpoints:
  - It generates its database token locally.
  - It publishes events through the outbox instead of calling EventBridge.
- **The same Spring Boot JAR runs on Lambda**, through an adapter with SnapStart *(planned; adapter choice open, 7.2)*.
- **Same core security as prod:** MFA, CloudTrail, malware scanning, Row-Level Security and least-privilege IAM. Keys are AWS-managed while only the owner's data is present, and switch to customer-managed before invited testers' real statements arrive.

### 6.3 Prod deployment

![FinTracker prod deployment](images/fintracker-aws-prod.svg)

**How it runs**

- The request path matches dev, with two exceptions:
  - API Gateway runs the identity authorizer, then reaches the Ledger on Fargate through a VPC link to an **internal** load balancer.
    - The load balancer is not reachable from the internet, and its security group accepts only the VPC link.
    - That's why the Ledger can trust the `userId` header.
  - Chat streams through the chat REST API, with WAF, which reaches the AI assistant on Fargate through a VPC link to an **internal** ALB (D19). There is no public ALB.
- Fargate tasks run in private subnets across two AZs. Egress goes through a NAT gateway, which is needed to reach the regional internal API and, later, Teller.io. S3 and DynamoDB traffic uses gateway endpoints.
- Aurora runs a writer and a reader in different AZs, with deletion protection.
- WAF protects CloudFront and the chat REST API. DynamoDB point-in-time recovery and S3 versioning are on.

**Key decisions for this environment**

- **Always-on where latency matters:** a warm Ledger connection pool, and chat without cold starts or a 15-minute limit.
- **The internal APIs stay regional HTTP APIs with IAM auth, one per receiving service**, as in dev (D7, D18). Only `ledger-internal` uses the VPC link; the others integrate with Lambda.
- Rough fixed cost: $200–300/month before usage.

### 6.4 Build and release

- **IaC:** Terraform reusable modules plus one folder per environment. The Data pipeline is migrated first and the other services follow. The earlier CDK stack is kept for reference only.
- **CI/CD:** GitHub Actions deploys the `dev` profile from pull requests and `prod` on a release tag.
- **Migrations:** Flyway (`ledger`) and the `knowledge` schema run as a separate deploy step before the new service version, never at startup. The Ledger runs on Lambda in dev, where startup migrations would run on every cold start.
- **Migration role:** migrations connect as the schema owner role. They are ordered so RLS is enabled last ([ADR-002](architectural_decision_records/ADR-002-rls-and-ownership-scoped-queries.md)).

---

## 7. Architectural decisions

A decision is listed here when at least two of these are true:
- it is expensive to reverse
- it affects more than one service, or the security, compliance or cost model
- a real alternative existed
- a new developer might otherwise "fix" it by accident

Decisions with a linked ADR have a full record of context, alternatives and consequences. The rest are fully captured by their row. New ADRs follow [`docs/templates/adr-template.md`](../templates/adr-template.md), which compares the options in one short trade-off table on the few dimensions that decided it.

### 7.1 Decisions

| # | Decision | Choice | Alternatives considered | Why | Revisit when | Status | ADR |
|---|---|---|---|---|---|---|---|
| D1 | Ledger ownership column | Denormalize `user_id` onto every Ledger child table, filled by a trigger from the parent row | Join through parent tables; add it to `transactions` only | RLS stays a single equality check on the hottest table, and account deletion is one `DELETE … WHERE user_id = ?` per table | Never; `user_id` is immutable | Accepted (Ledger scope) | [ADR-001](architectural_decision_records/ADR-001-user-id-denormalization.md) |
| D2 | Tenant isolation | PostgreSQL RLS forced on every table, plus owner-scoped repository queries; cross-tenant requests return 404 | Spring method security; `SET LOCAL` inside transactions; a `DataSource` wrapper | Two independent layers: a missed check in code is still blocked by the database | Per-query `SET`/`RESET` latency shows up in profiling (move to `SET LOCAL`) | Accepted | [ADR-002](architectural_decision_records/ADR-002-rls-and-ownership-scoped-queries.md) |
| D3 | Internal user ID | User profile maps Cognito `sub` → `userId` | Use `sub` everywhere | Avoids identity-provider lock-in | Changing identity provider | Accepted | — |
| D4 | Who calls the LLM | Only the AI assistant; Analytics is deterministic | LLM calls inside Analytics | One place for prompts, guardrails, evaluation and LLM cost; numbers stay testable | Never, without a new record | Accepted | — |
| D5 | Database access path | RDS Data API for Python services; JDBC with IAM DB auth for the Ledger; same in both profiles | RDS Proxy for everything; Data API for everything | Python Lambdas avoid the VPC and connection pools, and the Ledger keeps jOOQ, Flyway and native RLS. RDS Proxy costs 8 ACUs minimum and stops Aurora from pausing | Analytics load affects Ledger latency (move Analytics to a reader over JDBC) | Accepted | [ADR-003](architectural_decision_records/ADR-003-database-access-path.md) |
| D6 | Async messaging | EventBridge bus, one SQS queue and DLQ per consumer | SNS fan-out; direct SQS | Routing by event type, plus per-consumer retries and isolation | Ordered, replayable streams needed | Accepted | — |
| D7 | Internal API | Regional API Gateway HTTP API with IAM auth, in both profiles | Private REST API with a VPC endpoint | SigV4 plus allow-lists already prove the caller. A private API would require REST APIs and put every calling Lambda in a VPC | A compliance requirement mandates network isolation for internal traffic | Accepted | [ADR-004](architectural_decision_records/ADR-004-internal-api-regional-iam.md) |
| D8 | File ownership | One Document service owns every file from upload to deletion; the Ledger owns a statement's meaning, linked by `documentId` | Ledger stores statement files; separate upload paths per pipeline | Upload, download and deletion controls exist once; no service stores another's storage keys | Never, without a new record | Accepted | *Candidate* |
| D9 | Statement deletion | Starts in the Ledger, which publishes `StatementDeleted` | Starts in the Document service | Removing transactions is the consequential part, so it happens first and in one place | Never, without a new record | Accepted | [ADR-005](architectural_decision_records/ADR-005-statement-deletion-starts-in-ledger.md) |
| D10 | Vector store | pgvector in the Aurora `knowledge` database | OpenSearch Serverless; Bedrock Knowledge Bases | Reuses the cluster and RLS; avoids a large fixed monthly cost | Corpus or query volume outgrows Postgres | Recommended | [ADR-006](architectural_decision_records/ADR-006-vector-store-pgvector.md) |
| D11 | Compute per profile | Lambda in dev, Fargate in prod for the Ledger and AI assistant, same artifact | One compute type everywhere | Near-zero idle cost in dev; warm, long-lived processes in prod | Dev cold starts block testing | Accepted | [ADR-007](architectural_decision_records/ADR-007-compute-per-profile.md) |
| D12 | Environments | Separate AWS accounts; one `profile` setting lists every difference | Shared account; ad-hoc per-environment config | Isolates real data; makes drift visible | A third environment is needed | Accepted | [ADR-008](architectural_decision_records/ADR-008-environments-and-profile-setting.md) |
| D13 | Encryption keys | Prod: customer-managed KMS keys, one per data type, decrypt limited to the owning service. Dev: free AWS-managed or default keys until invited testers, then customer-managed | Customer-managed in both from day one; one key per user | Same encryption and audit either way. The key policy is a second lock worth having once others' data is present; while dev holds only the owner's data, a switch takes about an hour. Per-user KMS keys cost $1/user/month and don't add isolation, because the service role can use them all | Invited testers (switch dev); crypto-shredding needed (per-user data keys wrapped by one KMS key) | Accepted | — |
| D14 | Ledger event publishing | Transactional outbox with a relay Lambda outside the VPC, schedule set per stage | EventBridge interface endpoint; NAT gateway | Event committed atomically with the change; no endpoint or NAT in dev | A Ledger event needs near-real-time delivery | Accepted | [ADR-009](architectural_decision_records/ADR-009-ledger-event-publishing-outbox.md) |
| D15 | Retention and deletion | 30-day grace period, then hard deletion within 7 days; keep only a deletion record (24 months), audit logs and later billing records; legal hold pauses deletion | Immediate deletion; longer retention of financial content | Protects against accidental closure while staying inside the 45-day state-law window; FinTracker has no obligation to keep users' financial content | Counsel advises otherwise, or paid plans add billing records | Accepted (confirm with counsel) | — |
| D16 | Recovery targets | Prod: RPO under 5 min / RTO under 1 h in-region; region outage 24 h / 24 h. Dev: 24 h / best effort | Cross-region active standby | Matches a pre-revenue consumer app that doesn't move money; in-region coverage comes from Aurora Multi-AZ and point-in-time restore | Before paying customers (add cross-region backup copies) | Proposed | — |
| D17 | RAG ownership | Knowledge owns retrieval (ingestion, vector store, embedding model, `retrieve` API); the AI assistant owns generation. Contract: text in, chunks with sources out | Whole pipeline inside the AI assistant; Bedrock Knowledge Bases retrieve-and-generate; retrieval in Analytics | One owner for vectors and per-user isolation, one owner for LLM risk; user documents later need no migration | Retrieval latency or cost becomes material (Bedrock Knowledge Bases retrieve-only behind the same API) | Accepted | [ADR-010](architectural_decision_records/ADR-010-rag-retrieval-in-knowledge-service.md) |
| D18 | Internal API layout | One internal HTTP API per receiving service (`analytics-`, `ledger-`, `knowledge-`, `user-profile-internal`; `document-internal` later), built from one Terraform module, same in both profiles | One shared internal API with a path prefix per service | Same cost and practically the same latency; least privilege per API ARN, blast radius limited to one service, independent deploys and per-service throttles and alarms | More than about 10 receiving services, or internal traffic moves off API Gateway | Accepted | [ADR-011](architectural_decision_records/ADR-011-internal-api-per-service.md) |
| D19 | Chat streaming entry | Its own Regional REST API with response streaming, behind the same identity authorizer; dev → Lambda, prod → VPC link → internal ALB | CloudFront + origin access control → Function URL; keep the open Function URL; WebSocket API | Junk requests stop at the authorizer, the built-in throttle caps the bill, one chat entry in both profiles, and it's cheaper than adding WAF to CloudFront to get a rate limit | The streaming spike fails with Lambda Web Adapter; HTTP APIs gain streaming | Accepted | [ADR-012](architectural_decision_records/ADR-012-chat-streaming-entry-rest-api.md) |
| D20 | Logging, tracing and audit | CloudWatch Logs and metrics plus X-Ray traces, instrumented with OpenTelemetry (traces), Powertools (Python logs and metrics) and Logback JSON (Ledger); one `trace_id` in every log line; a shared `audit()` helper writing to the `/fintracker/audit` log group; CloudTrail to S3. Prod later: monitoring account plus an S3 Object Lock archive | Grafana Cloud free tier; self-hosted Grafana stack or SigNoz | Nearly free in dev, data and audit stay inside AWS under IAM and KMS, nothing extra to run. OpenTelemetry keeps a later move to Grafana a configuration change | CloudWatch investigation becomes the bottleneck (send operational traces and logs to Grafana Cloud; audit stays in AWS) | Accepted | *Candidate* |
| D21 | Dashboard and Reports ownership | Dashboard = current month, served by the Ledger except Analytics' spending pace; Reports = completed periods, served by Analytics; no *This month* in Reports | Analytics serves both tabs; Ledger serves both tabs | One owner per figure; Dashboard reflects writes at once and survives an Analytics outage; cross-period work stays out of the system of record | Users want past months on the Dashboard | Accepted | [ADR-013](architectural_decision_records/ADR-013-dashboard-reports-ownership.md) |
| D22 | How Analytics reads Ledger data | Ledger-owned reporting views with counting fields, `security_invoker`, `SELECT` on views only; the Ledger's own totals use them too | Direct table reads (previous); event-fed copy in Analytics | One definition of income and spending; RLS still applies; no account names or numbers reach Analytics; the Ledger can change its tables | Analytics load affects Ledger latency, or the views can't express a need | Accepted | [ADR-014](architectural_decision_records/ADR-014-ledger-reporting-views.md) |
| D23 | User settings for calculations | Timezone and primary currency travel in the verified user context, attached by the identity authorizer and forwarded on internal calls; no default on a missing value | Sync call to User profile, cached (previous); event-fed copy per service; client header | No runtime dependency or extra state; trusted values; works for AI assistant calls | A scheduled job needs settings, or changes must apply within seconds | Accepted | [ADR-015](architectural_decision_records/ADR-015-settings-in-verified-context.md) |
| D24 | Transaction dates | Calendar dates as the source gives them, never converted between timezones; timezone only decides "today" | Timestamps converted to the user's timezone | History never moves when a user changes timezone, and dates match the user's statements | Bank sync delivers timestamps that need time-of-day logic | Accepted | — |

*Candidate* marks decisions that would benefit from a full ADR: each had several credible alternatives, or a cost, security, or compliance trade-off worth recording.

### 7.2 Open decisions

| Decision | Options | Notes |
|---|---|---|
| Ledger on Lambda (dev) | `aws-serverless-java-container`; Lambda Web Adapter | One JAR for both hosts. SnapStart works only with JAR/ZIP packages on AWS's Java runtime, not container images. Leaning: `aws-serverless-java-container`, which supports Spring Boot 3 with SnapStart |
| Tool transport, AI assistant → services | Signed internal REST; MCP over HTTP | Must be the same in both profiles. Leaning: signed REST now; add an MCP layer at the AI assistant if outside MCP clients need the tools |
| Statement-processed notification | Keep polling; WebSocket push from one notification owner; push from each producer | Leaning: keep polling for now; later, one owner of WebSocket connections pushes on the Ledger's import-committed event |
| First user document type *(later)* | Loan agreements; credit card terms | Deferred: current focus is the refactor, LLM features and RAG over system docs |

---

## 8. Invariants

These hold for every service, in every profile. A spec or design that conflicts with one is wrong.

1. **One owner per data store.** The only exception is Analytics' read-only role, which may read only the Ledger's reporting views. *Enforced by: per-service IAM roles and database roles.*
2. **Identity comes from the verified token.** `userId` is set by the identity authorizer, on the gateway and on the chat streaming API. It is never taken from a request body, query parameter, path, or LLM tool argument. *Enforced by: the authorizer; code review.*
3. **Internal calls prove both identities.** SigV4 says which service; the forwarded user context says on whose behalf. *Enforced by: IAM authorization and the caller allow-list.*
4. **Every database access runs with the user context set**, and Row-Level Security enforces it. A session without it sees nothing. *Enforced by: forced RLS policies ([ADR-002](architectural_decision_records/ADR-002-rls-and-ownership-scoped-queries.md)).*
5. **Cross-tenant requests return 404.** *Enforced by: owner-scoped repository queries; isolation tests.*
6. **Files never pass through a service.** Uploads are scanned before use. Downloads come only from the clean bucket after an ownership check. *Enforced by: bucket policies and presigned URLs.*
7. **Only the Document service knows where a file is stored.** Everyone else uses `documentId`.
8. **Statements become transactions, not search text.** Only the Data pipeline processes bank statements.
9. **Only Knowledge touches the vector tables.** *Enforced by: database role grants.*
10. **Only the AI assistant calls an LLM.** Knowledge calls an embedding model only. *Enforced by: IAM; only the AI assistant's role may invoke generation models, and only Knowledge's role may invoke the embedding model.*
11. **Deletion cascades.** Every service that stores user data handles `UserAccountDeleted`, plus `StatementDeleted` or `DocumentDeleted` for data it derived. It deletes only its own share, and reports completion.
12. **Profiles differ only in capacity, availability, perimeter, cost guards and defense-in-depth layers (WAF, key management)**, as listed in [6.1](#61-environments-and-what-differs-between-them). Identity, IAM, Row-Level Security, encryption and audit logging never differ.

---

## 9. Tech stack

| Area | Choice | Why |
|---|---|---|
| Ledger | Java 21, Spring Boot 3, jOOQ, Flyway | Compile-time SQL type safety, mature transaction management, virtual threads. Correctness first |
| Other services | Python, FastAPI, Pydantic | AI and data ecosystem (Bedrock, Textract, PDF tooling), fast iteration, lower cold starts than the JVM |
| Frontend | Angular 21 with Signals | Enterprise-grade framework with reactive state |
| Relational data | Aurora PostgreSQL Serverless v2, Row-Level Security | ACID for financial records; tenant isolation in the database |
| Key-value data | DynamoDB, on-demand | Low-latency per-user lookups, pay per request |
| Vector search | pgvector *(recommended)* | Reuses the database and RLS (D10) |
| Workflows | Step Functions (Standard) | Retries, waits for user confirmation, and visible execution state |
| Messaging | EventBridge + SQS | Routing by event type plus per-consumer retries (D6) |
| AI | Amazon Bedrock (LLM and embeddings); Textract (OCR) | Model calls stay inside AWS; customer data is not used for model training |
| Identity | Cognito + User profile identity authorizer | Managed sign-in and MFA; provider-independent internal ID |
| Observability | CloudWatch Logs and metrics; X-Ray traces through OpenTelemetry (ADOT); Powertools (Python); Logback JSON and the OpenTelemetry Spring Boot starter (Ledger) | One place for every service's logs, metrics, traces and audit events; data stays in AWS; nearly free at dev volume (D20) |
| IaC and CI/CD | Terraform, GitHub Actions | One `profile` setting per environment |

---

## 10. Compliance and standards

Legal applicability must be confirmed with counsel before launch; until then, regulations show *Applies (to confirm)*.

| Standard / regulation | Why it applies | How the architecture supports it | Status | Evidence |
|---|---|---|---|---|
| GLBA / FTC Safeguards Rule | Consumer financial data | Encryption at rest and in transit, MFA, least-privilege access, tenant isolation, audit logging, deletion; disposal no later than 2 years after last use | Applies (to confirm) | Written security program, incident response plan and data retention review still needed |
| State privacy laws (VCDPA, CCPA/CPRA) | Personal data of residents of those states | Download (access); deletion completed within the 45-day window (D15); records of requests kept 24 months | Applies (to confirm) | — |
| Record retention obligations | Could require keeping records after closure | None identified for users' financial content. Kept: deletion records, audit logs, later billing records; legal hold process (D15) | To confirm | — |
| GDPR | Only if serving EU users | Per-table erasure by `user_id` (ADR-001) is compatible with the right to erasure | Out of scope (no EU users) | ADR-001 |
| PCI DSS | Card data | Kept out of scope by never storing full card numbers | Out of scope | — |
| OWASP ASVS | Web application security baseline | Authentication, access control, input and file validation | Applies | — |
| OWASP Top 10 for LLM Applications | AI chat and summary | Prompt-injection handling, output validation, least-privilege tools, cost limits | In progress | Financial Summary output validation and evaluation suite |
| WCAG 2.2 AA | Accessible web app | Frontend concern; listed so it is tracked | Applies | — |

---

## 11. Related documents

**Service architecture documents** (each to be written from `docs/templates/service-level-architectural-doc-template.md`)

| Service | Architecture doc | Interim source until then |
|---|---|---|
| User profile | *to be created* | [user-profile-spec-01.md](../fintracker-user-profile-doc/user-profile-spec-01.md) |
| Ledger | [ledger-architecture.md](../fintracker-ledger-doc/architecture/ledger-architecture.md) | — |
| Data pipeline | *to be created* | [data-pipeline-spec-02.md](../fintracker-data-pipelines/data-pipeline-spec-02.md) |
| Analytics | [analytics-architecture.md](../fintracker-analytics/architecture/analytics-architecture.md) | — |
| Document service *(user documents later)* | *to be created* | `moved-to-specs.md` (Upload intake section) |
| Knowledge | [knowledge-architecture.md](../fintracker-knowledge/architecture/knowledge-architecture.md) | — |
| AI assistant | [ai-assistant-architecture.md](../fintracker-ai-assistant/architecture/ai-assistant-architecture.md) | — |
| Frontend | [fintracker-ui-architectural-doc.md](../fintracker-ui-doc/fintracker-ui-architectural-doc.md) | — |

**Other documents**

- **Architecture decision records:** [architectural_decision_records/](architectural_decision_records/)
- **Roadmap:** [roadmap.md](roadmap.md)
- **Content moved out of this document, pending its service docs:** [moved-to-specs.md](moved-to-specs.md)
- **Diagrams:** `images/` (SVG)
- **Superseded:** `fintracker_workflows.md` (replaced by section 5 and the service docs); `fintracker-analytics/architecture/ai-integration-architecture.md` and `ai-governance-monitoring.md` (written when AI lived in Analytics; replaced by the AI assistant doc)
