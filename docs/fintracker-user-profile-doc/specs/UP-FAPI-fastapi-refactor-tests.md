=========================
F2P TESTS (59)
=========================

--- TestGetProfile (4) ---
1. returns the profile, settings and privacy notice of the authorizer user: UP-FAPI-01 route contract (Appendix A GET /profile).
2. an unknown user is 404 problem+json with the trace id from traceparent: UP-FAPI-01 / UP-FAPI-04 trace_id from traceparent.
3. no authorizer context or a user that is not a UUID is 401: UP-FAPI-02 no valid authorizer user before any service call.
4. a client-sent user header is ignored for identity: UP-FAPI-02 headers never read, invariant 2.

--- TestSettings (3) ---
5. saves the timezone and returns the settings: UP-FAPI-01 route contract (PUT /profile/settings).
6. an invalid timezone is 400 invalid_setting with today's type URL, a trace id and without the value: UP-FAPI-04 problem+json with code and trace id.
7. a body that is not a JSON object is 400 invalid_setting and stores nothing: UP-FAPI-12 behavior unchanged.

--- TestPrivacyNotice (2) ---
8. accepting the current version is 204 and recorded: UP-FAPI-01 route contract (PUT /profile/privacy-notice).
9. another version or a bad body is 400 invalid_notice_version: UP-FAPI-04 today's codes and type URLs kept.

--- TestDeleteAccount (4) ---
10. deletes the user with the sub of the re-verified token: UP-FAPI-02 DELETE /profile re-verifies the bearer token.
11. no bearer token is 401 and deletes nothing: UP-FAPI-02 missing token.
12. a token that does not verify is 401 and deletes nothing: UP-FAPI-02 token does not verify.
13. a token of another user deletes nothing: invariant 2 identity only from the verified context.

--- TestFrameworkErrors (3) ---
14. an unknown path is 404 not_found and a wrong method is 405 method_not_allowed: UP-FAPI-01 framework errors as problem+json.
15. the API docs are not served outside the local container: UP-FAPI-01 docs disabled.
16. the trace id is generated when the request has no traceparent: UP-FAPI-04 trace_id generated.

--- test_goals_routes (6) ---
17. create, list and delete a goal: UP-FAPI-01 goals route contract (Appendix A).
18. a user sees only their own goals: invariants 4 and 5 owner-scoped goals.
19. a missing required field is 400 invalid_argument naming the field, not the value: UP-FAPI-04 4xx detail never holds the value.
20. a body that is not JSON is 400 invalid_argument, not 422: UP-FAPI-01 non-JSON body.
21. a goal id that is not a UUID is 400 invalid_argument: UP-FAPI-12 change recorded (old handler answered 500).
22. a request without the authorizer context is 401 and touches no goals: UP-FAPI-02 no valid authorizer user.

--- test_internal_routes (7) ---
23. an allow-listed caller gets the forwarded user's raw goals: UP-FAPI-03 happy path.
24. the internal settings route is gone: UP-FAPI-03 / XS-CTX-07 settings route returns 404.
25. no verified caller is 401 and the body does not say why: UP-FAPI-03 no verified caller, invariant 3.
26. a caller not on the list, or an unset list, is 403 and the user header is not read: UP-FAPI-03 caller_not_allowed, invariant 3.
27. a missing or invalid forwarded user is 400 without echoing it: UP-FAPI-03 forwarded user ID.
28. an unknown user is 404: UP-FAPI-03 unknown user.
29. the user comes from the forwarded header, never the path: invariant 2 / UP-FAPI-03.

--- test_failures_and_logging (6) ---
30. an unhandled exception is a generic 500 with nothing internal in it: UP-FAPI-04 internal_error without exception text, traceback logged once.
31. an unreachable database is 503 service_unavailable, not a stack trace: UP-FAPI-11 dependency down.
32. every log line of a request carries its trace id and the API Gateway request id: UP-FAPI-07 correlation IDs.
33. no log line holds a field from a settings or goal body: UP-FAPI-07 bodies never logged.
34. an email address and a card number in a log call are masked: UP-FAPI-07 / XS-ACCT-06 masking.
35. a standard-library log record is masked too: UP-FAPI-07 / XS-ACCT-06 masking.

--- test_post_confirmation (2) ---
36. creates the user and returns the original event: UP-FAPI-05 post_confirmation_handler contract.
37. a failure raises so Cognito does not confirm the user: UP-FAPI-05 post_confirmation_handler failure.

--- test_startup (10) ---
38. a dev user without the local flag stops startup: UP-FAPI-02 LOCAL_DEV_USER_ID needs the local flag.
39. the local flag on AWS stops startup even with a dev user: UP-FAPI-11 / invariant 12 local mode not deployable.
40. an unknown internal auth mode stops startup: UP-FAPI-11 INTERNAL_AUTH_MODE values.
41. a local container starts with the flag and a dev user: UP-FAPI-11 local container.
42. a cold start without the table name fails naming the variable but no value: UP-FAPI-06 startup check.
43. two requests in one process share one service instance: UP-FAPI-06 built once per process.
44. a route runs with a replaced service and creates no AWS client: UP-FAPI-06 dependency overrides; UP-FAPI-11 local GET /profile without a token.
45. without the local flag a public and an internal route are 401: UP-FAPI-11 local flag required.
46. locally the internal route needs a caller header and still applies the allow-list: UP-FAPI-03 with the local mode.
47. a user header on a public route never selects the local user: invariant 2 in the local container.

--- test_lambda_entry_points (2) ---
48. no module outside lambda_handlers defines an event, context function: UP-FAPI-05 structure test.
49. the two direct invocations are in lambda_handlers: UP-FAPI-05 Appendix B handler paths.

--- test_terraform_config (10) ---
50. the authorizer is a REQUEST authorizer with simple responses cached for 60 seconds: UP-FAPI-10 authorizer checks (UP-AUTH-03).
51. a zero-second authorizer cache fails the check: UP-FAPI-10 TTL check.
52. public and internal routes are listed one by one behind their own authorization: UP-FAPI-09 route split.
53. a default route on the public API fails the check: UP-FAPI-10 route check.
54. a route without its authorization type fails the check: UP-FAPI-09 authorization type on every route.
55. the authorizer role reads the table and the API role publishes to the deletion bus only: UP-FAPI-08 least-privilege roles.
56. a write permission on the authorizer role fails the check: UP-FAPI-08 / UP-FAPI-10 role check.
57. the table has keys, on-demand billing, TTL and point-in-time recovery by profile: UP-FAPI-08 table.
58. the allow-list is built from the caller roles and the local mode is not deployable: UP-FAPI-08 INTERNAL_ALLOWED_CALLER_ARNS and INTERNAL_AUTH_MODE.
59. no CDK or SAM resource is deployed: UP-FAPI-08 Terraform only.
