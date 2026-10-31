=========================
F2P TESTS (101)
=========================

--- test_router (18) ---
1. an allow-listed caller with a user context is served: KN-FAPI-01 Happy, KN-FAPI-02 Happy.
2. the success body has exactly the contract fields: KN-FAPI-10 same body as KN-RET Appendix B.
3. a caller off the allow-list gets 403 and no work is done: KN-FAPI-02 Fail.
4. no caller identity is 401 unauthorized and no work is done: KN-FAPI-02 Fail.
5. a missing or blank user context is 401 user_context_missing: KN-FAPI-02 Fail.
6. a user_id in the body is rejected and never used: KN-FAPI-02 Fail, section 8 invariant 2.
7. a body that is not JSON is 400 invalid_argument, not 422: KN-FAPI-01 Fail.
8. an empty body is 400 invalid_argument: KN-FAPI-01 Fail.
9. a body far larger than any valid request is rejected unread: KN-FAPI-01 Fail.
10. a validation failure keeps its 400 and names the field, not the value: KN-FAPI-01 Fail, KN-RET-02 validation.
11. the error body is RFC 9457 with code and trace_id but no request_id: KN-FAPI-10 Happy, KN-RET-07 errors.
12. the trace_id comes from the incoming traceparent: KN-FAPI-10 Happy, KN-RET-07 errors.
13. an unexpected exception in the service is a 500 without its text, with both IDs logged: KN-FAPI-10 Happy, KN-RET-07 errors.
14. an exception outside the service is a 500 problem without its text: KN-FAPI-01 Fail, KN-RET-07 errors.
15. refused requests are still counted in the metrics: KN-FAPI-10 Alt, KN-RET-08 metrics.
16. a served request emits one metric with the caller and no error: KN-FAPI-10 Alt, KN-RET-08 metrics.
17. a chunk owned by another user is dropped and signalled through the route: KN-FAPI-10 Alt, KN-RET-05 ownership re-check.
18. a unique query marker appears in no log line: KN-FAPI-10 Fail, KN-RET-08 no content in logs.

--- test_internal_http_library (6) ---
19. the route answers every row of the shared caller matrix: KN-FAPI-02 Alt, LB-IHTTP-09 Appendix A rows.
20. the library conformance suite passes against the real route: KN-FAPI-02 Alt, LB-IHTTP-08 conformance.
21. a forwarded user ID that is not a UUID is 400 and never used: KN-FAPI-02 Fail, XS-CTX-04 UUID user.
22. the caller is decided before the body is read: KN-FAPI-02 Requirement.
23. the service keeps no copy of signing or caller handling: KN-FAPI-02 Requirement, LB-IHTTP-09 no copy.
24. the route depends on the shared caller check and user context: KN-FAPI-02 Requirement.

--- test_app (16) ---
25. an unknown path is a 404 not_found problem: KN-FAPI-01 Alt.
26. a known path with another method is a 405 method_not_allowed problem: KN-FAPI-01 Alt.
27. the API docs are not served in the default strict mode: KN-FAPI-01 Alt.
28. the API docs are served only in local mode: KN-FAPI-01 Alt.
29. the not-found answer leaks neither the path nor the method: KN-FAPI-01 Alt, error-catalog not_found.
30. a test can replace the service and no client or connection is created: KN-FAPI-03 Happy.
31. two requests in one process get the same service instance: KN-FAPI-03 Alt.
32. startup without a required variable stops with its name and never a value: KN-FAPI-03 Fail.
33. data_api mode requires its own variables, not the postgres ones: KN-FAPI-03 Fail, KN-FAPI-04 Appendix B.
34. an unknown database mode stops the start naming the variable: KN-FAPI-03 Fail.
35. iam mode with no allow-list still starts and every call is a 403: KN-FAPI-03 Fail, fail closed.
36. local mode with an AWS runtime marker stops the start: KN-FAPI-03 Fail, LB-IHTTP-02.
37. a global endpoint override stops the start naming the variable: KN-FAPI-05 Fail.
38. a service-specific endpoint override is allowed: KN-FAPI-05 Requirement.
39. importing the entry point with a missing variable raises naming it: KN-FAPI-03 Fail.
40. the entry point exposes the app and the Lambda handler: KN-FAPI-01 Requirement.

--- test_embedding_client (5) ---
41. the client uses the configured region, short timeouts and no SDK retries: KN-FAPI-05 Requirement.
42. the model ID sent to Bedrock is the configured one: KN-FAPI-05 Alt.
43. without credentials the first query is a 503 embedding_unavailable without waiting for retries: KN-FAPI-05 Fail.
44. the embedding client is not configured without credentials: KN-FAPI-05 Fail, KN-FAPI-08 readiness.
45. the embedding client is configured with credentials: KN-FAPI-05 Happy.

--- test_embedder (1) ---
46. missing credentials fail at once without retries: KN-FAPI-05 Fail, KN-CHUNK-02 retries.

--- test_health (5) ---
47. health is 200 without touching any dependency: KN-FAPI-08 Requirement.
48. ready is 200 when the database answers and the embedding client is configured: KN-FAPI-08 Requirement.
49. ready is 503 database_unavailable when the database is stopped while health stays 200: KN-FAPI-08 Alt.
50. ready is 503 embedding_unavailable without credentials while health stays 200: KN-FAPI-05 Fail, KN-FAPI-08 Alt.
51. the probes return no user data and need no headers: KN-FAPI-08 Requirement.

