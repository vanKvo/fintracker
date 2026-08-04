# ADR-002: PostgreSQL Row-Level Security and Ownership-Scoped Repository Queries

## Service Name: fintracker-ledger

## Date
2026-06-26

## Context
The multi-tenancy audit identified two independent failure modes that can expose one user's financial data to another:

**Application-layer failure:** Repository methods (`findById`, `deleteById`) fetched and mutated rows by resource ID alone with no user filter. A caller who guesses or enumerates a UUID can read, delete, or modify any record in the database.

**Database-layer failure:** The PostgreSQL schema had no Row-Level Security policies. If the application layer were bypassed (a compromised service, a direct DB connection, a SQL injection surviving jOOQ's parameterisation, a future developer adding a raw query), all rows across all tenants would be visible.

Key requirements:
- Defense-in-depth: isolation must not depend on a single checkpoint. Both the application layer and the database layer must enforce it independently.
- No silent data leak: a cross-tenant access attempt must produce a 404 (not found), not a 403 (forbidden), to avoid confirming that a resource exists.
- The Postgres session variable used by RLS must be set and cleared reliably on every request, including virtual threads (Project Loom).
- The fix must not require changes to the database connection pool or to `@Transactional` boundaries, to keep the scope contained.

## Decision

### Layer 1 — PostgreSQL Row-Level Security (database)

Migration `V3__Add_User_Stamp_And_RLS.sql` enables RLS on all seven ledger tables and creates a single isolation policy per table:

```sql
ALTER TABLE ledger.<table> ENABLE ROW LEVEL SECURITY;
ALTER TABLE ledger.<table> FORCE ROW LEVEL SECURITY;

CREATE POLICY <table>_isolation ON ledger.<table>
    USING (user_id = current_setting('app.current_user_id', true)::uuid);
```

`FORCE ROW LEVEL SECURITY` applies the policy even to the table owner (the application DB user), so no connection can bypass it. The `true` argument to `current_setting` returns `NULL` instead of throwing when the variable is unset (e.g. during Flyway migrations), and a `NULL = UUID` comparison is always `FALSE`, so unset sessions see zero rows.

### Layer 2 — Postgres session variable per request (infrastructure)

Two new Spring components wire the RLS variable into the jOOQ request lifecycle:

**`UserContextHolder`** (`shared/UserContextHolder.java`) — a `ThreadLocal<UUID>` that carries the authenticated user identity within a single request thread. Virtual-thread safe: each Loom virtual thread has its own `ThreadLocal` stack.

**`RlsExecuteListener`** (`config/RlsExecuteListener.java`) — a jOOQ `DefaultExecuteListener` registered as a Spring bean. Spring Boot's jOOQ auto-configuration picks up any `ExecuteListenerProvider` bean automatically.

- `start()`: executes `SET app.current_user_id = ?` on the JDBC connection before every query, using the value from `UserContextHolder`.
- `end()`: executes `RESET app.current_user_id` after every query so pooled connections (HikariCP) never carry one user's identity to the next request.

**`UserContextFilter`** (`config/UserContextFilter.java`) — extended to call `UserContextHolder.set(userId)` after binding the request attribute, and `UserContextHolder.clear()` in a `finally` block wrapping `filterChain.doFilter(...)`.

### Layer 3 — Ownership-scoped repository methods (application)

All repository `findById` variants that back mutation endpoints are replaced with `findByIdAndUserId(UUID id, UUID userId)`:

| Repository | Old method | New method |
|---|---|---|
| `StatementRepository` | `findById(UUID)` | `findByIdAndUserId(UUID, UUID)` |
| `StatementRepository` | `deleteById(UUID)` | `deleteByIdAndUserId(UUID, UUID)` |
| `TransactionRepository` | `findById(UUID)` | `findByIdAndUserId(UUID, UUID)` |
| `BillRepository` | `findById(UUID)` | `findByIdAndUserId(UUID, UUID)` |

The SQL adds `AND user_id = ?` to each query. If the row does not belong to the caller, `Optional.empty()` is returned and the service throws a `*NotFoundException`, producing a 404.

`userId` is threaded from `@RequestAttribute("userId")` (set by `UserContextFilter`) through each controller → service → repository call. No endpoint can call a mutation without the filter-validated identity.

The internal `save()` reload in `JooqTransactionRepository` uses a private `findByIdInternal(UUID)` (no user filter) because it runs immediately after a successful `INSERT` on the same connection — the row is guaranteed to belong to the caller by the trigger that derived its `user_id`.

## Alternatives Considered

### Spring Security `@PreAuthorize` / method security
- Pros: Declarative, centralised ACL expressions.
- Cons: Requires loading the entity before the security check (two queries), or maintaining a separate ownership table. Does not protect raw JDBC or Flyway migrations.
- Rejected: Adds framework coupling without providing the database-layer safety net. The repository-level `AND user_id = ?` is simpler, cheaper (one query), and already where the data access happens.

### `SET LOCAL app.current_user_id` inside `@Transactional` boundaries
- Pros: `SET LOCAL` automatically reverts when the transaction ends, no explicit `RESET` needed.
- Cons: Requires every service method to be wrapped in a `@Transactional` boundary. The ledger service currently has no `@Transactional` annotations; adding them changes commit semantics and risks deadlocks on read-heavy paths.
- Rejected: The chosen approach (`SET` + explicit `RESET` in `end()`) achieves the same safety without requiring transaction restructuring.

### Custom `DataSource` wrapper that sets the variable on `Connection.getConnection()`
- Pros: Transparent to jOOQ; works for any SQL library.
- Cons: Overengineered for this codebase; wrapping HikariCP requires proxying the `DataSource`, which complicates observability and connection health checks.
- Rejected: The jOOQ `ExecuteListener` hook is a first-class extension point for this use case and requires zero infrastructure changes.

## Consequences
- Every jOOQ query now incurs two additional round-trips to Postgres (`SET` before, `RESET` after). On localhost or a co-located DB this is sub-millisecond; on a high-latency connection it adds measurable overhead. If profiling reveals a bottleneck, migrating mutation paths to `@Transactional` + `SET LOCAL` eliminates the `RESET` call.
- Flyway migrations run with `current_setting('app.current_user_id', true)` returning `NULL`, so all RLS policies evaluate to `FALSE` and migrations see zero rows. Flyway must connect as the schema owner (`ledger` superuser) and Postgres must be configured to exempt that role from RLS, or Flyway must run before `FORCE ROW LEVEL SECURITY` is applied. The V3 migration order (add columns + triggers first, enable RLS last) ensures existing migrations complete safely.
- Cross-tenant access attempts now return 404 (resource not found) rather than a distinct 403, preventing resource existence enumeration.
- `UserContextHolder.clear()` in the `finally` block of `UserContextFilter` guarantees the `ThreadLocal` is cleaned up even if the request throws, preventing virtual-thread identity leakage on thread reuse.
