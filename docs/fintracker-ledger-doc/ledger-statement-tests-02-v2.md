# Statement Upload Flow — Test Coverage for Spec 02, v2

Adds Ledger-side coverage for **REQ-STMT-04**, **REQ-STMT-05** and **REQ-STMT-08** on top of v1
(REQ-STMT-02/03/06/07). See `ledger-statement-tests-02-v1.md` for the earlier inventory and
`ledger-statement-spec-02.md` for the requirements themselves.

**Status as of 2026-09-09:** 27 new Ledger tests and 13 new UI tests, all passing. Ledger suite
green at **105 unit + 287 integration = 392** (was 365); UI suite green at **30**.

```bash
cd services/fintracker-ledger
export JAVA_HOME=$(/usr/libexec/java_home -v 21)   # Java 21 — Maven's own JVM, not just the target
mvn clean verify -DskipITs=false -DskipJooq=true

cd ../../fintracker-ui
npx ng test --watch=false
```

---

# Test strategy

## The question each test has to answer

A test earns its place by being the *only* thing that would catch a specific failure. Before
writing each one below, the question was: **what breaks in production if this is wrong, and would
any other test already notice?** If another test already notices, the new one is duplicated cost —
it slows every future run and gives no new signal. Tests that fail for the same underlying reason
are one test wearing several costumes.

That filter is why there is no test here for "the fingerprint is a good discriminator", or for how
the fingerprint is computed. The spec puts that computation entirely in the Data Pipeline; the
Ledger only stores a value and answers whether it matches. Testing it here would assert something
this codebase does not decide.

## Why the tests are grouped the way they are

The split is by **what kind of proof the test can produce**, not by which class it exercises. That
matters because the two layers can be wrong about completely different things.

**Unit layer (`*Test`, surefire, mocked repository, milliseconds).** Proves *decisions*: which
branch runs, in what order, and what happens on each. A mocked repository is the right tool
because the decisions are the thing under test and a real database would only slow down the same
assertion. This is where ordering lives — `deleteForOverwrite` running before the duplicate check
is a decision, and getting it backwards makes every overwrite fail with the very duplicate the
user just chose to replace.

**Integration layer (`*IT`, failsafe, Testcontainers, seconds).** Proves *guarantees the database
makes*, which a mock cannot see because a mock will happily agree with a wrong implementation. Two
of these are load-bearing:

- **Round trips.** Every mocked fingerprint test would pass against an implementation that queries
  `content_fingerprint` but never writes it — leaving REQ-STMT-04 permanently unable to match
  anything in production. `StatementFingerprintIT` writes and then reads back through the real
  column, so that implementation fails.
- **Referential behavior.** REQ-STMT-05's overwrite depends on deleting a statement actually
  deleting its transactions. That is a foreign-key property, invisible to a mock.

## The one test that mattered most, and the proof it works

`StatementOverwriteIT.overwriteRemovesTheOldStatementsTransactions` is the highest-value test in
this change, because the bug it guards is a live one the spec found while being written: V1
declared `transactions.statement_id` as `ON DELETE SET NULL`, so deleting a statement **orphaned**
its transactions — they stayed in the account, still counted, with a NULL `statement_id` — while
`StatementServiceImpl.deleteStatement` logged "Cascaded transactions removed". An overwrite on that
schema silently doubles the account's transactions. That is wrong numbers in the user's money.

A passing test proves nothing unless it can fail, so this one was mutation-checked: V18 was removed
and the suite re-run. It failed with exactly the intended symptom —

```
[the replaced statement's transactions must be gone, not orphaned] expected: 0 but was: 2
```

— then passed again once V18 was restored. Worth noting: the *first* attempt at that check passed
misleadingly, because Maven leaves deleted resources in `target/classes` and Flyway still found the
old migration. `mvn clean` is required for any migration-level mutation check to mean anything.

## Multi-tenant coverage

Production-grade here means the tenancy boundary is proven at **every layer that could breach it
independently**, because each layer fails differently and a guard at one does not imply a guard at
the next.

