# XS-RPTV: Ledger Reporting Views

| Field | Value |
|---|---|
| Product | FinTracker |
| Prefix | XS-RPTV |
| File | fintracker-cross-services/specs/XS-RPTV-ledger-reporting-views-spec.md |
| Owner | Van Vo |
| Status | Draft |
| Last updated | 2026-10-20 |

**Services:** Ledger (owns the views), Analytics (reads them). Decision record: [ADR-014](../../fintracker-architecture/architectural_decision_records/ADR-014-ledger-reporting-views.md).

---

## 1. Overview

### Problem
Analytics reads the Ledger's tables directly and repeats the rules for what counts as income and spending. The Ledger's Dashboard totals and budget spend repeat them a third time. The copies have already drifted: the Analytics Dashboard counted each account's balance once per transaction (bug of 2026-10-08), and a type rename would make Analytics' filters silently return zeros. Analytics also doesn't set the user context for Row-Level Security and connects with a direct database URL instead of the RDS Data API (extraction notes of 2026-10-18).

### Goals
- A month's income and spending are the same number on the Dashboard, in Reports, in budgets and in the Financial Summary.
- Analytics can read only what it needs: no account names, account numbers or other users' rows.
- Every Analytics query for one user's 24 months of history returns in under 300 ms at p95 (warm database).

### Non-Goals
- An Analytics-owned copy of Ledger data (Analytics SDR-001).
- New metrics. This spec changes where the numbers come from, not which numbers exist.
- Multi-currency conversion.

### Design Principles
1. **The Ledger owns the counting rules.** They live in one view definition, versioned in the Ledger's migrations.
2. **Views run as the caller.** `security_invoker = true`, so RLS on the base tables still applies.
3. **Least data at the database.** A view exposes only the columns a consumer needs.
4. **One contract, tested from both sides.** A breaking view change fails Analytics' CI before it ships.

---

## 2. Workflow

```
[Ledger migration creates the views, grants and index] ──► XS-RPTV-01 … XS-RPTV-06
    │
[Analytics request: one Data API transaction, set user context] ──► XS-RPTV-07
    │
[Queries read only ledger.rpt_* views] ──► XS-RPTV-05, XS-RPTV-07
    │
[Ledger Dashboard and budget spend read the same views] ──► XS-RPTV-08
    │
[CI contract test on every Ledger or Analytics change] ──► XS-RPTV-09
```

---

## 3. Requirements Index

| ID | Title | Area | Priority | Status |
|---|---|---|---|---|
| XS-RPTV-01 | Transactions view with counting fields | Data | MVP | Implemented |
| XS-RPTV-02 | Budget limits view | Data | MVP | Implemented |
| XS-RPTV-03 | Accounts view without identifying data | Security | MVP | Implemented |
| XS-RPTV-04 | Views run as the caller | Security | MVP | In progress |
| XS-RPTV-05 | Grants: views only | Security | MVP | Implemented |
| XS-RPTV-06 | Per-user date index | Performance | MVP | Implemented |
| XS-RPTV-07 | Analytics reads through the Data API with the user context | Security | MVP | Implemented |
| XS-RPTV-08 | The Ledger reads its own totals from the views | Data | MVP | Implemented |
| XS-RPTV-09 | Contract test and change rules | Quality | MVP | Implemented |

---

## 4. Requirements

### XS-RPTV-01: Transactions view with counting fields  `Priority: MVP`

**Requirement:** `ledger.rpt_transactions` exposes one row per non-deleted transaction with the columns in Appendix A, including `counts` and `flow`, derived by the rules in Appendix B. Amounts are always positive (LG-TXT-03); the direction of money is expressed by `flow`.
**Acceptance Criteria:**
- [Happy] A posted `EXPENSE` of $40 has `counts = true`, `flow = SPEND`, `amount = 40.00`; a posted `REFUND` of $10 has `flow = REFUND` and offsets spend in its category (LG-TXT-02).
- [Alt] `TRANSFER` and `ADJUSTMENT` rows have `flow = NONE` and `counts = false`; pending and excluded rows appear with `counts = false`, so data-quality counts still work.
- [Alt] A split parent has `counts = false` and its children count, so a split purchase is never counted twice.
- [Fail] Rows with status `DELETED` never appear in the view.
**Refs:** Appendix A; Appendix B; LG-TXT-01; LG-TXT-02; LG-CORE-2.2 (splits, exclusion)

