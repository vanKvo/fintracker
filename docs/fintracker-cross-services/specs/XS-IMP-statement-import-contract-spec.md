# XS-IMP: Statement Import Contract

| Field | Value |
|---|---|
| Product | FinTracker |
| Prefix | XS-IMP |
| File | fintracker-cross-services/specs/XS-IMP-statement-import-contract-spec.md |
| Owner | Van Vo |
| Status | Draft |
| Last updated | 2026-10-26 |

**Services:** Data pipeline (sends rows and outcomes), Ledger (stores them, owns the statement record), UI (shows them). Categories in the import package are covered separately by [XS-DPCAT](XS-DPCAT-dp-ledger-categories-spec.md).

---

## 1. Overview

### Problem
Three gaps sit on the boundary between the Data pipeline and the Ledger:
- The pipeline knows which rows came from a weak OCR read, but the Ledger never hears it, so the user can't tell which amounts and dates to check.
- When an import fails, only the pipeline's job record knows. The Ledger's statement stays `PROCESSING`, and re-uploading the same file is answered with "this statement already exists".
- Raw exception text reaches the user through the job status.

### Goals
- A user can see which pending rows need a closer look, and why.
- A failed or abandoned import never blocks the user from uploading the statement again.
- No raw error text reaches the user. Every failure the user sees comes with the next step they can take.

### Non-Goals
- Changing categories in the package (XS-DPCAT).
- Retrying a failed import automatically. The user uploads again.
- Translating messages. The catalog is English-only for now.

### Design Principles
1. **The Ledger decides what a re-upload is.** Only the Ledger sees uploads before they start, so duplicate and re-upload rules live there. The pipeline never looks for earlier jobs of the same file; every import it sees has a new statement id.
2. **Reason codes cross service boundaries, not messages.** Services exchange stable codes. The UI owns the wording.
3. **Details go to logs, actions go to users.** Exception text, stack traces and IDs stay in logs, keyed by job id and trace id.

---

## 2. Workflow

```
[Pipeline flags low-confidence rows in the package] ──► XS-IMP-01
    │
[Import fails or is abandoned → pipeline tells the Ledger] ──► XS-IMP-02
    │
[User uploads the statement again → starts clean] ──► XS-IMP-03
    │
[Every failure shown to the user → reason code → catalog message] ──► XS-IMP-04
```

---

## 3. Requirements Index

| ID | Title | Area | Priority | Status |
|---|---|---|---|---|
| XS-IMP-01 | Review flag for low-confidence rows | Data | MVP | Implemented |
| XS-IMP-02 | Failed imports reach the Ledger | Reliability | MVP | Implemented |
| XS-IMP-03 | Re-uploading after a failed import starts clean | Reliability | MVP | Implemented |
| XS-IMP-04 | User-facing errors come from reason codes | Security | MVP | Implemented |

---

## 4. Requirements

### XS-IMP-01: Review flag for low-confidence rows  `Priority: MVP`

**Problem:** OCR can misread a date or an amount. The pipeline computes `needs_review` but doesn't send it, so the Pending tab treats a blurry screenshot row like a clean CSV row.
**Requirement:** Each row in the import package carries an optional `reviewReason`. The pipeline sets `LOW_CONFIDENCE_EXTRACTION` when the row's extraction confidence is below its threshold (0.70 today). The confidence score itself and the threshold stay in the pipeline. The Ledger stores the reason with the pending transaction, and the Pending tab highlights the row with "Check the date and amount against your statement". This highlight is separate from the uncategorized highlight.
**Acceptance Criteria:**
- [Happy] A row read by Textract from a screenshot (confidence 0.55) arrives with `reviewReason = LOW_CONFIDENCE_EXTRACTION` and is highlighted in the Pending tab.
- [Alt] CSV rows and text-layer rows never carry a review reason.
- [Alt] A row that is both low-confidence and uncategorized shows both highlights.
- [Alt] Approve and Approve Selected still work on flagged rows. The flag highlights; it never blocks.
- [Alt] Once the row is approved, the flag is kept but no longer highlighted.
- [Fail] A `reviewReason` value the Ledger doesn't know is stored as `null` and logged. The row is still imported.
**Refs:** DP-ING-01 ("Manual Review Routing"), Appendix A.

### XS-IMP-02: Failed imports reach the Ledger  `Priority: MVP`

**Problem:** The pipeline records a failure only in its own job record, which expires after 7 days. The Ledger's statement stays `PROCESSING` forever, and the Statements tab can't say what went wrong.
**Requirement:** When an import ends as `FAILED`, the pipeline calls the Ledger's internal route `POST /statements/internal/{statementId}/import-failure` with the reason code. This covers every cause: a stage error, the column-check timeout (DP-ING-09) and a cancelled column check. The call is signed like every other internal call. The Ledger sets the statement to `FAILED` and stores the reason code. The Statements tab shows the failure with the catalog message (XS-IMP-04).
**Acceptance Criteria:**
- [Happy] The user closes the column dialog without confirming. Within 1 minute the statement shows "Upload cancelled. Upload the file again when you're ready." in the Statements tab.
- [Happy] A PDF with no readable transactions ends with the statement `FAILED` and reason `NO_VALID_TRANSACTIONS`.
- [Alt] A statement that already has imported rows is never set to `FAILED` by this call. The Ledger answers 409 and logs it. The Ledger's statement has only `PROCESSING`, `COMPLETED` and `FAILED`: a partial import is a `COMPLETED` statement, and the job carries `PARTIALLY_COMPLETED` with `failedCount`/`totalCount` (DP-ING-10).
- [Alt] The call is idempotent: repeating it for an already-failed statement changes nothing and answers 204.
- [Fail] If the Ledger can't be reached, the pipeline retries with backoff (up to 4 attempts) and then logs `LEDGER_FAILURE_NOTICE_FAILED`, which raises an alarm. The job record still shows `FAILED`.
- [Fail] An unknown statement or another user's statement answers 404.
**Refs:** DP-ING-09, DP-ING-10; Ledger statement statuses (LG-STMT shared contract).

