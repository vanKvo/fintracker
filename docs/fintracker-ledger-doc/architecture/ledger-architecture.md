# Ledger Architecture

| Status | Owner | Last reviewed | Applies to | App architecture |
|---|---|---|---|---|
| Existing (runs locally; AWS deployment planned) | Van Vo | 2026-10-20 | main | [FinTracker architecture](../../fintracker-architecture/fintracker-architectural-doc.md) |

This document describes how the Ledger works and the workflows it owns. Rules that apply to every service are in the app architecture doc. These include identity, events and invariants. Field-level rules, payloads and schemas live in the Ledger specs listed in section 5.

---

## 1. Overview

**Purpose:** the Ledger is FinTracker's system of record for money. Every account, transaction, statement record, budget and bill lives here, and every change to them goes through it. It is a separate service because financial records need strict consistency and a narrow, guarded write path.

**Responsibilities**
- **Accounts:** the user's bank, card and cash accounts.
- **Categories:** system categories, each with a stable `code`, plus each user's custom categories.
- **Transactions:**
  - list and filter;
  - approve pending rows, edit, split, tag and exclude;
  - manual entry, and bulk actions.
- **Import:** the internal endpoint that stores a statement's transactions from the Data pipeline, as pending.
- **Statements:** statement records, duplicate checks, and deletion with its transactions. Today it also issues the presigned upload URL.
- **Budgets:**
  - monthly budgets and their lines, templates and quick start;
  - spend against each line;
  - the monthly job that closes past budgets.
- **Bills:** recurring bills and marking them paid for a month.
- **Dashboard:** every Dashboard widget except spending pace, for the current month (app doc D21).
- **Reporting views:** the read contract for income and spending, used by its own totals and by Analytics (D22).
- **Events:** publishes its events through a transactional outbox (D14).

**Does not do**
- Parse statements or assign first-pass categories. The Data pipeline does.
- Hold files. The Document service will; today the Ledger only presigns the upload.
- Trends, period comparisons, category trends, top merchants or detectors. Analytics does.
- Call an LLM. The AI assistant does, calling the Ledger only through read tools.
- Map identities or store user settings. User profile does.

**Owns**
- The Aurora `ledger` database: accounts, categories, transactions, statements, budgets, budget lines, budget templates, bills, bill payments, and the outbox.

---

## 2. Architecture and workflows

![Ledger components](images/ledger-components.svg)

**How to read the diagram**
- Two front doors share one request pipeline:
  - the **public API** for the web client, behind the gateway's identity authorizer;
  - **`ledger-internal`** for the Data pipeline and the AI assistant, signed with IAM and checked against a caller allow-list (D18).
- Every request runs the numbered steps:
  1. **Request context** reads the user from the verified context. On an internal route, the caller check comes first.
  2. **RLS session** sets `app.current_user_id` before each query and resets it after (ADR-002).
  3. The **feature service** runs one ACID transaction.
  4. jOOQ queries reach Aurora over JDBC with an IAM auth token. Repositories add owner filters as a second layer.
  5. A change that others must hear about, such as a statement deletion, writes an outbox row in the same transaction.
  6. The relay publishes outbox rows to EventBridge.
- **Analytics** never touches the Ledger's tables. It reads only the reporting views (D22).

### Workflows

#### Serve the Dashboard

**Trigger:** the Dashboard tab loads · **Result:** five widgets for the current month · **On failure:** a widget whose request fails shows its own error state; the others still render

1. Resolve the user and the current month from the verified context. The month is today's date in the user's timezone (D23, D24).
2. **Data through:** the earliest of each active account's latest statement closing date or latest transaction date, plus the count of pending transactions. Pending rows are not in any total yet.
3. **Summary cards:**
   - total balance across accounts;
   - income, expenses and net for the month, from the reporting views' counted rows in the primary currency.
4. **Budget alerts:** the month's budget lines that are nearing or over their limit. Spend comes from the same views, so refunds offset spending (TXT-02).
5. **Bills:** the month's active bills, each marked paid or unpaid from bill payments.
6. **Recent transactions:** the latest transactions, with pending rows marked.

#### Start a statement upload *(today; moves to the Document service)*

**Trigger:** the user uploads a statement · **Result:** a statement record and a presigned upload URL · **On failure:** a clear message for an unowned account, a bad file type or a month that's already taken

