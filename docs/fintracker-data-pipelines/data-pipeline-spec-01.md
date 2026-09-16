# Import Channels

## REQ-DP-01: Hardening Imports

A. Business Rules:
- Format Detection: The Gatekeeper detects whether an uploaded file is PDF, CSV, or Image from magic bytes/extension before any other processing runs. **[Implemented — `gatekeeper/service.py::_detect_format`]**
- CSV Bank-Specific Column Mapping: The user selects a bank institution when uploading a CSV. The system looks up that bank's known column-name variants (a per-bank mapping table) and proposes a mapping to the canonical `date`/`merchant`/`amount` fields, instead of requiring one fixed header set. **[Not Implemented — current check only accepts the literal headers `date`, `merchant`, `amount`; a bank exporting `Transaction Date`/`Description`/`Debit` is rejected]**
- Mapping Transparency: After a CSV is uploaded, the system shows the user every column it found and how each one was mapped — a matched column paired with its canonical field, and any column it could not confidently map left visibly unmapped — rather than silently accepting or silently discarding columns. **[Not Implemented]**
- User Mapping Confirmation Gate: Processing does not continue until the user reviews and confirms (or manually corrects) the proposed mapping in the mapping dialog. This is what keeps a bank's column-name change from producing wrong data instead of an error — the user catches it at confirmation time instead of transactions being posted with columns swapped. **[Not Implemented]**
- CSV Validity Gate: A CSV is only accepted if it has at least one data row and at least the confirmed `date`/`merchant`/`amount` fields mapped. **[Partially Implemented — a row/header check exists, but only against the fixed header set, and with no user mapping step]**
- CSV Transaction Parsing: A CSV whose mapping is confirmed has its rows parsed into transactions (using the confirmed mapping) and carried through Normalization and the Ledger push, the same as the OCR path. **[Not Implemented — confirmed gap: `GatekeeperOutput.csv_s3_key` is produced for a valid CSV but no downstream stage reads it; the Extractor only reads `valid_page_keys`, which is always empty for CSV, so every CSV upload currently completes with zero transactions imported and no error surfaced]**
- Text-Layer Fast Path (Tier 1): For a PDF with an extractable text layer (i.e., not a scanned image), the system reads transaction rows directly from the text layer (via PyMuPDF) without calling OCR. **[Not Implemented]**
- Textract Fallback (Tier 2): For a PDF/image with no usable text layer, or where Tier 1 finds no transaction-shaped rows, the system calls Textract `AnalyzeDocument` with `FeatureTypes=["TABLES"]` per page — the same call both decides whether a page has a transaction table and extracts it, so there's no separate classify-then-extract round trip. A page with no `TABLE` blocks in the response is junk; a page with `TABLE` blocks is extracted directly from that same response. **[Not Implemented as a fallback — `AnalyzeDocument` is already called this way in `extractor/service.py`, but only after a separate YOLO classification step (being removed) rather than as Tier 1's fallback]**
- Confidence Scoring: Every PDF/Image transaction row carries a confidence signal reflecting how it was extracted (text layer > Textract). CSV rows are always high-confidence once the user has confirmed the mapping, since there's no OCR step involved. **[Not Implemented]**
- Manual Review Routing: A row below the confidence threshold is posted to the Ledger as `PENDING_APPROVAL` for manual review instead of being accepted. **[Not Implemented]**
- Screenshot Stricter Gate: Screenshots (single image, no multi-page context) use a lower auto-post confidence threshold than PDFs, since they're the easiest format to be blurry, cropped, or mis-rotated. **[Not Implemented]**

B. Constraints:
- The tiering logic (Tier 1/2) applies only to PDF and Image formats — it must not add latency to the CSV happy path.
- Text-layer detection must reliably distinguish a digitally-generated PDF from a scanned one (e.g., a minimum extractable-character threshold per page) so Tier 1 is never skipped for a PDF that could have used it.
- No new Ledger transaction status is introduced — low-confidence rows reuse the existing `PENDING_APPROVAL` status.
- Per-bank CSV column mappings live in a runtime-writable store, not a file bundled into the Lambda deployment — see Data Impacts below for why.
- The mapping dialog must show unmapped columns even when every required field (`date`/`merchant`/`amount`) was successfully mapped, so the user can catch a column the system mapped to the wrong field, not just columns it failed to map at all.

