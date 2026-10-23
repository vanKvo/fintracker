=========================
F2P TESTS (45)
=========================

--- test_chunker (16) ---
1. three h2 sections become three chunks with heading paths: KN-CHUNK-01 Happy.
2. chunk text excludes its own heading and reports token count: KN-CHUNK-01 Happy.
3. long section splits at paragraph boundaries with overlap: KN-CHUNK-01 Alt.
4. oversized paragraph is split at sentences: KN-CHUNK-01 Alt.
5. short section merges into the next sibling: KN-CHUNK-01 Alt.
6. last short section merges into the previous one: KN-CHUNK-01 Alt.
7. short section with a different parent stays alone: KN-CHUNK-01 Alt.
8. sections without body produce no chunk: KN-CHUNK-01 Requirement.
9. front matter and html comments are removed: KN-CHUNK-01 Alt.
10. code blocks are never split in the middle: KN-CHUNK-01 Alt.
11. headings inside code blocks and h4 do not split: KN-CHUNK-01 Requirement.
12. same input gives identical chunks: KN-CHUNK-01 Alt, Design Principle 3.
13. doc without headings uses the front matter title: KN-CHUNK-01 Fail.
14. doc without headings or title uses the file name: KN-CHUNK-01 Fail.
15. empty doc gives no chunks and no error: KN-CHUNK-01 Fail.
16. config changes split levels and sizes: KN-CHUNK-01 Appendix A.

--- test_embedder (12) ---
17. chunk gets a normalized vector tagged with the active model: KN-CHUNK-02 Happy.
18. embedded text is heading path, blank line, chunk text: KN-CHUNK-02 Requirement.
19. model id comes from config, not from code: KN-CHUNK-02 Requirement, Design Principle 1.
20. query is embedded without a heading prefix: KN-CHUNK-02 Requirement, KN-RET-03.
21. vector that is not unit length is normalized: KN-CHUNK-02 Happy.
22. text over the model limit is rejected before any call: KN-CHUNK-02 Alt.
23. failed call is retried three times with backoff then succeeds: KN-CHUNK-02 Fail.
24. exhausted retries fail with embedding_unavailable and no internal detail: KN-CHUNK-02 Fail.
25. response with wrong dimension count is treated as a failure: KN-CHUNK-02 Happy, Fail.
26. embedding a batch is all or nothing: KN-CHUNK-02 Fail.
27. embedding a batch returns one result per chunk in order: KN-CHUNK-02 Happy.
28. failure logs never contain chunk text: KN-CHUNK-02 Fail, invariant 10.

--- test_model_switch (7) ---
29. switch sets the new model and deletes the old models rows: KN-CHUNK-03 Requirement.
30. switch is refused naming docs with no chunks under the target model: KN-CHUNK-03 Fail.
31. partial rebuild is refused because failed docs have no new chunks: KN-CHUNK-03 Fail, KN-SDOC-05 Fail.
32. failed rebuild keeps the setting and deletes the new models rows: KN-CHUNK-03 Alt.
33. failed quality gate keeps the setting and deletes the new models rows: KN-CHUNK-03 Alt.
34. switching to the model already active changes nothing: KN-CHUNK-03 Requirement.
35. quality gate is not run when docs are missing: KN-CHUNK-03 Requirement.

--- test_quality_gate (10) ---
36. recall above threshold with no drop passes and becomes the baseline: KN-CHUNK-04 Happy.
37. first run without a baseline passes on the threshold alone: KN-CHUNK-04 Happy.
38. a question is a hit when any expected path is in the top k: KN-CHUNK-04 Alt.
39. paths beyond the top k do not count: KN-CHUNK-04 Alt.
40. report lists each missed question with the paths returned instead: KN-CHUNK-04 Alt.
41. recall below threshold fails with score and baseline in the message: KN-CHUNK-04 Fail.
42. drop of more than five points from the baseline fails even above threshold: KN-CHUNK-04 Requirement.
43. drop of exactly five points passes: KN-CHUNK-04 Requirement.
44. golden set under thirty questions is refused: KN-CHUNK-04 Requirement.
45. golden questions load from yaml: KN-CHUNK-04 Appendix B.

