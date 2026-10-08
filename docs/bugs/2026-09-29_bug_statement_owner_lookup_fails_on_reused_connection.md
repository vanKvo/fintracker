# Bug name: Statement owner lookup fails on a reused database connection

## Problem
The Ledger's internal statement owner lookup is how the Data Pipeline verifies who owns an uploaded statement (REQ-DP-05). It returned HTTP 500 whenever it ran on a pooled database connection that had already served a normal user request. In a running Ledger almost every pooled connection has served a user request, so the Data Pipeline's owner check would fail intermittently and statement processing would never start. The tests missed it because the connection they happened to use was fresh; adding new test classes changed the order and exposed it (`InternalApiSecurityIT.ownerLookupReturnsTheRealOwner`).

### Root cause:
- Every statement query is also checked by the per-user row-security rule, which converts the session setting `app.current_user_id` to a UUID.
- On a brand-new connection that setting has never been set, so reading it returns NULL, and converting NULL is harmless.
- After a normal user request, the Ledger sets the setting and then resets it. In Postgres, a reset custom setting reads back as an empty string, not NULL.
- `''::uuid` is invalid, so the query failed with `invalid input syntax for type uuid: ""`. This happened even though the separate owner-lookup rule would have allowed the row.
- The owner lookup runs on its own raw connection outside the Ledger's usual query hook, so nothing set a valid user ID first.

### Code with bug:
```java
// JooqStatementRepository.findOwnerByStatementId
try (var set = conn.prepareStatement(
        "SELECT set_config('app.internal_owner_lookup', 'true', false)")) {
    set.execute();
}
// ... SELECT account_id, user_id FROM ledger.statements WHERE statement_id = ?
//     -> statements_isolation evaluates current_setting('app.current_user_id', true)::uuid = ''::uuid -> error
```

## Solution
1. For the duration of the lookup, the owner lookup now also sets `app.current_user_id` to the nil UUID (`00000000-0000-0000-0000-000000000000`). The per-user rule then evaluates cleanly to "no match" (no real user has the nil UUID), and the owner-lookup rule alone allows the row.
2. Both settings are reset afterwards, as before.
3. A regression test (`JooqStatementRepositoryIT.ownerLookupWorksOnAConnectionReusedAfterAUserRequest`) pins a single connection inside a transaction, runs a user-style set/reset on it, and then performs the owner lookup on that same connection.

A broader hardening would change every row-security rule to use `NULLIF(current_setting('app.current_user_id', true), '')::uuid`. That would make any query without a user context return no rows instead of failing. It isn't done here; it's worth considering as its own change.

### Fixed Code
```java
try (var set = conn.prepareStatement(
        "SELECT set_config('app.internal_owner_lookup', 'true', false), "
                + "set_config('app.current_user_id', '00000000-0000-0000-0000-000000000000', false)")) {
    set.execute();
}
// ...
try (var reset = conn.prepareStatement("RESET app.internal_owner_lookup; RESET app.current_user_id")) {
    reset.execute();
}
```