C. Data Impacts:
- `GatekeeperOutput` needs a new field recording which tier classified each page (`TEXT_LAYER` / `TEXTRACT`).
- `NormalizedTransaction` needs a `confidence` (or `needs_review`) field carried into the Ledger push payload.
- Bank column mappings move from a bundled `bank_mappings.json` to a DynamoDB table, one item per `bank_id` (same table/pattern as the existing MerchantRegistry). Reasoning: once users can correct a mapping at upload time, that correction needs to persist and improve future uploads for that bank without a code deploy — a file shipped with the Lambda package can't be written back to at runtime. The table is seeded from a baseline mapping per bank at deploy time and updated whenever a user confirms a manual correction, the same write-back pattern the Categorizer already uses for merchant learning.
- A new job status `PENDING_MAPPING_CONFIRMATION` is introduced for CSV jobs waiting on the user's mapping dialog.
- No Ledger schema changes — `PENDING_APPROVAL` already exists on the Ledger side.

D. Pipeline Stage Mapping:
Location: `services/fintracker-data-pipeline/src/gatekeeper/`, `src/extractor/`
- Gatekeeper Lambda — format detection; for CSV, proposes a column mapping and pauses the job at `PENDING_MAPPING_CONFIRMATION`; for PDF/Image, runs Tier 1/2 page classification.
- (New) Mapping Confirmation handler — invoked when the user submits the confirmed/corrected mapping from the dialog; writes corrections back to the bank mapping table and resumes the Step Functions execution.
- Extractor Lambda — CSV row parsing (new, using the confirmed mapping), text-layer parsing (Tier 1, new), Textract `AnalyzeDocument` (Tier 2).
- Normalizer Lambda — attaches `confidence`/`needs_review` before handoff to the Data Dispatcher.

E. Interface Details:
Location: `services/fintracker-data-pipeline/src/gatekeeper/service.py`, `src/extractor/service.py`

```python
def propose_column_mapping(bucket: str, csv_s3_key: str, bank_id: str) -> ColumnMappingProposal:
    """Looks up bank_id's known mapping and matches it against the CSV's
    actual headers. Returns every column found, each either paired with its
    matched canonical field or flagged unmapped, for the confirmation dialog.
    Never parses transaction rows — that only happens after confirmation.
    """

def confirm_column_mapping(job_id: str, bank_id: str, confirmed_mapping: dict[str, str]) -> None:
    """Persists the user-confirmed mapping (writing back any correction to
    the bank_id mapping table) and resumes the paused Step Functions
    execution for job_id.
    """

def parse_csv_transactions(bucket: str, csv_s3_key: str, confirmed_mapping: dict[str, str]) -> list[RawTransaction]:
    """Parses CSV rows using the user-confirmed mapping. Raises
    CsvRowParseError per row on a bad date/amount rather than failing
    the whole file.
    """

def classify_and_extract_page(bucket: str, page_key: str) -> PageExtraction:
    """Tier 1 (text layer) -> Tier 2 (Textract AnalyzeDocument+TABLES)
    waterfall for a single PDF/Image page. Tier 2's single call both
    classifies (has a TABLE block?) and extracts the page — no separate
    classification call.
    """
```

F. Error Handling:
- **UNSUPPORTED_FORMAT**: Uploaded file is not PDF, CSV, or Image after Gatekeeper detection — reject immediately, job status `FAILED`, no downstream stage invoked.
- **UNKNOWN_BANK_MAPPING**: Selected bank has no baseline mapping in the mapping table — the mapping dialog still opens with every column shown as unmapped, so the user can build the mapping from scratch instead of being blocked.
- **MAPPING_CONFIRMATION_TIMEOUT**: User never responds to the mapping dialog — job status `FAILED` after a bounded wait, so the paused Step Functions execution doesn't stay open indefinitely; the user can re-upload and retry.
- **CSV_ROW_PARSE_ERROR**: Individual row fails to parse against the confirmed mapping (bad date/amount format) — skip that row, log it, continue with the rest of the file; do not fail the whole statement for one bad row.
- **TEXT_LAYER_EMPTY**: Tier 1 text-layer read succeeds but yields zero transaction-shaped rows on a digitally-generated PDF — fall through to Tier 2 rather than treating the document as empty.
- **TEXTRACT_TRANSIENT_FAILURE**: Tier 2 `AnalyzeDocument` call is throttled or hits a transient AWS error — retry with backoff via the existing `tenacity` policy; on exhaustion, mark that page failed and continue with the rest of the statement rather than failing the whole job.
- **NO_VALID_PAGES**: Every page in the statement is rejected by both tiers (no text layer and no `TABLE` blocks found) — job status `FAILED` with this reason, mirroring today's `HasValidPages?` gate in the state machine.

