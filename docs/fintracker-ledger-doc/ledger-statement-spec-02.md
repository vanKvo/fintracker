# Statement Upload Flow — Planned Changes and Known Gaps (Spec 02)

**Scope:** everything in the statement-upload flow that is not yet implemented — one confirmed missing connection between two parts of the system, a set of new requirements to recognize and handle a statement being uploaded more than once, and the date-range collection change (REQ-STMT-07) that keeps those duplicate checks simple. For what already works today, see `ledger-statement-spec-01.md`. See also `flows/uploading-csv-statement-flow.md` for the end-to-end sequence diagram across the Ledger (Statement Module) and Data Pipeline teams.

---

## Shared Contract: Job Lifecycle and Status Payload

Several requirements below (REQ-STMT-04, REQ-STMT-05, REQ-STMT-08) need to tell the user about something discovered *after* the upload request already returned. This section defines that one shared mechanism once, so those requirements can reference it instead of each inventing their own.

### How it works, in plain terms

Starting an upload is a request the system accepts rather than completes. The user gets back a tracking number immediately, and the work of reading and checking the file happens in the background. The user's screen follows along using that tracking number, and anything the system discovers later — the file turned out to be a duplicate, the layout needs confirming, the import finished — is reported through that same channel rather than as a failure of the original request.

Two kinds of "discovered later" outcomes exist, and they behave differently:

- **The system needs a decision from the user.** Work stops and waits. Nothing is lost; the import resumes or is abandoned based on what the user chooses.
- **The system cannot safely continue.** The import ends with a specific, named reason the screen can turn into a clear message, never a generic failure.

The one rule that must never bend: an upload that the background check finds to be a duplicate is never quietly allowed through just because the fast up-front check let it past.

### Technical Reference

**Interface Details** — `initiate-upload` becomes an accepted-not-completed response:

```
POST /api/v1/ledger/statements/initiate-upload
202 Accepted
{
  "jobId": "…",              // === statementId; the tracking id for everything below
  "status": "PROCESSING",
  "uploadUrl": "https://…"   // presigned S3 PUT, unchanged from today
}
```
A synchronous duplicate hit (REQ-STMT-03 / REQ-STMT-06) still short-circuits this with `409 Conflict` before any job exists — 202 and 409 are the only two outcomes of a well-formed request.

Job status, polled by the UI (`GET /jobs/{jobId}`, Data Pipeline-owned, shape extended here):

```jsonc
{
  "jobId": "…",
  "status": "PROCESSING",              // see status list below
  "errorCode": "SERVER_DUPLICATE_DETECTED",  // present only when status = FAILED
  "duplicate": {                        // present only for PENDING_DUPLICATE_RESOLUTION
                                        // and for FAILED/SERVER_DUPLICATE_DETECTED
    "matchType": "CONTENT_FINGERPRINT",
    "existingStatementId": "…",
    "existingUploadDate": "2026-08-27T10:15:00Z",
    "existingTransactionCount": 34
  }
}
```
The `duplicate` object is deliberately the same shape as `DuplicateCheckResponse` (REQ-STMT-03) and the `409` problem-detail properties, so the UI renders one "statement already exists" panel regardless of which of the three paths produced it.

Statuses, extending the set the UI already knows (`statement.service.ts`):

| Status | Meaning | Terminal? |
|---|---|---|
| `PROCESSING` | Normal in-flight work | No |
| `PENDING_MAPPING_CONFIRMATION` | Existing pause — unfamiliar CSV layout | No, waits on user |
| `PENDING_DUPLICATE_RESOLUTION` | **New** — REQ-STMT-04 match found mid-processing, waiting on overwrite/cancel | No, waits on user |
| `COMPLETED` / `PARTIALLY_COMPLETED` / `FAILED` | Final outcome | Yes |

`errorCode` values relevant to this document: `SERVER_DUPLICATE_DETECTED` (REQ-STMT-08).

**Delivery is transport-agnostic.** Polling `GET /jobs/{jobId}` is what ships today (see the Resolved item at the end of this document) and is sufficient for every requirement here. A WebSocket or webhook push carrying the identical payload is a latency/cost optimization that can be added later without changing any of the shapes above — no requirement in this document depends on which transport delivers the status.

**Required UI change — this is a MUST, not incidental:** `pollJobStatus` (`fintracker-ui/src/app/core/services/statement.service.ts:131-142`) currently stops only on a terminal status or `PENDING_MAPPING_CONFIRMATION`. A new waiting status that isn't added to that stop condition would leave the poller silently spinning until its 1000-tick ceiling and the user would never be prompted. `PENDING_DUPLICATE_RESOLUTION` must be added to `PipelineJobStatus` and to the `takeWhile` stop condition, and the caller must handle it the same way it already handles the mapping-confirmation pause.

---


## REQ-STMT-02: Connecting Statement Reading to the Ledger

### Problem

Once the system finishes reading a bank statement and pulling out its transactions, there is currently no connection that saves those transactions into the user's account. The part of the system that reads statements and the part that stores transactions were never properly wired together: a statement can be read successfully from start to finish and the user still ends up with no new transactions to show for it.

### Requested Change

Build a real, secure connection between the statement-reading system and the ledger, so that once transactions are extracted from a statement, they are saved in the correct user's data. The connection should identify itself as a trusted internal caller (not a regular user), and it should be safe to retry — if the same batch of transactions is sent twice, for example, after a network hiccup causes an automatic retry, it should not create the same transactions twice.

The identity of that caller should come from the cloud platform's own identity system — the same mechanism that already decides which parts of the system are allowed to touch storage, queues, and secrets — rather than from a password-like value shared between the two services. Platform-issued identity is granted to a specific component, verified on every request without either side holding a copy, refreshed automatically, and recorded per-caller, so the permission to write transactions can be given to exactly the one component that reads statements and revoked from it after the task is done.

### Constraints

- One call per statement, not one call per transaction: A single batch call — the whole statement's transactions in one request body — collapses that to one round trip and one DB statement. A single multi-row `INSERT ... ON CONFLICT(statement_id, row_fingerprint) DO NOTHING` is natively partial-tolerant, where Postgres skips rows that already exist and inserts the rest, atomically, in one statement. Rows that fail validation (not a duplicate — genuinely malformed) are checked in application code before the insert is built, so one bad row never aborts the whole batch.

- Idempotency key: `row_fingerprint` is a hash of that row's own date/merchant/amount — the same per-transaction hash REQ-STMT-04 already wants for its content fingerprint, reused here rather than inventing a second identifier. A unique index on `(statement_id, row_fingerprint)` is what the `ON CONFLICT` clause above targets — a retried batch call is a safe no-op for every row already recorded, not an error.

- Every internal write must be scoped by the caller-supplied `X-Internal-User-Id`/`accountId` the same way a regular user request is scoped by `UserContextFilter` — never by a value alone inside the JSON body without that cross-check. See the Multi-Tenant Security note below.

- The statement-reading component is trusted to write transactions; it is not trusted to nominate an arbitrary account to write them into. Whatever account it names must still be checked against the statement it claims to be importing.


### Technical Reference

**Interface Details**

New internal-only controller, separate from the user-facing `TransactionController` so the two authentication models (Cognito-derived user identity vs. AWS SigV4 caller identity) are never mixed on the same route tree:

