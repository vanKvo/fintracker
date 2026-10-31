=========================
F2P TESTS (52)
=========================

--- TestSettings (7) ---
1. an unset mode is iam: LB-IHTTP-01 default is strict.
2. INTERNAL_AUTH_MODE=local gives mode local: LB-IHTTP-01 local mode.
3. Local, LOCAL and an empty set value are invalid: LB-IHTTP-01 case-sensitive, never falls back to local.
4. an invalid mode raises naming the variable and the allowed values: LB-IHTTP-01 startup failure.
5. allowed caller ARNs are trimmed, empty entries dropped and duplicates ignored: LB-IHTTP-01 list parsing.
6. an empty or unset list is valid: LB-IHTTP-01 empty list means every call is 403.
7. a missing INTERNAL_BASE_URL_<SERVICE> raises when that client is built, naming the variable: LB-IHTTP-01 missing base URL.

--- TestLocalGuard (6) ---
8. local starts when no AWS marker is set: LB-IHTTP-02 happy path.
9. iam starts with or without the markers: LB-IHTTP-02 iam unaffected.
10. local with AWS_EXECUTION_ENV set raises and names the marker, not its value: LB-IHTTP-02 marker one.
11. local with AWS_LAMBDA_FUNCTION_NAME set raises: LB-IHTTP-02 marker two.
12. local with ECS_CONTAINER_METADATA_URI or ECS_CONTAINER_METADATA_URI_V4 set raises: LB-IHTTP-02 markers three and four.
13. a service's terraform test fails if INTERNAL_AUTH_MODE is in any function or task environment: LB-IHTTP-02 never deployable (one per service, run in that service).

--- TestOutboundRequest (8) ---
14. iam signs with SigV4, service execute-api, and sends the three user headers: LB-IHTTP-03 iam request.
15. the signature covers the body hash: LB-IHTTP-03 body hash included.
16. local sends no Authorization header, X-Internal-Caller-Arn and the three user headers: LB-IHTTP-03 local request.
17. INTERNAL_LOCAL_CALLER_ARN overrides the default arn:local:caller: LB-IHTTP-03 local caller.
18. a call without a UserContext raises before any network call: LB-IHTTP-03 programming error.
19. reserved headers set by the library user are replaced, not merged: LB-IHTTP-03 reserved headers.
20. missing credentials in iam raise InternalCallError signing_failed and send nothing: LB-IHTTP-03 credentials.
21. an empty user ID or a malformed currency raises before any network call: LB-IHTTP-03 incomplete context.

--- TestOutboundPolicy (9) ---
22. a 200 returns the parsed body and status: LB-IHTTP-04 happy path.
23. a GET that gets 503 then 200 returns the 200 after one retry: LB-IHTTP-04 retry.
24. a GET is retried at most twice with jittered delays inside 100 ms and 300 ms bands: LB-IHTTP-04 retry limits.
25. a 4xx is never retried and surfaces the body's code, or upstream_error without one: LB-IHTTP-04 4xx.
26. a POST that gets 503 is not retried and raises InternalCallError status 503: LB-IHTTP-04 non-idempotent.
27. a response slower than the total deadline raises InternalCallError timeout: LB-IHTTP-04 deadline 25 s.
28. connect and read timeouts default to 2 s and 10 s and can be overridden: LB-IHTTP-04 timeouts.
29. traceparent is sent, taken from the current request or generated: LB-IHTTP-04 trace propagation.
30. no log line holds a body, a header value or the URL query string: LB-IHTTP-04 no leaks.

--- TestInboundCaller (8) ---
31. iam: a caller on the list passes: LB-IHTTP-05 happy path.
32. iam: no verified caller is 401 unauthorized: LB-IHTTP-05 / Appendix A row 1.
33. iam: X-Internal-Caller-Arn without a verified caller is 401: LB-IHTTP-05 header ignored in iam.
34. iam: a caller off the list is 403 caller_not_allowed: LB-IHTTP-05 / Appendix A row 3.
35. iam: an empty or unset list is 403: LB-IHTTP-05 / Appendix A row 4.
36. local: header present and no list set passes: LB-IHTTP-05 local happy path.
37. local: header missing is 401; header present but off a set list is 403: LB-IHTTP-05 local rows.
38. the raw-event adapter caller_rejection(event) returns the same decision as the dependency for every row: LB-IHTTP-05 adapters agree.

--- TestUserContext (7) ---
39. a valid user ID returns the context with timezone and currency when sent: LB-IHTTP-06 happy path.
40. a route declaring only user accepts a request without timezone and currency: LB-IHTTP-06 requirement per route.
41. a missing user ID is 401 user_context_missing: LB-IHTTP-06 / Appendix A.
42. a user ID that is not a UUID is 400 invalid_argument and the value is not echoed: LB-IHTTP-06 malformed.
43. a missing timezone on a route that requires it is 409 user_settings_incomplete: LB-IHTTP-06 XS-CTX-05.
44. an invalid timezone or currency is 500 user_context_invalid: LB-IHTTP-06 XS-CTX-05.
45. when the caller check fails the user headers are never read: LB-IHTTP-06 order (access raises in the test).

--- TestProblems (4) ---
46. a 403 body has code caller_not_allowed, the right type, and a trace_id: LB-IHTTP-07 happy path.
47. trace_id comes from a valid traceparent, else is generated: LB-IHTTP-07 trace id.
48. the Lambda adapter returns the same body in the statusCode, headers, body shape: LB-IHTTP-07 adapter.
49. a rejection for an unlisted ARN does not contain that ARN: LB-IHTTP-07 no leaks.

--- TestTestingKit (3) ---
50. run_conformance passes for a FastAPI route wired with the dependencies: LB-IHTTP-08 happy path.
51. run_conformance fails for a route that skips require_internal_caller: LB-IHTTP-08 fail on the 401 case.
52. importing fintracker_internal does not import fintracker_internal.testing: LB-IHTTP-08 not in production paths.

=========================
SERVICE ADOPTION TESTS (run in each service's repository)
=========================

A1. the service's internal routes pass run_conformance in CI: LB-IHTTP-09 / LB-IHTTP-08.
A2. existing internal-route tests pass unchanged except the setting name: LB-IHTTP-09.
A3. Analytics in local mode applies the allow-list when a list is set: LB-IHTTP-09 old skip removed.
A4. a repository check fails when a service imports botocore.auth for signing or handles X-Internal-Caller-Arn itself: LB-IHTTP-09.
A5. a service built against a library version that fails its conformance run does not build: LB-IHTTP-09.

=========================
LEDGER TESTS (Java, in the Ledger repository)
=========================

L1. every row of the copied vectors/internal_auth.json passes against InternalCallerFilter and UserContextFilter: LB-IHTTP-10 happy path.
L2. a Python service in local mode calls Ledger in local mode and gets 200 (compose smoke test): LB-IHTTP-10 alt.
L3. Ledger in local mode with AWS_EXECUTION_ENV set exits at startup: LB-IHTTP-10 guard.
L4. a vectors file whose recorded library version differs from the version in the Ledger test config fails: LB-IHTTP-10 version recorded.
