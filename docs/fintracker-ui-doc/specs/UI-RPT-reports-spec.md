# UI-RPT: Reports Tab

| Field | Value |
|---|---|
| Product | FinTracker |
| Prefix | UI-RPT |
| File | fintracker-ui-doc/specs/UI-RPT-reports-spec.md |
| Owner | Van Vo |
| Status | Draft |
| Last updated | 2026-10-23 |

---

## 1. Overview

### Problem
The Financial Summary panel assumes the daily refresh limit is 5 (`REFRESHES_PER_DAY`). The AI assistant's limit is 10 generations a day, so the panel shows the wrong limit and could block a refresh the server would allow.

### Goals
- The panel shows only what the server says about refreshes.

### Non-Goals
- Reports CSV and PDF export. It is a stub today and no spec defines it, so it stays a stub until one does.
- The period selector and the charts ([AN-RPT-01, -03 to -07](../../fintracker-analytics/specs/AN-RPT-dashboard-reports-widgets-spec.md)), which are built.

### Design Principles
1. **No limit or threshold lives in the browser.** The server owns it.

---

## 2. Workflow

```
[Open or refresh the Financial Summary] ──► UI-RPT-01
```

---

## 3. Requirements Index

| ID | Title | Area | Priority | Status |
|---|---|---|---|---|
| UI-RPT-01 | Refresh limit comes from the server | UI | MVP | Proposed |

---

## 4. Requirements

### UI-RPT-01: Refresh limit comes from the server  `Priority: MVP`

**Requirement:** The panel removes its hardcoded limit. It shows and enforces the remaining refreshes from `refreshes_remaining` in each summary response.
**Acceptance Criteria:**
- [Happy] After a refresh, the remaining count equals the server's `refreshes_remaining`.
- [Alt] At 0 remaining, the button is disabled and reads "No refreshes left today. Try again tomorrow." The message states no number.
- [Fail] If the refresh call is rejected (limit reached or cost guard), the previous summary stays and the panel shows the reason from the server.
**Refs:** AI assistant architecture (10 generations per user per day); AN-FS-14 and AN-FS-15.

---

## 5. Open Questions (consolidated)

| # | Question | Blocks |
|---|---|---|
| 1 | Does the summary response need a `refreshes_limit` so the panel can say "n of N"? | UI-RPT-01 |