| Layer | What could breach it | Tests |
|---|---|---|
| Controller | `accountId` arrives as a raw query param; the service method takes no `userId`, so the controller is the *only* place it is bound to the caller | 13, 14 |
| Service | A client-supplied `statementId` used to delete without re-binding it to the caller | 6, 7, 8 |
| Filter chain | A new internal route falling outside the filter's path scope, reachable with an attacker-set `X-Internal-User-Id` | 24, 25 |
| Database | Application-level `WHERE` clauses being the only thing standing between tenants | 18, 22, 23 |

Two properties are asserted repeatedly and deliberately, because they are the ones that turn a bug
into a breach:

- **A foreign resource is reported as "not found", never "forbidden".** A distinct error is an
  existence oracle: it confirms another tenant holds that statement id. Tests 2, 7, 23.
- **A rejected write leaves nothing behind.** Tests assert not just the thrown exception but that
  nothing was deleted or modified (`verify(..., never())`, and a re-read of the victim's row in the
  IT layer). An exception thrown *after* a delete is still a deleted row. Tests 7, 8, 18, 23.

## Should slow tests be labelled for selective runs?

**Yes — but tagged by reason, not by duration, and never to routinely skip them.**

Duration is a symptom that drifts; the *reason* a test is slow is stable and actionable. And this
suite already gets the fast/slow split for free: the `*Test` / `*IT` naming convention routes unit
tests to surefire and Testcontainers tests to failsafe, so `mvn test` is already the fast loop and
`mvn verify` the full one. Adding `@Tag("slow")` on top would duplicate a distinction the build
already makes — cost with no new capability, and a second thing to keep in sync.

What that split **cannot** express is a cross-cutting concern, so that is what got tagged:

```bash
mvn test -Dgroups=multi-tenant      # every tenancy proof in the unit layer — verified, 6 tests
mvn verify -Dgroups=multi-tenant    # …and across both layers
```

This is worth its keep because "run every tenant-isolation proof" is a question you genuinely want
to ask before a security-sensitive release, and it spans both layers and four packages — no
file-name convention can select that set.

**The caution that matters more than the tagging.** The tests you would be tempted to skip for
speed are precisely the ones that catch cross-tenant leaks: RLS enforcement, cascade behavior,
filter path scoping. None of them can be replaced by a faster mocked equivalent — that is the
definition of what they test. If total runtime becomes a real problem, the honest fixes are
container reuse and parallel execution, not a `slow` tag that quietly becomes "the tests we do not
run". A tag used to skip tenancy tests is a tag that ships a data-isolation bug.

Right now the integration layer runs in well under a minute against a shared container, so this is
a convention to establish early rather than a problem to solve today.

---

# New tests (26)

## Unit layer — surefire, 16 tests

### `StatementFingerprintTest` (5) — REQ-STMT-04

`recordContentFingerprint()`
1. Stores the fingerprint against the statement, and the caller's identity reaches the repository —
   the write itself carries the tenancy scope, so a call that dropped `userId` would still pass a
   status-only assertion.
2. **Multi-tenant** — a statement belonging to another tenant is reported as *not found*, exactly
   like a nonexistent one, so the response is not an existence oracle for other tenants' ids.

`checkForDuplicateByContentFingerprint()`
3. A match is always `CONTENT_FINGERPRINT`, carrying the existing statement's id, upload date and
   transaction count — the three fields REQ-STMT-05 shows the user to decide overwrite-or-cancel.
   A match that cannot name what it matched is not actionable.
4. No match returns empty — the baseline that stops a first upload being flagged against itself.
5. The month rule is not consulted. This check runs mid-processing, long after `initiateUpload`
   settled the month question; re-applying it here would resurrect a rejection the user already
   passed.

### `StatementOverwriteTest` (5) — REQ-STMT-05

6. The replaced statement is deleted **before** the duplicate check runs, verified with an ordered
   `InOrder`. Ordering is the substance, not incidental: a duplicate check running first would match
   the very statement being replaced and reject the overwrite outright.
7. **Multi-tenant** — overwriting another user's statement is *not found*, and nothing is deleted.
   Deleting on the strength of a client-supplied id alone would let any authenticated user erase any
   statement in the system.
8. **Multi-tenant** — overwriting a statement in a different account *of the same user* is rejected
   as a bad request, and nothing is deleted. The statement is genuinely theirs; this is a malformed
   request, not a permission failure, and must not become a way to move statements between accounts.
9. Without `overwriteStatementId`, a duplicate is still a rejection — overwrite is opt-in, never the
   default.
