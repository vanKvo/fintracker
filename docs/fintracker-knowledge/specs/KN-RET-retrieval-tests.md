=========================
F2P TESTS (56)
=========================

--- test_validation (12) ---
1. valid request passes: KN-RET-02 Happy.
2. missing k defaults to five: KN-RET-02 Alt.
3. k below 1 or above 10 is invalid and names the field: KN-RET-02 Fail.
4. non-integer k is invalid: KN-RET-02 Fail.
5. blank or non-string query is invalid: KN-RET-02 Fail.
6. query over 1000 characters is invalid and 1000 passes: KN-RET-02 Fail.
7. extra field including a user id is rejected: KN-RET-02 Fail, KN-RET-01 Fail.
8. missing query or scope is invalid: KN-RET-02 Requirement.
9. scope mine returns scope_not_enabled: KN-RET-02 Fail.
10. unknown scope is invalid: KN-RET-02 Fail.
11. body that is not an object is invalid: KN-RET-02 Requirement.
12. error message never echoes the input: KN-RET-02, KN-RET-07 Requirement.

--- test_router (9) ---
13. allow-listed caller with user context is accepted: KN-RET-01 Happy.
14. caller not on the allow-list gets 403 and no work is done: KN-RET-01 Fail.
15. request with no caller identity is refused fail-closed: KN-RET-01 Fail.
16. missing or blank user context gets 401: KN-RET-01 Fail.
17. user id in the body is rejected and never used: KN-RET-01 Fail.
18. body that is not JSON gets 400: KN-RET-02 Fail.
19. error body has code, generic message and request id: KN-RET-07, Appendix C.
20. unexpected exception returns 500 without its text and logs the request id: KN-RET-07 Fail.
21. refused requests are still counted in metrics: KN-RET-08 Requirement.

--- test_search (9) ---
22. system scope returns only system chunks nearest first even when user chunks are nearer: KN-RET-04 Happy.
23. hits carry source path, heading, text and distance: KN-RET-04, KN-RET-06 Requirement.
24. user context is set in the same transaction so only own mine rows are visible: KN-RET-04 Requirement.
25. only chunks of the active model are searched: KN-RET-03 Happy.
26. fewer matches than the limit returns them all without error: KN-RET-04 Alt.
27. empty index returns no hits and no commit: KN-RET-04 Alt.
28. index commit is the commit of the latest indexed system doc: KN-RET-06 Alt.
29. database error surfaces as database_unavailable without driver text: KN-RET-04 Fail.
30. search runs as the retrieve role: KN-RET-04 Requirement.

--- test_service (26) ---
31. query is embedded as is and search uses the active model: KN-RET-03 Happy.
32. embedding failure returns embedding_unavailable: KN-RET-03 Fail.
33. query too long to embed is an invalid argument: KN-RET-03 Requirement.
34. search gets the context user and requested scope, never a body user: KN-RET-04, KN-RET-01 Requirement.
35. empty result is a success with no chunks: KN-RET-04 Alt.
36. at most three chunks per document and k is respected: KN-RET-04 Alt.
37. database failure is retried once after one second: KN-RET-04 Fail.
38. database failing twice returns database_unavailable: KN-RET-04 Fail.
39. correct RLS drops nothing and emits no mismatch: KN-RET-05 Happy.
40. chunk owned by another user is dropped and counted with ids only: KN-RET-05 Alt, Fail.
41. system chunk with an owner is dropped: KN-RET-05 Requirement.
42. chunk of a scope other than requested is dropped: KN-RET-05 Requirement.
43. a mismatch is reported even when it empties the result: KN-RET-05 Fail.
44. response has exactly the contract fields in descending score order: KN-RET-06 Happy, Fail.
45. score is one minus distance to three decimals: KN-RET-06 Requirement.
46. score is clamped between zero and one: KN-RET-06 Requirement.
47. response names the model and index commit: KN-RET-06 Alt.
48. response never carries vectors, owner or document id: KN-RET-06 Requirement.
49. slow embedding returns timeout within the budget: KN-RET-07 Happy.
50. unexpected step exception surfaces as internal_error without its text: KN-RET-07 Fail.
51. every error code has a stable status and generic message: KN-RET-07, Appendix C.
52. a request emits ids, counts, scores and step timings only: KN-RET-08 Happy.
53. a failed request emits the error code and zero results: KN-RET-08 Requirement.
54. a validation failure still emits a metric with unknown scope and k: KN-RET-08 Requirement.
55. no log line contains the query or chunk text: KN-RET-08 Fail.
56. empty-result alarm needs over 30 percent and at least 20 requests: KN-RET-08 Alt.