1. Check that the account belongs to the user.
2. Check for duplicates: same file, or a month already covered (REQ-STMT-03, REQ-STMT-06).
3. Create the statement record with status `PROCESSING`.
4. Return a presigned S3 URL. The client uploads directly, and the Data pipeline starts from the storage event.

#### Import a statement's transactions *(internal)*

**Trigger:** the Data pipeline's signed import call, one per statement · **Result:** the statement's rows stored as `PENDING` · **On failure:** per-row results; the pipeline retries the whole call safely

1. Check the caller against the allow-list, then read the user from the signed context.
2. Check that the statement belongs to that user and that the account matches. The caller can't nominate another account.
3. Validate each row in code. A row whose category is unknown or inactive is stored as Uncategorized and reported with a reason.
4. Insert the valid rows in one statement, skipping rows already stored ([SDR-001](decision_records/SDR-001-import-idempotency.md)).
5. Return each row's result: `ACCEPTED`, `ALREADY_STORED` or `REJECTED` with a reason.

#### Approve pending transactions

**Trigger:** Approve or Approve Selected · **Result:** rows move from `PENDING` to `POSTED` and start counting · **On failure:** nothing changes

1. Promote only rows that are currently `PENDING` and owned by the user.
2. In the same transaction, mark a statement `COMPLETED` when it has no pending rows left.

#### Delete a statement

**Trigger:** the user deletes a statement · **Result:** the statement and its transactions are gone, and the file follows · **On failure:** nothing changes, and no event is published

1. In one database transaction:
   - delete the statement record; the foreign key cascades to its transactions;
   - write `StatementDeleted(documentId)` to the outbox (ADR-005).
2. The relay publishes the event on its next run (ADR-009), and the Document service deletes the file.

#### Close budget periods

**Trigger:** the scheduler, on the 1st of each month at 00:00 UTC · **Result:** past `ACTIVE` budgets become `CLOSED` · **On failure:** the next run closes them; the job is idempotent

1. For each user in turn, with that user's context set, close every `ACTIVE` budget for a month before the current one. The job never reads all users' rows through a bypass (app doc 4.2).
2. A closed budget is read-only until the user reopens it explicitly.

#### Delete a user's data *(proposed; no handler today)*

**Trigger:** `UserAccountDeleted` · **Result:** none of the user's records remain · **On failure:** the message retries, then goes to the dead-letter queue

1. With the user's context set, delete their rows from every table by `user_id`, in one transaction (ADR-001).
2. In the same transaction, write `UserDataDeleted(userId, ledger)` to the outbox.

---

## 3. Concepts of Operation

### 3.1 Enter: what does this service expose and consume?

| Interface | Type | Caller / producer | Purpose |
|---|---|---|---|
| `/api/v1/ledger/accounts`, `/categories` | Public API | Web client | Accounts and custom categories |
| `/api/v1/ledger/transactions` (+ approve, split, bulk) | Public API | Web client | Transactions tab, manual entry |
| `/api/v1/ledger/statements` (+ initiate-upload) | Public API | Web client | Statements tab, uploads, deletion |
| `/api/v1/ledger/budgets`, `/budget-templates` | Public API | Web client | Budgets tab |
| `/api/v1/ledger/bills` (+ pay) | Public API | Web client | Bills on the Dashboard |
| `/api/v1/ledger/dashboard/*` | Public API | Web client | Data-through, summary cards, budget alerts |
| Statement owner lookup, statement import | Internal API (IAM) | Data pipeline | Ownership check and pending rows |
| Categories read (system and user) | Internal API (IAM) | Data pipeline | Category mapping during normalization |
| Read tools *(proposed)* | Internal API (IAM) | AI assistant | Transactions by category and date range, budget status |
| Reporting views | Read contract (database) | Analytics | Income and spending with counting rules (D22) |
| `StatementDeleted` *(proposed)* | Event published | — | Document service deletes the file |
| `UserDataDeleted` *(proposed)* | Event published | — | User profile tracks deletion |
| `UserAccountDeleted` *(proposed handler)* | Event consumed | User profile | Delete the user's records |
| Budget period close | Scheduled | Scheduler | Close past budgets |

Route names are indicative; the contract files are authoritative.

### 3.2 Trust: who may call it, and how is each request scoped to a user?