### XS-IMP-03: Re-uploading after a failed import starts clean  `Priority: MVP`

**Problem:** The same-file check (LG-STMT-03), the same-statement check (LG-STMT-04) and the month check (LG-STMT-06) all match a failed statement. A user retrying after a timeout is asked whether to overwrite a statement that never imported anything.
**Requirement:** The Ledger's duplicate checks ignore statements that are `FAILED` and have no transactions. When a new upload starts for the same account and either the same content hash or the same month, the Ledger deletes those failed statement records in the same transaction that creates the new one. The new upload gets a new statement id, so the pipeline starts a new execution as usual.
**Acceptance Criteria:**
- [Happy] A CSV upload times out at the column check. The user uploads the same file 2 hours later. No duplicate prompt appears, the import runs, and the Statements tab lists one statement for that month.
- [Alt] A statement that is `PARTIALLY_COMPLETED`, or `FAILED` with any transactions, still triggers the duplicate prompt.
- [Alt] A failed statement the user never re-uploads stays in the Statements tab until the user deletes it.
- [Fail] If deleting the failed record fails, the new upload is not created and the user sees a retryable error. The two changes happen in one transaction.
**Refs:** LG-STMT-03, LG-STMT-04, LG-STMT-05, LG-STMT-06.

### XS-IMP-04: User-facing errors come from reason codes  `Priority: MVP`

**Problem:** The Gatekeeper and Extractor store exception text in the job record, and the status API returns it to the client. That text can reveal internal details and gives the user nothing to act on.
**Requirement:** Only reason codes from Appendix A cross service boundaries: the pipeline's job status, the import-failure call and the Ledger's statement status. The UI maps each code to a message and an action from the catalog. Any code missing from the catalog is shown as `PIPELINE_ERROR`. Exception text, stack traces and statement content appear only in logs, together with the job id and trace id.
**Acceptance Criteria:**
- [Happy] A 30 MB PDF shows "This file is larger than 25 MB. Export a shorter date range from your bank and upload it again."
- [Alt] An error caused on our side shows "Something went wrong on our side. Try again in a few minutes. If it keeps happening, contact support with reference {jobId}."
- [Alt] Partial completion is reported as structured fields (`failedCount`, `totalCount`), not a sentence.
- [Fail] A test fails the build if any stage can write a job error that isn't a catalog code.
**Refs:** DP-ING-10, Appendix A.

---

## 5. Open Questions (consolidated)

| # | Question | Blocks |
|---|---|---|
| — | None | — |

---

## Appendix A: Reason code catalog

Produced by the pipeline (job status and import-failure call) and the Ledger (statement status). The UI owns the wording; this table is the starting copy.

| Code | Kind | Message and action shown to the user |
|---|---|---|
| `FILE_TOO_LARGE` | User can fix | This file is larger than 25 MB. Export a shorter date range from your bank and upload it again. |
| `TOO_MANY_PAGES` | User can fix | This PDF has more than 50 pages. Export a shorter date range and upload it again. |
| `UNSUPPORTED_FORMAT` | User can fix | Upload a CSV or PDF statement downloaded from your bank, or a clear screenshot of one. |
| `INVALID_CSV_FORMAT` | User can fix | This CSV is missing a header row or transactions. Download it from your bank again and upload it. |
| `NO_VALID_TRANSACTIONS` | User can fix | We couldn't find any transactions in this file. Try your bank's CSV export instead. |
| `CSV_COL_MAPPING_CONFIRMATION_TIMEOUT` | User can fix | This upload expired before the columns were confirmed. Upload the file again. |
| `CSV_COL_MAPPING_CANCELLED` | User can fix | Upload cancelled. Upload the file again when you're ready. |
| `SERVER_DUPLICATE_DETECTED` | User can fix | This file was already uploaded on {existingUploadDate}. Open that statement, or delete it and upload again. (LG-STMT-08) |
| `DUPLICATE_RESOLUTION_TIMEOUT` | User can fix | This upload expired before you chose whether to replace the existing statement. Upload the file again. (LG-STMT-04) |
| `CATEGORIES_UNAVAILABLE`, `LEDGER_PUSH_FAILED`, `PIPELINE_ERROR` and any unknown code | Our side | Something went wrong on our side. Try again in a few minutes. If it keeps happening, contact support with reference {jobId}. |

| Review reason (XS-IMP-01) | Shown on the row |
|---|---|
| `LOW_CONFIDENCE_EXTRACTION` | Check the date and amount against your statement. |

---

## Change Log

| Change | Reason |
|---|---|
| 2026-10-26: Appendix A adds `SERVER_DUPLICATE_DETECTED` and `DUPLICATE_RESOLUTION_TIMEOUT`. XS-IMP-02 no longer names `PARTIALLY_COMPLETED` as a statement status. The field name across boundaries is `reason` (DP-ING-10; the LG-STMT Shared Contract now matches). | Both codes are produced by the pipeline and must reach the user with a message. The Ledger has no `PARTIALLY_COMPLETED` statement status. |
