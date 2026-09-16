# Statement Upload Flow — Test Coverage for Spec 02

Test inventory for the Ledger-side implementation of `ledger-statement-spec-02.md` for REQ-STMT-02, REQ-STMT-03, REQ-STMT-06 and REQ-STMT-07

**Source of truth:** `golden_tests/run_tests_f2p.sh`. That script rewrites all nine test files
listed below to their canonical locations on every run, then executes them. Anything added
directly to those nine files is discarded the next time it runs — see "Tests kept outside the
generator" for the one class that deliberately lives elsewhere.

**Status as of 2026-09-08:** all 89 fail-to-pass tests pass, and the full Ledger suite
(89 unit + 276 integration = 365 tests) is green. Requirements covered: REQ-STMT-02, 03, 06, 07.
REQ-STMT-04, 05 and 08 have no Ledger implementation yet and therefore no tests here.

## How to run

```bash
cd services/fintracker-ledger
export JAVA_HOME=$(/usr/libexec/java_home -v 21)   # Java 21 — see "Known environment traps"
../../golden_tests/run_tests_f2p.sh
```

---

# F2P TESTS (89)

## Unit layer — surefire, 61 tests

### StatementServiceTest (14)

**`checkForDuplicateByContentHash()` (4)**
1. REQ-STMT-03 — an `EXACT_FILE` match is found by content hash, scoped to the account, with
   `existingTransactionCount` populated from the matched statement's own count.
2. REQ-STMT-06 — a `SAME_MONTH` match is found when no content-hash match exists.
3. REQ-STMT-03/06 specificity priority — `EXACT_FILE` takes priority when a statement matches
   both, and the `SAME_MONTH` query is never issued once `EXACT_FILE` has matched. The
   highest-signal case in the spec and the easiest to get backwards.
4. Neither `contentHash` nor `statementMonth` matching returns empty — the baseline negative.

**`initiateUpload()` (5)**
5. REQ-STMT-07 — `closingDate` before `openingDate` is rejected, and nothing is inserted.
6. REQ-STMT-07 — `closingDate` equal to `openingDate` is accepted (single-day statement). The
   spec rejects only *before*, not *not-after*; this pins the boundary.
7. REQ-STMT-07 — the grouping month is derived from `closingDate`, truncated to the first of
   that month, server-side rather than accepted from the client.
8. REQ-STMT-03 — a matching `contentHash` throws `DuplicateStatementException` and creates
   nothing: no presigned URL, no statement row.
9. Multi-tenant — an `accountId` not belonging to the user throws before `S3PresignService` is ever reached.

**`initiateUpload()` — REQ-STMT-06 same-month duplicate (1)**
10. A genuinely different file whose month is already taken throws with `matchType=SAME_MONTH`.

**Request bean validation (4)**
11. REQ-STMT-07 — a CSV upload with no `openingDate` is rejected.
12. REQ-STMT-07 — a CSV upload with no `closingDate` is rejected.
13. REQ-STMT-03 — an upload with no `contentHash` at all is rejected. This is the constraint that
    changed during speccing: the hash is required, so no client can opt itself out of duplicate detection by omitting a field.
14. REQ-STMT-03 — `contentHash` must be exactly 64 lowercase hex characters.

### StatementControllerTest (2)
15. REQ-STMT-03 — a successful `initiate-upload` answers `202 Accepted` with the job object, per the Shared Contract section of the spec.
16. Multi-tenant — the upload is attributed to the `X-Internal-User-Id`-derived identity, never to anything in the request body.

### InternalStatementControllerTest (3)
17. Delegates to `checkForDuplicateByContentHash` and reports the match.
18. Multi-tenant — an `accountId` not belonging to the calling identity is rejected, so an
    internal caller cannot probe another tenant's account for statement existence.
19. `contentHash` and `contentFingerprint` are mutually exclusive: both, or neither, is a `400`
    rather than silently answering a different question than the one asked.

### TransactionServiceTest (40)

**Pre-existing REQ-2.2 / REQ-2.3 regression cases (32)** — approve (5), bulk approve (2),
toggle-exclude (3), split (4), delete-manual (2), update category (2), update amount (3),
append tags (7), create manual (4). Carried forward unchanged; they are the reason the
`Transaction` record shape change is safe.

**`bulkCreateFromStatement()` (5)**
20. REQ-STMT-02 multi-tenant — a `statementId` not belonging to the caller's
    `X-Internal-User-Id` throws `StatementNotFoundException` and never reaches the repository.
21. Boundary — an empty transaction list inserts nothing and reports `insertedCount=0` without
    calling the repository.
22. Partial failure — a malformed row inside an otherwise-valid batch is excluded and reported,
    not aborting the batch. Asserts both `failedRows` content and that only the valid row
    reaches the repository.
23. Idempotency — `skippedDuplicateCount` reflects rows the repository reports as already
    present, simulating a retried batch.
24. Multi-tenant — transactions are created against the statement's own `accountId`.
    `BulkCreateTransactionsRequest` carries no `accountId` field by design; this pins that the
    service resolves it from the statement rather than from client input, and that
    `source`/`status`/`rowFingerprint` are set correctly on every row.

