# Analytics Architecture

| Status | Owner | Last reviewed | Applies to | App architecture |
|---|---|---|---|---|
| Proposed: final design before implementation (AI already moved to the AI assistant) | Van Vo | 2026-10-20 | main | [FinTracker architecture](../../fintracker-architecture/fintracker-architectural-doc.md) |

This document describes the complete design of Analytics: the Dashboard and Reports widgets it serves, how it reads Ledger data, and the workflows it runs. Rules that apply to every service are in the app architecture doc. These include identity, events and invariants. Formulas, thresholds and the facts payload schema live in [FS: Financial Summary](../FS-financial-summary-spec.md): Appendix A, plus FS-03 to FS-08, FS-19 and FS-23 to FS-30.

---

## 1. Overview

**Purpose:** Analytics is FinTracker's metrics and detection engine. It turns Ledger history into numbers and detected patterns with deterministic code. It is a separate service because cross-period analysis is read-heavy, and it keeps that work and its rules out of the Ledger's write path.

**Responsibilities**

| Widget | Tab | Section | Period |
|---|---|---|---|
| Spending pace | Dashboard | Spending so far this month vs the same days last month | This month to date |
| Financial Summary | Reports | Facts payload, which the AI assistant explains | Reports period selector: Last month, Last 3 months, Year to date, Last 12 months |
| Income vs expenses | Reports | Income and expenses for each month | Last 12 complete months |
| Spending by category | Reports | Every category's spend, with change vs the comparison period | Reports period selector |
| Category trends | Reports | Each category's spend for each month | Last 12 complete months |
| Top merchants | Reports | Merchants ranked by spend, with transaction count | Reports period selector |

It also runs the Financial Summary detectors and serves read-only internal routes to the AI assistant.

**Does not do**
- Dashboard totals, data-through date, budget alerts, bills or recent transactions. The Ledger serves these (app doc D21).
- Call an LLM, build prompts, cache summaries, control LLM cost or audit AI output. The AI assistant does all of these.
- Look up user settings. Timezone and primary currency arrive in the verified user context (app doc D23).
- Convert currencies. Only the user's primary currency counts (S8).
- Write financial data (Ledger) or parse statements (Data pipeline).

**Owns**
- No persistent data (S6). It reads Ledger-owned reporting views through a read-only role.

---

## 2. Architecture and workflows

![Analytics components](images/analytics-components.svg)

**How to read the diagram**
- Two front doors share one engine:
  - the **public API** for the web client, behind the gateway's identity authorizer;
  - the **internal API** for the AI assistant, signed with IAM and checked against a caller allow-list.
- Every request runs the numbered steps in one registry of read-only functions with the shape `(ctx, period) → section`. The same function serves a Reports chart, the facts payload and a chat tool, so a number is computed one way everywhere.
- Step 3 is the only step that touches the database. It reads Ledger-owned **reporting views**, never the Ledger's tables (app doc D22).
- Step 5a covers every widget in the table above. Step 5b runs only for the facts payload.

### How Analytics reads Ledger data

Each person's history is small: at most a few thousand transactions over the 24 months the detectors look at. One indexed query over that is fast, so Analytics computes on read and stores nothing (S6).

1. **One read contract, owned by the Ledger.** The Ledger publishes reporting views over its transactions, monthly budget limits and accounts. Each transaction row carries counting fields: whether it counts, and whether it is income, spending or a refund offset (TXT-02). The views use `security_invoker`, so Row-Level Security still applies. They leave out account names, account numbers and every other column Analytics doesn't use.
2. **One definition of income and spending.** The Ledger's Dashboard totals and budget alerts read the same views. October's spending is therefore the same number on the Dashboard, in Reports and in the Financial Summary.
3. **Aggregate in the database.** Widget sections run a `GROUP BY` query and get back a few dozen rows, well under the Data API's 1 MiB limit.
4. **Row-level reads only for detectors.** Detectors need individual transactions, such as medians, 48-hour duplicates and first-seen merchants. They fetch only the columns they use, paged by date.
5. **One Data API transaction per request.** Begin, set the user context, run the request's queries, then commit. The `/reports` route fetches all four chart sections in one transaction. The Data API cost is cents per month.
6. **One index makes every query a range scan.** The Ledger adds a partial index on `(user_id, tx_date)` for non-deleted rows.

