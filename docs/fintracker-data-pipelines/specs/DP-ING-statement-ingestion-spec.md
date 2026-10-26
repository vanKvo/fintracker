# DP-ING: Statement Ingestion

> **Formerly:** `docs/fintracker-data-pipelines/data-pipeline-spec-01.md`, IDs REQ-DP-01 … REQ-DP-08 → DP-ING-01 … DP-ING-08 (renamed 2026-10; see [SPECS.md](../../SPECS.md))

## Status

| ID | Status |
|---|---|
| DP-ING-01 | Implemented (parts superseded by XS-IMP-01; column-mapping storage extended by DP-MAP) |
| DP-ING-02 | Implemented |
| DP-ING-03 | Implemented (parts superseded by DP-ING-09) |
| DP-ING-04 | Implemented |
| DP-ING-05 | Implemented |
| DP-ING-06 | Implemented |
| DP-ING-07 | Implemented |
| DP-ING-08 | Implemented (parts superseded by DP-ING-10) |
| DP-ING-09 | Implemented |
| DP-ING-10 | Implemented |
| DP-ING-11 | In progress (pages never stored, built; the one-time cleanup leaves old versions and images whose original was deleted) |
| DP-ING-12 | Proposed |


# Import Channels

## DP-ING-01: Hardening Imports *(was REQ-DP-01)*

A. Business Rules:
- Format Detection: The Gatekeeper detects whether an uploaded file is PDF, CSV, or Image from magic bytes/extension before any other processing runs.
- CSV Bank-Specific Column Mapping: The user selects a bank institution when uploading a CSV. The system looks up that bank's known column-name variants (a per-bank mapping table) and proposes a mapping to the canonical `date`/`merchant`/`amount` fields, instead of requiring one fixed header set. *(Extended by [DP-MAP](DP-MAP-csv-column-mapping-spec.md): mappings per bank and header signature, per-user mappings, and promotion of shared corrections.)*
- Mapping Transparency: After a CSV is uploaded, the system shows the user every column it found and how each one was mapped — a matched column paired with its canonical field, and any column it could not confidently map left visibly unmapped — rather than silently accepting or silently discarding columns.
- User Mapping Confirmation Gate: Processing does not continue until the user reviews and confirms (or manually corrects) the proposed mapping in the mapping dialog. This is what keeps a bank's column-name change from producing wrong data instead of an error — the user catches it at confirmation time instead of transactions being posted with columns swapped.
- CSV Validity Gate: A CSV is only accepted if it has at least one data row and at least the confirmed `date`/`merchant`/`amount` fields mapped.
- CSV Transaction Parsing: A CSV whose mapping is confirmed has its rows parsed into transactions (using the confirmed mapping) and carried through Normalization and the Ledger push, the same as the OCR path.
- Text-Layer Fast Path (Tier 1): For a PDF with an extractable text layer (i.e., not a scanned image), the system reads transaction rows directly from the text layer (via PyMuPDF) without calling OCR.
- Textract Fallback (Tier 2): For a PDF/image with no usable text layer, or where Tier 1 finds no transaction-shaped rows, the system calls Textract `AnalyzeDocument` with `FeatureTypes=["TABLES"]` per page — the same call both decides whether a page has a transaction table and extracts it, so there's no separate classify-then-extract round trip. A page with no `TABLE` blocks in the response is junk; a page with `TABLE` blocks is extracted directly from that same response.
- Confidence Scoring: Every PDF/Image transaction row carries a confidence signal reflecting how it was extracted (text layer > Textract). CSV rows are always high-confidence once the user has confirmed the mapping, since there's no OCR step involved.
- Review Flag: Defined by [XS-IMP-01](../../fintracker-cross-services/specs/XS-IMP-statement-import-contract-spec.md). A row whose confidence is below 0.70 is sent with `reviewReason = LOW_CONFIDENCE_EXTRACTION`. Every row, flagged or not, is stored as `PENDING` and waits for the user's approval.
- Screenshot Confidence: Screenshot rows read by Textract get confidence 0.55, below PDF rows read by Textract (0.75), because a single image is the easiest format to be blurry, cropped or rotated. So every Textract-read screenshot row is flagged for review.

