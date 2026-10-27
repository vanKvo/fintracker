> **Tests for:** [LG-STMT-statement-upload-spec.md](LG-STMT-statement-upload-spec.md) · **Formerly:** `ledger-statement-tests-02-v1.md`, `ledger-statement-tests-02-v2.md` (merged 2026-10)

=========================
F2P TESTS (144)
=========================

--- StatementServiceTest (14) ---
1. an EXACT_FILE match is found by content hash, scoped to the account, with the matched statement's own transaction count: LG-STMT-03.
2. a SAME_MONTH match is found when no content-hash match exists: LG-STMT-06.
3. EXACT_FILE takes priority when a statement matches both, and the SAME_MONTH query is never issued: LG-STMT-03/06 specificity priority.
4. neither contentHash nor statementMonth matching returns empty: LG-STMT-03/06 baseline negative.
5. closingDate before openingDate is rejected and nothing is inserted: LG-STMT-07.
6. closingDate equal to openingDate is accepted as a single-day statement: LG-STMT-07 boundary.
7. the grouping month is derived server-side from closingDate, truncated to the first of the month: LG-STMT-07.
8. a matching contentHash throws DuplicateStatementException and creates no presigned URL or statement row: LG-STMT-03.
9. an accountId not belonging to the user throws before S3PresignService is reached: Multi-tenant.
10. a different file whose month is already taken throws with matchType SAME_MONTH: LG-STMT-06.
11. a CSV upload with no openingDate is rejected: LG-STMT-07.
12. a CSV upload with no closingDate is rejected: LG-STMT-07.
13. an upload with no contentHash is rejected so no client can opt out of duplicate detection: LG-STMT-03.
14. contentHash must be exactly 64 lowercase hex characters: LG-STMT-03.

--- StatementControllerTest (2) ---
15. a successful initiate-upload answers 202 Accepted with the job object: LG-STMT-03 Shared Contract.
16. the upload is attributed to the X-Internal-User-Id identity, never to the request body: Multi-tenant.

--- InternalStatementControllerTest (3) ---
17. the duplicate check delegates to checkForDuplicateByContentHash and reports the match: LG-STMT-03.
18. an accountId not belonging to the calling identity is rejected so another tenant's statements cannot be probed: Multi-tenant.
19. contentHash and contentFingerprint are mutually exclusive, so both or neither is a 400: LG-STMT-03/04.

--- TransactionServiceTest — bulkCreateFromStatement (8) ---
20. a statementId not belonging to the caller throws StatementNotFoundException and never reaches the repository: LG-STMT-02 multi-tenant.
21. an empty transaction list inserts nothing and reports insertedCount 0 without calling the repository: LG-STMT-02 boundary.
22. a malformed row in an otherwise valid batch is excluded and reported without aborting the batch: LG-STMT-02 partial failure.
23. skippedDuplicateCount reflects rows the repository reports as already present on a retried batch: LG-STMT-02 idempotency.
24. transactions are created against the statement's own accountId, with source, status and rowFingerprint set on every row: LG-STMT-02 multi-tenant.
25. a type outside PURCHASE/CREDIT is reported as a failedRow and not inserted: LG-STMT-02 row validation.
26. failedRows carry the row's index in the original request, not after filtering: LG-STMT-02 row validation.
27. a batch in which every row is malformed inserts nothing and never calls the repository: LG-STMT-02 boundary.

--- InternalTransactionControllerTest (2) ---
28. the bulk-create route is reachable and delegates correctly: LG-STMT-02.
29. identity comes from the header, never the body: LG-STMT-02 multi-tenant.

--- BulkCreateAmountValidationTest (4) ---
30. both a negative PURCHASE and a positive CREDIT amount are accepted: LG-STMT-02 amount validation.
31. an amount of exactly zero is rejected so the table's non-zero check cannot abort the batch: LG-STMT-02 amount validation.
32. a DECIMAL(15,2) overflow is rejected in both directions while the exact ceiling 9999999999999.99 is accepted: LG-STMT-02 amount validation.
33. sub-cent precision is rejected while trailing zeros and whole numbers are accepted: LG-STMT-02 amount validation.