### Workflows

#### Serve spending pace

**Trigger:** `GET /dashboard/spending-pace` from the Dashboard · **Result:** spending so far this month, the same days last month, and the difference · **On failure:** a retryable error; only the spending-pace card shows its error state, and the Ledger's widgets are unaffected

1. Resolve the context: user, timezone and primary currency.
2. Resolve "today" in the user's timezone, then this month to date and the same day range last month (FS-03).
3. Run one aggregate query over the counted spending rows for both ranges.
4. Return both totals, the difference, and the pending count, so the client can show that pending rows aren't included yet.

#### Serve Reports sections

**Trigger:** `GET /reports?period` from the Reports tab · **Result:** the four chart sections in one response · **On failure:** a section that fails is `null` with a reason, and the others still render

1. Resolve the context and the period. The period is the Reports selector, which also drives the Financial Summary. Both trend charts always use the last 12 complete months, so the current month never appears in Reports except inside Year to date.
2. In one Data API transaction, run four aggregate queries:
   - income and expenses by month;
   - spend by category for the period and for the comparison period;
   - spend by category by month, for every category, so switching categories in the trend chart needs no new request;
   - top merchants by spend, with transaction count.
3. Apply the counting rules and data-quality flags, then return.

#### Build the facts payload

**Trigger:**
- `GET /facts?period` from the Reports tab, so the summary's numbers render first;
- the internal facts route, called by the AI assistant for the Financial Summary.

**Result:** a facts payload that validates against Appendix A, plus its `facts_hash`. **On failure:** an error the caller shows. The AI assistant then does not call the LLM.

![Facts payload workflow](images/analytics-facts-payload.svg)

1. Receive the request, from the public route or the internal route.
2. Resolve the context, from the authorizer context (public) or the signed user context (internal).
3. Resolve the period and its comparison period (FS-03).
4. Load the aggregates, plus the detector rows for the period and the 12 months before it.
5. Apply the counting rules (FS-23): primary currency only. Record data-quality flags for pending rows, adjustments, other currencies, and stale or incomplete accounts.
6. Compute the metric sections. A section without data becomes `null` with a reason flag.
7. Run the detectors. A detector that errors is logged, skipped and listed in `data_quality.skipped_detectors`.
8. Score and rank the candidates: score = impact ÷ $100, capped at 1. The top 8 become `cand_1` … `cand_8`.
9. Assemble the payload and validate it against the schema.
10. Compute `facts_hash` and return it with the payload.

#### Serve section tools to the AI assistant *(chat, proposed)*

**Trigger:** a signed internal request from the AI assistant's `execute_tool` · **Result:** one section for the user in the request context · **On failure:** a generic error message, never raw exception text

1. Check that the caller's IAM role is on the allow-list.
2. Validate the arguments: enums, period at most 24 months, no extra fields.
3. Run the same registry function the Reports tab and the facts payload use, and return the section.

---

## 3. Concepts of Operation

### 3.1 Enter: what does this service expose and consume?

| Interface | Type | Caller | Purpose |
|---|---|---|---|
| `GET /dashboard/spending-pace` | Public API (gateway) | Web client | Dashboard spending-pace card |
| `GET /reports?period` | Public API (gateway) | Web client | Income vs expenses, category breakdown, category trends, top merchants |
| `GET /summary/periods` | Public API (gateway) | Web client | Selectable Reports periods |
| `GET /facts?period` | Public API (gateway) | Web client | Facts payload, so summary numbers render before the AI text |
| Internal facts route | Internal API (IAM) | AI assistant | Facts payload and `facts_hash` for the Financial Summary |
| Internal section routes *(proposed)* | Internal API (IAM) | AI assistant | One route per section, used as chat tools |

There are no events and no scheduled jobs. Everything is computed on request. Route names here are indicative; the contract files are authoritative.

