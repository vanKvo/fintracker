# ADR-001: Denormalize user_id onto Every Ledger Child Table

## Service Name: fintracker-ledger

## Date
2026-06-26

## Context
The ledger schema has two categories of tables:

- **Root tables** that own a user directly: `accounts`, `budgets`, `upcoming_bills` — all have a `user_id` column.
- **Child tables** that reach a user through a foreign-key chain: `statements → accounts → user_id`, `transactions → accounts → user_id`, `budget_lines → budgets → user_id`, `bill_payments → upcoming_bills → user_id`.

Key requirements:
- Every API endpoint must be scoped to the authenticated user; no user may read or mutate another user's records.
- PostgreSQL Row-Level Security (RLS) must enforce isolation at the database layer as a second line of defence.
- GDPR Article 17 (Right to Erasure) requires all rows belonging to a user to be deletable via a single, auditable operation per table.
- Ownership checks in application code must be fast and unambiguous — a single `WHERE user_id = ?` rather than a multi-hop join.
- The `transactions` table is the hottest read path in the system; any per-query overhead compounds at scale.

Without denormalization, implementing RLS on `transactions` requires a correlated subquery per row:

```sql
USING (
  EXISTS (
    SELECT 1 FROM ledger.accounts a
     WHERE a.account_id = transactions.account_id
       AND a.user_id = current_setting('app.current_user_id', true)::uuid
  )
)
```

This subquery is evaluated for every row Postgres considers, making RLS prohibitively expensive on large result sets. The same problem applies to `statements`, `budget_lines`, and `bill_payments`.

## Decision
Add a `user_id UUID NOT NULL` column to `statements`, `transactions`, `budget_lines`, and `bill_payments` (migration `V3__Add_User_Stamp_And_RLS.sql`).

The column is not supplied by the application on insert. Instead, a `BEFORE INSERT` trigger on each table reads the `user_id` from the parent row and writes it automatically:

1. `trg_statements_set_user_id` — reads `accounts.user_id` via the inserted `account_id`.
2. `trg_transactions_set_user_id` — reads `accounts.user_id` via the inserted `account_id`.
3. `trg_budget_lines_set_user_id` — reads `budgets.user_id` via the inserted `budget_id`.
4. `trg_bill_payments_set_user_id` — reads `upcoming_bills.user_id` via the inserted `bill_id`.

If the parent row does not exist (e.g. an orphaned insert), the trigger raises an exception, blocking the write.

Indexes added to support the new column:

- `idx_statements_user ON statements(user_id)`
- `idx_tx_user_date ON transactions(user_id, tx_date DESC)` — covers the primary list query
- `idx_budget_lines_user ON budget_lines(user_id)`
- `idx_bill_payments_user ON bill_payments(user_id)`

## Alternatives Considered

### Keep normalized — join through parent table for all ownership checks
- Pros: No data duplication; strict 3NF.
- Cons: RLS policies require a correlated subquery on every row. Complex `findByIdAndUserId` joins in repositories. Cannot partition `transactions` by user. GDPR deletion requires multi-table cascade logic.
- Rejected: The performance and compliance costs outweigh the normalization benefit. `user_id` is immutable (a user never changes identity), eliminating the update-anomaly risk that makes denormalization dangerous.

### Use a generated/computed column
- Pros: Database derives the value automatically without a trigger.
- Cons: PostgreSQL does not support generated columns that reference other tables via a join — only expressions over the row's own columns are allowed.
- Rejected: Not supported by Postgres.

### Add `user_id` only to `transactions` (highest-traffic table)
- Pros: Smaller migration scope.
- Cons: RLS on `statements`, `budget_lines`, and `bill_payments` still needs subqueries. GDPR deletion still requires cascades on those tables.
- Rejected: Partial fix leaves three tables with weak isolation.

## Consequences
- All four child tables gain a `user_id` column populated automatically by DB triggers; application insert code requires no changes.
- RLS policies on all ledger tables reduce to a single equality predicate (see ADR-002).
- Repository `findById` methods are replaced with `findByIdAndUserId` across `StatementRepository`, `TransactionRepository`, and `BillRepository`, closing the IDOR vulnerabilities identified in the multi-tenancy audit.
- GDPR erasure is reduced to seven `DELETE FROM <table> WHERE user_id = ?` statements, one per table, with no join logic.
- The trigger adds one `SELECT` per insert against the parent table; on a write path that already validates the FK, this is a negligible overhead compared to the read-path gains.
