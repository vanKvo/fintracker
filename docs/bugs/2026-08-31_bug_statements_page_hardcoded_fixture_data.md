# Bug name: Bank Statements page showed a hardcoded fixture list for every user, never called the real API

## Problem

Logging in as a brand-new user (zero statements in Postgres) still showed five bank statements
("Chase Checking", "Capital One", "Amex Platinum", ...) on the Statements page. This is worse
than a per-user data leak: the same static fixture array was served to **every** account
unconditionally — it was never fetched per-user at all, and (unlike the Dashboard's demo-data
fallback) there was no environment flag gating it out of a production build. Had this shipped, it
would have shown identical fake statement data to every real user in production.

Found during the same multi-tenant isolation check that surfaced the Dashboard demo-data bug: a
newly created second local user, with confirmed-zero rows in `ledger.statements`, still saw the
full fixture list.

### Root cause

`statements.ts` initialized `statementsList` with a hardcoded literal array, and `ngOnInit()`
never called `StatementService.getStatements()` at all — the service existed, was correctly built
to call `GET /api/v1/ledger/statements` (which the auth interceptor correctly scopes with
`X-Internal-User-Id`), but nothing in the component invoked it. A comment on the page already
flagged this as a known, deliberate gap:

> statementsList is still the page's pre-existing mock array, not fed by
> StatementService.getStatements() — that call already assumes txCount/pendingCount/approvedCount
> fields the Ledger's Statement API doesn't return yet.

That assumption was correct: `Statement` (the Ledger's Java domain record) had no
`txCount`/`pendingCount`/`approvedCount` fields, so wiring the component to the real service
without first closing that gap would have shown every real statement with `0/0/0` counts.

### Code with bug

```ts
// statements.ts
statementsList = signal<Statement[]>([
  { id: '1', account: 'Chase Checking', period: 'Oct 1 – Oct 31, 2025', transactions: 142, ... },
  { id: '2', account: 'Capital One', period: 'Sept 1 – Sept 30, 2025', transactions: 110, ... },
  // ...3 more hardcoded entries
]);

ngOnInit() {
  this.extractUniqueAccounts();   // derives the account dropdown from the mock array above
  // StatementService.getStatements() is never called anywhere in this file
}
```

```java
// Statement.java (Ledger)
public record Statement(
        UUID statementId, UUID accountId, String s3ObjectKey, LocalDate statementMonth,
        StatementStatus status, String description, OffsetDateTime uploadDate,
        String sourceFormat, String bankId
        // no per-statement transaction counts
) {}
```

## Solution

1. **Closed the backend schema gap first.** Added `txCount`, `pendingCount`, `approvedCount` to
   `Statement` (Ledger), computed via a `LEFT JOIN` from `ledger.statements` to
   `ledger.transactions` on `statement_id`, using `COUNT(...) FILTER (WHERE ...)` grouped by
   statement (`JooqStatementRepository.findAllByUserId`). Verified the aggregation logic directly
   against Postgres (inserted a statement with POSTED/PENDING/DELETED transactions, confirmed
   `tx_count`/`pending_count`/`approved_count` matched expectations) before wiring the frontend to
   it, and confirmed `mvn test` (47 tests) and `mvn compile` stay green.
2. **Deleted the hardcoded array** in `statements.ts` and wired `ngOnInit()` to call
   `StatementService.getStatements()` for real, with proper loading/error/empty states (mirroring
   the pattern already established on Budgets/Dashboard): a load failure shows a retry banner, a
   real empty result shows "No statements yet" with an upload CTA.
3. **Generalized the year-grouping**, which was hardcoded to exactly "2025" and "2024" — any
   statement outside those two literal years would previously have been silently dropped from
   every group. Replaced with `priorYears()`, computed from whatever years are actually present in
   the data.
4. Derived a `'Needs Attention'` status from `pendingCount > 0` on a completed statement (the
   backend only has `PROCESSING`/`COMPLETED`/`FAILED`), giving that UI state a real backing
   condition instead of an unreachable dead branch.
5. Wired `deleteStatement()` to the real `StatementService.deleteStatement(id)` call — it
   previously only mutated the local signal, so a "deleted" statement reappeared on next page
   load. (`approveAllPending()` remains local-only; there is no bulk-approve-by-statement backend
   endpoint yet, called out in a comment for a future fix.)

Verified with a Playwright e2e test (`fintracker-ui/e2e/fresh-user-empty-state.spec.ts`) that
signs in as a freshly generated user id and asserts the page shows "No statements yet" and none of
the old fixture account names ("Chase Checking", "Capital One", "Amex Platinum").

### Fixed Code

```java
// JooqStatementRepository.java
public List<Statement> findAllByUserId(UUID userId) {
    var txId = field(name(SCHEMA, "transactions", "transaction_id"));
    var txStatus = field(name(SCHEMA, "transactions", "status"), String.class);

    var txCount = count(txId).filterWhere(txStatus.ne(Transaction.TransactionStatus.DELETED.name())).as("tx_count");
    var pendingCount = count(txId).filterWhere(txStatus.eq(Transaction.TransactionStatus.PENDING.name())).as("pending_count");
    var approvedCount = count(txId).filterWhere(txStatus.eq(Transaction.TransactionStatus.POSTED.name())).as("approved_count");

    return dsl.select(/* statement columns */, txCount, pendingCount, approvedCount)
            .from(table(name(SCHEMA, TABLE)))
            .join(table(name(SCHEMA, "accounts"))).on(/* ... */)
            .leftJoin(table(name(SCHEMA, "transactions")))
            .on(field(name(SCHEMA, "transactions", "statement_id")).eq(field(name(SCHEMA, TABLE, "statement_id"))))
            .where(field(name(SCHEMA, "accounts", "user_id")).eq(userId))
            .groupBy(/* statement columns */)
            .orderBy(field(name(SCHEMA, TABLE, "upload_date")).desc())
            .fetch(this::mapToStatementWithCounts);
}
```

```ts
// statements.ts
statementsList = signal<Statement[]>([]);
loading = signal(true);
loadFailed = signal(false);

ngOnInit() {
  this.loadStatements();
}

loadStatements() {
  this.loading.set(true);
  this.loadFailed.set(false);
  this.statementService.getStatements().subscribe({
    next: raw => {
      const statements = raw.map(r => this.toViewModel(r));
      this.statementsList.set(statements);
      this.extractUniqueAccounts();
      this.loading.set(false);
    },
    error: err => {
      this.loading.set(false);
      this.loadFailed.set(true);
      this.snackBar.open(err?.error?.detail || 'Failed to load statements.', 'Dismiss', { duration: 5000 });
    }
  });
}
```

## Related follow-ups (not fixed here)

- `approveAllPending()` is still local-optimistic-only — there is no bulk "approve all
  transactions for a statement" backend endpoint (only single-transaction
  `TransactionService.approveTransaction(id)` exists). Flagged in code with a comment; needs a
  real endpoint before this action persists.
- The detail panel's `totalPurchases`/`totalCredits`/`totalBalance`/`fileName`/`lastUploadInfo`/
  `updatedAt` fields still have no backend source and always render their existing safe fallback
  (`$0.00` / hidden row) — same category of gap as the counts fixed here, not yet closed.
