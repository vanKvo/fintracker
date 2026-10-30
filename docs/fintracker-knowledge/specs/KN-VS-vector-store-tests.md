=========================
F2P TESTS (36)
=========================

--- test_schema (10) ---
1. migration creates both tables and the pgvector extension: KN-VS-01 Happy.
2. check constraint rejects invalid scope and owner combinations: KN-VS-01 Alt.
3. second document with the same scope, owner and path is rejected: KN-VS-01 Alt.
4. same path under a different owner or embedding model is allowed: KN-VS-01 Appendix A unique key.
5. deleting a document deletes its chunks: KN-VS-01 Alt.
6. chunk embedding model must equal the document's: Appendix A kn_chunks.
7. chunk scope and owner must equal the document's: Appendix A kn_chunks.
8. chunk matching its document is accepted: Appendix A kn_chunks.
9. embedding must have the configured dimensions: Appendix A kn_chunks, KN-CHUNK-02.
10. failed migration stops later migrations and leaves nothing partial: KN-VS-01 Fail.

--- test_roles (8) ---
11. each workflow role exists and may connect: KN-VS-02 Happy.
12. each role holds exactly the Appendix B privileges on both tables: KN-VS-02 Happy.
13. retrieve role can select but insert, update and delete fail: KN-VS-02 Alt.
14. ingest role can write system documents: KN-VS-02 Happy, Appendix B.
15. delete role cannot delete system rows: KN-VS-02 Alt.
16. delete role deletes only the current user's user rows: KN-VS-02 Appendix B.
17. delete role without user context deletes nothing: KN-VS-02 Appendix B, KN-VS-03.
18. other services' roles cannot connect or read: KN-VS-02 Fail.

--- test_rls (8) ---
19. row-level security is enabled and forced on both tables: KN-VS-03 Requirement.
20. user context shows system rows and own rows only: KN-VS-03 Happy.
21. no user context shows system rows only: KN-VS-03 Alt.
22. context set in a separate call does not apply: KN-VS-03 Alt.
23. context from one transaction does not leak into the next: KN-VS-03 Requirement.
24. writing a user row for another user is rejected: KN-VS-03 Fail.
25. writing a user row without user context is rejected: KN-VS-03 Fail.
26. writing a user row for the current user is accepted: KN-VS-03 Happy.

--- test_vector_index (5) ---
27. index is hnsw with cosine distance, m 16, ef_construction 64, and valid: KN-VS-04 Requirement, Fail.
28. search session applies ef_search 100 and relaxed-order iterative scan: KN-VS-04 Requirement.
29. search returns exactly k when enough rows pass the filter: KN-VS-04 Happy.
30. search still returns k when 99 percent of rows belong to other users: KN-VS-04 Alt.
31. search returns all matching rows without error when fewer than k pass: KN-VS-04 Alt.

--- test_isolation (5) ---
32. user A never sees user B rows in either table or in vector search, on every role and both call paths: KN-VS-05 Happy, Alt.
33. system-scope search returns no user rows even when user rows are nearer: KN-VS-05 Alt.
34. single-transaction path returns the caller's own rows and system rows: KN-VS-05 Alt.
35. separate-call path returns system rows only: KN-VS-05 Alt.
36. a leak fails the build naming the table and never the row text: KN-VS-05 Fail.