10. **Multi-tenant** — a foreign `accountId` is rejected before the overwrite is even considered,
    pinning that the ownership guard precedes the delete rather than merely existing somewhere.

### `InternalStatementFingerprintControllerTest` (6) — REQ-STMT-04 / REQ-STMT-08

11. **REQ-STMT-08** — a `contentFingerprint` query is answered by the fingerprint check, never the
    content-hash check. This *is* REQ-STMT-08's test: the spec's entire Ledger obligation is that
    this endpoint "never returns `duplicateFound=false` for a fingerprint that in fact matches", and
    misrouting the parameter would do exactly that — silently answer a different question and let a
    duplicate through.
12. A fingerprint with no match answers `duplicateFound=false`, not an error — a first upload is not
    a failure.
13. **Multi-tenant** — a fingerprint query for an account the caller does not own is rejected before
    any lookup runs. This response carries another account's statement metadata, so an unguarded
    branch leaks it to any caller the allow-list admits.
14. **Multi-tenant** — recording a fingerprint onto another tenant's statement surfaces as not
    found, not a silent success.
15. Recording answers `204` and passes the caller's identity through, not just the path id.
16. A fingerprint that is not 64 hex characters is rejected before it can be stored and then
    silently fail to match anything later.

## Integration layer — failsafe, Testcontainers, 10 tests

### `StatementFingerprintIT` (5) — REQ-STMT-04

17. A fingerprint recorded on one statement is found by a later lookup — the write-then-read round
    trip that fails against a query-only implementation.
17b. The stored fingerprint reads back on the statement record itself, which is what catches a
    write that landed in the wrong column or was truncated by the `CHAR(64)` type. Matching alone
    would not: a lookup keyed on the same wrong value still finds its own row.
18. A statement with no fingerprint yet matches nothing: two in-flight uploads both have NULL
    fingerprints, and treating NULL as a match would flag every concurrent upload as a duplicate of
    every other.
19. **Multi-tenant** — the same fingerprint in another tenant's account is not a duplicate. A global
    lookup would both block a legitimate upload and disclose that another account holds identical
    contents.
20. **Multi-tenant** — recording onto another tenant's statement neither succeeds nor modifies their
    row. Re-read afterwards, because a rejected write that had already landed is worse than one that
    errored.

### `StatementOverwriteIT` (3) — REQ-STMT-05

21. **The cascade test** — overwriting removes the old statement's transactions, so the replacement
    is a clean swap rather than a doubling. Mutation-verified against V18 (see above).
22. After an overwrite the account holds exactly one statement for that month — the replacement, not
    both. The unique index on `(account_id, statement_month)` would have rejected the replacement
    outright had the delete not really happened first.
23. **Multi-tenant** — overwriting another tenant's statement deletes nothing of theirs, asserted by
    re-reading both the victim's statement *and* their transaction count. With V18's cascade now in
    place, a missing ownership bind here would destroy another tenant's transactions, not just their
    statement row — the blast radius of this particular bug grew with the fix.

### `InternalFingerprintEndpointSecurityIT` (3) — REQ-STMT-04

24. **Multi-tenant** — fails closed with `401` when no verified caller principal is present.
25. **Multi-tenant** — a verified caller ARN not on the allow-list is rejected with `401`.
26. An allow-listed caller reaches the controller (asserted as `404` for a random statement id, not
    merely "not 401"). Without this, the suite would still pass with the route accidentally blocked
    to everyone including the pipeline — a test that only ever asserts rejection cannot tell a
    working gate from a broken one.

**Why this class exists at all,** given `InternalEndpointSecurityIT` already proves the filter
works: the filter is *path-scoped*, so a newly added internal route is only covered if the scoping
actually catches it, and nothing in the filter's own tests would notice a new endpoint that fell
outside the pattern. The stakes are specific to this route — it is a **write** reachable with a
caller-supplied `X-Internal-User-Id`; unguarded, any caller could stamp a fingerprint onto any
tenant's statement and make that tenant's next legitimate upload look like a duplicate.

---

# Requirement → test mapping