- **Public routes:**
  - The gateway's identity authorizer attaches the verified context, and the Ledger reads `userId`, timezone and primary currency only from it.
  - In prod, the Ledger is reachable only through the VPC link to an internal load balancer, whose security group accepts only the VPC link. That is why it can trust the `userId` header (app doc 6.3).
- **Internal routes:**
  - Only allow-listed IAM roles may call them: the Data pipeline and the AI assistant.
  - The user comes from the signed user context, never from a body field or path parameter.
  - An import may write only into the account of the statement it names.
- **Database:**
  - RLS is forced on every table, and `app.current_user_id` is set before every query and reset after (ADR-002). A session without it sees nothing.
  - Repositories also filter by owner (`…ByIdAndUserId`).
  - The service connects with an IAM auth token, so no password is stored.
  - Migrations run under a separate schema-owner role, in a deploy step before the new version.
  - Analytics' role may `SELECT` only the reporting views.
- **Cross-tenant requests return 404,** never 403.
- **Scheduled jobs** set each user's context in turn and never read all rows through a bypass.

### 3.3 Flow: how does it depend on other services?

| Depends on | How | Why | If unavailable |
|---|---|---|---|
| Aurora (`ledger`) | JDBC with IAM auth, from inside the VPC | Every read and write | Dev: waits for Aurora to resume (timeouts above 30 s) and retries. Prod: the reader in a second AZ takes over |
| EventBridge | Through the outbox relay, never called directly | Publish events without a NAT or endpoint in dev | Events wait in the outbox; nothing is lost |
| S3 *(today)* | Presigned URL, signed locally | Direct client upload | The upload fails and the statement record stays `PROCESSING` |

The Ledger makes no synchronous calls to other services. The Data pipeline, the AI assistant and Analytics depend on it, not the reverse.

### 3.4 Store: what data does it keep, and for how long?

| Data | Store | Retention | On account deletion |
|---|---|---|---|
| Accounts, categories, transactions, statement records, budgets, templates, bills, bill payments | Aurora `ledger` | Until the user deletes them or closes the account | Deleted by `user_id` in every table *(proposed handler)* |
| Outbox rows | Aurora `ledger` | 7 days after publishing | Deleted with the user's rows once published |
| Statement files *(today)* | S3, keyed `statements/{userId}/{statementId}/…` | Until the statement is deleted | Moves to the Document service's deletion |

### 3.5 Protect: what does this service guard beyond the app-level rules?

- **Narrow write path:** imports enter only through the signed internal endpoint, and users change only their own records through the public API.
- **Imported rows are immutable in substance:**
  - Imported rows can't be deleted; users exclude them instead.
  - Only manual rows can be deleted.
  - Deleting a statement removes its rows as a unit.
- **Closed budgets are read-only** until explicitly reopened.
- **Money is exact:**
  - amounts are `DECIMAL(15,2)`;
  - input with more than 2 decimal places is rejected, never rounded;
  - a split's children must sum exactly to the parent, in one transaction.
- **One counting rule set:** the reporting views define what counts as income and spending for the Dashboard, budgets and Analytics.
- **Logs never contain financial values** or account numbers (app doc 4.7).

### 3.6 Recover: how does it fail, and how does it recover?

- **Every change is one ACID transaction,** so a failure leaves nothing half-written: splits, approvals with statement completion, and deletions with their outbox row.
- **Imports are idempotent:** a retried call stores nothing twice ([SDR-001](decision_records/SDR-001-import-idempotency.md)).
- **Events can't be lost:** they wait in the outbox until the relay publishes them, and consumers are idempotent.
- **The budget-close job is idempotent:** a missed run is caught by the next.
- **Data recovery:** Aurora point-in-time restore, kept 14 days in prod and 1 day in dev (app doc 4.6).

### 3.7 Observe: how do we know it is healthy?

- Latency and errors per route, with the Dashboard summary as the critical path (target under 200 ms, REQ-6.1).
- Import results per statement: accepted, already stored, rejected by reason.
- Age of the oldest unpublished outbox row, alarmed whenever the relay is enabled.
- Budget-close job runs and failures.
- RLS isolation tests and repository owner-scope tests in CI.

---

## 4. Service decisions

Cross-service decisions this service applies are in the app architecture doc: D1 (`user_id` on every table), D2 (RLS), D5 (JDBC with IAM auth), D9 (statement deletion starts here), D11 (Lambda in dev, Fargate in prod), D14 (outbox), D18 (`ledger-internal`), D21 (Dashboard ownership), D22 (reporting views), D23 (settings in the verified context) and D24 (calendar dates).