```
POST /api/v1/ledger/transactions/internal/bulk
```
`services/fintracker-ledger/src/main/java/com/fintracker/ledger/transaction/controller/InternalTransactionController.java` (new file)

```java
@RestController
@RequestMapping("/api/v1/ledger/transactions/internal")
public class InternalTransactionController {

    private final TransactionService transactionService;

    public InternalTransactionController(TransactionService transactionService) { ... }

    @PostMapping("/bulk")
    public ResponseEntity<BulkCreateTransactionsResponse> bulkCreate(
            @Valid @RequestBody BulkCreateTransactionsRequest request,
            @RequestAttribute("userId") UUID userId) {
        var response = transactionService.bulkCreateFromStatement(
                request.statementId(), userId, request.transactions());
        return ResponseEntity.ok(response);
    }
}
```

Request/response DTOs (new files):

```java
// services/fintracker-ledger/src/main/java/com/fintracker/ledger/transaction/dto/BulkCreateTransactionsRequest.java
public record BulkCreateTransactionsRequest(
        @NotNull UUID statementId,
        @NotEmpty List<@Valid TransactionLine> transactions
) {
    public record TransactionLine(
            @NotNull LocalDate date,
            @NotNull String merchant,
            @NotNull BigDecimal amount,
            @NotNull String category,
            String subCategory,
            @NotNull @Pattern(regexp = "PURCHASE|CREDIT") String type,
            @NotNull @Pattern(regexp = "[a-f0-9]{64}") String rowFingerprint
    ) {}
}

// services/fintracker-ledger/src/main/java/com/fintracker/ledger/transaction/dto/BulkCreateTransactionsResponse.java
public record BulkCreateTransactionsResponse(
        int insertedCount,
        int skippedDuplicateCount,
        List<FailedRow> failedRows
) {
    public record FailedRow(int index, String reason) {}
}
```

`TransactionService` interface addition (`services/fintracker-ledger/src/main/java/com/fintracker/ledger/transaction/service/TransactionService.java`):

```java
/**
 * REQ-STMT-02. Validates statementId belongs to userId, converts each accepted
 * TransactionLine into a Transaction (source=STATEMENT_UPLOAD, status=PENDING),
 * and delegates to TransactionRepository.bulkInsertIgnoringDuplicates. Rows that
 * fail basic validation (non-positive amount, blank merchant, etc.) are excluded
 * from the insert and reported back as failedRows rather than aborting the batch.
 */
BulkCreateTransactionsResponse bulkCreateFromStatement(
        UUID statementId, UUID userId, List<BulkCreateTransactionsRequest.TransactionLine> lines);
```

`TransactionRepository` interface addition (`services/fintracker-ledger/src/main/java/com/fintracker/ledger/transaction/repository/TransactionRepository.java`):

```java
/**
 * Single multi-row INSERT ... ON CONFLICT (statement_id, row_fingerprint) DO NOTHING.
 * Returns how many of the given rows were actually inserted — the caller derives
 * skippedDuplicateCount as rows.size() - insertedCount.
 */
int bulkInsertIgnoringDuplicates(UUID statementId, List<Transaction> rows);
```
Implemented in `JooqTransactionRepository` (`.../transaction/repository/JooqTransactionRepository.java`) as one `dsl.insertInto(...).columns(...).values(...).onConflictDoNothing().execute()` call built from the full row list, mirroring the multi-row insert pattern already used in `JooqStatementRepository.insert`.

**Caller authentication — AWS SigV4 **

Internal routes are authenticated by AWS SigV4 request signing, verified at the edge in front of the Ledger rather than by application code holding a comparable secret. There is no internal API key to generate, store in SSM, inject as an environment variable, rotate, or send on each request: the caller's Lambda execution role signs each request with credentials the platform issues and rotates on its own, and the edge verifies the signature and evaluates an IAM policy before the request reaches Spring.

| Ledger fronted by | Verification mechanism | Authorization |
|---|---|---|
| API Gateway (private or regional) | `AWS_IAM` authorizer on the internal routes | Resource policy allowing only the dispatcher role's ARN |
| Internal ALB (ECS/EKS) | Signature verified by a lightweight edge filter or sidecar | Caller ARN matched against an allow-list |

Least privilege is expressed as an IAM policy on the Data Pipeline's dispatcher role, naming only the
internal routes — not the Ledger's whole API surface:

```jsonc
// Data Pipeline dispatcher role — the ONLY principal granted these actions
{
  "Effect": "Allow",
  "Action": "execute-api:Invoke",
  "Resource": [
    "arn:aws:execute-api:*:*:*/*/POST/api/v1/ledger/transactions/internal/bulk",
    "arn:aws:execute-api:*:*:*/*/GET/api/v1/ledger/statements/internal/duplicate-check",
    "arn:aws:execute-api:*:*:*/*/PATCH/api/v1/ledger/statements/internal/*/content-fingerprint"
  ]
}
```

The Ledger still needs to know which verified caller it is serving, so the edge forwards the authenticated principal and the application asserts it:

```java
// services/fintracker-ledger/src/main/java/com/fintracker/ledger/config/InternalCallerFilter.java (new)
@Component
public class InternalCallerFilter extends OncePerRequestFilter {
    // Applies only to request paths matching "/api/v1/ledger/**/internal/**".
    //
    // Reads the caller principal the edge injected after verifying the SigV4
    // signature (API Gateway: the requestContext identity ARN, forwarded as a
    // header the edge sets and strips from client input; ALB: the verified ARN
    // from the signing filter). Confirms it is on the configured allow-list of
    // permitted internal caller ARNs, and rejects with 401 via the same
    // ProblemDetail-writing helper pattern UserContextFilter already uses.
    //
    // This filter never verifies a signature itself and holds no secret — the
    // edge has already done the cryptographic work. It exists so the Ledger
    // fails closed if an internal route is ever exposed without the edge in
    // front of it, rather than trusting an unauthenticated request by default.
    //
    // Runs before UserContextFilter for any internal-prefixed path: a verified
    // caller identity AND an X-Internal-User-Id are both required on every
    // internal call — see the Multi-tenant security note below for why proving
    // the caller is not the same as authorizing the target account.
}
```

**Local development.** SigV4 verification is an edge concern with no local equivalent, so local runs skip it the same way the Ledger already runs without an authorizer locally: the profile-gated
allow-list accepts a development principal, and `docker-compose`/Maven runs supply it. Nothing about the request shape changes between local and deployed — only whether a real signature was verified
upstream.

**Data Contracts:** 

New column and unique index on `ledger.transactions`, added by `services/fintracker-ledger/src/main/resources/db/migration/V12__Add_Row_Fingerprint_To_Transactions.sql`:
```sql
ALTER TABLE ledger.transactions ADD COLUMN row_fingerprint CHAR(64);

CREATE UNIQUE INDEX idx_unique_statement_row_fingerprint
    ON ledger.transactions(statement_id, row_fingerprint)
    WHERE row_fingerprint IS NOT NULL;
```
Nullable, and indexed only where non-null, the same pattern already used for `idx_unique_external_tx` in `V1__Initial_Schema.sql:58-59` — manual entries and bank-sync rows never set this column, so they're correctly excluded from the uniqueness check.

**Error Handling**