| Requirement | Ledger scope per spec | Tests | Notes |
|---|---|---|---|
| REQ-STMT-04 | Store the fingerprint; answer whether it matches | 1–5, 11–20, 24–26 | Computing the fingerprint is Data Pipeline scope and is not tested here |
| REQ-STMT-05 | Ownership-checked delete-then-recreate via `overwriteStatementId` | 6–10, 21–23 | The `PENDING_DUPLICATE_RESOLUTION` pause is Data Pipeline job orchestration; the Ledger has no notion of a paused job |
| REQ-STMT-08 | Answer the duplicate-check query truthfully | 11 | No new Ledger endpoint, method or DTO — the requirement is a dispatch-correctness property, so it has exactly one test |

## Deliberately not tested here, and why

- **The `PENDING_DUPLICATE_RESOLUTION` status and the mid-processing pause.** Spec assigns these to
  Data Pipeline job orchestration. The Ledger cannot observe a paused job, so a test here would
  assert a fiction.
- **`SERVER_DUPLICATE_DETECTED` / `status: FAILED`.** Same reason — a Data Pipeline job-status
  concern, not a Ledger response shape.
- **The UI's `pollJobStatus` stop-condition change** (Shared Contract, flagged a MUST). Real and
  still outstanding, but it lives in `fintracker-ui`, not this service.
- **How the aggregate fingerprint is built** (sort, concatenate, re-hash). Data Pipeline scope.

---

# Implementation delivered alongside these tests

| Requirement | Change |
|---|---|
| REQ-STMT-04 | `V17__Add_Statement_Content_Fingerprint.sql`; `findByAccountIdAndContentFingerprint` / `updateContentFingerprint`; `recordContentFingerprint` / `checkForDuplicateByContentFingerprint`; `PATCH /api/v1/ledger/statements/internal/{id}/content-fingerprint` + `RecordContentFingerprintRequest` |
| REQ-STMT-05 | `V18__Cascade_Delete_Transactions_On_Statement_Delete.sql`; `deleteForOverwrite` inside `initiateUpload` |
| REQ-STMT-08 | `InternalStatementController.checkDuplicate` now dispatches the `contentFingerprint` branch instead of rejecting it as unsupported |

**Two deliberate deviations from the spec's Technical Reference**, both narrowing rather than
extending it:

1. **`updateContentFingerprint` takes a `userId`** the spec's signature omits, and returns a boolean
   rather than void. Without the `userId` in the `UPDATE`'s own `WHERE` clause, tenancy would depend
   on a separate prior read — a check-then-write window, and one more thing a future caller can
   forget. The boolean lets a no-op become a clean 404 without a second query.
2. **`content_fingerprint` is not added to the `Statement` record.** The spec implies it as a column
   only; nothing reads it back into the domain model, since REQ-STMT-04 writes it and matches on it
   in a `WHERE` clause. Adding it would have cost a `GROUP BY` term, a field nothing consumes, and —
   the deciding factor — it breaks `run_tests_f2p.sh`, which regenerates two test files containing
   15-argument `Statement` constructors. Discovered only after forcing a clean rebuild: the
   incremental build reported "Nothing to compile" and hid four broken call sites.

Also worth recording: the index behind `content_fingerprint` is deliberately **not unique**, unlike
V15's `content_hash` index. REQ-STMT-04 treats a fingerprint match as "probably the same, please
confirm" rather than a hard block — two genuinely different statements on a low-activity account can
legitimately collide, and a unique index would have the database refuse the second one with no way
for the user to override it.


---

# UI wiring (13 tests)

The Ledger changes are only half of each requirement — a duplicate the user is never shown is a
duplicate that still costs them a re-upload. `fintracker-ui` was behind the spec on every point
below, so this pass brought it up to the contract.

## What was out of date

| Area | Before | Now |
|---|---|---|
| Upload request | `statementMonth`, dates only for PDF/IMAGE, no hash | Range for every format, required `contentHash`, optional `overwriteStatementId` |
| Upload response | `statementId` / `presignedUploadUrl` | `jobId` / `status` / `uploadUrl`, the 202 job object |
| Job statuses | No `PROCESSING`, no `PENDING_DUPLICATE_RESOLUTION` | Both present; `errorCode` and `duplicate` on the status payload |
| Poll stop condition | Terminal or `PENDING_MAPPING_CONFIRMATION` | A `WAITING_STATUSES` list both pauses belong to |
| Duplicate handling | None — a 409 fell into the generic error panel | One prompt shared by all three detection paths |