---

# Scalability

## REQ-DP-02: Warm-Start Caching and Parallel Processing

A. Business Rules:
- Parallel Page Extraction: Pages within one statement (text-layer parses or Textract `AnalyzeDocument` calls) are processed concurrently rather than in a sequential loop. **[Not Implemented — `extract_transactions` loops over `page_keys` one at a time]**
- Parallel/Batched Ledger Push: Normalized transactions for one job are pushed to the Ledger concurrently or as a single batch call, not one HTTP request per transaction. **[Not Implemented — `push_transactions_to_ledger` loops and calls the internal endpoint once per transaction]**
- Tier Skipping at Scale: When Tier 1 (text-layer) fully classifies a document, Tier 2 (Textract) is never invoked for that document — this is what actually caps Textract spend as upload volume grows, not just per-call optimization. **[Not Implemented — depends on REQ-DP-01's tiering existing first]**

B. Constraints:
- Concurrency within a job is bounded by the Lambda's memory/CPU allocation and by how many concurrent requests the Ledger's internal endpoint can safely accept.

C. Data Impacts:
- No database schema changes. Lambda memory/timeout configuration may need adjustment to support concurrent per-page work within one invocation (or a Step Functions `Map` state, if concurrency is moved to the orchestration layer instead of in-process).

D. Pipeline Stage Mapping:
Location: `services/fintracker-data-pipeline/src/extractor/service.py` (parallel extraction), `src/data_dispatcher/service.py` (parallel/batched push)

E. Interface Details:
Location: `services/fintracker-data-pipeline/src/data_dispatcher/service.py`

```python
def push_transactions_to_ledger(
    job_id: str,
    transactions: list[dict],
) -> LedgerPushResult:
    """Pushes all transactions for one job concurrently (or as one batch
    call, if the Ledger's internal endpoint is extended to accept a list).
    Aggregates per-transaction outcomes into success/total counts; a single
    transaction failing does not block the others from being pushed.
    """
```

F. Error Handling:
- **PARTIAL_EXTRACTION_FAILURE**: [One page's concurrent extraction call fails while others in the same statement succeed — record that page as failed, continue processing the rest, report the statement as partially extracted rather than failing the whole job]
- **PARTIAL_LEDGER_PUSH_FAILURE**: [One transaction's push to the Ledger fails while others in the same batch succeed — record it in `LedgerPushResult` (`success_count`/`total_count`), and per REQ-DP-03 the job status must reflect partial failure rather than being marked `COMPLETED`]
- **LEDGER_THROTTLED**: [Concurrency causes the Ledger's internal endpoint to rate-limit — back off and retry with reduced concurrency rather than failing the whole batch on the first 429/503]

## REQ-DP-03: Failure Handling and Idempotency

**Problem:**
The pipeline has no retry/catch logic configured at the Step Functions level, so if any stage fails (e.g., Textract throttling past its retries, a bad Normalizer input), the whole job dies silently — the job's status is never updated to `FAILED`, so it just sits at its last known state until it quietly expires. Separately, S3 can deliver the same upload event more than once, and nothing stops the pipeline from running twice and pushing duplicate transactions to the Ledger.

**Requested Changes:**
- Add failure handling to every Step Functions task so any failure updates the job status to `FAILED` with a reason, instead of leaving the job stuck.
- Make the Ledger push idempotent per statement, so re-running the same statement (whether from a duplicate S3 event or a retried step) doesn't create duplicate transactions.

**Constraints (if applicable):**
- None beyond what Step Functions and the Ledger API already support.

**Interface (if applicable):**
- The Ledger's internal push endpoint should accept or generate an idempotency key (e.g., derived from `statement_id`) and safely no-op on a repeat.

---

# Costs

## REQ-DP-04: Cap Resource Consumption Per Upload

**Problem:**
There's no limit today on file size or PDF page count before it's handed to Textract. A single large or malicious upload can run up Textract/Comprehend/Lambda spend, and since this cost is shared across all tenants, one user's oversized file affects everyone's cost and available capacity.

**Requested Changes:**
- Enforce a maximum file size and page count at the Gatekeeper step, before any paid inference (Textract, Comprehend) runs.
- Reject oversized uploads early with a clear, user-facing error rather than partially processing them and failing later.

**Constraints (if applicable):**
- Limits need to be generous enough to cover legitimate multi-page statements (e.g., a full monthly credit card statement).

**Interface (if applicable):**
- None — this is enforced internally at the Gatekeeper before the file reaches later stages.

---

# Multi-Tenant Security

## REQ-DP-05: Verify Tenant Identity at Ingestion

**Problem:**
The pipeline currently reads `user_id` and `account_id` from S3 object metadata (tags set at upload time) and trusts them for the rest of the pipeline, including the final Ledger push. This is the same trust class as accepting a user-supplied ID from a request body, which the project's architecture explicitly disallows for data scoping. If the upload path is ever weaker than assumed, this could let one tenant's data get attributed to another tenant's account.

**Requested Changes:**
- Instead of trusting the S3 metadata tags directly, look up the statement's owner from a server-side record created by the authenticated upload request (keyed by `statement_id`), and use that as the source of truth for `user_id`/`account_id` throughout the pipeline.

**Constraints (if applicable):**
- Requires the upload/presign flow to create that server-side record at request time, tied to the authenticated user.

**Interface (if applicable):**
- None new — this changes where the pipeline reads identity from, not what it passes downstream.

## REQ-DP-06: Tenant Scoping on the Ledger Push

**Problem:**
The Data Dispatcher authenticates to the Ledger with a single static internal API key shared across all tenants, and doesn't forward any per-request tenant identity (like the `X-Internal-User-Id` header the Ledger's `UserContextFilter` expects). This means tenant scoping on write, if it happens at all, relies on trusting the `user_id`/`account_id` fields embedded in the transaction body — the same pattern the architecture explicitly warns against.

**Requested Changes:**
- Forward the verified tenant identity (from REQ-DP-05) as a header on every internal Ledger call, so the Ledger enforces scoping the same way it does for user-facing requests, instead of trusting the request body.

**Constraints (if applicable):**
- Must match whatever header/claim format the Ledger's `UserContextFilter` already expects for other internal calls.

**Interface (if applicable):**
- Internal Ledger push endpoint contract: add a required tenant-identity header (e.g., `X-Internal-User-Id`) alongside the existing internal API key.

## REQ-DP-07: Least-Privilege IAM Policies

**Problem:**
The Textract and Comprehend IAM policies attached to their Lambdas use a wildcard resource (`resources=["*"]`), which contradicts the stack's own least-privilege intent. Separately, the Comprehend classifier is called with a placeholder account ID in its ARN, which will fail at runtime as written.

**Requested Changes:**
- Scope IAM policies to the specific resources these services support (e.g., the specific Comprehend classifier endpoint ARN) instead of a blanket wildcard.
- Fix the placeholder account ID in the Comprehend endpoint ARN so the categorizer's Comprehend fallback actually works.

**Constraints (if applicable):**
- Some AWS APIs (like Textract's `AnalyzeDocument`) don't support resource-level scoping at all — where that's the case, document it as an accepted exception rather than leaving it silently identical to a scoped policy.

**Interface (if applicable):**
- None — this is an infrastructure-only change.

## REQ-DP-08: PII and Log Hygiene

**Problem:**
There's no explicit control over what OCR'd statement content (merchant names, amounts, account/bank details) is allowed to reach application logs. Bank statements are sensitive financial documents, and logging raw extracted text or full transaction payloads would leak PII into CloudWatch, which typically has weaker access controls and longer retention assumptions than the primary data stores.

**Requested Changes:**
- Audit every log statement in the pipeline and restrict them to IDs, counts, and status — never raw transaction content, account numbers, or full OCR text.

**Constraints (if applicable):**
- None.

**Interface (if applicable):**
- None.