| # | Decision | Choice | Why | Revisit when | Status | Record |
|---|---|---|---|---|---|---|
| S1 | Data layer | jOOQ with Flyway on JDBC | Compile-time SQL type safety; works with the RLS listener; migrations are plain SQL | Never | Accepted | — |
| S2 | Import idempotency | Unique `(statement_id, row_fingerprint)`, `ON CONFLICT DO NOTHING`, per-row results | Retries are free and one bad row never fails the statement | Bank sync arrives (use the bank's transaction ID for synced rows) | Proposed | [SDR-001](decision_records/SDR-001-import-idempotency.md) |
| S3 | Statement deletion | Foreign key `ON DELETE CASCADE` from transactions to statements | Atomic, and no future code path can delete a statement but leave its rows | Never | Accepted | — |
| S4 | Removing transactions | Only manual rows can be deleted; imported rows are excluded instead | The import stays an accurate record of the statement | Never | Accepted | — |
| S5 | Budget periods | One budget per month; past budgets closed by a scheduled job; reopen is explicit | Past months stay a stable record for comparisons | Users need to edit history often | Accepted | — |
| S6 | Current month | Resolved from the user's timezone in the verified context; the client doesn't pass it | One rule for every caller, and nothing extra to validate (D23) | Never | Proposed | — |

**Open questions**
- **Account numbers.** REQ-3.1 stores the full account number. Storing only the last four digits would remove the most sensitive field from the database, logs and backups (GLBA Safeguards). Confirm whether anything needs the full number.
- **Budget closing time.** The job closes budgets at 00:00 UTC on the 1st, which is still the last evening of the month for US users. Either run it daily and close a budget once its month has ended in that user's timezone, or accept the gap.

---

## 5. Related documents

- **App architecture:** [FinTracker architecture](../../fintracker-architecture/fintracker-architectural-doc.md).
- **Decisions:**
  - app-level: [ADR-001](../../fintracker-architecture/architectural_decision_records/ADR-001-user-id-denormalization.md), [ADR-002](../../fintracker-architecture/architectural_decision_records/ADR-002-rls-and-ownership-scoped-queries.md), [ADR-003](../../fintracker-architecture/architectural_decision_records/ADR-003-database-access-path.md), [ADR-005](../../fintracker-architecture/architectural_decision_records/ADR-005-statement-deletion-starts-in-ledger.md), [ADR-007](../../fintracker-architecture/architectural_decision_records/ADR-007-compute-per-profile.md), [ADR-009](../../fintracker-architecture/architectural_decision_records/ADR-009-ledger-event-publishing-outbox.md), [ADR-013](../../fintracker-architecture/architectural_decision_records/ADR-013-dashboard-reports-ownership.md), [ADR-014](../../fintracker-architecture/architectural_decision_records/ADR-014-ledger-reporting-views.md), [ADR-015](../../fintracker-architecture/architectural_decision_records/ADR-015-settings-in-verified-context.md);
  - service-level: [SDR-001](decision_records/SDR-001-import-idempotency.md).
- **Specs:**
  - [ledger-spec.md](../ledger-spec.md) (modules 1–6; parts superseded, see below);
  - [TXT-transaction-types-spec.md](../TXT-transaction-types-spec.md) (types, counting rules, current transaction schema);
  - [ledger-transaction-spec-01.md](../ledger-transaction-spec-01.md) (custom categories);
  - [ledger-budget-spec-01.md](../ledger-budget-spec-01.md) (budgets, templates, pacing);
  - [ledger-statement-spec-01.md](../ledger-statement-spec-01.md), [-02](../ledger-statement-spec-02.md), [-03](../ledger-statement-spec-03.md) (upload, import, duplicates);
  - [dp-ledger-categories-spec.md](../../fintracker-cross-services/dp-ledger-categories-spec.md) (categories with the Data pipeline).
- **Superseded in part:**
  - `ledger-schema.md` (old type and status values, no categories or `user_id`); TXT Appendix A and the Flyway migrations are current.
  - `ledger-spec.md` REQ-6.1 (Dashboard metrics) and REQ-4.3 (downloads); see D21 and the Document service.
  - `ledger-api-ui-mapping` (Dashboard charts now belong to Reports).
- **Diagram:** `images/ledger-components.svg`.
