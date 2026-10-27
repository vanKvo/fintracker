# DS-DL: Document Download

| Field | Value |
|---|---|
| Product | FinTracker |
| Prefix | DS-DL |
| File | fintracker-document-service/specs/DS-DL-document-download-spec.md |
| Owner | Van Vo |
| Status | Draft (implementation deferred) |
| Last updated | 2026-10-21 |

> **Replaces LG-CORE-4.3.** The Document service owns statement downloads (app doc D8; invariants 6 and 7). Until DS-DL-01 is implemented, the Ledger's existing download keeps working unchanged; don't extend it.

---

## 1. Overview

### Problem
Statement downloads run through the Ledger today, which reads an S3 key from `ledger.statements`. That breaks the rule that only the Document service knows where a file is stored, and puts download controls in a service that shouldn't hold files.

### Goals
- One owner for upload, download and deletion controls on every user file.
- The Ledger and the client refer to a statement file only by `documentId`.

### Non-Goals
- Moving uploads to the Document service (separate spec).
- Downloads of user documents other than statements (later, same route).

### Design Principles
1. **Files never pass through a service.** The client downloads straight from the clean bucket with a short-lived link.
2. **Ownership from the verified context.** `userId` comes only from the verified user context, never from the request.

---

## 2. Workflow

```
[1] Client → Document service: request download for documentId ──► DS-DL-01
[2] Document service: check owner, write audit record, sign link ──► DS-DL-01
[3] Client → S3 clean bucket: download with no-store headers ──► DS-DL-01
[4] Ledger stops serving downloads ──► DS-DL-02
```

---

## 3. Requirements Index

| ID | Title | Area | Priority | Status |
|---|---|---|---|---|
| DS-DL-01 | Download a statement file by `documentId` | Security | Later | In progress |
| DS-DL-02 | Retire the Ledger download | Data | Later | Proposed |

---

## 4. Requirements

### DS-DL-01: Download a statement file by `documentId`  `Priority: Later`

**Requirement:** The Document service returns a presigned GET link for a file the caller owns. The link expires in 15 minutes at most and is served with `Cache-Control: private, no-store, no-cache, must-revalidate`. Each download writes an audit record (user, `documentId`, time, outcome).
**Acceptance Criteria:**
- [Happy] The owner requests a download → 200 with a link that downloads the original file from the clean bucket.
- [Alt] Within one session the client reuses the Blob it already fetched (Object URL in app state) instead of requesting a new link.
- [Fail] Another user's `documentId`, or one that doesn't exist → 404, the same for both; an audit record is written.
- [Fail] File still in quarantine or failed its scan → 409; no link is issued.
**Refs:** LG-CORE-4.3 (replaced); app doc 5 "Download a statement or document"; D8

### DS-DL-02: Retire the Ledger download  `Priority: Later`

**Requirement:** After DS-DL-01 ships, the Statements tab gets the statement's `documentId` from the Ledger and downloads through the Document service. The Ledger's download route and any S3 access it holds for downloads are removed.
**Acceptance Criteria:**
- [Happy] The Statements tab downloads through the Document service.
- [Fail] A call to the old Ledger route → 404 after removal.
**Refs:** DS-DL-01; Ledger architecture, statement files row

---

## 5. Open Questions (consolidated)

None.
