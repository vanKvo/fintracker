# LG-READ: Internal Read Routes for the AI Assistant

| Field | Value |
|---|---|
| Product | FinTracker |
| Prefix | LG-READ |
| File | fintracker-ledger-doc/specs/LG-READ-internal-read-routes-spec.md |
| Owner | Van Vo |
| Status | Draft |
| Last updated | 2026-10-26 |

**Caller:** the AI assistant's chat tools `search_transactions` and `get_budget_status` (AI-CHAT-05, Appendix B). Mechanism: the `ledger-internal` API (ADR-004, ADR-011).

---

## 1. Overview

### Problem
Chat answers questions about the user's transactions and budgets from the Ledger, but no spec defines how. The AI assistant calls the Ledger's public routes (`GET /api/v1/ledger/transactions`, `GET /api/v1/ledger/budgets`) with a SigV4 signature and a forwarded `X-Internal-User-Id`. Those routes skip the caller check (`InternalCallerFilter` covers only `/internal/` paths) and trust that header because, in prod, only the gateway can reach them. A direct caller that can set the header could read any user's data. The search also pages through up to 1,000 rows to total the matches, and the totals are incomplete past that.

### Goals
- The AI assistant reads the Ledger only through internal routes behind the caller allow-list.
- Search totals cover every match, computed by the database in one query.
- Each call answers within the chat tool timeout (5 s, AI-CHAT-06) with time to spare.

### Non-Goals
- Write tools. Chat never changes Ledger data.
- Analytics figures (spending by category, cash flow): those are Analytics tools (AN-RPT-09).
- Exposing these routes to the web client.

### Design Principles
1. **Internal only.** These routes are under `/internal/` paths, so `InternalCallerFilter` checks the caller before anything runs, and the user comes from the signed context (XS-CTX-04). No route takes a user ID in its path, query or body.
2. **Same rules as the screens.** A transaction counts as spending exactly as in the reporting views (XS-RPTV Appendix B), and budget spend is the Budgets tab's figure (LG-BUD-05).
3. **Minimum data.** A row carries date, merchant, category and amount only (AI-GUARD).

---

## 2. Workflow

```
[AI assistant tool call, SigV4-signed, with the forwarded user context] ──► LG-READ-01
    │
[search_transactions → filtered rows plus totals] ──► LG-READ-02
[get_budget_status → one month's lines with limit, spent, remaining] ──► LG-READ-03
    │
[Invalid argument, no data, database down] ──► LG-READ-04
```

---

## 3. Requirements Index

| ID | Title | Area | Priority | Status |
|---|---|---|---|---|
| LG-READ-01 | Internal routes and caller check | Security | MVP | Implemented |
| LG-READ-02 | Transaction search with database totals | Data | MVP | Implemented |
| LG-READ-03 | Budget status for one month | Data | MVP | Implemented |
| LG-READ-04 | Errors and response time | Reliability | MVP | In progress (errors built; the 10,000-transaction load test is not run) |

---

## 4. Requirements

### LG-READ-01: Internal routes and caller check  `Priority: MVP`

**Requirement:** The Ledger serves `GET /api/v1/ledger/transactions/internal/search` and `GET /api/v1/ledger/budgets/internal/status` (Appendix A). Both are registered under `InternalCallerFilter`, whose allow-list includes the AI assistant's role, and they are exposed on `ledger-internal` with IAM authorization. The user comes from `X-Internal-User-Id`, and the timezone and currency from `X-User-Timezone` / `X-User-Currency` (XS-CTX-04, XS-CTX-05). The AI assistant calls only these routes, never a public Ledger route.
**Acceptance Criteria:**
- [Happy] A signed call from the AI assistant's role with user A's context returns only user A's data.
- [Fail] A call without the caller header, or from a role not on the allow-list, is rejected before any query runs (XS-CTX-04: 403).
- [Fail] A query parameter named `userId`, `user_id`, `timezone` or `currency` is rejected with 400 `invalid_argument`.
- [Fail] A test fails the build if the AI assistant's Ledger client calls any path without `/internal/`.
**Refs:** ADR-004; ADR-011; XS-CTX-04; `config/InternalCallerFilterConfig.java` (add the `/budgets/internal/*` pattern)

