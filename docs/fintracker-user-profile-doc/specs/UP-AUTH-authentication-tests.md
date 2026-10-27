> **Tests for:** [UP-AUTH-authentication-spec.md](UP-AUTH-authentication-spec.md) · **Formerly:** `docs/fintracker-user-profile-doc/user-profile-tests-01.md` (renamed 2026-10)

=========================
F2P TESTS (45)
=========================

--- TestReqUp02JwtVerification (4) ---
1. a valid token is verified before sub resolution proceeds: UP-AUTH-02 A1 "JWT Signature Verification" — asserts `verify_access_token` is called with the bearer token before any DynamoDB lookup. Errors at fixture setup today (`authorizer_handler` doesn't exist).
2. an invalid-signature token denies without touching DynamoDB: UP-AUTH-02 A1 / F1 "INVALID_OR_EXPIRED_TOKEN" — asserts `IdentityService.get_profile_and_settings` is never called once JWT verification fails, i.e. denial happens before any lookup, not after a failed one.
3. an expired token denies: UP-AUTH-02 F1 "INVALID_OR_EXPIRED_TOKEN" — expiry is a distinct failure mode from a bad signature; both must deny.
4. a request with no `Authorization` header denies: UP-AUTH-02 A1, read against the implicit precondition that there's nothing to verify without a token.

--- TestReqUp02SubResolutionAndSubscriptionLookup (2) ---
5. `internal_user_id` is resolved via the existing `IdentityService.get_profile_and_settings`: UP-AUTH-02 A2 "Sub Resolution" — asserts the authorizer reuses the same DynamoDB-backed path `get_profile_handler` already exercises rather than a new repository method.
6. the returned context's `subscription_tier` comes from the profile record: UP-AUTH-02 A3 "Subscription Lookup" — same call as #5 also supplies subscription data, consistent with "never a Cognito custom attribute."

--- TestReqUp02ContextInjection (2) ---
7. an Allow response has the exact `{isAuthorized, context: {internal_user_id, subscription_tier}}` shape: UP-AUTH-02 A4 "Context Injection" — the simple-response contract `HttpApi` parameter mapping depends on.
8. a denied response carries no identity context: UP-AUTH-02 A4, defensive read — a deny must not leak a partially-built context for API Gateway to accidentally forward.

--- TestReqUp02DenyOnUnmappedSub (1) ---
9. a sub with no `IDENTITY#` mapping yet denies: UP-AUTH-02 A5 / F2 "UNMAPPED_SUB" — the race between a brand-new signup and the Post-Confirmation trigger must fail closed, not forward a request with no identity.

--- TestReqUp04FailClosed (2) ---
10. a DynamoDB failure denies rather than allowing: UP-AUTH-04 "Fail-Closed Authorization" / UP-AUTH-02 F3 "DYNAMODB_UNAVAILABLE" — an outage must not grant access with stale/default data.
11. an unexpected exception never propagates unhandled: UP-AUTH-04 — a raised exception reaching API Gateway from a REQUEST authorizer surfaces as a 500, not a deny; the handler must catch broadly and return an explicit deny instead.

--- TestReqUp03AuthorizerResultCaching (7) ---
12. the `HttpApi` has an `Auth` block configured at all: UP-AUTH-02 B1 — today there's no authorizer wired to the API Gateway definition in `template.yaml`.
13. the configured authorizer is `FunctionPayloadType: REQUEST`, not the built-in JWT type: UP-AUTH-02 B1 — the built-in type can't call DynamoDB, so it's explicitly ruled out; this pins the choice in config, not just prose.
14. the authorizer uses `EnableSimpleResponses: true`: UP-AUTH-02 A4 — must match the simple-response shape `authorizer_handler` returns (test #7), not an IAM policy document.
15. the identity source includes the `Authorization` header: UP-AUTH-03 A1 — caching is keyed on this value; if it's misconfigured, requests would be cached under the wrong (or no) key.
16. `AuthorizerResultTtlInSeconds` is exactly `60`: UP-AUTH-03 A1 — pins the specific recommended value, not just "some TTL is set."
17. the TTL is within API Gateway's `[1, 3600]` bound: UP-AUTH-03 B1 — sanity check against the platform's own cap.
18. the `/profile` GET route is actually covered by an authorizer (route-level or `DefaultAuthorizer`): UP-AUTH-02 B1, read end-to-end — an authorizer existing in the template isn't useful if no route is configured to require it.

--- test_route_identity.TestGetProfile (4) ---
19. GET /profile reads the user from the authorizer context: UP-AUTH-02 A4 / B1.
20. a request without the authorizer context, in the JWT shape or none, is 401 and not a server error: UP-AUTH-02 B1.
21. an internal user id that is not a UUID is 401: UP-AUTH-02 A4.
22. an unknown user is 404: UP-AUTH-02 A5.

--- test_route_identity.TestUpdateSettings (2) ---
23. settings are saved for the user in the authorizer context: XS-CTX-01 / UP-AUTH-02 A4.
24. a request without the authorizer context saves nothing: XS-CTX-01 / UP-AUTH-02 B1.

--- test_route_identity.TestDeleteAccount (4) ---
25. the user in the authorizer context is deleted with the sub of the verified token: UP-AUTH-02 A4.
26. a request without the authorizer context deletes nothing: UP-AUTH-02 B1.
27. a request without a bearer token deletes nothing: UP-AUTH-02 A1.
28. a token that does not verify deletes nothing: UP-AUTH-02 A1.

--- test_route_identity.TestGoals (4) ---
29. listing goals uses the authorizer context without resolving a sub: UP-AUTH-02 A4.
30. creating a goal uses the authorizer context: UP-AUTH-02 A4.
31. deleting a goal uses the authorizer context: UP-AUTH-02 A4.
32. a request without the authorizer context is 401 and touches no goals: UP-AUTH-02 B1.

--- test_route_identity.TestIdentityService (6) ---
33. a profile for a user id needs no sub lookup: UP-AUTH-02 A4.
34. a user id with no records is not found: UP-AUTH-02 A5.
35. saving settings for a user id needs no sub lookup: XS-CTX-01.
36. deleting an account removes the records for the user id and sub, then publishes: UP-AUTH-02 A4.
37. a sub that maps to another user deletes and publishes nothing: UP-AUTH-02 A4 / invariant 5.
38. a sub with no mapping deletes and publishes nothing: UP-AUTH-02 A5.

--- TestXsCtx02RestApiFormat (7) ---
39. an allowed REST request gets an Allow policy with the same four context fields: XS-CTX-02 / ADR-012.
40. the policy covers every method of the API so a cached result serves them all: XS-CTX-02.
41. a missing or malformed token gets a Deny policy and no identity: UP-AUTH-02 A1 / UP-AUTH-04.
42. an invalid token gets a Deny policy: UP-AUTH-02 F1.
43. an unmapped sub gets a Deny policy: UP-AUTH-02 A5.
44. a DynamoDB failure gets a Deny policy, not an exception: UP-AUTH-04 / UP-AUTH-02 F3.
45. an HTTP API event still gets the simple response: UP-AUTH-02 A4.

Not automated (excluded from both counts):
- UP-AUTH-01 "Cognito Hosted UI Login" — already implemented, and lives in `fintracker-ui` (TypeScript/Angular, Vitest), a different test runtime than this Python suite. Documented in the spec as a confirmed-correct baseline, not a gap; no new test added here.
- UP-AUTH-05 "Live, Uncached Check for Cost-Bearing Actions" — the cost-bearing route this applies to (statement upload) is defined in a different service's API Gateway configuration (data-pipeline/ledger), not in `services/fintracker-user-profile/template.yaml`. Nothing in this service's own template or code implements or references that route yet, so there is no local artifact to assert against; needs a test in whichever service/stack ends up owning that route's `template.yaml`/CDK stack.


=========================
P2P TESTS
=========================

Not applicable. Every test in this suite targets net-new behavior (the
authorizer function and its `HttpApi` wiring) that doesn't exist yet — there
is no currently-passing code path for this flow to regression-test. The
existing `TestResolveSub`/`TestRegisterUser`/etc. suites in
`test_identity_service.py` already cover `IdentityService`'s pre-existing
behavior and continue to pass unmodified (verified: 12 passed alongside the
18 new failures in this run) — they're not duplicated here since this
document is scoped to the new authorizer flow, not the whole service.