### 3.2 Trust: who may call it, and how is each request scoped to a user?

- **Context comes only from verified sources.**
  - Public routes: `userId`, timezone and primary currency come from the identity authorizer's context. User profile owns the authorizer and attaches the settings with the `userId` (app doc D23).
  - Internal routes: the same fields come from the signed user context the AI assistant forwards.
  - Values in query strings, headers, bodies or tool arguments are ignored.
- **Settings are validated.** Timezone must be an IANA name and currency an ISO 4217 code. If either is missing or invalid, the request fails closed with a retryable error. Analytics never falls back to UTC or USD.
- **Input validation:** periods are enums, unknown parameters are rejected, and internal requests allow at most 24 months.
- **Internal routes:** only allow-listed IAM roles may call them; today that is only the AI assistant.
- **Database:**
  - The read-only role has `SELECT` on the Ledger's reporting views only, with no grants on base tables.
  - The user context is set inside every Data API transaction, and a session with no user set sees no rows.
  - Analytics' IAM policy allows the Data API only on the Ledger cluster and its one secret.
- **Local development:** `LOCAL_DEV_USER_ID` is honoured only when `APP_ENV=local`.

### 3.3 Flow: how does it depend on other services?

| Depends on | How | Why | If unavailable |
|---|---|---|---|
| Ledger database | RDS Data API, read-only role, Ledger's reporting views | All transaction, budget and account data | Wait out the Aurora resume in dev (timeout above 30 s, one retry), then return a retryable error. The Ledger's Dashboard widgets are unaffected |
| Ledger reporting views | Read contract, versioned in the Ledger's migrations | One definition of what counts as income and spending | A breaking change fails Analytics' contract tests in CI before it ships |
| User profile | Indirect: its identity authorizer attaches the settings | Timezone and primary currency | If the authorizer fails, the gateway rejects the request. Analytics makes no call of its own |

Analytics calls no other service at runtime and never calls the AI assistant.

### 3.4 Store: what data does it keep, and for how long?

| Data | Store | Retention | On account deletion |
|---|---|---|---|
| None | — | — | Nothing to delete |

There is no settings cache either, because settings arrive with every request. The summary cache, audit records, payload snapshots and usage counters belong to the AI assistant.

### 3.5 Protect: what does this service guard beyond the app-level rules?

- **Read-only by construction:** the role can't write, it can only read the views, and every registry function is read-only.
- **Minimum data, enforced in the database:** account names and numbers never reach Analytics, because the views don't include them.
- **Payload allowlist:**
  - The facts payload never contains account numbers, raw descriptions, names, emails, bank names or account nicknames.
  - Accounts appear only as an opaque `account_ref`.
  - Merchant names are normalized and are the only free text. Raw descriptions are read only by the fee detector's keyword match and never leave it.
- **Contract tests against the reporting views:** a silent mismatch is the main risk. If counting rules drifted from the Ledger's transaction types, Analytics would return zeros that the AI would then explain confidently.
- **Fail closed on missing settings:** a wrong currency or timezone produces numbers that look right, so a missing setting is an error, never a default.
- **Error hygiene:** callers, including the model through tools, get generic error messages. Details go to the logs, which never contain financial values.

### 3.6 Recover: how does it fail, and how does it recover?

- **Sections fail independently:** a failing Reports section is `null` with a reason, and the other sections still render.
- **Detector errors are isolated:** a failing detector is skipped and listed, and the payload is still produced.
- **Missing data degrades gracefully:** a section without data is `null` with a reason flag, such as `no_budgets`, instead of an error.
- **Facts engine failure:** the caller shows an error state, and the AI assistant does not call the LLM.
- **Analytics down:** the Dashboard still shows every Ledger widget. Only the spending-pace card and Reports show errors.
- **Stateless:** recovery is a redeploy. There is nothing to restore or replay.

### 3.7 Observe: how do we know it is healthy?