### LG-READ-02: Transaction search with database totals  `Priority: MVP`

**Requirement:** The search returns the user's spending rows that match every given filter: `merchant` (case-insensitive substring of the merchant name, at most 50 characters), `category` (the name of one of the user's active categories or an active SYSTEM category), and `start`/`end` (inclusive dates, at most 24 months apart; `end` defaults to today in the user's timezone, `start` to 12 months before `end`). A row matches only if it counts as spending in `rpt_transactions` (`counts = true` and `flow = 'SPEND'`), so pending, excluded and split-parent rows never match. The response holds the 25 newest matches plus `totalCount` and `totalAmount` over all matches, computed by the database in the same request.
**Acceptance Criteria:**
- [Happy] "Starbucks in the last 3 months" with 40 matches returns the 25 newest rows, `totalCount = 40` and the sum of all 40 amounts.
- [Alt] A pending row and an excluded row from that merchant are not in the rows or the totals.
- [Alt] No match returns `rows: []`, `totalCount = 0`, `totalAmount = 0.00`.
- [Fail] A range longer than 24 months, `start` after `end`, or an unknown category returns 400 `invalid_argument` naming the field.
**Refs:** AI-CHAT-05; XS-RPTV-01, Appendix B (counting rules); Appendix A

### LG-READ-03: Budget status for one month  `Priority: MVP`

**Requirement:** Budget status takes `month` (`YYYY-MM`; the current month in the user's timezone, or one of the 24 months before it; default the current month) and returns that month's budget lines, each with category, limit, spent and remaining (limit − spent, negative when over). Spent is computed exactly as the Budgets tab computes it (LG-BUD-05), so chat and the tab never disagree.
**Acceptance Criteria:**
- [Happy] For a month with a budget, every line's `spent` equals the Budgets tab's figure for that line.
- [Alt] A month with no budget returns 404 `budget_not_found`; the tool tells the model "No budget for that month".
- [Alt] An over-limit line has a negative `remaining`.
- [Fail] A month in the future or more than 24 months back returns 400 `invalid_argument`.
**Refs:** AI-CHAT-05; LG-BUD-04, LG-BUD-05; Appendix A

### LG-READ-04: Errors and response time  `Priority: MVP`

**Requirement:** Errors are RFC 9457 `application/problem+json` with the error catalog's codes. Each route answers within 1 s at p95 for a user with 10,000 transactions, using the per-user date index (XS-RPTV-06).
**Acceptance Criteria:**
- [Happy] A load test with 10,000 transactions for one user shows p95 under 1 s for both routes.
- [Fail] A database that can't be reached returns 503 `database_unavailable` with `retryable = true`; the tool tells the model the data is temporarily unavailable (AI-CHAT-05 Fail).
- [Fail] No response or log contains another user's data or the request's merchant text; logs carry the request ID, route, row count and duration only.
**Refs:** error catalog; app doc 4.8; XS-RPTV-06

---

## 5. Open Questions (consolidated)

| # | Question | Blocks |
|---|---|---|
| — | None | — |

---

## Appendix A: Contracts

Produced by: the Ledger (code). Consumed by: the AI assistant's tool clients.

`GET /api/v1/ledger/transactions/internal/search?merchant=starbucks&start=2026-07-01&end=2026-09-30`

```json
{
  "rows": [
    { "txDate": "2026-09-28", "merchant": "Starbucks", "category": "Food & Drink", "amount": "6.45" }
  ],
  "totalCount": 40,
  "totalAmount": "251.30",
  "currency": "USD"
}
```

`GET /api/v1/ledger/budgets/internal/status?month=2026-09`

```json
{
  "month": "2026-09",
  "lines": [
    { "categoryId": "…", "category": "Groceries", "limitAmount": "500.00", "spentAmount": "540.20", "remainingAmount": "-40.20" }
  ],
  "currency": "USD"
}
```

Amounts are decimal strings with 2 places, always positive except `remainingAmount`.
