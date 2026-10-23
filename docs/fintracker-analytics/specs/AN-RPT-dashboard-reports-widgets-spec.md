# AN-RPT: Dashboard and Reports Widgets

| Field | Value |
|---|---|
| Product | FinTracker Analytics |
| Prefix | AN-RPT |
| File | fintracker-analytics/specs/AN-RPT-dashboard-reports-widgets-spec.md |
| Owner | Van Vo |
| Status | Draft |
| Last updated | 2026-10-20 |

---

## 1. Overview

### Problem
The Dashboard shows where the user stands this month but not whether they're on track, and the Reports tab has no charts beyond the Financial Summary. Users can't see how this month compares with last month so far, how income and spending moved over the year, which categories changed, or who gets most of their money.

### Goals
- The spending-pace card loads in under 500 ms at p95 (warm), independently of the Ledger's Dashboard widgets.
- The four Reports charts load in one request, in under 1 s at p95 (warm).
- Every figure matches the Dashboard, budgets and the Financial Summary for the same month and period.

### Non-Goals
- Dashboard totals, data-through date, budget alerts, bills and recent transactions: the Ledger serves them (ADR-013).
- *This month* in Reports: the Dashboard owns the current month (AN-FS-01, ADR-013).
- Savings-rate trend, budget performance history, export and multi-currency conversion.

### Design Principles
1. **Compute on read.** Every section is an aggregate query over the Ledger's reporting views; Analytics stores nothing (Analytics SDR-001, XS-RPTV).
2. **One counting rule set.** Income and spending use `rpt_transactions` with `counts = true`, in the primary currency (XS-RPTV-01).
3. **One function per section.** Each section is a registry function `(ctx, period) → section`, reused by chat tools (AN-FS-09).
4. **Settings from the verified context.** Timezone decides "today"; currency decides what counts (XS-CTX-05). There is no default.
5. **Sections fail alone.** A failed section is `null` with a reason; the others still render.

---

## 2. Workflow

```
[Dashboard loads → GET /dashboard/spending-pace] ──► AN-RPT-02
    │
[Reports loads → period selector → GET /reports?period] ──► AN-RPT-01, AN-RPT-03
    │
[Resolve context and period; one Data API transaction] ──► AN-RPT-03
    │
[Sections: income vs expenses, categories, trends, merchants] ──► AN-RPT-04 … AN-RPT-07
    │
[Counting rules and data-quality flags] ──► AN-RPT-08
    │
[Same functions exposed as chat tools] ──► AN-RPT-09
    │
[Old Dashboard routes removed] ──► AN-RPT-10
    │
[Failure at any step → section null + reason, or retryable error] ──► AN-RPT-11
```

---

## 3. Requirements Index

| ID | Title | Area | Priority | Status |
|---|---|---|---|---|
| AN-RPT-01 | Reports period selector | UI | MVP | Implemented |
| AN-RPT-02 | Spending pace | Data | MVP | Implemented |
| AN-RPT-03 | One Reports request | Performance | MVP | Implemented |
| AN-RPT-04 | Income vs expenses by month | Data | MVP | Implemented |
| AN-RPT-05 | Spending by category vs the comparison period | Data | MVP | Implemented |
| AN-RPT-06 | Category trends | Data | MVP | Implemented |
| AN-RPT-07 | Top merchants | Data | MVP | Implemented |
| AN-RPT-08 | Counting rules and data quality | Data | MVP | Implemented |
| AN-RPT-09 | Sections as chat tools | AI integration | MVP | Proposed |
| AN-RPT-10 | Remove Analytics Dashboard totals | Data | MVP | Implemented |
| AN-RPT-11 | Failure handling and observability | Reliability | MVP | Implemented |

---

## 4. Requirements

### AN-RPT-01: Reports period selector  `Priority: MVP`

**Requirement:** One period selector at the top of the Reports tab drives the Financial Summary, spending by category and top merchants. It uses the AN-FS-01 periods and comparison rules. The two trend charts always show the last 12 complete months, whatever is selected.
**Acceptance Criteria:**
- [Happy] The default is *Last month*; choosing *Last 3 months* reloads the summary, categories and merchants, and the label reads "Jul–Sep 2026 vs. Apr–Jun 2026".
- [Alt] Periods with no counted transactions are disabled, as in AN-FS-01.
- [Fail] If `/reports` fails, the previous charts stay visible with an inline error and a Retry button; the Financial Summary loads on its own.
**Refs:** AN-FS-01; AN-FS-03