- Latency and error rate per route, with alarms on `/reports` and `/facts` (the Reports tab's critical path).
- Data API calls and query time per request, plus retries caused by Aurora resuming in dev.
- Requests rejected for missing or invalid settings. This should be zero, and any count means the authorizer contract broke.
- Detector errors and skips, by detector.
- Contract-test results in CI.

---

## 4. Service decisions

Cross-service decisions this service applies are in the app architecture doc: D4 (only the AI assistant calls an LLM), D5 (Data API access), D21 (Dashboard and Reports ownership), D22 (reporting views), D23 (settings in the verified context) and D24 (calendar dates).

| # | Decision | Choice | Why | Revisit when | Status | Record |
|---|---|---|---|---|---|---|
| S1 | No AI in Analytics | Deterministic code only; every LLM concern lives in the AI assistant | Numbers stay testable and auditable; one place for AI risk (app doc D4) | Never | Accepted | — |
| S2 | One registry of read-only section functions | `(ctx, period) → section`, shared by the Reports widgets, the facts payload and chat tools | A metric is computed one way everywhere; tools need no separate logic | Never | Accepted | — |
| S3 | `facts_hash` | Hash of the assembled payload, returned with it | Lets the AI assistant cache by content, so new transactions invalidate the summary automatically | Never | Accepted | — |
| S4 | Detector thresholds | Config values, with unit tests on a positive and a negative fixture per detector | Tunable without code changes; each detector is proven both ways | Never | Accepted | — |
| S5 | Reports periods | Last month (default), Last 3 months, Year to date, Last 12 months; trend charts use the last 12 complete months. No *This month* | The Dashboard owns the current month (D21); complete months compare like with like | Never | Accepted | — |
| S6 | Storage | Stateless: compute on read from the Ledger's reporting views | A person's history is small enough for indexed SQL; a copy adds sync, invalidation and deletion work | Reports latency or Analytics' Aurora load becomes material | Proposed | [SDR-001](decision_records/SDR-001-compute-on-read.md) |
| S7 | Reports request shape | One `GET /reports` returns all four chart sections; a failed section is `null` with a reason | One Data API transaction and one cold start per page load; sections still fail independently | A section becomes slow enough to delay the others | Proposed | — |
| S8 | Currency | Primary currency only; other currencies are excluded and flagged (FS-23) | No FX rates to source, store or explain | Multi-currency accounts are supported | Accepted | — |

**Open question:** with no FX, changing the primary currency in Settings would exclude every existing transaction. Lock it to the accounts' currency until multi-currency is supported; this is a User profile and UI decision.

---

## 5. Related documents

- **App architecture:** [FinTracker architecture](../../fintracker-architecture/fintracker-architectural-doc.md).
- **Decisions:** app-level [ADR-013](../../fintracker-architecture/architectural_decision_records/ADR-013-dashboard-reports-ownership.md), [ADR-014](../../fintracker-architecture/architectural_decision_records/ADR-014-ledger-reporting-views.md), [ADR-015](../../fintracker-architecture/architectural_decision_records/ADR-015-settings-in-verified-context.md); service-level [SDR-001](decision_records/SDR-001-compute-on-read.md).
- **Ledger** (publishes the reporting views Analytics reads): [ledger-architecture.md](../../fintracker-ledger-doc/architecture/ledger-architecture.md).
- **AI assistant** (the main consumer of the facts payload): [ai-assistant-architecture.md](../../fintracker-ai-assistant/architecture/ai-assistant-architecture.md).
- **Specs:**
  - [FS: Financial Summary](../FS-financial-summary-spec.md). Analytics owns FS-01 (periods API), FS-02 for its own routes, FS-03 to FS-08, FS-19, FS-23 to FS-30, the section functions in FS-09, and Appendix A. The AI assistant owns the rest.
  - [TXT: Transaction types](../../fintracker-ledger-doc/TXT-transaction-types-spec.md), which defines what counts as income, spending and refunds.
- **Superseded:** [ai-integration-architecture.md](ai-integration-architecture.md) and [ai-governance-monitoring.md](ai-governance-monitoring.md), which describe AI inside Analytics. Their content now lives in the AI assistant doc.
- **Diagram sources:** `images/analytics-components.svg`, `images/analytics-facts-payload.svg`.