--- JooqStatementRepositoryIT (8) ---
34. a statement is invisible to another user and visible to its owner at the database layer: LG-STMT-02 RLS.
35. findByAccountIdAndContentHash finds a real match scoped to the account: LG-STMT-03.
36. the same contentHash on a different account is not a match: LG-STMT-03.
37. findByAccountIdAndStatementMonth finds the account's existing statement: LG-STMT-06.
38. insert round-trips openingDate and closingDate while the database derives statement_month, without INSERT ... RETURNING losing the row under forced RLS: LG-STMT-07.
39. the unique index on (account_id, statement_month) still rejects a second statement for the same month after statement_month became generated: LG-STMT-06/07.
40. another account's statement for the same month is not reported: LG-STMT-06 multi-tenant.
41. duplicate lookups made with another tenant's accountId return nothing: Multi-tenant.

--- StatementUploadDuplicateIT (3) ---
42. re-uploading the exact same file is recognized as EXACT_FILE end to end: LG-STMT-03.
43. a different file whose closingDate falls in an already-taken month is rejected as SAME_MONTH: LG-STMT-06/07.
44. the identical file uploaded by a different user to their own account is not a duplicate: LG-STMT-03 multi-tenant.

--- JooqTransactionRepositoryIT (7) ---
45. bulkInsertIgnoringDuplicates is idempotent, leaving exactly 2 rows after two identical calls: LG-STMT-02.
46. a row that already exists from an earlier call is skipped and left unmodified: LG-STMT-02 DO NOTHING semantics.
47. the bulk insert cannot write into another tenant's account: LG-STMT-02 multi-tenant.
48. rows written by the bulk insert are correctly attributed: LG-STMT-02 multi-tenant.
49. an identical rowFingerprint under two different statements inserts both: LG-STMT-02 multi-tenant.
50. rows with no rowFingerprint are exempt from the uniqueness check: LG-STMT-02.
51. the same rowFingerprint twice within one batch inserts once: LG-STMT-02.

--- InternalEndpointSecurityIT (6) ---
52. the internal bulk-create endpoint fails closed with 401 when no verified caller principal is present: LG-STMT-02.
53. a verified caller ARN that is not on the allow-list is rejected: LG-STMT-02.
54. an allow-listed caller ARN is admitted and reaches the controller: LG-STMT-02.
55. the internal duplicate-check endpoint fails closed the same way: LG-STMT-03.
56. a call carrying neither a caller ARN nor a user identity is rejected: LG-STMT-02.
57. user-facing routes are unaffected by the internal filter: LG-STMT-02.

--- StatementFingerprintTest — LG-STMT-04 (5) ---
58. recordContentFingerprint stores the fingerprint and passes the caller's identity to the repository: LG-STMT-04.
59. a statement belonging to another tenant is reported as not found, like a nonexistent one: LG-STMT-04 multi-tenant.
60. a fingerprint match is always CONTENT_FINGERPRINT and carries the existing statement's id, upload date and transaction count: LG-STMT-04/05.
61. no fingerprint match returns empty so a first upload is not flagged against itself: LG-STMT-04.
62. the same-month rule is not consulted during the fingerprint check: LG-STMT-04.

--- StatementOverwriteTest — LG-STMT-05 (5) ---
63. the replaced statement is deleted before the duplicate check runs: LG-STMT-05 ordering.
64. overwriting another user's statement is not found and nothing is deleted: LG-STMT-05 multi-tenant.
65. overwriting a statement in a different account of the same user is a bad request and nothing is deleted: LG-STMT-05 multi-tenant.
66. without overwriteStatementId a duplicate is still a rejection: LG-STMT-05 opt-in.
67. a foreign accountId is rejected before the overwrite is considered: LG-STMT-05 multi-tenant.