--- test_retrieval_through_app (3) ---
52. a user row of user A is never returned to user B and no mismatch is signalled: KN-FAPI-04 Fail, KN-RET-05 ownership re-check.
53. the route returns ranked system chunks with the index commit: KN-FAPI-04 Happy.
54. a stopped database through the route is a 503 database_unavailable: KN-FAPI-04 Fail, KN-RET-04 retry.

--- test_connections (9) ---
55. a search as the login role sets the user and returns only visible rows: KN-FAPI-04 Happy, KN-VS-03 user context.
56. a superuser connection is refused at startup naming the role, never the password: KN-FAPI-04 Fail.
57. a BYPASSRLS role is refused at startup naming the role: KN-FAPI-04 Fail.
58. a safe login role passes the startup check: KN-FAPI-04 Requirement.
59. a stopped database is database_unavailable without the driver message: KN-FAPI-04 Fail, KN-RET-04.
60. the ping answers for a reachable database and fails as database_unavailable otherwise: KN-FAPI-04, KN-FAPI-08 readiness.
61. the Data API search runs context, settings and query in one transaction and commits: KN-FAPI-04 Alt, KN-VS-03, KN-VS-04.
62. a Data API failure rolls back and surfaces database_unavailable without the AWS message: KN-FAPI-04 Alt, Fail.
63. the Data API ping runs a trivial query: KN-FAPI-04 Alt, KN-FAPI-08 readiness.

--- test_logging_config (1) ---
64. a standard-library logger writes one JSON line with card numbers masked: XS-ACCT-06 log mask, KN-FAPI-10 no content in logs.

--- test_local_source (5) ---
65. paths are relative to the root and only help markdown is listed: KN-FAPI-06 Requirement, Alt.
66. a document is read by its path: KN-FAPI-06 Requirement.
67. a path with .. , outside help/ or not markdown is missing: KN-FAPI-06 Alt.
68. a symlink that leaves the root is neither listed nor readable: KN-FAPI-06 Alt.
69. a root without a help folder lists nothing: KN-FAPI-06 Requirement.

--- test_cli (15) ---
70. indexing a folder writes every help document and prints the counts: KN-FAPI-06 Happy.
71. a second run with no changes writes nothing and skips every document: KN-FAPI-06 Alt, KN-SDOC hash skip.
72. a changed file replaces only its own chunks: KN-FAPI-06 Alt, KN-SDOC atomic replace.
73. only help markdown is read and other files under the root are ignored: KN-FAPI-06 Alt.
74. a Bedrock failure keeps the previous chunks, exits non-zero and names the document: KN-FAPI-06 Fail.
75. a total Bedrock outage exits non-zero after the retries: KN-FAPI-06 Fail.
76. a database host that is not local exits before any database or Bedrock call: KN-FAPI-06 Fail.
77. local hosts are accepted: KN-FAPI-06 Requirement.
78. the command runs only against a direct connection and names the variable when it does not: KN-FAPI-06 Requirement.
79. a missing ingest credential stops the command naming the variable, never a value: KN-FAPI-06 Fail, KN-FAPI-03 Principle 4.
80. a root without a help folder is an error, not an empty success: KN-FAPI-06 Requirement.
81. rebuild embeds every document again even when unchanged: KN-FAPI-06 Requirement.
82. status prints the document and chunk counts and the last run commit: KN-FAPI-06 Requirement.
83. the default commit is the short commit and gets -dirty with uncommitted docs: KN-FAPI-06 Requirement.
84. outside a git repository the commit label says so: KN-FAPI-06 Requirement.

--- test_login_roles (4) ---
85. the login roles exist, cannot bypass RLS and belong to their NOLOGIN roles: KN-FAPI-07 Happy.
86. the retrieve login sees no user rows without a user context and cannot read the run log: KN-FAPI-07 Fail.
87. the ingest login can write system documents: KN-FAPI-07 Happy.
88. the init script refuses to create roles without a password: KN-FAPI-07 Fail.

--- test_repo_hygiene (9) ---
89. the local env file is ignored and not tracked: KN-FAPI-07 Fail.
90. no password literal appears in a compose, SQL, script or Dockerfile: KN-FAPI-07 Fail.
91. an example env file documents every secret the stack reads: KN-FAPI-07 Requirement.
92. the app and the index command wait for the migration step to finish successfully: KN-FAPI-07 Fail, KN-FAPI-09 Requirement.
93. the index command is on demand and mounts the docs read-only: KN-FAPI-09 Requirement.
94. the host AWS profile is mounted read-only and no global endpoint is set: KN-FAPI-09 Requirement, KN-FAPI-05 Fail.
95. local auth mode and the caller allow-list are set in the compose file only: KN-FAPI-09 Requirement, KN-FAPI-08 Fail.
96. the postgres container publishes no port that clashes with the shared local Postgres: KN-FAPI-09 Requirement.
97. the root compose file includes this stack: KN-FAPI-09 Requirement.

--- test_image (4) ---
98. the process runs as a non-root user: KN-FAPI-08 Fail.
99. the image holds no env file, credential file or test data: KN-FAPI-08 Alt.
100. health answers 200 within ten seconds even with no database: KN-FAPI-08 Happy, Alt.
101. the default command refuses local auth mode inside an AWS runtime: KN-FAPI-08 Fail, LB-IHTTP-02.