B. Constraints:
- The tiering logic (Tier 1/2) applies only to PDF and Image formats — it must not add latency to the CSV happy path.
- Text-layer detection must reliably distinguish a digitally-generated PDF from a scanned one (e.g., a minimum extractable-character threshold per page) so Tier 1 is never skipped for a PDF that could have used it.
- No new Ledger transaction status is introduced: flagged rows are `PENDING` like every imported row.
- CSV column mappings live in a runtime-writable store, not a file bundled into the Lambda deployment ([DP-MAP](DP-MAP-csv-column-mapping-spec.md)).
- The mapping dialog must show unmapped columns even when every required field (`date`/`merchant`/`amount`) was successfully mapped, so the user can catch a column the system mapped to the wrong field, not just columns it failed to map at all.

C. Data Impacts:
- Each `RawTransaction` and `NormalizedTransaction` carries its extraction tier (`CSV` / `TEXT_LAYER` / `TEXTRACT`) and `confidence`. The confidence stays in the pipeline; only the review reason it implies is sent to the Ledger (XS-IMP-01).
- Bank column mappings are stored in a DynamoDB table keyed by bank and header signature, seeded from `infrastructure/seed/bank_mapping_baseline.json`. A confirmation saves the user's own mapping and a vote; it never writes the bank's baseline ([DP-MAP](DP-MAP-csv-column-mapping-spec.md)).
- Job status `PENDING_CSV_COL_MAPPING_CONFIRMATION` marks a CSV job waiting on the user's mapping dialog.

D. Pipeline Stage Mapping:
Location: `services/fintracker-data-pipeline/src/gatekeeper/`, `src/extractor/`
- Gatekeeper Lambda: format detection, resource caps (DP-ING-04), the file-hash duplicate check (LG-STMT-08); for CSV, proposes a column mapping and pauses the job at `PENDING_CSV_COL_MAPPING_CONFIRMATION`; for PDF, reads the page count only.
- Mapping Confirmation handler: invoked when the user submits the confirmed or corrected mapping; resumes the Step Functions execution, then saves the user's mapping and vote (DP-MAP-03).
- Extractor Lambda: CSV row parsing with the confirmed mapping, text-layer parsing (Tier 1), Textract `AnalyzeDocument` (Tier 2) per page.
- Normalizer Lambda: sets the review reason from the confidence (XS-IMP-01) before handoff to the Data Dispatcher.

E. Interface Details:
Location: `services/fintracker-data-pipeline/src/gatekeeper/service.py`, `src/extractor/service.py`

```python
def propose_column_mapping(bucket: str, csv_s3_key: str, bank_id: str, user_id: str) -> ColumnMappingProposal:
    """Proposes a mapping for the CSV's actual headers in DP-MAP-02 order (the user's own
    mapping, the bank's baseline, the nearest baseline, default names). Returns every column
    found, each either paired with its canonical field or flagged unmapped, for the
    confirmation dialog. Never parses transaction rows.
    """

def confirm_column_mapping(job_id: str, bank_id: str, confirmed_mapping: dict[str, str]) -> None:
    """Resumes the paused Step Functions execution for job_id, then saves the user's
    mapping and vote (DP-MAP-03). A job no longer waiting raises the timeout or cancel
    reason and resumes nothing (DP-ING-09).
    """

def parse_csv_transactions(bucket: str, csv_s3_key: str, confirmed_mapping: dict[str, str]) -> list[RawTransaction]:
    """Parses CSV rows using the user-confirmed mapping. Raises
    CsvRowParseError per row on a bad date/amount rather than failing
    the whole file.
    """

def classify_and_extract_page(
    document_bytes: bytes, page_num: int, is_pdf: bool, is_screenshot: bool, statement_id: str
) -> PageExtraction:
    """Tier 2 for one page that Tier 1 couldn't read: a single Textract
    AnalyzeDocument+TABLES call both classifies (has a TABLE block?) and
    extracts the page. The page is sent as bytes and never stored (DP-ING-11).
    """
```

F. Error Handling:
- **UNSUPPORTED_FORMAT**: Uploaded file is not PDF, CSV, or Image after Gatekeeper detection — reject immediately, job status `FAILED`, no downstream stage invoked.
- **Unknown bank format**: The bank has no baseline for these headers — the dialog opens with the nearest baseline or default names, and any column it can't map shown as unmapped, so the user can build the mapping instead of being blocked (DP-MAP-02).
- **CSV_COL_MAPPING_CONFIRMATION_TIMEOUT**: Defined by DP-ING-09 (30 minutes).
- **CSV_ROW_PARSE_ERROR**: Individual row fails to parse against the confirmed mapping (bad date/amount format) — skip that row, log it, continue with the rest of the file; do not fail the whole statement for one bad row.
- **TEXT_LAYER_EMPTY**: Tier 1 text-layer read succeeds but yields zero transaction-shaped rows on a digitally-generated PDF — fall through to Tier 2 rather than treating the document as empty.
- **TEXTRACT_TRANSIENT_FAILURE**: Tier 2 `AnalyzeDocument` call is throttled or hits a transient AWS error — retry with backoff via the existing `tenacity` policy; on exhaustion, mark that page failed and continue with the rest of the statement rather than failing the whole job.
- **NO_VALID_TRANSACTIONS**: No page yields a transaction in either tier — job status `FAILED` with this reason (XS-IMP Appendix A), through RecordFailure (DP-ING-09).

