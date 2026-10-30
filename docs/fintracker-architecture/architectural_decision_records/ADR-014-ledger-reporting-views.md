# ADR-014: Analytics Reads Ledger Data Through Ledger-Owned Reporting Views

## Service Name: app-wide (Ledger, Analytics)

## Status
Accepted (architecture doc D22). Narrows the exception in invariant 1; the access path stays as in [ADR-003](ADR-003-database-access-path.md).

## Date
2026-10-20

## Context
Analytics reads the Ledger's database through a read-only role. Today it queries the Ledger's tables directly and repeats the rules for what counts as income and spending (LG-TXT-02). That couples it to every column and type value: when the Ledger renamed transaction types and statuses, Analytics' filters would have silently returned zeros. The Ledger's Dashboard totals and budget spend repeat the same rules a third time.

Key requirements:
- One definition of income and spending, shared by the Dashboard, Reports, budgets and the Financial Summary.
- Row-Level Security still applies to every read.
- Analytics stays read-only, outside the VPC, on the Data API (ADR-003).
- The Ledger can change its tables without breaking Analytics.
- Analytics receives only the columns it needs.

## Decision
**The Ledger publishes reporting views, and Analytics reads only those, in both profiles.**

**Why:** The Ledger already owns the counting rules, so one definition of income and spending lives there. The views are a versioned contract: the Ledger can change its tables without breaking Analytics, and Analytics sees only the columns it needs. The cost is a few migrations and a PostgreSQL 15 requirement, against separate rules in two languages (direct reads) or a whole event pipeline (copy).

1. **The views,** defined in the Ledger's Flyway migrations:
   - transactions, with a counting field (counts or not) and a flow field (income, spending, refund offset, or none for transfers and adjustments), following LG-TXT-02;
   - budget limits per month and category;
   - accounts as an opaque reference, type and sync timestamps, without names or account numbers.
2. **`security_invoker = true`** on every view, so RLS on the base tables applies to the caller. This requires PostgreSQL 15 or later.
3. **Grants:** Analytics' read-only role gets `SELECT` on the views and nothing on the base tables.
4. **Index:** a partial index on `(user_id, tx_date)` for non-deleted transactions.
5. **One definition:** the Ledger's Dashboard totals, budget alerts and budget spend read the same views.
6. **Contract:** changing a view's columns or meaning is a breaking change. Analytics' contract tests run against the migrated schema in CI.

## Alternatives Considered

### Direct table reads (today)
Analytics queries the Ledger's tables and applies its own counting rules.
- Pros: Nothing new to build.
- Cons:
  - The rules are repeated in Java and Python, so figures can drift.
  - Analytics is coupled to every table, column and type value. A rename would have silently returned zeros.
  - Analytics can read every column, including account numbers.
- Rejected: It is the source of the drift and coupling this decision fixes.

### Event-fed copy
The Ledger publishes transaction events and Analytics keeps its own tables (see [SDR-001](../../fintracker-analytics/architecture/decision_records/SDR-001-compute-on-read.md)).
- Pros: Coupling is limited to the event schema, and Analytics sees only the event fields.
- Cons:
  - Events, a consumer, tables, a backfill and a deletion handler to build.
  - The counting rules are still separate, plus sync lag.
- Rejected: It has the most moving parts and still duplicates the rules.

**Also considered**
- **Ledger SQL functions per query** (`SECURITY INVOKER`): each Data API call would set the user context and query in one statement, saving three requests per read. Rejected because every new Analytics query would need a Ledger migration, and the saving is cents a month.
- **`BYPASSRLS` role or `SECURITY DEFINER` functions:** Rejected. They remove the database-level tenant check from the service that reads the most users' data.

## Consequences

**Pros**
- Type and status renames in the Ledger stop breaking Analytics: the views absorb them.
- The Ledger owns the counting rules. A change to LG-TXT-02 is a view migration, and all consumers pick it up together.
- Least privilege moves into the database: Analytics cannot read account names or numbers even with a bug.

**Cons**
- The Ledger has views, grants and an index to maintain, and a breaking view change needs contract tests in CI.
- Requires PostgreSQL 15 or later for `security_invoker`.

**Follow-up**
- The Analytics code moves to the Data API and sets the user context, as the 2026-10-18 extraction notes found it does neither yet.

## Revisit when
- Analytics needs data the views can't express efficiently, or its load affects Ledger latency (then move it to JDBC on an Aurora reader, ADR-003).

## Related
- [ADR-002](ADR-002-rls-and-ownership-scoped-queries.md): RLS policies. [ADR-003](ADR-003-database-access-path.md): Data API for Analytics.
- [SDR-001](../../fintracker-analytics/architecture/decision_records/SDR-001-compute-on-read.md): Analytics stores nothing.
- App architecture doc: 4.2 Trust, 4.4 Store, 7.1 D22, invariant 1. Spec: LG-TXT-02, AN-FS-23.
