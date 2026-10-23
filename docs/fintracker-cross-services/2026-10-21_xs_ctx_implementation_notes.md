# XS-CTX implementation notes (2026-10-21)

Spec: [XS-CTX-verified-user-context-spec.md](specs/XS-CTX-verified-user-context-spec.md). Tests: [XS-CTX-verified-user-context-tests.md](specs/XS-CTX-verified-user-context-tests.md).

## Status

| ID | Status | What is left |
|---|---|---|
| XS-CTX-01 | Implemented | Run the backfill once per existing user (`scripts/one_time/backfill_user_settings.py`) |
| XS-CTX-02 | Implemented | — |
| XS-CTX-03 | In progress | The gateway's parameter mapping for `X-User-Timezone` / `X-User-Currency` and the Ledger's VPC-link-only reachability are infrastructure; neither is defined in this repository |
| XS-CTX-04 | In progress | Ledger still answers 401, not 403, to an unlisted internal caller (see below); Knowledge doesn't exist yet; `execute_tool` is a minimal version (see below) |
| XS-CTX-05 | In progress | The CloudWatch alarm on the `user_context_invalid` metric is infrastructure; the metric and error log it needs are emitted by Analytics, the AI assistant and the Ledger |
| XS-CTX-06 | Implemented | — |
| XS-CTX-07 | In progress | Waiting for permission to delete four files (below); IAM policies are not in this repository |

## What was built
- **User profile:** `PUT /profile/settings`; sign-up stores currency `USD` and no timezone; the authorizer reads PROFILE + SETTINGS with one Query and returns `timezone` and `currency` (empty string when unset); no `UTC`/`USD` default anywhere on the read path; the backfill script.
- **Analytics and AI assistant:** `core/user_context.py` reads and validates the values (409 `user_settings_incomplete`, 500 `user_context_invalid`, metric + error log). Analytics' facts and periods routes use it; the Financial Summary no longer calls User profile. The AI assistant forwards `X-Internal-User-Id`, `X-User-Timezone` and `X-User-Currency` on every Analytics and Ledger call, and passes a 409 from Analytics through to the client.
- **Ledger:** `UserSettings` is resolved from the two headers only for controllers that ask for it; the Dashboard summary uses the user's local date to pick the month.
- **UI:** first app load saves the browser timezone (or shows a picker with nothing preselected); a 409 `user_settings_incomplete` from any service opens the picker and retries once; Settings has a timezone select and a read-only USD currency and says "Saved. It can take up to 5 minutes to apply everywhere."; in local dev the Ledger interceptor sends the two headers a gateway would.

## Needs your decision

1. **Files to delete for XS-CTX-07** (your rule: ask before deleting). All belong to the retired internal settings route and its cache:
   - `services/fintracker-user-profile/app/identity/internal_handlers.py` (the only handler in it is `internal_settings_handler`)
   - `services/fintracker-user-profile/tests/unit/identity/test_internal_settings.py`
   - `services/fintracker-analytics/src/summary/profile_client.py` (the settings client and its 5-minute cache; nothing imports it any more)
   - `services/fintracker-analytics/tests/summary/test_profile_client.py`

   After deleting them, also remove `IdentityService.get_settings` in `services/fintracker-user-profile/app/identity/service.py` (marked in its docstring).
2. **Error body shape.** Appendix C shows `{ "error": { "code", "message", "request_id" } }`, but CLAUDE.md requires RFC 9457. The new errors are RFC 9457 problem bodies with two extra members, `code` and `request_id`. If you want Appendix C literally, say so; the UI reads `error.code` in one place (`settings-incomplete.interceptor.ts`).
3. **401 vs 403 for an unlisted caller.** XS-CTX-04 says 403. Analytics now answers 403 to a verified caller that is not on the allow-list (401 stays for "no IAM identity"). The Ledger's internal routes still answer 401 in both cases, which nine existing Ledger tests pin (REQ-STMT-02). Changing the Ledger is a small edit to `InternalCallerFilter` plus those tests.
4. **Authorizer cache TTL.** XS-CTX-06 says 300 s; the local SAM template and UP-AUTH-03 say 60 s (pinned by `test_authorizer_caching_config.py`). I left 60 s and added a test that the TTL is at most 300 s, so the Settings message ("up to 5 minutes") is true either way.
5. **`execute_tool`.** AI-CHAT-04 (the chat tool registry) is not built. XS-CTX-04's tool-argument criterion is met by a minimal `src/tools/execute.py` over the existing MCP tools: it rejects `user_id`, `timezone`, `currency` and any argument the tool doesn't declare, and logs a security event. AI-CHAT-04 should extend it with the chat allowlist and strict schemas rather than replace it.
6. **Ledger currency.** The Dashboard sums don't filter by currency (every account is USD today), so only the timezone changes the Ledger's numbers; the currency is validated.
7. **Spec index.** `docs/SPECS.md` still lists XS-CTX as "7 Proposed" and "Tests: —". It is a spec file, so I didn't edit it.

## Found on the way
- `DynamoDBUserRepository.create_user` called a boto3 method that doesn't exist, so no user could ever register through it. Fixed; see `docs/bugs/2026-10-21_bug_user_profile_create_user_calls_nonexistent_transact_write.md`.

## Not verified
- Nothing was run against real API Gateway, Cognito or CloudWatch. The authorizer, Analytics, AI assistant and User profile tests use mocks or moto; the Ledger tests use Testcontainers Postgres; the UI tests use Vitest.
- No browser run of the picker dialog or the Settings page.
