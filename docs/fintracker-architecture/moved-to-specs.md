# Moved from the architecture doc

These sections were removed from `fintracker-architectural-doc.md` because they describe how a single service works, which changes often. They are kept here word for word, grouped by the spec each belongs in. Move each block into its service spec, then delete this file.

Where a statement here conflicts with the architecture doc (for example, Analytics reading a read replica), the architecture doc is current.

---

## → Data pipeline spec

### 1. Data pipeline service

**Purpose:** the asynchronous ingestion engine. It processes uploaded statement files, standardizes their format, assigns a first-pass category, and sends normalized transactions to the Ledger for the user to review.

**Why it's a separate service:** parsing, deduplication, and categorization are messy, retry-heavy background work. Keeping it away from the Ledger means a failed or slow import never affects the system of record.

**What changes with Upload intake:** file-upload handling (issuing the upload URL, validation, storage) is done today by the **Ledger** (it creates the statement record and issues the upload URL), and the pipeline is triggered by the file landing in storage. Upload intake would take over the front door; the pipeline would subscribe to "statement uploaded" events instead of the raw storage event. Everything statement-specific—format detection, extraction, normalization, categorization—stays here.

**Modules**

- **Statement ingestion:** reacts to a new file, verifies who owns the statement by asking the Ledger, starts one workflow run per statement, and records job status for the UI to poll.
- **Gatekeeper:** detects the file format (PDF, image, CSV), enforces size and page limits before any paid processing, and for CSV proposes a column mapping for the user to confirm.
- **Extractor:** reads CSV rows directly; for PDFs, reads the document's own text layer first and falls back to Amazon Textract only for pages that need OCR (and always for images).
- **Normalizer:** cleans merchant strings, parses amounts and transaction direction, and fingerprints each row for deduplication.
- **Categorizer:** assigns a first-pass category: the bank's own category (CSV only) → a built-in merchant pattern list → Uncategorized.
- **Data dispatcher:** sends one package per statement to the Ledger.

**Workflow A: Statement upload**

*Trigger:* the file lands in the statement bucket (upload URL issued by the Ledger). *Planned:* an `UploadAccepted` event from Upload intake.

1. **Verify ownership.** Look up the statement's owner (user and account) from the Ledger. The file's own metadata is never trusted for identity. An unknown statement is not processed.
2. **Gatekeeper.** Detect format, enforce limits, and for CSV propose a column mapping.
   - **CSV:** the workflow pauses until the user confirms or corrects the mapping in the UI. A correction is saved per bank for future uploads.
3. **Extract** rows (CSV parse, PDF text layer, or Textract).
4. **Normalize and categorize** each row.
5. **Push to the Ledger** in one call per statement. Every row arrives as pending; the Ledger skips duplicate rows and treats an unknown category as Uncategorized.
6. **Update job status** (started → … → completed/failed). The UI polls the job status; there is no push notification today.

**Workflow B: Bank sync** *(phase 2, not built)*

*Trigger:* EventBridge schedule (e.g., every 6 hours).

1. Teller.io ingestion (API call).
2. Normalize with the shared Normalizer.
3. Categorize with the shared Categorizer.
4. Push to the Ledger.

**Tech stack:** Python, AWS Lambda, AWS Step Functions (Standard workflow—required for the CSV pause), Amazon S3, Amazon DynamoDB (job tracker, bank column mappings), Amazon Textract, PyMuPDF. Infrastructure in Terraform.

**Workload profile:** highly asynchronous, compute- and memory-intensive, and event-driven. Optimized for background processing where sub-second latency isn't required.

---

## → Ledger spec

### 2. Ledger service (core)

**Purpose:** the application's system of record. It manages all ACID-compliant financial records, enforces budget rules against real spending, and owns statement records.

**Why it's a separate service:** financial records need strict consistency and a narrow, carefully guarded write path. Statement imports enter only through one internal, signed endpoint used by the Data pipeline; users change their own records through the app.

**Modules**

