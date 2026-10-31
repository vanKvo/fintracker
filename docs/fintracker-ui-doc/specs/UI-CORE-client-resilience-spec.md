# UI-CORE: Client Resilience and Hygiene

| Field | Value |
|---|---|
| Product | FinTracker |
| Prefix | UI-CORE |
| File | fintracker-ui-doc/specs/UI-CORE-client-resilience-spec.md |
| Owner | Van Vo |
| Status | Draft |
| Last updated | 2026-10-23 |

---

## 1. Overview

### Problem
Four client-wide gaps against the app architecture. The UI sets no request timeout or retry, although the app doc requires clients to time out above Aurora's 15–30 s cold resume and retry (4.6). The Settings page logs the profile form to the console. There is no client error reporting. And Settings shows fields that nothing saves.

### Goals
- A cold database never shows up as a broken page.
- The browser console and any error report never carry financial values or personal details.
- Every Settings field either saves or is not shown as editable.

### Non-Goals
- Automatic retry of writes.
- The Content Security Policy, CORS and auth audit events (Phase 2).

### Design Principles
1. **Retry only what is safe to repeat.**
2. **Log references, not content.** Status, code and route only.

---

## 2. Workflow

```
[API call] ──► UI-CORE-01 (timeout, one retry for reads)
    │
[Failure or error] ──► UI-CORE-02 (console), UI-CORE-03 (report)
    │
[Settings page] ──► UI-CORE-04
```

---

## 3. Requirements Index

| ID | Title | Area | Priority | Status |
|---|---|---|---|---|
| UI-CORE-01 | Timeout and one retry for reads | Reliability | MVP | Proposed |
| UI-CORE-02 | No personal or financial data in the console | Security | MVP | Proposed |
| UI-CORE-03 | Redacted client error reporting | Observability | Later | Proposed |
| UI-CORE-04 | Settings shows only what it saves | UI | Later | Proposed |

---

## 4. Requirements

### UI-CORE-01: Timeout and one retry for reads  `Priority: MVP`

**Problem:** After Aurora auto-pauses in dev, the first request can take 15 s, or 30 s or more after a day. With no client rule, the user sees a spinner that never ends or a plain failure.
**Requirement:** Read requests (`GET`) time out after 45 s and are retried once after 2 s on a timeout or a 503 `database_unavailable`. Writes are never retried automatically.
**Acceptance Criteria:**
- [Happy] A `GET` that answers after 25 s succeeds with no error shown.
- [Alt] A 503 `database_unavailable` is retried once; a success on the retry shows no error.
- [Alt] `POST`, `PUT`, `PATCH` and `DELETE` (including initiate-upload) are never retried automatically.
- [Alt] The import status poll keeps its own 3 s interval and is not retried.
- [Fail] After the retry fails, the widget shows its error state with a Retry button.
**Open Questions:** Are 45 s and 2 s the right values? (A default: above the 30 s resume, under typical gateway limits.)
**Refs:** App doc 4.6 "Cold resume (dev)"; XS-RPTV-07.

### UI-CORE-02: No personal or financial data in the console  `Priority: MVP`

**Problem:** The Settings page logs the profile form values (name, email, phone) with `console.log`.
**Requirement:** The UI writes no form values, descriptions, amounts, merchant names or response bodies to the console. At most it logs a route, a status and an error code.
**Acceptance Criteria:**
- [Happy] Saving the profile writes nothing to the console. A unit test spies on it.
- [Alt] A lint rule fails the build on `console.log`; `console.error` is allowed only with a status and code.
- [Fail] A failed upload logs the status and code only, never the response body.
**Refs:** App doc 4.7 (logs never contain financial values or document text).

### UI-CORE-03: Redacted client error reporting  `Priority: Later`

**Requirement:** An unhandled error, or an API call that failed after its retry, sends one redacted report: route, HTTP status, error code, app version and the trace ID if the response carries one. It never contains bodies, URLs with IDs, or user input.
**Acceptance Criteria:**
- [Happy] A failed `/reports` call produces one report with the fields above and nothing else.
- [Alt] Reports are capped at 10 a minute per tab.
- [Fail] If the reporting call fails, it is dropped silently and never shown to the user or retried.
**Open Questions:** Where do reports go (a small endpoint behind the gateway, or CloudWatch RUM)? Decide before invited testers arrive. This needs an app-level decision, because app doc 4.7 covers services only.

### UI-CORE-04: Settings shows only what it saves  `Priority: Later`

**Problem:** Only the timezone is saved. The profile (name, email, phone), language, and notification and marketing toggles look editable but go nowhere.
**Requirement:** Each Settings field either saves through a backend route or is shown read-only with no Save action. Currency is read-only (USD).
**Acceptance Criteria:**
- [Happy] After changing the timezone and reloading, the saved value is shown.
- [Alt] Name and email are shown read-only until the User profile service has a route to change them.
- [Fail] A save error keeps the previous value and shows "Could not save. Your previous setting is unchanged."
**Open Questions:** Which of these fields does the User profile service plan to save?
**Refs:** XS-CTX-06; app doc 4.2.

---

## 5. Open Questions (consolidated)

| # | Question | Blocks |
|---|---|---|
| 1 | Are 45 s and 2 s the right timeout and retry delay? | UI-CORE-01 |
| 2 | Where do client error reports go? | UI-CORE-03 |
| 3 | Which Settings fields will the User profile service save? | UI-CORE-04 |