--- InternalStatementFingerprintControllerTest — LG-STMT-04 / LG-STMT-08 (6) ---
68. a contentFingerprint query is answered by the fingerprint check, never the content-hash check: LG-STMT-08.
69. a fingerprint with no match answers duplicateFound false, not an error: LG-STMT-04.
70. a fingerprint query for an account the caller does not own is rejected before any lookup: LG-STMT-04 multi-tenant.
71. recording a fingerprint onto another tenant's statement surfaces as not found: LG-STMT-04 multi-tenant.
72. recording answers 204 and passes the caller's identity through: LG-STMT-04.
73. a fingerprint that is not 64 hex characters is rejected before storage: LG-STMT-04.

--- StatementFingerprintIT — LG-STMT-04 (5) ---
74. a fingerprint recorded on one statement is found by a later lookup: LG-STMT-04 write-then-read.
75. the stored fingerprint reads back on the statement record itself, untruncated by the CHAR(64) type: LG-STMT-04.
76. a statement with no fingerprint yet matches nothing, so concurrent uploads are not duplicates of each other: LG-STMT-04.
77. the same fingerprint in another tenant's account is not a duplicate: LG-STMT-04 multi-tenant.
78. recording onto another tenant's statement neither succeeds nor modifies their row: LG-STMT-04 multi-tenant.

--- StatementOverwriteIT — LG-STMT-05 (3) ---
79. overwriting removes the old statement's transactions so the replacement is a clean swap: LG-STMT-05 cascade.
80. after an overwrite the account holds exactly one statement for that month: LG-STMT-05.
81. overwriting another tenant's statement deletes nothing of theirs, neither statement nor transactions: LG-STMT-05 multi-tenant.

--- InternalFingerprintEndpointSecurityIT — LG-STMT-04 (3) ---
82. the fingerprint route fails closed with 401 when no verified caller principal is present: LG-STMT-04 multi-tenant.
83. a verified caller ARN not on the allow-list is rejected with 401: LG-STMT-04 multi-tenant.
84. an allow-listed caller reaches the controller, answering 404 for a random statement id: LG-STMT-04.

--- statement.service.spec.ts (6) ---
85. contentHash, openingDate and closingDate are on every request and statementMonth is gone: LG-STMT-03/07.
86. overwriteStatementId is sent when the user chose to replace: LG-STMT-05.
87. computeContentHash matches the known SHA-256 of empty input: LG-STMT-03.
88. polling stops on PENDING_DUPLICATE_RESOLUTION and hands the payload on: LG-STMT-04.
89. polling still stops on PENDING_MAPPING_CONFIRMATION: LG-STMT-04.
90. a FAILED status carries the reason code and duplicate through to the caller: LG-STMT-08.

--- upload-statement-modal.spec.ts (12) ---
91. CSV now requires the date range too: LG-STMT-07.
92. a closing date before the opening date blocks submission before anything uploads: LG-STMT-07.
93. a single-day statement is allowed, matching the server rule: LG-STMT-07.
94. the date range survives a document-type change: LG-STMT-07.
95. the file is hashed and the hash reaches the request: LG-STMT-03.
96. a 409 opens the duplicate prompt instead of the error panel: LG-STMT-05.
97. Overwrite re-submits with overwriteStatementId and the first attempt carries none: LG-STMT-05.
98. Cancel attempts no second upload: LG-STMT-05.
99. dismissing the dialog is treated as Cancel, not Overwrite: LG-STMT-05.
100. a non-duplicate failure still reaches the error panel: LG-STMT-05.
101. a mid-processing duplicate prompts with midProcessing true and discards the abandoned tracking record: LG-STMT-04.
102. a SERVER_DUPLICATE_DETECTED failure names the existing statement: LG-STMT-08.

--- TestLedgerDuplicateCheckClient (7) ---
103. a content hash check is a signed get for the owner's account: LG-STMT-08.
104. a fingerprint check sends only the fingerprint: LG-STMT-04.
105. exactly one of hash or fingerprint is required: LG-STMT-03/04.
106. an unreachable Ledger is retried, then fails closed: LG-STMT-08 MUST.
107. an unset Ledger URL fails closed rather than skipping the check: LG-STMT-08 MUST.
108. recording a fingerprint is a signed patch with the value in the body: LG-STMT-04.
109. recording a fingerprint the Ledger cannot take raises: LG-STMT-04.

