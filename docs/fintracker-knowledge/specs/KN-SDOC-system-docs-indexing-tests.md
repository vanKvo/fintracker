=========================
F2P TESTS (42)
=========================

--- test_publisher (6) ---
1. two changed and one deleted doc upload two files and one manifest listing all three: KN-SDOC-01 Happy.
2. merge without help changes uploads nothing and writes no manifest: KN-SDOC-01 Alt.
3. non-markdown and oversized files are skipped and listed while the job succeeds: KN-SDOC-01 Alt.
4. path escaping the help folder is skipped: KN-SDOC-01 Requirement.
5. failed upload writes no manifest and fails the job with a generic error: KN-SDOC-01 Fail.
6. git name-status output becomes the changed and deleted lists: KN-SDOC-01 Requirement.

--- test_trigger (5) ---
7. manifest is parsed into commit, changed and deleted paths: KN-SDOC-02 Requirement, Appendix A.
8. malformed manifest is rejected: KN-SDOC-02 Requirement.
9. manifest event starts one execution named after the commit: KN-SDOC-02 Requirement.
10. replayed manifest event starts no second execution: KN-SDOC-02 Alt.
11. other start errors are not swallowed: KN-SDOC-02 Requirement.

--- test_source (3) ---
12. source reads a doc by its repo path: KN-SDOC-02 Requirement.
13. missing object is reported as source missing: KN-SDOC-02 Fail.
14. listing returns markdown docs without manifests: KN-SDOC-05 Requirement.

--- test_indexing (17) ---
15. each changed path is its own branch ending indexed or skipped: KN-SDOC-02 Happy.
16. unchanged hash is skipped without embedding calls: KN-SDOC-02 Alt.
17. hash is the sha-256 of the uploaded bytes: KN-SDOC-02 Requirement.
18. missing source fails its branch and other branches continue: KN-SDOC-02 Fail.
19. unreadable source fails as invalid source: KN-SDOC-02 Appendix B.
20. at most four branches run at once: KN-SDOC-02 Requirement.
21. new version replaces the old one for search: KN-SDOC-03 Happy.
22. concurrent search sees only the old version until commit: KN-SDOC-03 Alt.
23. deleted path removes its document and chunks: KN-SDOC-03 Requirement.
24. deleting a path that is not indexed is a no-op: KN-SDOC-03 Alt.
25. failed transaction commits nothing and the old version stays searchable: KN-SDOC-03 Fail.
26. transient embedding failure is retried and the doc is indexed: KN-SDOC-04 Happy.
27. retries back off two, four, eight seconds then fail: KN-SDOC-04 Requirement.
28. one permanent failure leaves four docs indexed and the run partial: KN-SDOC-04 Alt.
29. permanently failed doc keeps its previous version searchable: KN-SDOC-04 Fail.
30. database resuming is retried like any transient error: KN-SDOC-04 Fail.
31. logs carry paths and codes but never doc text: KN-SDOC-06 Requirement.

--- test_runs (11) ---
32. rebuild indexes every doc under the requested model: KN-SDOC-05 Happy.
33. rebuild with a new model writes alongside the old chunks: KN-SDOC-05 Requirement.
34. rebuild with the active model ignores the hash and replaces in place: KN-SDOC-05 Alt.
35. rebuild with a failed doc ends partial: KN-SDOC-05 Fail.
36. rebuild is limited to allow-listed callers: KN-SDOC-05 Alt.
37. finished run records commit, status and counts: KN-SDOC-06 Happy.
38. index status returns the last successful commit and time: KN-SDOC-06 Alt.
39. index status is empty before any run and denied to other callers: KN-SDOC-06 Alt.
40. alarm fires for partial or failed runs only: KN-SDOC-06 Fail.
41. alarm fires when no success follows a manifest within thirty minutes: KN-SDOC-06 Fail.
42. run table is readable by ingest only: KN-SDOC-06 Appendix C.