- **Invalid or missing SigV4 signature**: rejected at the edge (`403` from API Gateway's `AWS_IAM` authorizer, or the ALB signing filter) before the request reaches the Ledger at all. Nothing to implement in application code.
- **Verified caller not on the internal allow-list**: rejected by `InternalCallerFilter` as `401 Unauthorized` before any controller method runs — same short-circuit pattern `UserContextFilter` already uses for a missing `X-Internal-User-Id`. No new `GlobalExceptionHandler` entry needed since the filter writes the `ProblemDetail` response itself.
- **StatementNotFound / StatementNotOwnedByUser** (statementId in the body doesn't belong to the `X-Internal-User-Id` caller claims): `TransactionServiceImpl.bulkCreateFromStatement` throws the existing `StatementNotFoundException` (`.../statement/exception/StatementNotFoundException.java`), already mapped to `404` by `GlobalExceptionHandler.handleStatementNotFound`. Reused as-is — no new exception type.
- **Row-level validation failure** (non-positive amount, blank merchant, `type` outside `PURCHASE`/`CREDIT`): not thrown at all — caught in `TransactionServiceImpl.bulkCreateFromStatement` per-row and returned as a `FailedRow` entry in the `200 OK` response body, per the Constraints section above. Bean Validation (`@Valid`) on `BulkCreateTransactionsRequest.TransactionLine` handles structurally malformed JSON (missing required fields) at the request-parsing layer, before this per-row logic runs, via the already-existing `MethodArgumentNotValidException` → `handleValidation` mapping.

**REST API / Implementation Mapping**

| Stage | File |
|---|---|
| SigV4 verification | Edge (API Gateway `AWS_IAM` authorizer / ALB signing filter) — no Ledger code |
| Verified-caller allow-list check | `config/InternalCallerFilter.java` (new) |
| Caller-side request signing | Data Pipeline dispatcher (SigV4 via its execution role) |
| Bulk-create endpoint | `transaction/controller/InternalTransactionController.java` (new) |
| Request/response shapes | `transaction/dto/BulkCreateTransactionsRequest.java`, `BulkCreateTransactionsResponse.java` (new) |
| Validation + statement-ownership check | `transaction/service/impl/TransactionServiceImpl.bulkCreateFromStatement` (new method) |
| `ON CONFLICT DO NOTHING` multi-row insert | `transaction/repository/JooqTransactionRepository.bulkInsertIgnoringDuplicates` (new method) |
| Schema change | `db/migration/V12__Add_Row_Fingerprint_To_Transactions.sql` (new) |

**Multi-tenant security:** 
This new internal route must scope every write through the request's `X-Internal-User-Id` header the same way `UserContextFilter` scopes every regular user request — `TransactionServiceImpl.bulkCreateFromStatement` must verify the given `statementId` belongs to that `userId` (reusing the same ownership-lookup shape `StatementServiceImpl.deleteStatement` already uses) before inserting a single row, never trusting a `userId`/`accountId` value embedded in the request body. An internal bulk-create endpoint with no tenant check, or one that trusts a body-supplied identity, is a cross-tenant data-injection vector. SigV4 proves the caller is the dispatcher role, and the dispatcher role is legitimately allowed to write transactions. A compromised dispatcher Lambda can sign valid requests naming any account; however, authenticating the caller and authorizing the target account are separate controls, and only the second one stops that. 

---

## REQ-STMT-03: Recognizing the Exact Same File Uploaded Again

### Problem

If a user uploads the exact same file twice — by accident, a double click, or trying again after thinking an upload failed — the system today treats it as two completely unrelated uploads. There is nowhere that recognizes this is the same file that is uploaded.

### Requested Change

When a file is selected for upload, the user's browser should generate a unique fingerprint of the file's exact contents before sending it. The system checks that fingerprint against the account's previous uploads; if it recognizes a match, it stops before wasting any time uploading or processing the file, and tells the user the statement already exists — showing them when it was originally uploaded and how many transactions came from it — so they can decide whether to overwrite it (see REQ-STMT-05) or cancel.

Because a fingerprint sent by the user's browser could in principle be wrong (a bug, a misbehaving browser extension, or something worse), the system should not rely on that fingerprint alone — it should independently recompute the same fingerprint once the file safely arrives on the server side, and trust that computed value as the final answer if the two fingerprints disagree (see REQ-STMT-08 for what happens when they do).

### Constraints

- The fingerprint is required. An upload that arrives without one is rejected outright rather than accepted and processed without the check. Treating it as optional would let any client — buggy or deliberate — opt itself out of duplicate detection simply by omitting a field, which defeats the requirement entirely. Every supported client can compute this before uploading, so there is no legitimate caller this excludes.

- This check only compares a file against that same account's own previous uploads. The same statement accidentally uploaded to the wrong account is a different mistake (the user picked the wrong account) and should not be confused with a true duplicate.

- When more than one check matches, the most specific answer wins. An identical file recognized as an exact match is a more precise statement of what happened than "some statement already covers this month," so the user is told about the exact-file match. The month-level message (REQ-STMT-06) is the fallback, used when nothing more specific applies. The user is never shown two competing explanations for the same rejection.

### Technical Reference

**Interface Details**

`InitiateStatementUploadRequest` gains a **required** `contentHash` and an optional `overwriteStatementId`
(`services/fintracker-ledger/src/main/java/com/fintracker/ledger/statement/dto/InitiateStatementUploadRequest.java`):

```java
public record InitiateStatementUploadRequest(
        @NotNull UUID accountId,
        String description,
        @NotNull @Pattern(regexp = "PDF|CSV|IMAGE") String sourceFormat,
        String fileName, String bankId,
        @NotNull LocalDate openingDate, @NotNull LocalDate closingDate,   // REQ-STMT-07
        @NotNull @Pattern(regexp = "[a-f0-9]{64}") String contentHash,   // REQ-STMT-03, REQUIRED
        UUID overwriteStatementId                                       // REQ-STMT-05, optional
) {}
```
(`statementMonth` is removed per REQ-STMT-07 — see that section.)

Success response is `202 Accepted` carrying the job object and the presigned URL, per the Shared Contract section above; a duplicate hit returns `409 Conflict` instead.

`StatementService.initiateUpload` (`.../statement/service/StatementService.java`) gains a duplicate-check helper used by both this requirement and REQ-STMT-06:

```java
/**
 * REQ-STMT-03/06 check, run synchronously inside initiateUpload before any S3 URL or statement row is created.
 * Checks contentHash and statement_month (both always present) against the account's existing statements.
 * Specificity priority: EXACT_FILE is evaluated first and returned if it matches; SAME_MONTH is only
 * consulted when no exact-file match exists. At most one match is ever returned.
 * Throws nothing — the caller (initiateUpload) decides whether to surface a DuplicateStatementException or proceed with an overwrite.
 */
Optional<DuplicateCheckResult> checkForDuplicateByContentHash(
        UUID accountId, String contentHash, LocalDate statementMonth);

record DuplicateCheckResult(
        DuplicateStatementException.MatchType matchType, UUID existingStatementId,
        OffsetDateTime existingUploadDate, int existingTransactionCount) {}
```

`StatementRepository` additions (`.../statement/repository/StatementRepository.java`):

```java
Optional<Statement> findByAccountIdAndContentHash(UUID accountId, String contentHash);

Optional<Statement> findByAccountIdAndStatementMonth(UUID accountId, LocalDate statementMonth);
```

New internal-only controller (reused by REQ-STMT-04's mid-processing check and REQ-STMT-08's disagreement handling — see those sections):

```
GET /api/v1/ledger/statements/internal/duplicate-check?accountId=...&contentHash=...
GET /api/v1/ledger/statements/internal/duplicate-check?accountId=...&contentFingerprint=...
```
`services/fintracker-ledger/src/main/java/com/fintracker/ledger/statement/controller/InternalStatementController.java` (new file), protected by the same SigV4 + `InternalCallerFilter` + `X-Internal-User-Id` pattern as REQ-STMT-02's bulk-create endpoint (and covered by the same IAM policy shown there). `contentHash` and `contentFingerprint` are mutually exclusive on a single call — the Gatekeeper calls this endpoint at two different pipeline stages (REQ-STMT-03's server-side recompute right after upload, REQ-STMT-04's aggregate fingerprint after parsing), never both at once:

```java
@RestController
@RequestMapping("/api/v1/ledger/statements/internal")
public class InternalStatementController {

    @GetMapping("/duplicate-check")
    public ResponseEntity<DuplicateCheckResponse> checkDuplicate(
            @RequestParam UUID accountId,
            @RequestParam(required = false) String contentHash,
            @RequestParam(required = false) String contentFingerprint,
            @RequestAttribute("userId") UUID userId) {
        // Verifies accountId belongs to userId (same ownership guard as
        // StatementServiceImpl.initiateUpload). Exactly one of contentHash /
        // contentFingerprint is expected; dispatches to
        // StatementService.checkForDuplicateByContentHash (statementMonth
        // omitted — this internal query is never about the month check) or
        // StatementService.checkForDuplicateByContentFingerprint accordingly.
        // Both present, or neither, is rejected as 400 (IllegalArgumentException)
        // rather than silently picking one.
    }
}
```

```java
// services/fintracker-ledger/src/main/java/com/fintracker/ledger/statement/dto/DuplicateCheckResponse.java (new)
public record DuplicateCheckResponse(
        boolean duplicateFound, String matchType, UUID existingStatementId,
        OffsetDateTime existingUploadDate, Integer existingTransactionCount
) {}
```

New domain exception, thrown by `StatementServiceImpl.initiateUpload` and mapped by `GlobalExceptionHandler` (used by REQ-STMT-03, REQ-STMT-06, and indirectly REQ-STMT-05):

```java
// services/fintracker-ledger/src/main/java/com/fintracker/ledger/statement/exception/DuplicateStatementException.java (new)
public class DuplicateStatementException extends RuntimeException {
    public enum MatchType { EXACT_FILE, CONTENT_FINGERPRINT, SAME_MONTH }
    // fields: matchType, existingStatementId, existingUploadDate, existingTransactionCount
    // + getters, used directly by GlobalExceptionHandler to populate ProblemDetail properties
}
```

**Data Contracts:** new column and per-account index on `ledger.statements`, added by
`services/fintracker-ledger/src/main/resources/db/migration/V13__Add_Statement_Content_Hash.sql`:
```sql
ALTER TABLE ledger.statements ADD COLUMN content_hash CHAR(64);

CREATE INDEX idx_statements_account_content_hash
    ON ledger.statements(account_id, content_hash) WHERE content_hash IS NOT NULL;
```

A follow-up migration, `V15__Make_Statement_Content_Hash_Unique.sql`, replaces that index with a
**unique** one (`idx_unique_account_content_hash`, same columns and same partial predicate). The
pre-check and the insert are separate statements, so two concurrent uploads of the same file can
both pass the check before either inserts, and a non-unique index would store both rows and
violate this requirement silently. Making it unique turns that race into a constraint violation
for the loser, which `StatementServiceImpl` catches and translates into the contractual `409` by
re-running the duplicate lookup against the now-visible winner. This gives the exact-file check the
same DB-level backstop the same-month check already has from `idx_unique_account_statement_month`,
rather than trusting the pre-check alone.

**Error Handling**

- **DuplicateStatement (matchType=EXACT_FILE)**: `StatementServiceImpl.initiateUpload` calls `checkForDuplicateByContentHash`; a match (and no `overwriteStatementId` given) throws `DuplicateStatementException`, mapped by a new `GlobalExceptionHandler.handleDuplicateStatement` to `409 Conflict` with `type=.../problems/duplicate-statement`, carrying `matchType`, `existingStatementId`, `existingUploadDate`, `existingTransactionCount` as `ProblemDetail` properties.
- **contentHash missing, or present but not 64 hex chars**: rejected as `400` by the existing `MethodArgumentNotValidException` → `handleValidation` path via the `@NotNull`/`@Pattern` annotations on the DTO field — no new handler needed, and no code path anywhere accepts an upload without one.

**REST API / Implementation Mapping**

| Stage | File |
|---|---|
| Request shape (`contentHash`, `overwriteStatementId`) | `statement/dto/InitiateStatementUploadRequest.java` |
| Synchronous duplicate check inside upload | `statement/service/impl/StatementServiceImpl.initiateUpload` |
| Content-hash duplicate-check logic | `statement/service/StatementService.checkForDuplicateByContentHash` (new method) |
| Content-hash lookup query | `statement/repository/JooqStatementRepository.findByAccountIdAndContentHash` (new method) |
| Internal recheck endpoint (called by Gatekeeper) | `statement/controller/InternalStatementController.java` (new) |
| Duplicate exception + RFC 9457 mapping | `statement/exception/DuplicateStatementException.java` (new), `config/GlobalExceptionHandler.handleDuplicateStatement` (new) |
| Schema change | `db/migration/V13__Add_Statement_Content_Hash.sql` (new) |

---

## REQ-STMT-04: Recognizing the Same Statement Uploaded as a Different File

### Problem

REQ-STMT-03 only catches an identical file uploaded twice. It misses the same real-world statement arriving as a different file — for example, a corrected re-export from the bank, or the same period downloaded once as a CSV and once as a PDF. These have different bytes but describe the same transactions.

An earlier idea for solving this was to fingerprint just the first and last transaction on the statement (their dates and amounts). However, many accounts have the same recurring first-of-month transactions (rent, payroll) every single month, so two genuinely different months' statements could easily produce an identical "first and last transaction" fingerprint. Anchoring on just the two endpoints throws away nearly all the information that would actually distinguish one statement from another.

### Requested Change

After the system has fully read a file's transactions, it should build a fingerprint from the entire set of transactions — the number of transactions, their total value, and the earliest and latest dates among them — rather than only the first and last row. This fingerprint is compared against the account's
previous statements the same way REQ-STMT-03's file fingerprint is.

Because two different statements could still coincidentally produce a similar fingerprint (most plausible on an account with very little activity in a given month), a match here should always be treated as "probably the same, please confirm" rather than an automatic block that refuses a legitimate upload, which would be a worse outcome than occasionally asking the user to
confirm it's a different statement.

Since this fingerprint can only be known after the file has already been fully read — later in the process than REQ-STMT-03's check — a match here is discovered mid-way through processing, not at the very start of the upload. See REQ-STMT-05 for how the user is prompted at that later point.

### Constraints

- **Resolved — PDF/photo scope:** spreadsheet files only for now, confirmed. A PDF/photo reading is OCR-derived and noisier; extending this check to those formats is deferred as future work, not because it's hard, but because the failure mode of skipping it there is mild (at worst, an occasional missed duplicate that REQ-STMT-06's month check or REQ-STMT-03's exact-file check still has a chance to catch) and the formats aren't build-blocking today.
- **Resolved — storage shape:** a single aggregate hash, not individually-stored per-transaction hashes. Combine each row's fingerprint (the same one REQ-STMT-02 reuses for idempotency) into one value — sort them, concatenate, hash once more — so comparison stays a single indexed column lookup, the same shape as REQ-STMT-03's `content_hash`. Storing every individual transaction hash would only pay off for a future "explain why these look similar" screen or partial-overlap detection, and REQ-STMT-05 already puts reconciling individual transactions out of scope — no reason to pay for that storage/complexity now for a capability nothing else in this document uses yet. Revisit if that future screen becomes a real ask.
- **Ledger scope is narrow here.** Computing the fingerprint from the fully-read transaction set is entirely a Data Pipeline responsibility (it's the only side that has read the file by this point) — the Ledger's only job for this requirement is to (a) store the value once computed and (b) answer whether it matches an existing statement, using the same internal endpoint REQ-STMT-03 already defines.

**Cross-Service Note (informational, Data Pipeline team's own scope):** how and when the Normalizer/Data Dispatcher stage computes this aggregate fingerprint from the extracted rows, and calls the two Ledger endpoints below, is specified in `data-pipeline-spec-01.md`, not here.

### Technical Reference

**Interface Details**

One new endpoint, to persist the computed fingerprint once known (there is no request path today that writes it):

```
PATCH /api/v1/ledger/statements/internal/{id}/content-fingerprint
{ "contentFingerprint": "<sha256 hex>" }
204 No Content
```
`InternalStatementController.java` (same file as above), new method:

```java
@PatchMapping("/{id}/content-fingerprint")
public ResponseEntity<Void> recordContentFingerprint(
        @PathVariable UUID id,
        @Valid @RequestBody RecordContentFingerprintRequest request,
        @RequestAttribute("userId") UUID userId) {
    statementService.recordContentFingerprint(id, userId, request.contentFingerprint());
    return ResponseEntity.noContent().build();
}
```
```java
// services/fintracker-ledger/src/main/java/com/fintracker/ledger/statement/dto/RecordContentFingerprintRequest.java (new)
public record RecordContentFingerprintRequest(@NotNull @Pattern(regexp = "[a-f0-9]{64}") String contentFingerprint) {}
```

`StatementService` additions — `checkForDuplicateByContentFingerprint` is a separate method from REQ-STMT-03's `checkForDuplicateByContentHash`, not an overload of it: this check is scoped purely to the aggregate fingerprint, with no `statementMonth`/`EXACT_FILE` concern at this later pipeline stage (that was already resolved at `initiateUpload` time):
```java
void recordContentFingerprint(UUID statementId, UUID userId, String contentFingerprint);

/**
 * REQ-STMT-04. Checks the account's existing statements for a matching
 * content_fingerprint. A match here is always MatchType.CONTENT_FINGERPRINT —
 * see REQ-STMT-05/08 for how the caller uses a "probably the same, please
 * confirm" result rather than a hard block.
 */
Optional<DuplicateCheckResult> checkForDuplicateByContentFingerprint(
        UUID accountId, String contentFingerprint);
```
`StatementRepository` addition:
```java
Optional<Statement> findByAccountIdAndContentFingerprint(UUID accountId, String contentFingerprint);
void updateContentFingerprint(UUID statementId, String contentFingerprint, UUID userId);
```

The `CONTENT_FINGERPRINT` branch of `DuplicateStatementException.MatchType` (defined under REQ-STMT-03) is this requirement's match type, returned by `checkForDuplicateByContentFingerprint` above.

**Data Contracts:** new column and per-account index on `ledger.statements`, added by
`services/fintracker-ledger/src/main/resources/db/migration/V17__Add_Statement_Content_Fingerprint.sql`:
```sql
ALTER TABLE ledger.statements ADD COLUMN content_fingerprint CHAR(64);

CREATE INDEX idx_statements_account_content_fingerprint
    ON ledger.statements(account_id, content_fingerprint) WHERE content_fingerprint IS NOT NULL;
```

**Error Handling**

- **DuplicateStatement (matchType=CONTENT_FINGERPRINT)**: **not** a `409` — REQ-STMT-03's `409` is only reachable at `initiate-upload` time, and that request returned long before this check runs. `GET .../duplicate-check` answers with `200 OK` and `duplicateFound=true` rather than throwing, because a match here is a "probably the same, please confirm" signal the caller acts on, not an error the caller aborts on. The caller turns that into the `PENDING_DUPLICATE_RESOLUTION` job status defined in the Shared Contract section, carrying the same `duplicate` payload; see REQ-STMT-05 for what the user does next.
- **Statement not found / not owned** (`id` in the `PATCH` path doesn't belong to the `X-Internal-User-Id` caller claims): reuses the existing `StatementNotFoundException` → `404` mapping, same as REQ-STMT-02.

**REST API / Implementation Mapping**

| Stage | File |
|---|---|
| Fingerprint persistence endpoint | `statement/controller/InternalStatementController.recordContentFingerprint` (new method) |
| Fingerprint lookup (endpoint shared with REQ-STMT-03, dispatch differs by query param) | `statement/controller/InternalStatementController.checkDuplicate` |
| Persist/query logic | `statement/service/impl/StatementServiceImpl.recordContentFingerprint`, `checkForDuplicateByContentFingerprint` (new methods) |
| Repository queries | `statement/repository/JooqStatementRepository.findByAccountIdAndContentFingerprint`, `updateContentFingerprint` (new methods) |
| Schema change | `db/migration/V17__Add_Statement_Content_Fingerprint.sql` (new) |

---

## REQ-STMT-05: Letting the User Decide on a Detected Duplicate

### Problem

REQ-STMT-03 and REQ-STMT-04 detect that a statement was likely already uploaded, but neither one defines what the user actually sees or does next.

### Requested Change

Whenever either check finds a likely duplicate, show the user the existing statement's upload date and transaction count, and offer two clear choices:
- Overwrite — replace the existing import with the new one, or 
- Cancel — leave everything as it was and discard the new upload
attempt.

Choosing to overwrite means the old statement and everything that came from it is removed, and the new file is processed as if it were the first upload for that period. It's a clean replacement, not an attempt to merge the two — reconciling individual transactions between two similar statements is a much harder problem than detecting they're likely duplicates, and isn't
something this covers.

Because REQ-STMT-03's check happens right at the start of an upload, an overwrite there can happen immediately, as part of the same request. REQ-STMT-04's check happens partway through processing, after the system is already partway through reading the file — an overwrite there
needs the in-progress import to pause and wait for the user's decision before it can either continue or stop.

The user is offered the same two choices, and sees the same information about the existing statement, in both cases — the only difference is when the question is asked. Whichever way the user answers the later question, the paused import does not simply resume: choosing to overwrite starts the upload again cleanly from the beginning, and choosing to cancel discards it. Either way the system does not leave a half-finished import behind.

### Constraints

- Before overwriting, the system must re-confirm the existing statement actually belongs to the requesting user — never assume it does just because a duplicate check pointed to it.
- If keeping a record of overwritten statements (for audit or "undo") ever becomes a requirement, that is a separate, larger feature, not an incremental change to this one.
- **Resolved gap found while speccing this requirement — "overwrite" does not currently do what it says.** `ledger.transactions.statement_id` is declared `REFERENCES ledger.statements(statement_id) ON DELETE SET NULL` (`V1__Initial_Schema.sql:42`), not `ON DELETE CASCADE`. `StatementServiceImpl.deleteStatement`'s log line already claims "Cascaded transactions removed," but under the current FK, deleting a statement only orphans its transactions (`statement_id` becomes `NULL`) — it does not remove them. That contradicts this requirement's "the old statement and everything that came from it is removed" and is a pre-existing bug independent of anything new in this document (it affects today's manual statement delete too). **MUST fix as part of this requirement**, since REQ-STMT-05's overwrite path depends on the delete actually being a delete: change the FK to `ON DELETE CASCADE` (see Data Contracts below) rather than adding an explicit application-level delete-transactions-then-delete-statement step — a DB-enforced cascade is atomic and can't be bypassed by a future code path that deletes a statement without remembering to also delete its transactions.

- **The half-finished import must be cleaned up, not orphaned.** The mid-processing path already created a tracking record for the new upload before the duplicate was discovered. Because an overwrite is delivered as a fresh upload rather than a resume, that earlier record would otherwise be left behind as a permanent, empty, failed-looking entry in the user's statement list. It must be discarded as part of resolving the duplicate, on both the overwrite and the cancel answer.

**Cross-Service Note (informational, Data Pipeline team's own scope):** the REQ-STMT-04 (mid-processing) pause itself — parking the job in `PENDING_DUPLICATE_RESOLUTION` (Shared Contract section) while waiting for the user's answer, and terminating it once answered — is Data Pipeline job-orchestration logic, specified in `data-pipeline-spec-01.md`. The Ledger's only role in that path is answering the duplicate-check query (REQ-STMT-03/04) and, once told "overwrite," performing the delete-and-recreate below — it has no notion of a "paused job" itself.

### Technical Reference

**Interface Details**

No new endpoint for the REQ-STMT-03 (pre-processing) case — overwrite rides on the same `initiate-upload` call, using the `overwriteStatementId` field already added under REQ-STMT-03:

```java
// StatementServiceImpl.initiateUpload, extended:
if (request.overwriteStatementId() != null) {
    statementRepository.findByIdAndUserId(request.overwriteStatementId(), userId)
            .orElseThrow(() -> new StatementNotFoundException(request.overwriteStatementId()));
    statementRepository.deleteByIdAndUserId(request.overwriteStatementId(), userId);
    // falls through to the normal create-statement-and-presign path below
}
```

**There is exactly one overwrite mechanism, for both cases.** An earlier draft floated a second one (`POST /jobs/{jobId}/duplicate-resolution`); it is dropped. For the REQ-STMT-04 (mid-processing) case the Ledger exposes nothing new either — the client, on seeing `PENDING_DUPLICATE_RESOLUTION` in the job status, re-submits the exact same `initiate-upload` call with `overwriteStatementId` set, going through the identical code path. The Ledger does not distinguish "overwrite decided at start of upload" from "overwrite decided mid-processing" — both are the same request shape, and a mid-processing overwrite is a *new* job (new `jobId`), not a resumption of the paused one.

Cleanup of the paused job's own tracking record (per the Constraints above) uses the existing `deleteByIdAndUserId` — the client sends it as an ordinary statement delete for the abandoned `jobId` before (overwrite) or instead of (cancel) re-submitting. No new endpoint.

No changes needed to `StatementRepository.deleteByIdAndUserId`'s Java signature — its existing behavior changes correctly once the FK constraint below is fixed.

**Data Contracts:** fixes the FK gap described in Constraints above —
`services/fintracker-ledger/src/main/resources/db/migration/V18__Cascade_Delete_Transactions_On_Statement_Delete.sql`:
```sql
ALTER TABLE ledger.transactions DROP CONSTRAINT transactions_statement_id_fkey;
ALTER TABLE ledger.transactions
    ADD CONSTRAINT transactions_statement_id_fkey
    FOREIGN KEY (statement_id) REFERENCES ledger.statements(statement_id) ON DELETE CASCADE;
```

**Error Handling**

- **overwriteStatementId not found / not owned by requesting user**: `StatementNotFoundException` → existing `404` mapping (same exception REQ-STMT-02/04 reuse) — thrown before any delete happens, per the Constraints re-confirmation requirement.
- **overwriteStatementId belongs to a different account than `accountId` in the same request**: rejected as `IllegalArgumentException` → existing `400` mapping (`handleIllegalArgument`) — an overwrite is scoped to "replace this statement with this new upload for the same account," not a way to move a statement between accounts.

**REST API / Implementation Mapping**

| Stage | File |
|---|---|
| Overwrite request field | `statement/dto/InitiateStatementUploadRequest.overwriteStatementId` (REQ-STMT-03) |
| Ownership re-check + delete-then-create | `statement/service/impl/StatementServiceImpl.initiateUpload` |
| Cascade delete fix | `db/migration/V18__Cascade_Delete_Transactions_On_Statement_Delete.sql` (new) |

---

## REQ-STMT-06: Giving a Clear Answer When a Month Is Already Taken

### Problem

The system already refuses to let an account have two statements for the same calendar month — but today, when that refusal happens, the user just sees a generic, unhelpful error message with no indication of what actually went wrong.

### Requested Change

Recognize this specific situation when it happens and show the user a clear, specific message — reusing the same "statement already exists" prompt described in REQ-STMT-03/05 — instead of a generic error.

### Constraints

- This is a different situation from REQ-STMT-03/04's content-based checks — a user might legitimately upload a genuinely different, corrected statement for a month that already has one, and this message should still appear, since the rule is about the month, not the file's content.
- **This is the fallback explanation, not the first one.** Per the specificity-priority rule in REQ-STMT-03, if the upload is also recognized as the exact same file already on record, the user is told that instead — it's the more precise account of what happened. The month message is what the user sees when nothing more specific matched.
- Detect this synchronously, at `initiate-upload` time, by querying first — not by attempting the insert and catching the resulting DB constraint violation. A pre-check produces the existing statement's id/date/count needed for the response; catching `DataIntegrityViolationException` after the fact would not, without a second query anyway.

### Technical Reference

**Interface Details**

Folded into the same `StatementService.checkForDuplicateByContentHash` helper REQ-STMT-03 defines — no separate method. `StatementServiceImpl.initiateUpload` calls it with the request's `closingDate`-derived `statementMonth` (see REQ-STMT-07) always populated, regardless of whether `contentHash` was provided:

```java
// StatementServiceImpl.initiateUpload, order of checks:
// 1. accountId ownership (existing)
// 2. sourceFormat/bankId validation (existing)
// 3. checkForDuplicateByContentHash(accountId, contentHash, statementMonth)
//      -> specificity priority: EXACT_FILE evaluated first; SAME_MONTH consulted
//         only if no exact-file match. Returns at most one match, never both.
// 4. if overwriteStatementId present, skip step 3's result and overwrite (REQ-STMT-05)
// 5. otherwise, if step 3 found a match, throw DuplicateStatementException
// 6. otherwise, create the statement row + presigned URL, return 202 Accepted
//      with { jobId, status: "PROCESSING", uploadUrl } (Shared Contract section)
```

`StatementRepository.findByAccountIdAndStatementMonth` (defined under REQ-STMT-03) is this requirement's query — no new repository method beyond what REQ-STMT-03 already adds.

**Data Contracts:** none new — reuses the existing `idx_unique_account_statement_month` unique index (`V1__Initial_Schema.sql:33-34`), which stays in place as the DB-level backstop even though the application now checks proactively first.

**Error Handling**

- **DuplicateStatement (matchType=SAME_MONTH)**: same `DuplicateStatementException` → `409 Conflict` mapping as REQ-STMT-03, `matchType` set to `SAME_MONTH` instead of `EXACT_FILE`.
- **DB unique-index violation reached anyway** (a race between two concurrent requests for the same account+month, both passing the pre-check before either commits): falls through to `GlobalExceptionHandler`'s existing `handleUnexpected` today, still a generic `500`. **Deferred, not a MUST** — add a `DataIntegrityViolationException` handler that re-queries and returns the same `409` shape only if this race is observed in practice; a single-account upload race is rare enough (a user does not normally double-submit the same statement from two tabs simultaneously) that the pre-check alone covers the realistic case, and the existing unique index still guarantees correctness (no duplicate row can ever be committed) even while the error message stays generic in that rare race.

**REST API / Implementation Mapping**

| Stage | File |
|---|---|
| Synchronous month check | `statement/service/impl/StatementServiceImpl.initiateUpload` (via `checkForDuplicateByContentHash`) |
| Month-match query | `statement/repository/JooqStatementRepository.findByAccountIdAndStatementMonth` (REQ-STMT-03) |

---

## REQ-STMT-07: Collecting the Statement Date Range Upfront, for Every Format

### Problem

Today only a PDF or photo upload asks the user for the statement's opening and closing dates; a CSV upload only asks for a single "statement month," picked by the user before the file has even been read. This creates two problems. First, a real-world statement routinely contains transactions from the tail end of the previous month and the start of the next, so asking the user to commit to one "month" for the whole statement is inherently ambiguous — they're guessing at a label the system could otherwise derive from the file itself. Second, statements should be organized in the UI by their real closing date, and the actual date range should be shown to the user (e.g., "Aug 3 – Sep 2, 2026") — a single month field can't represent that.

### Requested Change

Collect `openingDate` and `closingDate` from the user for every format, CSV included — not just PDF/Image as today. The system derives the statement's grouping month from `closingDate` automatically (the month a bank statement is conventionally labeled by), rather than asking the user to pick a month directly. The full range is stored and displayed, not collapsed into a single month value.

This resolves a timing problem an earlier draft of this document was heading toward: deriving the period from the file's actual extracted transactions (rather than user input) sounds appealing, but for CSV that information isn't available until after the Extractor has fully read the file — well after the statement record is created and after REQ-STMT-06's one-per-month check would need to run. Asking the user for the range upfront (the same way PDF/Image already does) keeps period information available at `initiate-upload` time for every format, so REQ-STMT-06 can stay exactly as simple as it already is: a synchronous check at upload time, not a check that has to wait for extraction to finish.

### Constraints

- The user-declared range is a label for organizing and displaying the statement, not a validated fact — nothing in this requirement checks the declared range against the file's actual transaction dates. (A later, independent check along those lines is possible future work, but isn't part of closing this gap.)
- `statementMonth` as a field disappears from the client-facing request; the client sends `openingDate`/`closingDate` and the server computes the grouping month from `closingDate`.
- `closingDate` must not be before `openingDate` — validated server-side, not just assumed from correct client behavior.

### Technical Reference

**Interface Details:** `InitiateStatementUploadRequest` (`services/fintracker-ledger/src/main/java/com/fintracker/ledger/statement/dto/InitiateStatementUploadRequest.java`) drops the required `statementMonth` field; `openingDate`/`closingDate` become `@NotNull` for every `sourceFormat` (already reflected in the record shape shown under REQ-STMT-03), replacing today's conditional requirement in `StatementServiceImpl` that only enforces them for `PDF`/`IMAGE`.

```java
// StatementServiceImpl.initiateUpload, new validation step, run alongside the existing
// accountId/sourceFormat/bankId checks (before checkForDuplicateByContentHash):
if (request.closingDate().isBefore(request.openingDate())) {
    throw new IllegalArgumentException("closingDate must not be before openingDate.");
}
LocalDate statementMonth = request.closingDate().withDayOfMonth(1);
```
`statementMonth` becomes a local, server-computed value threaded into `checkForDuplicateByContentHash` only — it is no longer a field read off the request, and (once `statement_month` becomes a generated column, see Data Contracts below) it is never passed to `statementRepository.insert` either; the database derives its own copy from `closingDate` independently, so the two can't drift apart.

`StatementRepository.insert`'s signature (`.../statement/repository/StatementRepository.java`) drops `statementMonth` entirely — it is no longer accepted as a parameter at all, since the database now derives it directly from `closingDate` (see Data Contracts below), and also gains `openingDate`/`closingDate` for storage:
```java
Statement insert(UUID statementId, UUID accountId, String s3ObjectKey,
                  LocalDate openingDate, LocalDate closingDate, String description,
                  String sourceFormat, String bankId);
```
`JooqStatementRepository.insert` and its `mapToStatement`/`mapToStatementWithCounts` helpers gain the two new columns and stop writing `statement_month` in the `INSERT` column list (the database computes it); the `Statement` record (`.../statement/model/Statement.java`) gains `LocalDate openingDate, LocalDate closingDate` fields, and its `STATEMENT_COLUMNS` list in `JooqStatementRepository` gains `opening_date`/`closing_date` (both must appear in the existing `GROUP BY`, per the comment already on that list; `statement_month` also stays in that list unchanged — a generated column reads back like any other column, only writes to it are disallowed).

**Data Contracts:** `services/fintracker-ledger/src/main/resources/db/migration/V14__Add_Statement_Opening_Closing_Date.sql`. `statement_month` becomes a Postgres generated column derived from `closing_date`, rather than a value every caller (application code, and previously the client) had to compute and keep in sync by convention — the database is now the only source of truth for the derivation, so it is structurally impossible for `statement_month` to disagree with `closing_date` going forward.

Converting an *existing* column to `GENERATED` requires dropping and re-adding it, which would silently NULL out `statement_month` for every pre-existing row (all of them start with `closing_date` NULL, since this migration is what introduces that column) — a real data-loss risk for REQ-STMT-06's duplicate-month check on historical statements. The migration backfills `closing_date` from the current `statement_month` value first so no existing row loses its month, then converts the column, then recreates the unique index the column drop implicitly takes with it:
```sql
ALTER TABLE ledger.statements
    ADD COLUMN opening_date DATE,
    ADD COLUMN closing_date DATE;

-- Backfill closing_date for pre-existing rows from their current statement_month,
-- so no historical row loses its month once statement_month becomes generated
-- below. opening_date is left NULL for these rows — there is no historical
-- source to backfill it from, and it was never used for grouping/uniqueness.
UPDATE ledger.statements SET closing_date = statement_month WHERE closing_date IS NULL;

-- Dropping statement_month also drops idx_unique_account_statement_month
-- (V1__Initial_Schema.sql:33-34); recreated identically below.
ALTER TABLE ledger.statements DROP COLUMN statement_month;
ALTER TABLE ledger.statements
    ADD COLUMN statement_month DATE GENERATED ALWAYS AS (date_trunc('month', closing_date)::date) STORED;

CREATE UNIQUE INDEX idx_unique_account_statement_month
    ON ledger.statements(account_id, statement_month);

-- New rows always populate closing_date (enforced by @NotNull on the request
-- DTO, not a DB NOT NULL constraint here — every pre-existing row was just
-- backfilled above, so none needs a synthetic value).
```
`statement_month` stays the indexed grouping column REQ-STMT-06 queries against — only *how* its value comes to exist changes; the query shape (`findByAccountIdAndStatementMonth`) and the unique index's guarantee are unaffected.

**Error Handling**

- **closingDate before openingDate**: `IllegalArgumentException` → existing `400` mapping (`handleIllegalArgument`) — no new exception type.
- **openingDate/closingDate missing**: existing `MethodArgumentNotValidException` → `handleValidation` path via `@NotNull`, same as any other required field today.

**REST API / Implementation Mapping**

| Stage | File |
|---|---|
| Request shape change | `statement/dto/InitiateStatementUploadRequest.java` |
| Range validation + month derivation | `statement/service/impl/StatementServiceImpl.initiateUpload` |
| Storage | `statement/repository/{StatementRepository,JooqStatementRepository}.java`, `statement/model/Statement.java` |
| Schema change | `db/migration/V14__Add_Statement_Opening_Closing_Date.sql` (new) |

---

## REQ-STMT-08: When the Server-Side Recheck Disagrees with the Client

### Problem

REQ-STMT-03 has the Ledger do a fast check against the client-computed fingerprint at
`initiate-upload` time — before the file itself has gone anywhere — and separately requires an
authoritative recompute once the file actually lands, "trusting that computed value as the final
answer if the two ever disagree." What isn't defined anywhere is what happens *when* they disagree:
the Ledger's optimistic pre-check already said "proceed" and handed back a presigned upload URL,
the file is already in S3, and the Data Pipeline's Gatekeeper stage is the one that discovers,
mid-pipeline, that this is actually a duplicate. There's no pipeline status for this today, and the
Gatekeeper's exceptions currently only map to a generic `FAILED`.

### Requested Change

Resolve this through the ordinary job lifecycle described in the Shared Contract section, rather
than any new mechanism. Because starting an upload only ever *accepts* the work rather than
completing it, the system already has a channel for reporting something discovered afterwards. The
background check runs on the file that actually arrived, and if it finds the upload to be a
duplicate that the fast up-front check missed, the import ends there with a specific, named reason
(`SERVER_DUPLICATE_DETECTED`) instead of a generic failure. The user's screen — which is already
following the upload's progress — picks that up on its next check-in and shows a clear explanation,
naming the statement that already exists and when it was uploaded, rather than an unexplained
"upload failed."

**MUST — the one behavior that cannot bend:** the system must never treat this as a success and
create a duplicate statement just because the earlier optimistic check passed. Failing the import is
the required outcome; the quality of the message is what the deferred item below improves.

**Deferred — the polished version:** offering the same overwrite-or-cancel choice here that
REQ-STMT-05 offers for the mid-processing case (REQ-STMT-04) is a nicer experience, but this path
only triggers when a client's fingerprint was wrong or fabricated — described in REQ-STMT-03 itself
as "a bug, a misbehaving browser extension, or something worse." That's a low-likelihood, largely
adversarial-or-buggy-client case, not a routine one; a clear failure the user can act on (discard
the failed entry, try again) is a proportionate first version. Upgrade it to the same pause-and-ask
flow later if this path turns out to trigger more often than expected in practice.

### Constraints

- This only covers a *disagreement* between the two checks. A missing client fingerprint is not one
  of them: REQ-STMT-03 requires that fingerprint, so an upload without it never reaches this point —
  it is rejected outright at the start.
- **Ledger scope is narrow here, same as REQ-STMT-04.** The Ledger's entire contribution to this
  requirement is answering the duplicate-check query truthfully and completely — it has no notion
  of a "pipeline job" or a failed status itself. Deciding to end the import, and under what reason,
  is Data Pipeline logic.

**Cross-Service Note (informational, Data Pipeline team's own scope):** how the Gatekeeper maps a
`duplicateFound=true` response from the endpoint below into `status: "FAILED"` /
`errorCode: "SERVER_DUPLICATE_DETECTED"` with the `duplicate` payload attached, is specified in
`data-pipeline-spec-01.md`, not here. The status/errorCode/payload *shape* is fixed by the Shared
Contract section of this document, since the UI renders it.

### Technical Reference

Reuses REQ-STMT-03's `GET /api/v1/ledger/statements/internal/duplicate-check` endpoint
(`InternalStatementController.checkDuplicate`) exactly as-is — no new Ledger endpoint, method, or
DTO for this requirement. The Gatekeeper's authoritative recompute calls that same endpoint twice, at
two different moments, each with exactly one of the two query parameters set: once right after
upload with its recomputed `contentHash` (dispatching to `checkForDuplicateByContentHash`), and once
after REQ-STMT-04's mid-processing stage has run, with `contentFingerprint` (dispatching to
`checkForDuplicateByContentFingerprint`). A `duplicateFound=true` response from either call is this
requirement's disagreement signal. This is the same kind of trusted internal call REQ-STMT-02 defines
for pushing transactions — it reuses that same internal-caller identity and auth pattern
(SigV4 + `InternalCallerFilter` + `X-Internal-User-Id`) rather than inventing a second one.

**Data Contracts:** none new.

**Error Handling:** none new on the Ledger side — this requirement's failure handling
(`status: "FAILED"`, `errorCode: "SERVER_DUPLICATE_DETECTED"`) is a Data Pipeline job-status concern,
not a Ledger exception or HTTP response shape. The Ledger's only obligation is that `GET .../duplicate-check`
never returns `duplicateFound=false` for a fingerprint that in fact matches an existing statement —
covered by the same repository queries REQ-STMT-03/04 already define.

**REST API / Implementation Mapping**

| Stage | File |
|---|---|
| Endpoint reused for the recheck | `statement/controller/InternalStatementController.checkDuplicate` (REQ-STMT-03) |

---

## Resolved item

**Completion notification.** Confirmed implemented, functionally — via polling, not a real-time push. `fintracker-ui/src/app/core/services/statement.service.ts`'s `pollJobStatus` checks `GET /jobs/{jobId}` every 3 seconds until a terminal status, and the upload dialog is wired to it end-to-end (verified working, including the `PENDING_MAPPING_CONFIRMATION` pause). This satisfies the actual requirement — the user's screen updates without a manual refresh — even though CLAUDE.md's architecture doc describes a persistent WebSocket connection for this instead. A WebSocket push would reduce latency and eliminate the polling overhead, but that's a performance/cost optimization on top of a working feature, not a gap blocking it — reasonable to defer.
