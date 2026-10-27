> **Tests for:** [XS-IMP-statement-import-contract-spec.md](XS-IMP-statement-import-contract-spec.md)

=========================
F2P TESTS (93)
=========================

--- TestCatalog (pipeline) (5) ---
1. the catalog holds every Appendix A code: XS-IMP-04.
2. every pipeline error resolves to a catalog code: XS-IMP-04 / DP-ING-10.
3. a pipeline error gives its own reason: DP-ING-10.
4. any other exception is a PIPELINE_ERROR: DP-ING-10 Alt.
5. a pipeline error with a reason outside the catalog is a PIPELINE_ERROR: XS-IMP-04.

--- TestOnlyCatalogCodesAreStored (3) ---
6. the job repository refuses a reason outside the catalog: XS-IMP-04 Fail / DP-ING-10 Fail.
7. the job repository stores a catalog code with the failed and total counts: DP-ING-10 / XS-IMP-04 Alt.
8. no handler passes exception text as the reason: DP-ING-10 / DP-ING-08.

--- TestGatekeeperHandlerStoresReasonCodes (2) ---
9. a 30 MB file gives FILE_TOO_LARGE with no byte counts: DP-ING-10 Happy / XS-IMP-04 Happy.
10. an unexpected error gives PIPELINE_ERROR and is logged with the job id and stage: DP-ING-10 Alt.

--- TestExtractorHandlerStoresReasonCodes (2) ---
11. a KeyError gives PIPELINE_ERROR and the detail stays in the log: DP-ING-10 Alt.
12. a pipeline error keeps its own reason: DP-ING-10.

--- TestStatusApiShape (7) ---
13. a failed job returns status and reason without error text: DP-ING-10.
14. a partially completed job returns counts, not a sentence: DP-ING-10 / XS-IMP-04 Alt.
15. a running job has no reason or counts: DP-ING-10.
16. a reason stored before the catalog existed is shown as PIPELINE_ERROR: XS-IMP-04.
17. the failed duplicate keeps its named reason and payload: LG-STMT-08 / XS-IMP-04.
18. the column mapping proposal is returned in the shape the UI reads: DP-MAP-02 / DP-ING-01 Mapping Transparency.
19. a duplicate read back from a real (moto) job record, with `existingTransactionCount` stored as a DynamoDB number, returns 200 with that count as a JSON number: LG-STMT Shared Contract / LG-STMT-04 / LG-STMT-08.

--- TestRecordFailure (8) ---
20. a cancel sets the job failed and tells the Ledger: XS-IMP-02 Happy.
21. a timeout at the column check gives the confirmation timeout: XS-IMP-02 / DP-ING-09 Happy.
22. a stage failure keeps the reason the stage recorded: XS-IMP-02 / DP-ING-10.
23. a crash that recorded nothing is a PIPELINE_ERROR: XS-IMP-02 / DP-ING-10.
24. the cause text is never stored: XS-IMP-04 / DP-ING-08.
25. a duplicate's details survive the failed status: LG-STMT-08.
26. the counts of a failed push survive the failed status: DP-ING-10.
27. a missing job record is still failed and reported: XS-IMP-02.

--- TestReportImportFailure (5) ---
28. the signed internal route is called with the reason and the owner: XS-IMP-02.
29. a missing or imported statement is not retried: XS-IMP-02 Alt / Fail.
30. an unreachable Ledger is retried 4 times, then LEDGER_FAILURE_NOTICE_FAILED is logged: XS-IMP-02 Fail.
31. a server error is retried and a later success stops it: XS-IMP-02 Fail.
32. an unset Ledger URL is logged, not raised: XS-IMP-02 Fail.

--- StatementImportFailureTest (4) ---
33. a statement with nothing imported is failed with the reason code, scoped to the caller: XS-IMP-02 Happy.
34. repeating the call for an already-failed statement is a quiet success: XS-IMP-02 Alt.
35. a statement that already has imported rows is never failed: XS-IMP-02 Alt.
36. an unknown statement, or another user's, is not found: XS-IMP-02 Fail.

--- InternalStatementImportFailureControllerTest (4) ---
37. answers 204 and passes the caller's identity and the reason code through: XS-IMP-02.
38. an unknown or foreign statement answers 404: XS-IMP-02 Fail.
39. a statement that already has imported rows answers 409: XS-IMP-02 Alt.
40. a missing or malformed reason code is a 400 and nothing is recorded: XS-IMP-04.

--- StatementImportFailureIT (9) ---
41. a PROCESSING statement with nothing imported becomes FAILED with the reason code: XS-IMP-02 Happy.
42. the Statements tab reads the failure back as status and reason code: XS-IMP-02 Happy.
43. repeating the call changes nothing and answers 204: XS-IMP-02 Alt.
44. a statement that already has imported rows is never set to FAILED: XS-IMP-02 Alt.
45. rows the user deleted don't count as imported rows: XS-IMP-02.
46. an unknown statement answers 404: XS-IMP-02 Fail.
47. another user's statement answers 404 and is left as it was: XS-IMP-02 Fail / invariant 5.
48. a reason that isn't a code is a 400: XS-IMP-04.
49. the route fails closed without a verified caller: XS-IMP-02 / invariant 3.

