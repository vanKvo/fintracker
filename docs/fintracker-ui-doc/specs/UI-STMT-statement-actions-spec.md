# UI-STMT: Statement Actions

| Field | Value |
|---|---|
| Product | FinTracker |
| Prefix | UI-STMT |
| File | fintracker-ui-doc/specs/UI-STMT-statement-actions-spec.md |
| Owner | Van Vo |
| Status | Draft |
| Last updated | 2026-10-23 |

---

## 1. Overview

### Problem
The Statements tab has three gaps against the app architecture. The browser builds an S3 header from the Cognito `sub`, which differs from the internal user ID in production (D3), so the upload signature can fail. Upload and download still go through the Ledger and S3 directly, although the Document service is planned to own files. And *Approve all pending* changes only the screen.

### Goals
- A production upload does not depend on the browser knowing the internal user ID.
- Upload and download follow the Document service flow once it exists.
- Every visible action on a statement does what it says, on the server.

### Non-Goals
- Changing the duplicate and column-mapping dialogs or the 3-second job polling.
- Deleting a statement: it already starts in the Ledger (D9).

### Design Principles
1. **Files never pass through a service,** and the browser sends only what the server told it to sign.
2. **The server is the source of every count** the Statements tab shows.

---

## 2. Workflow

```
[Initiate upload (Ledger)] ──► UI-STMT-01
    │
[PUT to storage: today S3 by presigned URL; later quarantine via Document service] ──► UI-STMT-01, UI-STMT-02
    │
[Poll job status] (unchanged)
    │
[Row actions: download, approve all pending] ──► UI-STMT-03, UI-STMT-04
```

---

## 3. Requirements Index

| ID | Title | Area | Priority | Status |
|---|---|---|---|---|
| UI-STMT-01 | Upload headers come from the server | Security | MVP | Proposed |
| UI-STMT-02 | Upload through the Document service | Integration | Later | Proposed |
| UI-STMT-03 | Download through the Document service | Integration | Later | Proposed |
| UI-STMT-04 | Approve all pending, on the server | UI | MVP | Proposed |

---

## 4. Requirements

### UI-STMT-01: Upload headers come from the server  `Priority: MVP`

**Problem:** The S3 `PUT` sets `x-amz-meta-user-id` from `AuthService.getCurrentUserId()`, which returns the Cognito `sub` in production. The Ledger signs the internal user ID into the presigned URL. If they differ, S3 rejects the upload.
**Requirement:** The initiate-upload response lists the exact headers the browser must send. The UI sends those, and no header that it builds from an identity value.
**Acceptance Criteria:**
- [Happy] A user whose `sub` differs from their internal user ID uploads a file successfully.
- [Happy] The `PUT` carries exactly the headers from the response, plus the content type.
- [Fail] An S3 rejection shows the upload error panel ("Upload failed. Please try again."); the Ledger's record stays Processing; no host names or signature details are shown.
**Open Questions:** Does the Ledger still sign user and account metadata into the URL? If it does not, the metadata headers can simply go.
**Refs:** UI-AUTH-02 (removes `getCurrentUserId`); app doc D3, invariant 6.

### UI-STMT-02: Upload through the Document service  `Priority: Later`

**Requirement:** Once the Document service ships, the UI creates the statement record in the Ledger, asks the Document service for an upload URL for that statement, and uploads to quarantine. The polling and decision dialogs are unchanged.
**Acceptance Criteria:**
- [Happy] The file reaches quarantine, the scan passes, and the job status moves on as before.
- [Fail] A file that fails the scan shows a clear message and no transactions are created.
**Depends on:** The Document service upload spec (not written yet).
**Refs:** App doc 5 "Upload a bank statement (with the Document service, proposed)".

### UI-STMT-03: Download through the Document service  `Priority: Later`

**Requirement:** *Download* asks the Document service for a short-lived link and downloads from the clean bucket. The UI calls no Ledger route for the file.
**Acceptance Criteria:**
- [Happy] Download starts from the returned link.
- [Fail] An expired link or a failed ownership check shows "Couldn't download this statement" and offers a new request.
**Depends on:** [DS-DL-01](../../fintracker-document-service/specs/DS-DL-document-download-spec.md).
**Refs:** App doc 5 "Download a statement or document".

### UI-STMT-04: Approve all pending, on the server  `Priority: MVP`

**Problem:** The button updates the list on screen only. A reload shows the rows still pending.
**Requirement:** *Approve all pending* makes one server call that approves every pending transaction of that statement, then reloads the counts from the server.
**Acceptance Criteria:**
- [Happy] After the click and a reload, the statement shows 0 pending, and the approved rows now count in budgets and reports.
- [Alt] If some rows can't be approved, the UI shows "n approved, m not approved" using the server's counts.
- [Fail] If the call fails, nothing changes on screen and a snackbar shows the reason.
**Depends on:** A Ledger route to approve by statement. Today the UI can only approve by transaction IDs.
**Open Questions:** Is this a new Ledger route, or the existing bulk route taking a statement ID?

---

## 5. Open Questions (consolidated)

| # | Question | Blocks |
|---|---|---|
| 1 | Does the Ledger still sign user and account metadata into the presigned URL? | UI-STMT-01 |
| 2 | Which Ledger route approves all pending rows of a statement? | UI-STMT-04 |
