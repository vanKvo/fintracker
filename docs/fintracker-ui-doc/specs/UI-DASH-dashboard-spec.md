# UI-DASH: Dashboard

| Field | Value |
|---|---|
| Product | FinTracker |
| Prefix | UI-DASH |
| File | fintracker-ui-doc/specs/UI-DASH-dashboard-spec.md |
| Owner | Van Vo |
| Status | Draft |
| Last updated | 2026-10-23 |

---

## 1. Overview

### Problem
The Dashboard loads the user's whole transaction list and builds a category pie, a spending trend and a cash-flow chart in the browser, for a range the user picks. It uses the browser's clock, so a user whose browser timezone differs from their saved one can see a different month than the Ledger counts. The app architecture (D21, D23) makes the Dashboard a view of the current month, served by the Ledger, and moves the charts to Reports.

### Goals
- The Dashboard shows only the current month, and every figure is served, not computed in the browser.
- One widget failing never blanks the page.

### Non-Goals
- Past months or a range selector on the Dashboard (a revisit trigger for D21).
- Changing the spending-pace card ([AN-RPT-02](../../fintracker-analytics/specs/AN-RPT-dashboard-reports-widgets-spec.md)).

### Design Principles
1. **The server owns every figure and the current month.** The browser renders what it receives.
2. **One request per widget,** each with its own loading, empty and error state.

---

## 2. Workflow

```
[Open Dashboard] ──► UI-DASH-01
    │
[Parallel: data-through + pending, summary cards, budget alerts, bills, recent transactions] ──► UI-DASH-02
[Separately: spending pace] ──► AN-RPT-02
    │
[Dates and "today"] ──► UI-DASH-03
```

---

## 3. Requirements Index

| ID | Title | Area | Priority | Status |
|---|---|---|---|---|
| UI-DASH-01 | Current month only | UI | MVP | Proposed |
| UI-DASH-02 | Ledger widgets, one request each | UI | MVP | Proposed |
| UI-DASH-03 | No browser clock in Dashboard logic | Data | MVP | Proposed |

---

## 4. Requirements

### UI-DASH-01: Current month only  `Priority: MVP`

**Requirement:** The Dashboard has no time-range selector and no spending-by-category, spending-trend or cash-flow charts. It does not request the full transaction list.
**Acceptance Criteria:**
- [Happy] The page shows no range selector and no chart canvas.
- [Happy] Opening the Dashboard makes no request for the full transaction list. A test spies on requests.
- [Alt] An account with no transactions shows empty states, never sample data.
**Out of Scope:** The category, trend and cash-flow views now live in Reports (AN-RPT-04 to -06).
**Refs:** App doc D21; [ADR-013](../../fintracker-architecture/architectural_decision_records/ADR-013-dashboard-reports-ownership.md).

### UI-DASH-02: Ledger widgets, one request each  `Priority: MVP`

**Requirement:** In parallel, the UI requests the Ledger's widgets: data-through date with the pending count, summary cards, budget alerts, this month's bills, and recent transactions. Each renders as soon as its answer arrives.
**Acceptance Criteria:**
- [Happy] Five Ledger requests start together; the spending-pace request is separate.
- [Happy] The data-through date is shown, with "N awaiting approval aren't in these totals" when the pending count is above 0.
- [Alt] No budget alerts hides the alerts section. No bills shows "No bills due this month".
- [Alt] A 409 `user_settings_incomplete` opens the timezone picker, then the request is retried once.
- [Fail] If one request fails, that widget shows an error and a Retry button that re-requests only it; the others stay.
- [Fail] Amounts are shown as received. The UI sums nothing.
**Depends on:** The Ledger's `/dashboard/*` routes for data-through and budget alerts (the code today only calls `dashboard/aggregations` and `bills`).
**Open Questions:** Do the Ledger routes for data-through and budget alerts exist yet?
**Refs:** Ledger architecture "Serve the Dashboard"; XS-CTX-05.

### UI-DASH-03: No browser clock in Dashboard logic  `Priority: MVP`

**Requirement:** Nothing on the Dashboard decides "today", "this month" or "due in N days" from the browser's clock or timezone. Calendar dates stay `YYYY-MM-DD` and are never converted.
**Acceptance Criteria:**
- [Happy] A user whose saved timezone is Pacific/Auckland, on a browser set to America/New_York, sees the same bills and "due in" days that the Ledger reports for Auckland.
- [Alt] A bill due on the 1st is shown under the 1st, never the previous day.
**Open Questions:** Where does the UI get "today" for "due in N days"? Proposal: the Ledger returns the day count with each bill.
**Refs:** App doc D23, D24; the earlier month-shift bug (`bug_dashboard_date_only_parsed_as_utc_shifts_month`).

---

## 5. Open Questions (consolidated)

| # | Question | Blocks |
|---|---|---|
| 1 | Do the Ledger routes for data-through and budget alerts exist yet? | UI-DASH-02 |
| 2 | Where does "today" for bill day counts come from? | UI-DASH-03 |