**Row-validation edge cases (3)**
25. A `type` outside `PURCHASE`/`CREDIT` is reported as a `failedRow`, not inserted.
26. `failedRows` carry the row's index in the *original* request, not its position after
    filtering — the only way the caller can identify which input row failed.
27. Boundary — a batch in which every row is malformed inserts nothing and never calls the
    repository.

### InternalTransactionControllerTest (2)
28. The bulk-create route is reachable and delegates correctly.
29. Multi-tenant — identity comes from the header, never the body.

## Integration layer — failsafe, Testcontainers, 28 tests

### JooqStatementRepositoryIT (8)
30. RLS — a statement is invisible to another user and visible to its owner. Proves tenant
    isolation at the database layer, independent of the application's `WHERE user_id = ?`.
31. REQ-STMT-03 — `findByAccountIdAndContentHash` finds a real match, scoped to that account,
    against a real database rather than a stubbed return value.
32. REQ-STMT-03 — the same `contentHash` on a *different* account is not a match. The same file
    uploaded to two accounts must not collide.
33. REQ-STMT-06 — `findByAccountIdAndStatementMonth` finds the account's existing statement.
34. REQ-STMT-07 — `insert()` round-trips `openingDate`/`closingDate`, and the database derives
    `statement_month` itself. Also the test that caught a real bug: `INSERT ... RETURNING` under
    `FORCE ROW LEVEL SECURITY` silently returned zero rows, because Postgres re-checks the
    SELECT policy against the freshly written row before including it in `RETURNING` output.
    Fixed by replacing `.returning()` with an explicit follow-up `SELECT`.
35. REQ-STMT-06/07 — the DB-level unique index on `(account_id, statement_month)` still rejects
    a second statement for the same month after V16 converted that column to `GENERATED`.
36. REQ-STMT-06 multi-tenant — another account's statement for the same month is not reported.
37. Multi-tenant — duplicate lookups made with another tenant's real `accountId` return nothing.

### StatementUploadDuplicateIT (3)
38. REQ-STMT-03 — re-uploading the exact same file is recognized as `EXACT_FILE` end to end.
39. REQ-STMT-06/07 — a genuinely different file whose `closingDate` falls in an already-taken
    month is rejected as `SAME_MONTH`.
40. REQ-STMT-03 multi-tenant — the identical file uploaded by a different user to their own
    account is not a duplicate.

### JooqTransactionRepositoryIT (11)
41-44. Pre-existing: RLS isolation, `CHECK (amount != 0)`, and two split-exclusion cases.
45. REQ-STMT-02 — `bulkInsertIgnoringDuplicates` is idempotent: calling it twice with identical
    `rowFingerprint`s leaves exactly 2 rows, not 4. Proves against a real database that V12's
    unique index actually makes `ON CONFLICT DO NOTHING` idempotent.
46. REQ-STMT-02 — a row that already exists from an earlier, separate call is skipped and left
    unmodified, confirming `DO NOTHING` rather than `DO UPDATE` semantics.
47. REQ-STMT-02 multi-tenant — the bulk insert cannot write into another tenant's account.
48. REQ-STMT-02 multi-tenant — rows written by the bulk insert are correctly attributed.
49. REQ-STMT-02 multi-tenant — an identical `rowFingerprint` under two different statements both
    insert. The index is scoped per statement, so one tenant's upload can never suppress
    another's row.
50. REQ-STMT-02 — rows with no `rowFingerprint` are exempt from the uniqueness check, so manual
    and bank-sync entries are unaffected by the partial index.
51. REQ-STMT-02 — the same `rowFingerprint` twice within one batch inserts once.

### InternalEndpointSecurityIT (6)
52. REQ-STMT-02 — the internal bulk-create endpoint fails closed with `401` when no verified
    caller principal is present. This is the guard that matters if an internal route is ever
    exposed without the edge in front of it.
53. REQ-STMT-02 — a verified caller ARN that is not on the allow-list is rejected.
54. REQ-STMT-02 — an allow-listed caller ARN is admitted and reaches the controller.
55. REQ-STMT-03 — the internal duplicate-check endpoint fails closed the same way.
56. REQ-STMT-02 — a call carrying neither a caller ARN nor a user identity is rejected.
57. REQ-STMT-02 — user-facing routes are unaffected: a normal request carrying only the user
    header still works, so the new filter did not change the existing authentication model.

---

## Multi-tenant emphasis

The spec's own REQ-STMT-02 text says authenticating the caller and authorizing the target account
are separate controls, and that only the second stops a compromised dispatcher. SigV4 proves the
caller *is* the dispatcher; the dispatcher is legitimately allowed to write transactions, so a
compromised one signs perfectly valid requests naming any account it likes. The suite proves that
second control at every layer between an internal caller and another tenant's ledger:

| Layer | Proof | Tests |
|---|---|---|
| HTTP controllers | Identity comes from the header, never the body | 16, 18, 29 |
| Filter chain | Internal routes fail closed without an allow-listed caller ARN | 52-57 |
| Service | Statement ownership is checked before any insert | 9, 20, 24 |
| Postgres (RLS) | The database refuses a cross-tenant read or write | 30, 37, 41, 47-49 |

---

## Tests kept outside the generator

**`transaction/service/BulkCreateAmountValidationTest.java` (4 tests, all passing).**

`run_tests_f2p.sh` rewrites `TransactionServiceTest.java` verbatim on every run. Four
amount-validation cases written against this codebase before that script existed are not in its
inventory and were being silently discarded on each run. They now live in their own class, which
the generator does not touch:

- Both signs accepted — a negative `PURCHASE` and a positive `CREDIT` are both valid.
- Exactly zero rejected — the table's `CHECK (amount != 0)` would otherwise abort the whole batch.
- `DECIMAL(15,2)` overflow rejected in both directions, with the exact ceiling
  (`9999999999999.99`) accepted.
- Sub-cent precision rejected, while trailing zeros (`25.500`) and whole numbers (`600`) are
  accepted — the check is on significant scale, not on the literal the pipeline happened to send.

These matter because `amount` is only `@NotNull` on the request record: nothing in Bean Validation
constrains it to the column's `DECIMAL(15,2)` shape or its non-zero CHECK. Without a per-row
service check, such rows reach the multi-row INSERT and abort the entire batch at the database —
precisely the "one bad row never aborts the whole batch" constraint REQ-STMT-02 forbids.

---

# P2P BASELINE

The authoritative pass-to-pass boundary is the **full Ledger suite**, not a subset.
REQ-STMT-02 changed `Transaction`'s record shape (added `rowFingerprint`), which every consumer of
`TransactionRepository` reads — including the budget module's spend-calculation queries — and
`GlobalExceptionHandler` / `InternalCallerFilter` are process-wide rather than statement-scoped.

Confirmed green on 2026-09-08:

| Phase | Tests |
|---|---|
| Surefire (unit) | 89 |
| Failsafe (integration) | 276 |
| **Total** | **365** |

The budget IT classes most likely to catch a regression from the `Transaction` record change are
`BudgetSpendEnrichmentIT` and `BudgetYearListingIT`, which exercise `TransactionRepository`
queries directly despite living outside the statement/transaction packages.

`golden_tests/run_tests_p2p.sh` is still an unimplemented placeholder that exits 1; the full-suite
run above is what currently serves as the P2P check.

---

# Known environment traps

Both of these cost a full debugging cycle on 2026-09-08 and neither is a code defect.

**1. Java 21 is required; Java 25 fails 14 tests with a misleading error.** On Java 25, Mockito's
inline mock maker cannot mock `S3PresignService` and reports *"Mockito cannot mock this class"* —
which reads like a test-design problem but is purely a JDK-version mismatch. `pom.xml` sets
`<java.version>21</java.version>`; export a matching `JAVA_HOME` before running anything:

```bash
export JAVA_HOME=$(/usr/libexec/java_home -v 21)
```

**2. A stale migration in `target/classes` breaks every IT with a confusing Flyway error.**
Maven does not remove deleted resources from `target/classes` on an incremental build, so a
renamed migration leaves its old copy behind and both versions sit in Flyway's migration path.
Flyway applies the stale one, and the renamed one then dies on
`column "opening_date" of relation "statements" already exists` — which looks like a broken
migration but is purely a build-output artifact. Every IT then fails with
`NoClassDefFoundError: Could not initialize class AbstractIntegrationTest`, hiding the real cause
entirely.

**Always run `mvn clean` after renumbering or renaming a migration.** This has already bitten this
codebase twice: once when `V14__Add_Statement_Opening_Closing_Date.sql` was renamed to `V16__...`
during development, and again when the statement migrations were renumbered to close the V14/V15
gap (see "Migration numbering" below). A fresh container is unaffected — it has no `target/` to go
stale.

---

# Migration numbering

The statement migrations were renumbered on 2026-09-08 to remove a gap left by earlier drafts.
Safe to do because no environment had applied any migration past V11 at the time — the local
`fintracker` database's Flyway history stopped there, so no recorded version needed rewriting.
**This is a one-time correction, not a repeatable operation:** once a migration has run anywhere,
its version is recorded in `flyway_schema_history` and renumbering it breaks that environment.

| Was | Now | Requirement |
|---|---|---|
| V12 | V12 (unchanged) | REQ-STMT-02 — `row_fingerprint` + unique index |
| V13 | V13 (unchanged) | REQ-STMT-03 — `content_hash` + index |
| V16 | **V14** | REQ-STMT-07 — `opening_date`/`closing_date`, generated `statement_month` |
| V17 | **V15** | REQ-STMT-03 — make the content-hash index unique |
| V18 | **V16** | Classify derive-user-id errors |

Spec-02's two unimplemented migrations moved out of the numbers now taken:
REQ-STMT-04's `content_fingerprint` is now **V17**, and REQ-STMT-05's cascade-delete fix is now
**V18**.