- **Accounts:** the user's bank, card, and cash accounts.
- **Categories:** built-in system categories (each with a stable code) plus user-defined custom categories.
- **Transactions:** listing and filtering, approve pending rows, edit, exclude, split, tag, manual entry, bulk actions, and the internal bulk import from the Data pipeline (deduplicated by statement and row fingerprint).
- **Statements:** statement records, issuing the direct-to-storage upload URL, duplicate-file detection, and deletion (which removes the statement's transactions too).
- **Budgets:** monthly budgets and line items, reusable templates and quick start, spend calculation; a monthly job closes the previous period.
- **Bills:** upcoming bills and marking them paid.
- **Dashboard:** aggregations for the Dashboard tab.

**What changes:** nothing structural. The Ledger exposes read endpoints that the AI assistant uses as tools (for example, transactions by category and date range, and budget status).

**Tech stack:** Java 21, Spring Boot 3, jOOQ, Flyway, PostgreSQL (Amazon Aurora Serverless in deployment) with Row-Level Security.

**Workload profile:** synchronous, I/O-bound, and highly transactional. Requires strict data consistency and low-latency request-response cycles for accurate balance and budget calculations. Virtual threads (Project Loom) handle high-concurrency workloads; jOOQ provides compile-time SQL type safety, which is critical for financial correctness.

---

## → Analytics spec

### 3. Analytics service

**Purpose:** the application's metrics and detection engine. It computes aggregations, period-over-period comparisons, budget status, and detects patterns such as anomalies, duplicate charges, fees, subscription creep, free trials converting to paid, and spending velocity—all from ledger history on the read replica, with deterministic code.

**Why it's a separate service:** analytical queries are long-running and read-heavy. Running them against a read replica in their own service keeps them from slowing down real-time transactions in the Ledger.

**What changes:** see [Analytics refactor](#analytics-refactor). In short, every LLM call, prompt, and LLM-cost control moves to the AI assistant. Analytics keeps the numbers and the detectors and exposes them as read-only APIs that the AI assistant calls as tools.

**Modules (after refactor):** Dashboard, Reports (category spending, monthly trend), Financial facts (period selection, which transactions count, per-section metrics), Detectors.

**Tech stack:** Python, FastAPI on AWS Lambda, PostgreSQL (read replica).

**Workload profile:** read-only and analytical (OLAP).

### Analytics refactor (Analytics and AI assistant specs)

**Goal:** Analytics provides the numbers and the detected patterns; the AI assistant is the only service that talks to an LLM. Analytics never sees a prompt, and the AI assistant never computes a financial figure itself.

**Stays in Analytics (deterministic)**

- Dashboard and reports endpoints.
- Financial facts: period options (in the user's timezone), which transactions count, the per-section metrics (cash flow, categories, budgets, anomalies, data quality), and the assembled facts payload with its content hash.
- Detectors: duplicates, fees, leakage, free-trial conversion, spending velocity, subscription creep.
- The facts and section APIs, exposed to the AI assistant as read-only, user-scoped tools.

**Moves to the AI assistant**

- The Financial Summary flow: cache, cost guard (per-user and app-wide daily limits), LLM call, output validation and grounding against the facts, advice guardrails, facts-only fallback, audit records and snapshots, and the prompt evaluation suite.
- The summary endpoints the UI calls to get and refresh the AI summary. (Analytics keeps the periods and facts endpoints so the UI can show numbers before the AI text.)
- The agent tool catalog. Analytics' in-process MCP tool server is retired; the AI assistant holds the tool definitions and calls Analytics, Ledger, and User profile over signed internal APIs.
- Deletion of summary data on `UserAccountDeleted`.

**Retired**

- The old Bedrock-based "insights" endpoint (already unmounted). Anomaly and subscription-creep tools are backed by the deterministic detectors instead of an LLM call.

**Financial Summary flow after the refactor**

1. UI → AI assistant: "summary for this period."
2. AI assistant → Analytics: get the facts payload for the authenticated user and period.
3. AI assistant checks its cache (keyed by the facts hash) and cost limits; on a miss, calls the LLM with the facts only.
4. AI assistant validates the answer against the facts and returns it, or returns a facts-only fallback with a reason.

---

## → User profile spec

### 4. User profile service

**Purpose:** manages the user lifecycle. It creates the internal user record when a Cognito sign-up is confirmed, maps the Cognito identity (`sub`) to FinTracker's internal `userId`, runs the gateway's identity authorizer, stores settings (currency, timezone, notification preferences) and savings goals, tracks WebSocket connections, and handles account deletion.

**Why it's a separate service:** identity is a dependency for every service but the responsibility of none of them. Owning the internal `userId` here keeps the rest of the system independent of the identity provider.

**Modules**

- **Identity:** sign-up confirmation hook, identity authorizer, profile, internal settings lookup (used by Analytics), account deletion.
- **Goals:** savings goals, plus an internal read used by other services.
- **WebSocket:** connect/disconnect tracking. *Pushing messages to the browser is not wired to any producer yet.*

**What changes:** it is already the source of the **account-deleted** event (`UserAccountDeleted`). Every service that stores user data—including Knowledge (documents and vectors) and the AI assistant (conversations, summary cache)—subscribes and deletes its share. Subscription tier is stored and passed through the authorizer; it is not yet enforced anywhere.

**Tech stack:** Python (AWS Lambda handlers), Amazon DynamoDB (single-table design), Amazon Cognito, Amazon EventBridge. Local development via AWS SAM; no deployed IaC yet.

**Workload profile:** synchronous, high-read, low-write. Optimized for instant request-response with minimal cold starts for a seamless login and app bootstrap.

---

## → AI assistant spec

### 5. AI assistant service

**Purpose:** runs customer chat support and every LLM call in FinTracker, including the Reports tab's Financial Summary.

**Responsibilities**

- Chat orchestration: takes the user's question, decides which tools to call, and generates the answer with Amazon Bedrock.
- The Financial Summary (moved from Analytics, see above).
- Conversation history.
- The **tool catalog**: the list of tools the model can see, with their schemas and which feature may use which tool (for example, the Financial Summary gets a small read-only subset; chat gets more).
- Prompt templates, output validation, guardrails, token/cost budgets, LLM audit records, and prompt evaluation.

**How tools work:** the AI assistant holds the tool *definitions*. The tool *logic* stays in the service that owns the data. When the model calls `get_spending_by_category`, the assistant validates the arguments, then makes a signed internal call to Analytics or the Ledger for the current user. The user is fixed by the assistant from the authenticated request—no tool takes a user ID argument the model could choose. If the AI assistant were deleted, no business logic would be lost—only orchestration.

**Why it's a separate service (and not part of Analytics):**

1. **Right direction of dependency.** Chat calls Ledger, Analytics, User profile, and Knowledge. Inside Analytics, it would turn Analytics into a hub that depends on everything.
2. **Different runtime profile.** Chat means streaming responses and slow upstream LLM calls. Analytics means batch computation. They scale and fail differently.
3. **One place for AI risk.** Prompt-injection defenses, model upgrades, evaluation, and LLM cost control all live in a single service.

**Tech stack:** Python, Amazon Bedrock, DynamoDB for conversation history, summary cache, usage counters, and audit records. Exact compute (Lambda with response streaming vs. ECS Fargate) to be decided.

---

## → Knowledge spec

### 6. Knowledge service

**Purpose:** makes documents searchable for the AI assistant, while guaranteeing that a user can only ever retrieve their own documents.

**Responsibilities**

- **Ingestion workers:** extract text → redact sensitive data (account numbers, SSNs) → split into chunks → create embeddings → store in the vector store.
- **Retrieval API:** `retrieve(query, scope)`, where `scope` is `system` (help docs) or `mine` (the user's own documents).
- **Deletion:** when a document or account is deleted, removes its text, chunks, and vectors.

**Why it's a separate service:** it is the **single owner of the vector store**. If several services queried the index directly, each would need to remember the per-user filter, and one missed filter leaks another user's documents. With one owner, the rule is written once:

- The user's identity comes from the verified request inside Knowledge—never from a request parameter and never from a value the LLM supplies.
- After every search, Knowledge double-checks that each returned chunk belongs to the caller or is a system document.
- Only Knowledge's IAM role can access the vector store.

**Two document collections**

| Collection | Contents | Who can retrieve it | How it gets in |
|---|---|---|---|
| System | App navigation and how-tos, troubleshooting and FAQs, budgeting education, analytics methodology (how each metric is calculated), policies, glossary | Every user | Written in the Git repo, re-indexed by CI on merge |
| User | The user's own reference documents (see phasing below) | Only the uploading user | Upload intake → ingestion workers |

**Important:** questions about the user's own numbers ("How much did I spend on dining in May?") are answered by tool calls to the Ledger and Analytics, not by searching documents. Search is for text; the ledger is for numbers.

**Tech stack:** Python, Step Functions or Lambda workers, Bedrock embeddings. Vector store to be decided; candidates include pgvector on Aurora PostgreSQL (reuses existing infrastructure and RLS).

---

## → Document service spec (formerly Upload intake; see the architecture doc for download and deletion)

### 7. Upload intake

**Purpose:** a single, hardened front door for every file a user uploads.

**Responsibilities**

- Issue presigned S3 upload URLs, tied to the owner's `userId` (today the Ledger does this for statements).
- Check subscription limits before accepting an upload (not enforced anywhere today).
- Validate file type, size, and page count (today partly in the Data pipeline's Gatekeeper).
- Scan for malware; move files from a quarantine bucket to a clean bucket only after they pass.
- Detect duplicates by file hash (today the Ledger detects duplicate statements).
- Track upload status (`uploaded → scanning → processing → done/failed`) so the UI has one place to check.
- Route by document type and publish an `UploadAccepted` event:
  - `statement` → Data pipeline
  - any other allowed type → Knowledge

**Why it's a separate service:** both pipelines need the same security checks before touching a file. Implementing them once avoids two upload paths with two slightly different sets of gaps. Everything after routing stays separate, because statement extraction (exact tables and amounts) and document extraction (readable text) change for different reasons.

**Routing rule:** the user chooses the document type when uploading. Automatic classification is only a sanity check, never the primary router—a misrouted statement would become search text instead of transactions.

**Tech stack:** S3 event + Lambda (doesn't need to be an always-on service), EventBridge or SQS for routing.

---

## → Development standards

### Development standards

**Standard:** production-ready, secure, and cost-optimized.
**Code style:** feature-based layout, strict typing, comprehensive documentation.

### Feature-based layout

Code is organized by business feature (domain) rather than by technical layer. Each feature is a self-contained vertical slice with its own models, business logic, data access, and API handler. Cross-cutting concerns (auth, config, shared utilities) live in a top-level `shared/` or `core/` module.

**Python services** (data-pipeline, analytics, user-profile, and the new ai-assistant, knowledge, and upload-intake):

```
src/   (user-profile uses app/)
├── <feature>/         # e.g., gatekeeper/, summary/, goals/
│   ├── models.py      # Domain models (frozen dataclasses)
│   ├── schemas.py     # Data structure and validation (Pydantic)
│   ├── service.py     # Business logic
│   ├── repository.py  # Data access
│   ├── router.py      # API endpoints (FastAPI)
│   ├── handler.py     # Lambda handler
│   └── exceptions.py  # Feature-scoped exceptions
├── shared/            # Cross-cutting utilities (application-scoped exceptions, auth helpers)
└── core/              # App config, DI setup, logging
tests/
├── unit/              # Business logic tests with mocked repositories
└── integration/       # Adapter tests using Moto (AWS) or Testcontainers (Postgres)
```

**Java service** (ledger):

```
src/main/java/com/fintracker/ledger/
├── <feature>/                                    # e.g., transaction/, budget/, statement/
│   ├── model/<Feature>.java                      # Domain model (Java record)
│   ├── service/<Feature>Service.java             # Business logic (interface)
│   ├── service/impl/<Feature>ServiceImpl.java    # Business logic (implementation)
│   ├── controller/<Feature>Controller.java       # REST controller
│   ├── dto/<Feature>Dto.java                     # Data structures (Java record)
│   ├── repository/<Feature>Repository.java       # Repository interface
│   ├── repository/Jooq<Feature>Repository.java   # Repository implementation (jOOQ)
│   └── exception/                                # Feature-scoped exceptions
├── shared/                                       # Cross-cutting (user context holder, shared exceptions)
└── config/                                       # Spring wiring, filters (user context, internal caller), error handling
```

### Shared code between services

Shared code lives in a small `common` package in the monorepo, version-pinned per service. Share only what must behave identically everywhere:

- **Share:** user-context and internal-call verification, SigV4 signing helpers, event schemas (e.g., `UploadAccepted`, `UserAccountDeleted`), PII redaction rules, logging helpers, AWS client wrappers.
- **Don't share:** domain logic such as parsing, extraction, chunking, or categorization. If domain logic creeps into `common`, move it back to its service.

*Not built yet:* each service currently carries its own copy of the SigV4 helper.

---

## Superseded infrastructure notes (for reference)

Replaced by section 5 of the architecture doc. Kept for the details not carried over, such as the SQS retry queue for summary audit writes.

### Infrastructure & non-functional requirements

### Deployment & scalability

- **Infrastructure as code:** Terraform, starting with the Data pipeline (reusable modules plus one folder per environment; the dev environment deploys to real AWS). The earlier AWS CDK stack is kept for reference only. Other services have no deployed IaC yet (User profile has a local-only SAM template).
- **CI/CD:** GitHub Actions, deploying to staging on PR and to production on tag. CI also re-indexes system help docs on merge *(proposed)*.

### Compute

- **Lambda:** about 95% of the workload.
- **ECS Fargate:** reserved for long-running Python data processing that exceeds Lambda's 15-minute limit. The Ledger (Spring Boot) also needs an always-on host; choice to be confirmed.

### AWS services

- **Step Functions (Standard):** orchestrates the statement pipeline, including the pause for CSV mapping confirmation.
- **S3:** stores uploaded statements and CSV files (quarantine and clean buckets *proposed*).
- **API Gateway (HTTP API):** exposes backend APIs, with the User profile identity authorizer for user calls and IAM authorization for internal calls.
- **EventBridge:** carries `UserAccountDeleted` today; upload routing *(proposed)*.
- **SQS:** retry queue for failed summary audit writes.
- **CloudWatch:** logs and monitoring.