---

# Scalability

## DP-ING-02: Warm-Start Caching and Parallel Processing *(was REQ-DP-02)*

A. Business Rules:
- Parallel Page Extraction: Pages within one statement (text-layer parses or Textract `AnalyzeDocument` calls) are processed concurrently rather than in a sequential loop.
- Batched Ledger Push: All normalized transactions for one statement are pushed to the Ledger in a single bulk call (LG-STMT-02), not one HTTP request per transaction.
- Tier Skipping at Scale: When Tier 1 (text-layer) fully classifies a document, Tier 2 (Textract) is never invoked for that document — this is what actually caps Textract spend as upload volume grows, not just per-call optimization.

B. Constraints:
- Textract calls within a job run at most 8 at a time, bounded by the Lambda's memory/CPU allocation and Textract's rate limits.

C. Data Impacts:
- No database schema changes. Concurrency is in-process (a thread pool in the Extractor), not a Step Functions `Map` state.

D. Pipeline Stage Mapping:
Location: `services/fintracker-data-pipeline/src/extractor/service.py` (parallel extraction), `src/data_dispatcher/service.py` (batched push)

E. Interface Details:
Location: `services/fintracker-data-pipeline/src/data_dispatcher/service.py`

```python
def push_transactions_to_ledger(
    job_id: str,
    user_id: str,
    statement_id: str,
    transactions: list[dict],
) -> LedgerPushResult:
    """Pushes one statement's transactions in a single signed bulk call.
    Aggregates the Ledger's per-row results into success/total counts; a row
    the Ledger rejects does not block the others.
    """
```