## The MUST from the Shared Contract

`pollJobStatus` stopped only on terminal statuses and the mapping pause. A waiting status missing
from that condition **does not fail loudly** — the poller keeps spinning to its 1000-tick ceiling
and the user is never prompted, which presents as a hung upload rather than a bug. The stop
condition is now a named `WAITING_STATUSES` list, so adding a third pause later is a one-line
change in the place the reader is already looking, and two tests pin both pauses independently so
adding one cannot silently displace the other.

## New tests

**`statement.service.spec.ts` (6 new)**
1. REQ-STMT-03/07 — `contentHash`, `openingDate` and `closingDate` are on every request, and
   `statementMonth` is gone.
2. REQ-STMT-05 — `overwriteStatementId` is sent when the user chose to replace.
3. REQ-STMT-03 — `computeContentHash` is verified against the **known SHA-256 of empty input**.
   A subtly wrong hash (wrong algorithm, wrong encoding) still produces a plausible 64-character
   string, so only a fixed expected digest catches it.
4. REQ-STMT-04 — polling stops on `PENDING_DUPLICATE_RESOLUTION` and hands the payload on.
5. Polling still stops on `PENDING_MAPPING_CONFIRMATION` — the new status did not displace it.
6. REQ-STMT-08 — a `FAILED` status carries `errorCode` and `duplicate` through to the caller.

**`upload-statement-modal.spec.ts` (7 new, 4 rewritten)**
7. REQ-STMT-07 — CSV now requires the date range too.
8. REQ-STMT-07 — a closing date before the opening date blocks submission client-side, before
   anything uploads.
9. REQ-STMT-07 — a single-day statement is allowed: only *before* is invalid, not *equal*, matching
   the server rule exactly. A client stricter than the server rejects legitimate uploads.
10. REQ-STMT-07 — the range survives a document-type change, since every format needs it now.
11. REQ-STMT-03 — the file is hashed and the hash reaches the request.
12. REQ-STMT-05 — a 409 opens the prompt instead of the error panel.
13. REQ-STMT-05 — Overwrite re-submits with `overwriteStatementId`; the first attempt carries none.
14. REQ-STMT-05 — Cancel attempts no second upload.
15. REQ-STMT-05 — **dismissing the dialog is treated as Cancel**, not Overwrite. Overwrite destroys
    transactions, so it must never be reachable by accident.
16. A non-duplicate failure still reaches the error panel rather than being mistaken for a duplicate.
17. REQ-STMT-04 — a mid-processing duplicate prompts with `midProcessing: true` and discards the
    abandoned tracking record, so the user's statement list is not left with an empty failed entry.
18. REQ-STMT-08 — a `SERVER_DUPLICATE_DETECTED` failure names the existing statement rather than
    saying only that something failed.

## Deliberate UI decisions

- **Cancel is the dialog's default action** (`cdkFocusInitial`), and a dismissed dialog is a cancel.
  Overwrite removes an existing statement and its transactions; the safe choice is the one reached
  without aiming.
- **The fingerprint match is worded as a likelihood**, not a certainty — REQ-STMT-04 explicitly
  treats it as "probably the same, please confirm", and the dialog adds a line telling the user what
  to do if it is genuinely a different statement.
- **Cleanup failure is swallowed deliberately.** If discarding the abandoned job fails, the user's
  decision has already been taken and a leftover row is a tidiness problem they cannot act on —
  surfacing it would replace a completed action with a confusing error.
- **REQ-STMT-08 offers no overwrite option**, matching the spec's deferral. That path only triggers
  on a wrong or fabricated client hash, so a clear failure is the proportionate first version.

## Known environment gaps in the UI tests

- **jsdom's `File` has no `arrayBuffer()`**, which every target browser implements. The hashing test
  patches it onto the fixture rather than reshaping the production code around a test-environment
  gap.
- **`MatDialogModule` is imported by the standalone component**, so its `MatDialog` provider wins
  over one merely listed in `TestBed.providers` — the mock has to go through
  `TestBed.overrideProvider`. Worth knowing before writing the next dialog test.
- **`timer(0, n)` emits on a macrotask**, so the first poll request does not exist on the line after
  `subscribe`. The poll tests drain the queue explicitly instead of assuming synchronous delivery.
