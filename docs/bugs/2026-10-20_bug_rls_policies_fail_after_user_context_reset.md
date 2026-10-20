# Bug name: Queries without a user context fail on a reused database connection

## Problem
On a pooled connection that has already served a user request, a Ledger query that runs without a user context fails with `ERROR: invalid input syntax for type uuid: ""` instead of returning no user rows.

Affected:
- The month-end budget job (`BudgetPeriodCloser`, V8 policies). It runs without a user, so on most connections in a running service it would fail.
- Integration tests that query without setting `UserContextHolder`. These failed or passed depending on which pooled connection they happened to get: `JooqCategoryRepositoryIT.migrationSeedsTheSeventeenSystemCategories` and `CategoryCodeMigrationIT.repositoryExposesCodeAndActiveFlag` failed in the full run on 2026-10-20 after new test classes changed the order.

It is the same root cause as the statement owner-lookup failure fixed on 2026-09-29 (`2026-09-29_bug_statement_owner_lookup_fails_on_reused_connection.md`), which was fixed only for that one route.

### Root cause:
`RlsExecuteListener` sets `app.current_user_id` with `set_config(...)` before each query and runs `RESET app.current_user_id` after it. A custom setting that a session has set once never goes back to "unset": after `RESET`, `current_setting('app.current_user_id', true)` returns `''`, not `NULL`.

Every RLS policy casts that value straight to `uuid`. V3's comment assumes an unset variable gives `NULL`, so no rows match. On a reused connection the cast of `''` raises an error instead, and Postgres evaluates it even where another `OR` branch would allow the row (for example `level = 'SYSTEM'` on categories).

### Code with bug:
```sql
-- V3 (same pattern in V10 and V19)
CREATE POLICY transactions_isolation ON ledger.transactions
    USING (user_id = current_setting('app.current_user_id', true)::uuid);

CREATE POLICY categories_isolation ON ledger.categories
    USING (level = 'SYSTEM' OR user_id = current_setting('app.current_user_id', true)::uuid);
```
```java
// RlsExecuteListener.end(): leaves '' behind on the pooled connection
ctx.connection().createStatement().execute("RESET app.current_user_id");
```

## Solution
Treat `''` the same as unset in the policies, so "no user" matches no user rows again.

1. V25 adds `ledger.current_user_id()`, a `STABLE` SQL function that returns `NULLIF(current_setting('app.current_user_id', true), '')::uuid`. The planner inlines it.
2. V25 changes every policy that cast the setting (7 from V3, 8 from V10, 1 from V19) to use it, with `ALTER POLICY`. What each policy allows doesn't change.
3. The new `user_merchant_rules` policy (V27) uses the function from the start.
4. `CategoryCodeMigrationIT.repositoryExposesCodeAndActiveFlag` now sets a user context, as production requests do.

Regression test: `RlsResetConnectionIT` runs on one `app_user` connection. It sets a user, resets it, then runs a query without a user context on every RLS table. It asserts no user rows come back and no error is raised. It fails with the uuid error without V25.

### Fixed Code
```sql
-- V25__Rls_Treat_Reset_User_As_No_User.sql
CREATE FUNCTION ledger.current_user_id() RETURNS uuid
    LANGUAGE sql STABLE
AS $$ SELECT NULLIF(current_setting('app.current_user_id', true), '')::uuid $$;

ALTER POLICY transactions_isolation ON ledger.transactions USING (user_id = ledger.current_user_id());
ALTER POLICY categories_isolation ON ledger.categories
    USING (level = 'SYSTEM' OR user_id = ledger.current_user_id());
-- ... and the same for every other policy listed above
```
