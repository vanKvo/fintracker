# Statement Upload Flow — Implemented Behavior (Spec 01)
---

## REQ-STMT-01: Uploading and Processing a Bank Statement

### Business Rules

**Starting an upload.** When a user chooses to upload a bank statement, they pick which account it belongs to, which month it covers, and the file itself. The system verifies the account belongs to that user, prepares a secure, temporary storage location, and creates a tracking record for the import. The user's device then uploads the file directly to that storage location rather than through the main application — this keeps a large file from tying up the application's own resources.

**Reading the file.** What happens next depends on the file type.
- For a spreadsheet-style file (CSV), the system first looks only at the column headers (the file isn't fully read yet) and figures out which column holds the date, which holds the merchant name, and which holds the amount, based on patterns it already knows for that bank.
- For a PDF or a photo of a statement, the system examines each page to determine which ones contain a transaction table worth reading, so it doesn't waste effort on cover pages or unrelated content.

**Confirming an unfamiliar layout.** If the system isn't confident that it identified a CSV's columns correctly (a bank it hasn't seen before, or a layout that changed), it pauses the import and asks the user to review and, if needed, correct the mapping before continuing. Once confirmed, the system remembers that correction so the same bank's files are recognized automatically next time.

**Extracting the transactions.** Once the column layout (for CSV) or the relevant pages (for PDF/photo) are settled, the system reads out the actual list of transactions — date, merchant, and amount for each one.

**Categorizing.** Each extracted transaction is automatically labeled with a spending category based on its merchant name, using categories the system has learned over time.

**Tracking progress.** While all of this is happening in the background, the user's screen periodically checks in on how the import is progressing, so they see live status rather than a frozen page.

### Constraints

- An account can have at most one statement on file per calendar month.
- A spreadsheet (CSV) upload must indicate which bank it came from, since different banks layout their exports differently; a PDF or photo upload doesn't need this, since its layout is read visually instead.
- The system does not yet recognize when the exact same file — or the same real-world statement arriving as a different file — has already been uploaded before. That gap, and the plan to close it, is covered in `ledger-statement-spec-02.md`.

### Data Impact

A tracking record for the statement is created the moment an upload begins, before the file has actually been read — so a record can exist for an upload that later fails partway through.

---

## Interface Details

Endpoint that starts an upload and hands back a location to upload the file to:

```
POST /api/v1/ledger/statements/initiate-upload
```
`services/fintracker-ledger/src/main/java/com/fintracker/ledger/statement/controller/StatementController.java`

```java
public record InitiateStatementUploadRequest(
        UUID accountId, LocalDate statementMonth, String description,
        String sourceFormat,   // PDF | CSV | IMAGE
        String fileName, String bankId,          // bankId required only when sourceFormat = CSV
        LocalDate openingDate, LocalDate closingDate  // required only for PDF/IMAGE
) {}
```
`services/fintracker-ledger/src/main/java/com/fintracker/ledger/statement/dto/InitiateStatementUploadRequest.java`

Progress polling, used by the UI to show live status:

```ts
pollJobStatus(jobId: string, intervalMs = 3000): Observable<JobStatusResponse>
// Polls every intervalMs until a terminal status (COMPLETED / PARTIALLY_COMPLETED / FAILED)
// or PENDING_MAPPING_CONFIRMATION is reached.
```
`fintracker-ui/src/app/core/services/statement.service.ts:131-142`

Column-mapping confirmation, used when the system pauses on an unfamiliar CSV layout:

```
POST /jobs/{jobId}/mapping-confirmation
```
`fintracker-ui/src/app/core/services/statement.service.ts:145`, resumes a paused pipeline
execution at `gatekeeper/mapping_confirmation_handler.py:24`.

## Data Contracts

- `ledger.statements(account_id, statement_month)` has a uniqueness constraint
  (`idx_unique_account_statement_month`, `V1__Initial_Schema.sql:33-34`) enforcing the
  one-statement-per-account-per-month rule.
- `ledger.statements` has no content-based columns today (checked `V1__Initial_Schema.sql` and
  `V11__Add_Statement_Upload_Fields.sql`, which only adds `source_format`/`bank_id`) — see
  spec 02 for the planned addition.
- The S3 object key for an uploaded file is `statements/{userId}/{statementId}/{fileName}`,
  keyed by a freshly generated `statementId`, not by file content.

## Error Handling

- **Account not owned**: the selected account doesn't belong to the requesting user — rejected
  before any tracking record or upload location is created. `StatementServiceImpl.java:60-63`
- **Invalid file type / bank not specified when required**: validated before the tracking record
  is created. `StatementServiceImpl.java:65-80`
- **Duplicate month** (uploading a second statement for an account+month that already has one):
  currently surfaces as a generic server error rather than a clear message — tracked as a gap to
  fix in `ledger-statement-spec-02.md`.

## REST API / Implementation Mapping

| Stage | Owner | Location |
|---|---|---|
| Upload request, ownership check, presigned upload URL | Ledger | `statement/{controller,service,service/S3PresignService}` |
| Header-only read + column-mapping proposal (CSV); page classification (PDF/Image) | Data Pipeline | `gatekeeper/` |
| Pause-and-resume for an unconfirmed CSV mapping | Data Pipeline | `gatekeeper/mapping_confirmation_handler.py` |
| Transaction extraction | Data Pipeline | `extractor/` |
| Category enrichment | Data Pipeline | `normalizer/` |
| Upload modal, upload call, progress polling, mapping confirmation | UI | `features/statements/`, `core/services/statement.service.ts` |