--- TestServerSideHashRecheck (14) ---
110. the recomputed hash is what is sent for the check: LG-STMT-08.
111. the statement's own record matching its own hash is not a duplicate: LG-STMT-08.
112. another statement with the same hash ends the import as SERVER_DUPLICATE_DETECTED: LG-STMT-08.
113. a wrong client hash that is not a duplicate is corrected with `PATCH …/content-hash`, then the import continues and the mismatch is logged: LG-STMT-08.
114. an unreachable Ledger never lets the upload through: LG-STMT-08 MUST.
115. the recheck also covers PDFs and runs before any format work: LG-STMT-08.
116. an oversized file is rejected before it is hashed or sent anywhere: DP-ING-04.
117. the handler stores the named reason and the duplicate on the failed job: LG-STMT-08.
118. a 409 from the correction ends the import as SERVER_DUPLICATE_DETECTED: LG-STMT-08.
119. a correction that fails 3 times ends the import as PIPELINE_ERROR: LG-STMT-08.
120. Ledger: the route stores the hash for the caller's statement and answers 204, also when repeated: LG-STMT-08.
121. Ledger: another user's statement answers 404 and nothing changes: LG-STMT-08 / invariant 5.
122. Ledger: a hash held by another statement of the account answers 409: LG-STMT-08.
123. Ledger: the route rejects a caller that is not allow-listed: LG-STMT-08 / LG-STMT-02.

--- TestContentFingerprint (7) ---
124. it is the hash of count, total and the date range: LG-STMT-04.
125. row order does not matter: LG-STMT-04.
126. a different count, total or date range gives a different fingerprint: LG-STMT-04.
127. two months with the same first and last row do not collide: LG-STMT-04 Problem.
128. US and ISO dates give the same fingerprint: LG-STMT-04.
129. a decimal amount is summed exactly: LG-STMT-04.
130. a statement with no readable date has no fingerprint: LG-STMT-04.

--- TestDuplicateCheckStage (6) ---
131. no match records the fingerprint and lets the import continue: LG-STMT-04.
132. the check runs before the fingerprint is recorded, so a statement never matches itself: LG-STMT-04.
133. a match returns the duplicate and does not record the fingerprint: LG-STMT-04 / 05.
134. a PDF or image is not checked at all: LG-STMT-04 Constraint.
135. a statement with no readable date skips the check and is logged: LG-STMT-04.
136. an unreachable Ledger fails the job with a pipeline error and does not continue: LG-STMT-04.

--- TestDuplicatePause (2) ---
137. the job waits on the user with the duplicate and the task token: LG-STMT-04 / 05.
138. the state machine pauses on a duplicate and otherwise pushes: LG-STMT-04 / 05.

--- TestLedgerDuplicateCheckClient — hash correction (3) ---
139. correcting a hash is a signed patch with the hash in the body: LG-STMT-08.
140. a hash another statement holds is a server duplicate with that statement's details: LG-STMT-08.
141. a correction the Ledger cannot take is retried three times, then raises: LG-STMT-08.

--- TestServerSideHashRecheck — no rewrite (1) ---
142. a client hash that matches the file is not rewritten: LG-STMT-08.

--- InternalContentHashCorrectionIT (2) ---
143. the same hash in another account is not a conflict: LG-STMT-08.
144. a hash that is not 64 lowercase hex characters answers 400: LG-STMT-08.

=========================
P2P TESTS (4)
=========================

--- JooqTransactionRepositoryIT (4) ---
1. transactions are isolated by RLS between users: LG-CORE regression carried through the Transaction record change.
2. the transactions table rejects a zero amount: LG-CORE regression.
3. split-exclusion behaviour is unchanged, case one: LG-CORE regression.
4. split-exclusion behaviour is unchanged, case two: LG-CORE regression.