### AN-RPT-02: Spending pace  `Priority: MVP`

**Requirement:** `GET /dashboard/spending-pace` returns spending so far this month and spending over the same day range last month (AN-FS-03's month-to-date rule), the difference, and the pending count. "Today" is the date in the context timezone.
**Acceptance Criteria:**
- [Happy] On Oct 20, with $1,840 spent Oct 1–20 and $2,100 spent Sep 1–20, the response has `spent 1840.00`, `comparison 2100.00`, `abs_change −260.00`, `pct_change −12.4`.
- [Alt] On the 31st, the comparison range ends on the last day of the shorter previous month (AN-FS-03).
- [Alt] With no spending last month to date, `pct_change` is `null` and the flag `no_comparison_data` is set; on the 1st, both totals cover one day.
- [Alt] `pending_count` is the number of pending rows dated this month, so the card can say "12 awaiting approval aren't included".
- [Fail] A missing timezone returns 409 `user_settings_incomplete` (XS-CTX-05); any other failure returns a retryable error and only this card shows its error state.
**Refs:** Appendix A; AN-FS-03; XS-CTX-05

### AN-RPT-03: One Reports request  `Priority: MVP`

**Requirement:** `GET /reports?period=<key>` returns the four chart sections in one response (Appendix A), computed in one Data API transaction (XS-RPTV-07). The period key must be one of the AN-FS-01 keys.
**Acceptance Criteria:**
- [Happy] The response has `period`, `comparison_period`, `currency`, `data_quality` and the four sections.
- [Happy] p95 latency is under 1 s with a warm database and 5,000 transactions over 24 months.
- [Fail] An unknown period key, or any extra query parameter, returns 400 `invalid_argument`.
**Refs:** Appendix A; XS-RPTV-06; XS-RPTV-07

### AN-RPT-04: Income vs expenses by month  `Priority: MVP`

**Requirement:** The `monthly_cash_flow` section returns income, expenses (spend net of refunds) and net for each of the last 12 complete months, oldest first.
**Acceptance Criteria:**
- [Happy] On 2026-10-20 the section covers 2025-10 through 2026-09, 12 entries.
- [Alt] A month with no counted rows has zeros and `has_data: false`, so the chart can show a gap instead of a dip.
- [Alt] Expenses for a month equal the Ledger Dashboard's expenses for that month (XS-RPTV-08).
**Refs:** Appendix A; LG-TXT-02

### AN-RPT-05: Spending by category vs the comparison period  `Priority: MVP`

**Requirement:** The `categories` section lists every category with spend in the selected or the comparison period: amount, previous amount, absolute change and percent change, sorted by amount, highest first. Refunds offset their category.
**Acceptance Criteria:**
- [Happy] Food $310 now and $250 before shows `abs_change 60.00`, `pct_change 24.0`.
- [Alt] A category with spend only in the comparison period appears with `amount 0.00`; one with no previous spend has `pct_change: null`.
- [Alt] Net refunds larger than spend show a negative amount, never counted as income (LG-TXT-02).
- [Alt] Uncategorized spend is its own row.
**Refs:** Appendix A; AN-FS-05 (the facts payload keeps its top 3 from this same function)

### AN-RPT-06: Category trends  `Priority: MVP`

**Requirement:** The `category_trends` section returns, for every category with spend in the last 12 complete months, its spend in each of those months, aligned to the same 12 months as AN-RPT-04.
**Acceptance Criteria:**
- [Happy] Each category has exactly 12 values, oldest first; a month without spend is 0.
- [Alt] Switching categories in the chart needs no new request.
- [Alt] Categories with zero spend in all 12 months are left out.
**Refs:** Appendix A

### AN-RPT-07: Top merchants  `Priority: MVP`

**Requirement:** The `top_merchants` section returns the 10 merchants with the highest spend in the selected period: display name, spend net of refunds, transaction count and share of total spend. Merchants are grouped by `merchant_key`.
**Acceptance Criteria:**
- [Happy] A merchant with 14 purchases totalling $420 out of $2,100 spend shows `count 14`, `share_pct 20.0`.
- [Alt] Ties are broken by name; fewer than 10 merchants returns as many as exist.
- [Alt] A merchant whose refunds exceed its purchases is left out.
**Refs:** Appendix A; XS-RPTV-01 (`merchant_key`)

### AN-RPT-08: Counting rules and data quality  `Priority: MVP`

**Requirement:** Every section counts only `rpt_transactions` rows with `counts = true` in the context currency. The response's `data_quality` block reports the pending count and any `excluded_currency:<code>` flags for the period, using AN-FS-23's flag names.
**Acceptance Criteria:**
- [Happy] A transfer and an adjustment in the period change no section.
- [Alt] Three pending rows in the period give `pending_count: 3` and change no total.
- [Alt] A euro transaction in the period sets `excluded_currency:EUR` and is left out of every total.
**Refs:** XS-RPTV-01; AN-FS-23

### AN-RPT-09: Sections as chat tools  `Priority: MVP`

**Requirement:** The functions behind AN-RPT-02 and AN-RPT-04 to AN-RPT-07 are registered in the AN-FS-09 registry and served on the internal API as one route per section, for the AI assistant's chat tools (AI-CHAT-05). Internal calls take the user and settings only from the signed context (XS-CTX-04).
**Acceptance Criteria:**
- [Happy] The internal `category_trends` route returns the same values as the public `/reports` section for the same user.
- [Alt] Internal routes accept a period of at most 24 months and no other arguments.
- [Fail] A call from a role not on the allow-list returns 403; a body containing `user_id` returns 400.
**Refs:** AN-FS-09; AI-CHAT-05; XS-CTX-04

### AN-RPT-10: Remove Analytics Dashboard totals  `Priority: MVP`

**Requirement:** Analytics no longer serves Dashboard totals. The old dashboard overview and safe-to-spend routes, their queries and their tests are removed (ADR-013).
**Acceptance Criteria:**
- [Happy] The public API has `/dashboard/spending-pace` and no other dashboard route.
- [Fail] A request to a removed route returns 404.
**Refs:** ADR-013; bug of 2026-10-08 (balance counted per transaction)

### AN-RPT-11: Failure handling and observability  `Priority: MVP`

**Requirement:** A section whose query fails is returned as `null` with `reason`, and the others are returned. A database failure before any section runs returns 503 `database_unavailable` after one retry (XS-RPTV-07). Logs and metrics carry route, period, section, latency and error code, never amounts or merchant names.
**Acceptance Criteria:**
- [Happy] A dashboard shows p50/p95 latency and error rate per route and per section.
- [Alt] If the top-merchants query fails, the response has `top_merchants: { "data": null, "reason": "query_failed" }` and three good sections.
- [Fail] A log-scan test with a unique merchant name finds it in no log line.
**Refs:** Analytics architecture 3.6–3.7

---

## 5. Open Questions (consolidated)

None.

---

## Appendix A: Response shapes

Produced by: Analytics (code). Amounts are strings with 2 decimals; percentages have 1 decimal or are `null`.

**`GET /dashboard/spending-pace`**

```json
{
  "as_of": "2026-10-20",
  "range": { "start": "2026-10-01", "end": "2026-10-20" },
  "comparison_range": { "start": "2026-09-01", "end": "2026-09-20" },
  "currency": "USD",
  "spent": "1840.00",
  "comparison": "2100.00",
  "abs_change": "-260.00",
  "pct_change": -12.4,
  "pending_count": 12,
  "flags": []
}
```

**`GET /reports?period=last_3_months`**

```json
{
  "period": { "key": "last_3_months", "start": "2026-07-01", "end": "2026-09-30" },
  "comparison_period": { "start": "2026-04-01", "end": "2026-06-30" },
  "currency": "USD",
  "data_quality": { "pending_count": 0, "flags": [] },
  "monthly_cash_flow": { "data": [ { "month": "2025-10", "income": "5000.00", "expenses": "2050.00", "net": "2950.00", "has_data": true } ], "reason": null },
  "categories": { "data": [ { "category_id": "…", "category": "Food", "amount": "930.00", "prev_amount": "750.00", "abs_change": "180.00", "pct_change": 24.0 } ], "reason": null },
  "category_trends": { "months": ["2025-10", "…", "2026-09"], "data": [ { "category_id": "…", "category": "Food", "values": ["290.00", "…"] } ], "reason": null },
  "top_merchants": { "data": [ { "merchant": "Trader Joe's", "spend": "420.00", "count": 14, "share_pct": 20.0 } ], "reason": null }
}
```

A failed section is `{ "data": null, "reason": "<code>" }`.