--- FailedStatementReuploadTest (4) ---
50. failed statements with no transactions and the same hash or month are removed before the duplicate check and the insert: XS-IMP-03.
51. if removing the failed record fails, the new upload is not created: XS-IMP-03 Fail.
52. nothing is removed for an account the caller doesn't own: XS-IMP-03 / invariant 5.
53. the internal duplicate check does not remove anything: XS-IMP-03.

--- FailedStatementReuploadIT (9) ---
54. a CSV that timed out at the column check is uploaded again with no duplicate prompt and one statement for the month: XS-IMP-03 Happy.
55. a different file for the same month also replaces the failed record: XS-IMP-03.
56. the same file for a different month replaces the failed record too: XS-IMP-03.
57. a failed statement that has transactions still triggers the duplicate prompt: XS-IMP-03 Alt.
58. a COMPLETED or PROCESSING statement still triggers the duplicate prompt: XS-IMP-03 Alt.
59. a failed statement nobody re-uploads stays in the list: XS-IMP-03 Alt.
60. another account's failed statement is never touched: XS-IMP-03 / invariant 5.
61. the delete and the new statement commit together: XS-IMP-03 Fail.
62. the internal duplicate checks ignore a failed statement with no transactions: XS-IMP-03.

--- TestReviewReason (6) ---
63. a screenshot row read by Textract at 0.55 is flagged LOW_CONFIDENCE_EXTRACTION: XS-IMP-01 Happy.
64. a row exactly at the threshold is not flagged: XS-IMP-01.
65. a PDF row read by Textract at 0.75 is not flagged: XS-IMP-01.
66. CSV and text-layer rows never carry a review reason: XS-IMP-01 Alt.
67. the score stays in the pipeline and the old flag is gone: XS-IMP-01.
68. an unknown review reason is not accepted by the row: XS-IMP-01 Fail.

--- TransactionServiceImportTest (review reason) (3) ---
69. LOW_CONFIDENCE_EXTRACTION is stored with the pending row: XS-IMP-01 Happy.
70. a row without one carries none: XS-IMP-01 Alt.
71. a reason the Ledger doesn't know is stored as null and the row is still imported: XS-IMP-01 Fail.

--- statement.service.spec.ts (1) ---
72. a partially completed status carries the counts as fields: XS-IMP-04 Alt / DP-ING-10.

--- reason-messages.spec.ts (9) ---
73. each user-fixable code has its own message from the catalog: XS-IMP-04 Happy / Appendix A.
74. SERVER_DUPLICATE_DETECTED names the date of the statement it matched: XS-IMP-04 / LG-STMT-08.
75. SERVER_DUPLICATE_DETECTED without a date still reads as a sentence: XS-IMP-04.
76. our-side and unknown codes show the generic message with the reference: XS-IMP-04 Alt.
77. a code the catalog does not know is never echoed: XS-IMP-04 Fail.
78. a failed statement with no job id leaves the reference out: XS-IMP-04.
79. a partial import reports its counts as a sentence built in the UI: XS-IMP-04 Alt / DP-ING-10.
80. a partial import with no counts falls back to a plain sentence: XS-IMP-04.
81. LOW_CONFIDENCE_EXTRACTION asks the user to check the date and amount: XS-IMP-01 Appendix A.

--- statements.spec.ts (4) ---
82. a statement cancelled at the column check shows "Upload cancelled…": XS-IMP-02 Happy.
83. an unknown failure reason shows the generic message with the statement id: XS-IMP-04 Alt.
84. a failed statement with no recorded reason is an our-side failure, not blank: XS-IMP-02.
85. a completed statement has no failure message: XS-IMP-02.

--- upload-statement-modal.spec.ts (3) ---
86. a failed job shows the catalog message for its reason: XS-IMP-04 Happy.
87. a reason the catalog does not know is shown as an our-side error with the job reference: XS-IMP-04 Alt / Fail.
88. a partly imported statement reports the counts: XS-IMP-04 Alt.

--- statement.service.spec.ts — failure reason (1) ---
89. a listed statement carries the failure reason the Ledger stored: XS-IMP-02.

--- transaction.service.spec.ts — review fields (1) ---
90. a transaction carries its review reason, category issue and category source: XS-IMP-01.

--- transactions.spec.ts — review hint (3) ---
91. a pending low-confidence row is highlighted and says what to check: XS-IMP-01 Happy.
92. an approved row, or one with no review reason, is not highlighted: XS-IMP-01 Alt.
93. a row that is low-confidence and uncategorized shows both highlights: XS-IMP-01 Alt.