### XS-RPTV-02: Budget limits view  `Priority: MVP`

**Requirement:** `ledger.rpt_budget_limits` exposes, per user, month and category, the limit of the latest budget version for that month (Appendix A).
**Acceptance Criteria:**
- [Happy] A budget for 2026-10 with a $300 Food line returns one row: month 2026-10-01, Food's `category_id`, 300.00.
- [Alt] When a month has several budget versions, only the latest version's lines appear.
- [Alt] Lines are matched to transactions by `category_id`. Until budget lines store `category_id` (LG-CAT-01, item 8), the view resolves it from the category name, case-insensitively.
- [Fail] A line whose category name resolves to no category appears with `category_id` null and is reported as unbudgeted spend, never dropped silently.
**Refs:** Appendix A; LG-BUD-01; LG-CAT-01

### XS-RPTV-03: Accounts view without identifying data  `Priority: MVP`

**Requirement:** `ledger.rpt_accounts` exposes each account's opaque reference, type, sync mode, last synced time, creation time and latest transaction date. It never exposes the account name, number, owner name or balance.
**Acceptance Criteria:**
- [Happy] The view has exactly the columns in Appendix A.
- [Alt] An account with no transactions has `latest_tx_date` null.
- [Fail] A schema test fails the build if any column named like `name`, `number`, `owner` or `balance` is added to the view.
**Refs:** Appendix A; AN-FS-23 (stale and incomplete-account flags)

### XS-RPTV-04: Views run as the caller  `Priority: MVP`

**Requirement:** Every `rpt_*` view is created `WITH (security_invoker = true)`, so the RLS policies on the base tables apply to the role and user context of the session. The migration fails on PostgreSQL versions below 15.
**Acceptance Criteria:**
- [Happy] As Analytics' role with user A's context set, `rpt_transactions` returns only user A's rows.
- [Alt] With no user context set, every view returns zero rows.
- [Fail] The isolation test suite (ADR-002) includes the three views, seeded with two users, and fails if any view returns the other user's rows.
**Refs:** ADR-002; ADR-014

### XS-RPTV-05: Grants: views only  `Priority: MVP`

**Requirement:** Analytics' read-only database role has `SELECT` on the three `rpt_*` views and no privilege on any `ledger` base table. Earlier base-table grants to that role are revoked in the same migration.
**Acceptance Criteria:**
- [Happy] `SELECT` on `ledger.rpt_transactions` as Analytics' role succeeds.
- [Fail] `SELECT` on `ledger.transactions` or `ledger.accounts` as Analytics' role fails with a permission error.
- [Fail] Any `INSERT`, `UPDATE` or `DELETE` through the views fails for Analytics' role.
**Refs:** app doc invariant 1; ADR-014

### XS-RPTV-06: Per-user date index  `Priority: MVP`

**Requirement:** The Ledger adds an index on `ledger.transactions (user_id, tx_date)` for rows whose status isn't `DELETED`, so every reporting query scans one user's date range.
**Acceptance Criteria:**
- [Happy] `EXPLAIN` of a one-month aggregate over `rpt_transactions` for one user shows an index scan on the new index.
- [Alt] With 5,000 transactions for one user across 24 months, each Analytics aggregate in AN-RPT runs in under 300 ms at p95 on a warm database.
- [Fail] A migration test fails if the index is missing.
**Refs:** AN-RPT-03

### XS-RPTV-07: Analytics reads through the Data API with the user context  `Priority: MVP`

**Requirement:** Analytics reads Ledger data only through the RDS Data API. Each request opens one transaction, sets `app.current_user_id` with `set_config(..., true)`, runs its queries against `rpt_*` views only, and commits. The direct database URL path is removed, except for local development (`APP_ENV=local`), which uses a local connection with the same transaction rule.
**Acceptance Criteria:**
- [Happy] A Reports request issues one `BeginTransaction`, one `set_config`, its queries and one `CommitTransaction`.
- [Alt] Local development runs the same queries against local PostgreSQL, through an adapter that also sets the context in the same transaction.
- [Fail] A query that names a base table (`ledger.transactions` and so on) fails a static check in Analytics' CI.
- [Fail] Aurora resuming from pause (dev) is retried once after 2 s; a second failure returns a retryable error to the caller.
**Refs:** ADR-003; ADR-014; Analytics architecture 3.2