F. Error Handling:
- **PARTIAL_EXTRACTION_FAILURE**: [One page's concurrent extraction call fails while others in the same statement succeed — record that page as failed, continue processing the rest, report the statement as partially extracted rather than failing the whole job]
- **PARTIAL_LEDGER_PUSH_FAILURE**: [The Ledger rejects some rows of the bulk call — record them in `LedgerPushResult` (`success_count`/`total_count`) and mark the job `PARTIALLY_COMPLETED` with `failedCount`/`totalCount` (DP-ING-10). A push where no row is stored fails the import through RecordFailure (DP-ING-09)]
- **LEDGER_THROTTLED**: [The Ledger answers 429/503 or the connection fails — retry the whole bulk call up to 4 attempts with exponential backoff; retried rows are safe because the Ledger skips rows it already stored (DP-ING-03)]

## DP-ING-03: Failure Handling and Idempotency *(was REQ-DP-03)*

**Problem:**
The pipeline has no retry/catch logic configured at the Step Functions level, so if any stage fails (e.g., Textract throttling past its retries, a bad Normalizer input), the whole job dies silently — the job's status is never updated to `FAILED`, so it just sits at its last known state until it quietly expires. Separately, S3 can deliver the same upload event more than once, and nothing stops the pipeline from running twice and pushing duplicate transactions to the Ledger.

**Requested Changes:**
- Failure handling: defined by DP-ING-09 (every failure ends in RecordFailure, which sets the job `FAILED` with a reason code and tells the Ledger).
- Make the Ledger push idempotent per statement, so re-running the same statement (whether from a duplicate S3 event or a retried step) doesn't create duplicate transactions.

**Constraints (if applicable):**
- None beyond what Step Functions and the Ledger API already support.

**Interface (if applicable):**
- Every row carries a `rowFingerprint` (SHA-256 of statement id, row position, date, merchant, amount and type). The Ledger skips a row whose (statement id, row fingerprint) is already stored and counts it as `ALREADY_STORED`.

---

# Costs

## DP-ING-04: Cap Resource Consumption Per Upload *(was REQ-DP-04)*

**Problem:**
Without a limit on file size or PDF page count before a file reaches Textract, a single large or malicious upload can run up Textract and Lambda spend, and since this cost is shared across all tenants, one user's oversized file affects everyone's cost and available capacity.

**Requested Changes:**
- Enforce a maximum file size (25 MB) and PDF page count (50 pages) at the Gatekeeper step, before any paid inference (Textract) runs. Both are configuration values.
- Reject oversized uploads early with reason `FILE_TOO_LARGE` or `TOO_MANY_PAGES` (XS-IMP Appendix A) rather than partially processing them and failing later.

**Constraints (if applicable):**
- Limits need to be generous enough to cover legitimate multi-page statements (e.g., a full monthly credit card statement).

**Interface (if applicable):**
- None — this is enforced internally at the Gatekeeper before the file reaches later stages.

---

# Multi-Tenant Security

## DP-ING-05: Verify Tenant Identity at Ingestion *(was REQ-DP-05)*

**Problem:**
The pipeline currently reads `user_id` and `account_id` from S3 object metadata (tags set at upload time) and trusts them for the rest of the pipeline, including the final Ledger push. This is the same trust class as accepting a user-supplied ID from a request body, which the project's architecture explicitly disallows for data scoping. If the upload path is ever weaker than assumed, this could let one tenant's data get attributed to another tenant's account.

**Requested Changes:**
- Instead of trusting the S3 metadata tags directly, look up the statement's owner from a server-side record created by the authenticated upload request (keyed by `statement_id`), and use that as the source of truth for `user_id`/`account_id` throughout the pipeline.

**Constraints (if applicable):**
- Requires the upload/presign flow to create that server-side record at request time, tied to the authenticated user.

**Interface (if applicable):**
- None new — this changes where the pipeline reads identity from, not what it passes downstream.

## DP-ING-06: Tenant Scoping on the Ledger Push *(was REQ-DP-06)*

**Problem:**
Without a per-request tenant identity (the `X-Internal-User-Id` header the Ledger's `UserContextFilter` expects), tenant scoping on the Ledger push would rely on trusting `user_id`/`account_id` fields in the transaction body — the pattern the architecture explicitly warns against.

**Requested Changes:**
- Forward the verified tenant identity (from DP-ING-05) as a header on every internal Ledger call, so the Ledger enforces scoping the same way it does for user-facing requests, instead of trusting the request body.

**Constraints (if applicable):**
- Must match the header format the Ledger's `UserContextFilter` expects for other internal calls.

**Interface (if applicable):**
- Every internal Ledger call is SigV4-signed by the calling Lambda's role (no shared API key) and carries `X-Internal-User-Id`. The bulk body carries no `userId` or `accountId`.

## DP-ING-07: Least-Privilege IAM Policies *(was REQ-DP-07)*

**Problem:**
Wildcard resources (`resources = ["*"]`) in the pipeline's Lambda policies contradict the stack's least-privilege intent.

**Requested Changes:**
- Scope every IAM statement to the specific resources the action supports (the statement bucket, each DynamoDB table, the state machine) instead of a blanket wildcard. Each Lambda gets only the actions its handler uses.

**Constraints (if applicable):**
- Some AWS APIs don't support resource-level scoping (Textract's `AnalyzeDocument`; `states:SendTaskSuccess`/`SendTaskFailure`, which the task token scopes). Where that's the case, the statement keeps `*` with a comment naming the exception.

**Interface (if applicable):**
- None — this is an infrastructure-only change.

## DP-ING-08: PII and Log Hygiene *(was REQ-DP-08)*

**Problem:**
There's no explicit control over what OCR'd statement content (merchant names, amounts, account/bank details) is allowed to reach application logs. Bank statements are sensitive financial documents, and logging raw extracted text or full transaction payloads would leak PII into CloudWatch, which typically has weaker access controls and longer retention assumptions than the primary data stores.

**Requested Changes:**
- Audit every log statement in the pipeline and restrict them to IDs, counts, and status — never raw transaction content, account numbers, or full OCR text.

**Constraints (if applicable):**
- None.

**Interface (if applicable):**
- None.

---

# Reliability and User Feedback (added 2026-10-21)

## DP-ING-09: Column check expires after 30 minutes, or ends at once on cancel  `Priority: MVP`

**Problem:** The column dialog appears only during the upload session, but a paused import waits up to 24 hours. The 24-hour limit applies to the whole execution, and a state-level Catch doesn't run when the execution times out. The job is left at `PENDING_CSV_COL_MAPPING_CONFIRMATION` until its record expires, and the Ledger's statement stays `PROCESSING`.
**Requirement:**
- The Gatekeeper task state has its own timeout of 30 minutes (`TimeoutSeconds = 1800`), counted from the start of the task, so it covers the wait for the user.
- The 24-hour execution timeout stays as a backstop.
- Every Catch in the state machine, `States.Timeout` included, routes to one **RecordFailure** state. That state:
  1. sets the job to `FAILED` with a reason code (DP-ING-10);
  2. reports the failure to the Ledger (XS-IMP-02);
  3. ends the execution as failed.

  It replaces today's `PipelineFailed` state, which records nothing.
- Closing or cancelling the column dialog calls `POST /jobs/{jobId}/cancel`. The handler checks that the caller owns the job, then sends a task failure with reason `CSV_COL_MAPPING_CANCELLED`, which follows the same RecordFailure path.

**Acceptance Criteria:**
- [Happy] The user closes the dialog. The job is `FAILED` / `CSV_COL_MAPPING_CANCELLED` within 1 minute, and the Ledger statement is `FAILED`.
- [Happy] The user leaves the page without closing the dialog. 30 minutes after the pause, the job is `FAILED` / `CSV_COL_MAPPING_CONFIRMATION_TIMEOUT`.
- [Alt] A confirmation that arrives after the timeout or cancel answers 409 with the reason code, and nothing resumes.
- [Alt] A cancel for a job that isn't paused answers 409. Another user's job answers 404.
- [Fail] If RecordFailure itself fails, Step Functions retries it 3 times. The execution then fails, and the failure is visible in the execution history and the failed-executions alarm.

**Refs:** XS-IMP-02, XS-IMP-03, DP-ING-10.

## DP-ING-10: Job status carries reason codes, never exception text  `Priority: MVP`

**Problem:** The Gatekeeper and Extractor store `str(e)` as the job's error, and `GET /jobs/{jobId}` returns it to the client. The Normalizer and LedgerPush already store reason codes.
**Requirement:**
- Every stage stores only a catalog reason code as the job's error ([XS-IMP Appendix A](../../fintracker-cross-services/specs/XS-IMP-statement-import-contract-spec.md)):
  - for a `PipelineError`, its `reason`;
  - for anything else, `PIPELINE_ERROR`.
- The exception detail is logged at error level with the job id and stage, never with statement content (DP-ING-08).
- A partially completed job stores `failedCount` and `totalCount` as fields instead of a sentence.
- The status API returns `{jobId, status, reason, failedCount, totalCount}`.

**Acceptance Criteria:**
- [Happy] A 30 MB file gives the status `{status: FAILED, reason: FILE_TOO_LARGE}`, with no byte counts or exception text.
- [Alt] An unexpected `KeyError` in the Extractor gives `reason: PIPELINE_ERROR`. The `KeyError` appears in the Extractor's log with the job id.
- [Fail] A unit test fails if any handler can write an error value outside the catalog.

**Refs:** XS-IMP-04, DP-ING-08.

## DP-ING-11: Textract pages are never stored  `Priority: MVP`

**Problem:** Tier 2 renders each PDF page Tier 1 couldn't read and writes it next to the statement file, where it stays forever. Each image is another copy of a bank statement that deletion must find, and the bucket has no lifecycle rule.
**Requirement:**
- A rendered page is sent to Textract as bytes and is never written to S3. A page larger than Textract's synchronous limit is rendered again at lower resolution.
- **Failed pages aren't kept either.** A page that still fails after 3 Textract attempts is logged as `TEXTRACT_PAGE_FAILED` with the statement id, the page number and the error code, never the page content. To debug it, the page is rendered again on demand from the original file, which stays in the bucket until the statement is deleted.
- A one-time script removes the page images already stored next to statement files. The bucket is versioned, so it removes **every version** of each page image and its delete markers, not just the current object. It removes a page image whether or not the statement's original file is still in the bucket: an image whose original was deleted is exactly the copy deletion missed. A user's own upload directly under a statement prefix (for example `statements/{user}/{statement}/page_1.jpg`) never matches, because page images sit one folder deeper.

**Acceptance Criteria:**
- [Happy] A scanned 5-page PDF imports with no new objects in the bucket besides the original file.
- [Alt] A page that fails three times leaves one `TEXTRACT_PAGE_FAILED` log line with the statement id and page number, and no object in the bucket. Extraction continues with the other pages.
- [Alt] After the one-time script runs, `ListObjectVersions` returns no version and no delete marker of any `…/{file name}/page_N.jpg` key under any statement prefix, including prefixes whose original file is gone.
- [Alt] A dry run lists what it would remove and changes nothing; running the script twice is harmless.

**Refs:** DP-ING-01 (Tier 2), DP-ING-08; app doc D15 (deletion window).


## DP-ING-12: Transaction dates reach the Ledger as ISO dates  `Priority: MVP`

**Problem:** Banks write dates as `08/03/2026`, `8/3/26` or, on many PDF statements, `08/03` with no year. The pipeline sends that text to the Ledger unchanged, and the Ledger's bulk import (LG-STMT-02) accepts only `YYYY-MM-DD`, so a real bank file fails the whole import. Every test uses ISO dates, which is why this was never caught.
**Requirement:**
- The Normalizer converts each row's date to `YYYY-MM-DD` before the row leaves the pipeline. Accepted input: ISO dates (`2026-08-03`, optionally with a time part), `M/D/YYYY`, `M/D/YY`, `M-D-YYYY`, `M-D-YY`, and `M/D` or `M-D` with no year. Month comes first: FinTracker supports US banks only (XS-CTX Appendix A: USD).
- A two-digit year is 20YY.
- A date with no year takes the year that puts it inside the statement's declared period (opening to closing date, LG-STMT-07). A period that crosses New Year (Dec 15 – Jan 14) gives December dates the opening year and January dates the closing year. The pipeline reads the declared period with the statement's verified owner (DP-ING-05), so the owner lookup returns `openingDate` and `closingDate` as well.
- A row whose date can't be read, or falls more than 7 days outside the declared period, is skipped and counted in the job's `failedCount`; it is never sent with a guessed date. A statement where no row has a readable date ends as `NO_VALID_TRANSACTIONS`.
- The duplicate fingerprint (LG-STMT-04) uses the converted dates, so one parser serves both.

**Acceptance Criteria:**
- [Happy] A Chase checking CSV row dated `08/03/2026` reaches the Ledger as `2026-08-03` and is stored.
- [Happy] A PDF row dated `12/28` on a statement declared as 2026-12-15 to 2027-01-14 is sent as `2026-12-28`; a row dated `01/05` on the same statement is sent as `2027-01-05`.
- [Alt] `8/3/26` becomes `2026-08-03`; `2026-08-03T00:00:00` becomes `2026-08-03`.
- [Fail] A row dated `13/45/2026` is skipped, the import ends `PARTIALLY_COMPLETED` with `failedCount = 1`, and the log names the job id and row position, never the date text (DP-ING-08).
- [Fail] A test with a real bank export (Chase CSV, a PDF with `MM/DD` dates) fails the build if any date reaches the Ledger in another format.

**Refs:** LG-STMT-02 (bulk import date contract); LG-STMT-07 (declared period); DP-ING-05 (owner lookup); DP-ING-10 (`failedCount`); `duplicate_check/service.py::parse_statement_date` (move it to `shared/` and reuse it).

---

## Change Log

| Change | Reason |
|---|---|
| 2026-10-26: Removed stale text from DP-ING-01 to -07. DP-ING-01: review flag and screenshot confidence restated from XS-IMP-01 and the code; mapping storage, status name, stage mapping and interfaces brought up to DP-MAP and DP-ING-09; `NO_VALID_PAGES` replaced by `NO_VALID_TRANSACTIONS`. DP-ING-02: one bulk call, 8 concurrent Textract calls. DP-ING-03: failure handling points to DP-ING-09; idempotency by row fingerprint. DP-ING-04: limits stated (25 MB, 50 pages). DP-ING-06: SigV4 instead of an API key. DP-ING-07: Comprehend removed; Terraform exceptions named. | Owner request: remove stale specs. The text described behavior that later requirements (XS-IMP, DP-MAP, DP-ING-09/10/11, XS-DPCAT) replaced. No behavior changed. |
| 2026-10-26: DP-ING-11 states that the one-time cleanup removes every version and delete marker, including images whose original is gone; back to In progress. | The bucket is versioned, so deleting without a version id only adds a delete marker and the statement copy stays. The script also skipped images whose original was deleted. |
| 2026-10-26: DP-ING-12 added: dates are converted to ISO before the Ledger push, with the year taken from the declared period when the bank omits it. | Real bank files use `MM/DD/YYYY` or `MM/DD`; the Ledger accepts only ISO dates, so every row of a real file failed. No requirement covered the conversion. |