### XS-RPTV-08: The Ledger reads its own totals from the views  `Priority: MVP`

**Requirement:** The Ledger's Dashboard income, expenses and net, its budget spend (`spentAmount`, LG-BUD-04) and its budget alerts are computed from `rpt_transactions` with `counts = true` in the primary currency, replacing the separate `sumMonthlyIncome` and `sumMonthlyExpenses` queries.
**Acceptance Criteria:**
- [Happy] For the same fixture month, Ledger Dashboard expenses equal Analytics' monthly expenses for that month (AN-RPT-04).
- [Alt] A $10 refund in Food lowers both Food's budget spend and Dashboard expenses by $10.
- [Fail] A transfer between the user's own accounts changes neither expenses nor income.
**Refs:** ADR-013; LG-BUD-04; LG-CORE-6.1

### XS-RPTV-09: Contract test and change rules  `Priority: MVP`

**Requirement:** A shared fixture (two users, every transaction type, a split, a refund, pending and excluded rows, two currencies) is loaded into PostgreSQL migrated with the Ledger's Flyway scripts. Analytics' CI runs its queries against it and checks the expected results in Appendix C. Removing a column or changing the meaning of `counts` or `flow` is a breaking change that needs a new view name.
**Acceptance Criteria:**
- [Happy] The contract test passes in both the Ledger's and Analytics' CI.
- [Alt] Adding a column to a view is not breaking and needs no Analytics change.
- [Fail] A Ledger migration that changes a counting rule fails Analytics' contract test before merge.
**Refs:** Appendix C; ADR-014 Decision 6

---

## 5. Open Questions (consolidated)

None.

---

## Appendix A: View columns

Produced by: Ledger Flyway migrations (code).

**`ledger.rpt_transactions`**

| Column | Type | Notes |
|---|---|---|
| `transaction_id` | uuid | |
| `account_ref` | uuid | The account ID, used as an opaque reference |
| `tx_date` | date | Calendar date from the source (app doc D24) |
| `amount` | numeric(15,2) | Always positive (LG-TXT-03) |
| `currency` | char(3) | ISO 4217 |
| `type` | text | `EXPENSE`, `INCOME`, `REFUND`, `TRANSFER`, `ADJUSTMENT` |
| `flow` | text | `INCOME`, `SPEND`, `REFUND`, `NONE` (Appendix B) |
| `counts` | boolean | Appendix B |
| `status` | text | `PENDING`, `POSTED` |
| `is_excluded` | boolean | |
| `category_id` | uuid | |
| `category_name` | text | Display name |
| `merchant` | text | Normalized merchant name |
| `merchant_key` | text | Stable key for grouping (XS-DPCAT-04) |
| `description` | text | Raw description; read only by the fee detector (AN-FS-25), never sent to an LLM |
| `is_split_parent` | boolean | |

**`ledger.rpt_budget_limits`**: `month` (date, 1st of month), `category_id` (uuid, nullable), `category_name` (text), `limit_amount` (numeric(15,2)).

**`ledger.rpt_accounts`**: `account_ref` (uuid), `account_type` (text), `sync_mode` (text), `last_synced_at` (timestamptz, nullable), `created_at` (timestamptz), `latest_tx_date` (date, nullable).

---

## Appendix B: Counting rules

| Condition | `flow` | `counts` |
|---|---|---|
| `type = EXPENSE` | `SPEND` | true when `POSTED`, not excluded, not a split parent |
| `type = REFUND` | `REFUND` | same as above; offsets spend in its category |
| `type = INCOME` | `INCOME` | same as above |
| `type = TRANSFER` or `ADJUSTMENT` | `NONE` | false |
| `status = PENDING`, or `is_excluded`, or a split parent | (by type) | false |

Consumers filter the primary currency themselves (`currency = <context currency>`).

---

## Appendix C: Contract fixture results

| Check | Expected |
|---|---|
| User A, 2026-09: income | 5,000.00 |
| User A, 2026-09: spend net of refunds | 1,840.00 |
| User A, 2026-09: Food spend | 310.00 (350.00 expense − 40.00 refund) |
| User A, 2026-09: other-currency rows | 1, `counts = true`, excluded by the consumer's currency filter |
| User A, rows visible with user B's context | 0 |
| Split parent of $120 with children $70 + $50 | parent `counts = false`; children total 120.00 |
