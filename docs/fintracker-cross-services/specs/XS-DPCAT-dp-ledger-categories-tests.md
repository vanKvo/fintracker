> **Tests for:** [XS-DPCAT-dp-ledger-categories-spec.md](XS-DPCAT-dp-ledger-categories-spec.md) · **Formerly:** `docs/fintracker-cross-services/dp-ledger-categories-tests.md` (renamed 2026-10; merged with `-tests-02`)

=========================
F2P TESTS (169)
=========================

--- CategoryCodeMigrationIT (7) ---
1. every SYSTEM category has a code derived from its name: XS-DPCAT-01 code backfill.
2. a SYSTEM category's code cannot be changed after creation: XS-DPCAT-01 immutable code.
3. a SYSTEM category's name stays editable while its code is unchanged: XS-DPCAT-01 editable name.
4. a USER category cannot carry a code: XS-DPCAT-01 code empty for USER.
5. re-running the SYSTEM category seed creates no duplicates and keeps every UUID: XS-DPCAT-01 seed upsert by code.
6. the repository exposes code and isActive, and food-and-drink displays as "Food & Drink": XS-DPCAT-01 / 02.
7. upgrading an existing database keeps the others/dining UUIDs and renames their transaction text: XS-DPCAT-01 uncategorized fallback.

--- TransactionServiceTest (1) ---
8. recategorizing a transaction persists "Food & Drink": XS-DPCAT-01 renames.

--- JooqStatementRepositoryIT (1) ---
9. the internal owner lookup works on a pooled connection that already served a user request: DP-ING-05.

--- CategoryServiceTest (5) ---
10. re-creating a deactivated category reactivates it, keeping its UUID: XS-DPCAT-02 deactivate instead of delete.
11. deleting an unused custom category deactivates it: XS-DPCAT-02 deactivate instead of delete.
12. deleting an in-use category without a reassignment target deactivates it: XS-DPCAT-02 deactivate instead of delete.
13. deleting with a reassignment target reassigns transactions, then deactivates: XS-DPCAT-02 deactivate instead of delete.
14. the uncategorized SYSTEM category can never be deactivated: XS-DPCAT-01 uncategorized fallback.

--- CategoryControllerIT (2) ---
15. deleting an in-use category leaves the list while its transaction still references it: XS-DPCAT-02 deactivate instead of delete.
16. re-creating a deactivated category's name brings back the same category: XS-DPCAT-02 deactivate instead of delete.

--- JooqCategoryRepositoryIT (3) ---
17. the migration seed includes uncategorized instead of others: XS-DPCAT-01 uncategorized fallback.
18. a deactivated category leaves the list and name/cap checks but stays findable by id: XS-DPCAT-02 deactivate instead of delete.
19. reactivate brings a category back under the same id: XS-DPCAT-02 deactivate instead of delete.

--- InternalCategoryControllerIT (5) ---
20. GET /system returns every SYSTEM category with its code, display name and active flag: XS-DPCAT-02 system read API.
21. GET /system answers 304 when If-None-Match carries the current ETag: XS-DPCAT-02 ETag.
22. GET /users/{userId} returns only that user's categories, including deactivated ones: XS-DPCAT-02 user read API. *(Removed with the route when XS-DPCAT-02 retires it.)*
23. GET /users/{userId} answers 404 when the path user is not the caller's user: XS-DPCAT-02 user read API / invariant 5. *(Removed with the route when XS-DPCAT-02 retires it.)*
24. internal category endpoints reject a caller that is not allow-listed with 401: XS-DPCAT-02 internal-only.

--- InternalCallerFilterTest (1) ---
25. the internal caller filter guards the internal category routes: XS-DPCAT-02 internal-only.

--- RlsResetConnectionIT (1) ---
26. a query without a user context on a connection whose user was reset sees no user rows, on every RLS table: LG-CORE-1.1.

--- TransactionCategoryColumnsIT (3) ---
27. save() round-trips categoryId, sourceCategory and merchantKey: XS-DPCAT-04 source_category.
28. a bulk-inserted PDF row stores a null sourceCategory next to its categoryId and merchantKey: XS-DPCAT-04 source_category.
29. merchant rule lookups are backed by an index on (user_id, merchant_key): DP-CAT-01 #1.

--- StatementIngestCategoryIT (14) ---
30. a SYSTEM code is stored as PENDING with its id, display name, bank label, merchant key and source SUGGESTED: XS-DPCAT-04 #1 / 05 #3.
31. a user rule "Target -> Gifts" beats the bank label Shopping and the suggested code shopping, recorded as USER_RULE: XS-DPCAT-07 step 1.
32. another user's rule never applies: XS-DPCAT-07 step 1 / invariant 5.
33. a rule that points to a deactivated category is skipped and the suggested code decides: XS-DPCAT-07 step 1.
34. a user's own "Food & Drink" category beats the SYSTEM one for a bank row labeled Food & Drink, recorded as USER_CATEGORY: XS-DPCAT-07 step 2.
35. a PDF row with no bank label and no code is stored as uncategorized with no reason: XS-DPCAT-05 #3 / 06 #3.
36. an unknown code is stored as uncategorized with CATEGORY_NOT_FOUND, kept on the row: XS-DPCAT-05 #3 / #4.
37. a code whose SYSTEM category is inactive is stored as uncategorized with CATEGORY_INACTIVE: XS-DPCAT-05 #3 / #4.
38. a code never names a user category, so a user category's name is just an unknown code: XS-DPCAT-05 #3 / invariant 5.
39. rollout: a package that still sends categoryId is checked as before: XS-DPCAT-05 Rollout.
40. LOW_CONFIDENCE_EXTRACTION is stored with the pending row and an unknown reason is stored as null: XS-IMP-01.
41. a retried package reports every row ALREADY_STORED and stores nothing twice: XS-DPCAT-05 #2.
42. a malformed row is reported REJECTED while the rest of the package is stored: XS-DPCAT-05 #6.
43. a package without a packageId is rejected with 400: XS-DPCAT-05 #1.

--- LabelNormalizerTest (4) ---
44. the Appendix A cases normalize as specified: XS-DPCAT-07 / Appendix A.
45. an empty result means no label: XS-DPCAT Appendix A.
46. a null label is no label: XS-DPCAT Appendix A.
47. a stored category name and its display name normalize alike: XS-DPCAT-07 step 2.

--- IngestCatalogTest (15) ---
48. the user's merchant rule wins over the bank label and the suggested code: XS-DPCAT-07 step 1.
49. a rule that points at a deactivated category is skipped and the next step decides: XS-DPCAT-07 step 1.
50. a rule may point at a SYSTEM category: XS-DPCAT-07 step 1.
51. a row with no merchant key can match no rule: XS-DPCAT-07 step 1.
52. a bank label equal to the user's own category name files the row under it, not the SYSTEM one: XS-DPCAT-07 step 2.
53. an inactive user category of that name does not match: XS-DPCAT-07 step 2.
54. a blank bank label matches nothing: XS-DPCAT-07 step 2.
55. a suggested active SYSTEM code files the row under that category: XS-DPCAT-07 step 3.
56. a code no SYSTEM category has is downgraded as CATEGORY_NOT_FOUND: XS-DPCAT-05 #3.
57. a code whose SYSTEM category is inactive is downgraded as CATEGORY_INACTIVE: XS-DPCAT-05 #3.
58. a code only names SYSTEM categories: XS-DPCAT-05 #3.
59. no suggestion is plain uncategorized with no reason: XS-DPCAT-05 #3.
60. rollout: a category id from a pipeline that doesn't send codes yet is checked as before: XS-DPCAT-05 Rollout.
61. rollout: when a row carries both, the code is used: XS-DPCAT-05 Rollout.
62. the catalog refuses to build without the uncategorized SYSTEM category: XS-DPCAT-01.

--- TransactionServiceImportTest (category choice) (5) ---
63. a suggested code is stored as the category with source SUGGESTED: XS-DPCAT-07.
64. the user's merchant rule beats the suggestion and is recorded as USER_RULE: XS-DPCAT-07 step 1.
65. a code the Ledger can't use is stored as uncategorized and the result says why: XS-DPCAT-05 #3 / #5.
66. a row with no suggestion is plain uncategorized with no reason: XS-DPCAT-05 #3.
67. the user's rules and categories are read once per package, not once per row: XS-DPCAT-07.

--- TransactionServiceImportTest (approval re-check) (4) ---
68. a category that is still valid is posted: XS-DPCAT-04 #4.
69. a category deactivated while the row was pending keeps it PENDING, flagged CATEGORY_UNAVAILABLE, and the approval is refused: XS-DPCAT-04 #4.
70. a bulk approval posts the valid rows, leaves the unavailable ones pending and reports them: XS-DPCAT-04 #4.
71. a row with no category id (an old row) is not re-checked: XS-DPCAT-04 #4.

--- ApprovalCategoryRecheckIT (6) ---
72. a row whose category is still valid is posted: XS-DPCAT-04 #4.
73. a row whose category was deactivated while pending stays PENDING, flagged CATEGORY_UNAVAILABLE, with a 409: XS-DPCAT-04 #4.
74. the flag is on the transaction the Pending tab reads: XS-DPCAT-04 #4.
75. a bulk approval posts the valid rows, leaves the unavailable one pending and lists it: XS-DPCAT-04 #4.
76. a bulk approval where every row is valid is still 204: XS-DPCAT-04 #4.
77. choosing another category clears the flag, and the row can then be approved: XS-DPCAT-04 #4.

--- TransactionRecategorizeIT (8) ---
78. PATCH with the user's own categoryId stores that id and its display name: XS-DPCAT-04 #3.
79. PATCH with a custom category's name stores that category, not Uncategorized: XS-DPCAT-04 #3 (bug fix).
80. PATCH with a SYSTEM categoryId stores it with its display name: XS-DPCAT-04 #3.
81. PATCH with another user's categoryId is 404 and changes nothing: XS-DPCAT-04 #3 / invariant 5.
82. PATCH with a deactivated category is 400 and changes nothing: XS-DPCAT-04 #3.
83. PATCH with an unknown category name is 400 instead of silently saving Uncategorized: XS-DPCAT-04 #3 (bug fix).
84. the category picker lists the user's active custom categories next to SYSTEM ones: XS-DPCAT-04 #3.
85. split children are filed under the named category's id: XS-DPCAT-04 #3.

--- TransactionServiceTest (4) ---
86. updating the category by name stores the resolved category's id and display name: XS-DPCAT-04 #3.
87. recategorizing by id stores the category's id and display name: XS-DPCAT-04 #3.
88. a manual transaction is filed under the named category's id and display name: XS-DPCAT-04.
89. a manual transaction with an unknown category name is rejected and nothing is saved: XS-DPCAT-04.

--- ManualTransactionCategoryIT (2) ---
90. a manual transaction in a custom category stores that category's id and display name: XS-DPCAT-04.
91. a manual transaction with an unknown category is 400: XS-DPCAT-04.

--- MerchantRuleIT (9) ---
92. remember=true saves the rule and files the user's other pending uncategorized rows from that merchant: DP-CAT-01 #2.
93. without remember the change is a one-off with no rule and no other row changes: DP-CAT-01 #2.
94. remembering a merchant again replaces its rule, keeping one rule per merchant: DP-CAT-01 #1.
95. a rule never touches another user's transactions and RLS hides it from them: DP-CAT-01 #1 / #4.
96. remember on a transaction without a merchant key recategorizes it and saves no rule: DP-CAT-01 #2.
97. bulk CATEGORIZE files every selected row and remembers the merchant when asked: DP-CAT-01 #2.
98. bulk CATEGORIZE without a categoryId is 400: DP-CAT-01 #2.
99. the internal user categories endpoint returns the user's merchant rules: XS-DPCAT-02 / DP-CAT-01 #1. *(Removed with the route when XS-DPCAT-02 retires it.)*
100. the merchant rules table forces row-level security: DP-CAT-01 #1.

--- TestSeed (6) ---
101. the JSON seed equals the SQL seed: XS-DPCAT-06 #1.
102. the pipeline's SQL seed matches the documented seed: XS-DPCAT-06 #1.
103. the seed parser unescapes quotes and ignores trailing comments: XS-DPCAT-06 #1.
104. every seed code is a Ledger SYSTEM code: XS-DPCAT-06 #1.
105. the test's code list mirrors the Ledger's SYSTEM seed: XS-DPCAT-01.
106. every regex pattern compiles: XS-DPCAT-06 #1.

--- TestMatching (6) ---
107. merchant text is uppercased with whitespace collapsed and punctuation kept: XS-DPCAT-06 #1.
108. contains, regex and exact patterns each match as named: XS-DPCAT-06 #1.
109. the lowest priority number wins when several patterns match: XS-DPCAT-06 #1.
110. inactive patterns are skipped: XS-DPCAT-06 #1.
111. patterns whose code is not an active SYSTEM code are skipped: XS-DPCAT-03 #3.
112. an ambiguous bare Target stays unmatched while TARGET.COM is shopping: XS-DPCAT-06 #2 / #3.

--- TestRepository (2) ---
113. patterns load with one DynamoDB query and are cached: XS-DPCAT-06 #1.
114. the pattern cache expires after five minutes: XS-DPCAT-06 #1.

--- TestNormalization (2) ---
115. the Appendix A label cases (Café, --Travel--, blank, Gas/Automotive) normalize as the Ledger does: XS-DPCAT-03 step 1 / Appendix A.
116. the merchant key drops order ids, store numbers and POS prefixes: DP-CAT-01 #1.

--- TestSuggestionOrder (8) ---
117. a bank label in the table suggests its code: XS-DPCAT-03 step 2.
118. a label equal to a code's own label suggests that code: XS-DPCAT-03 step 2.
119. the bank label wins over the merchant map: XS-DPCAT-03 steps 2-3.
120. an unknown bank label falls through to the merchant map: XS-DPCAT-03 step 3 / 06.
121. a PDF row without a label uses the merchant map: XS-DPCAT-03 / 06.
122. a blank label is no label: XS-DPCAT-03 Appendix A.
123. no match suggests no code instead of uncategorized: XS-DPCAT-03 step 4 / 06 #3.
124. the user's own categories and rules are not known to the pipeline: XS-DPCAT-02 DP #1 / 07.

--- TestNoCategoryCopyInThePipeline (3) ---
125. the hard-coded regex list is gone: XS-DPCAT-06 #1.
126. there is no resolver over a cached copy of the Ledger's categories any more: XS-DPCAT-02 DP #1.
127. the Normalizer no longer imports the categories client or refresh: XS-DPCAT-02 DP #1.

--- TestBankLabelTable (4) ---
128. every table value is a Ledger SYSTEM code: XS-DPCAT-03.
129. keys are already normalized: XS-DPCAT-03 step 1.
130. every active SYSTEM code has an entry for its own label: XS-DPCAT-03.
131. uncategorized has no entry, since no suggestion is how the pipeline says it: XS-DPCAT-01.

--- TestDeployCheck (5) ---
132. matching tables pass clean: XS-DPCAT-02 DP #3.
133. a label code missing from the Ledger fails the deploy: XS-DPCAT-02 DP #3.
134. a merchant code inactive in the Ledger fails the deploy: XS-DPCAT-02 DP #3.
135. an active SYSTEM code with no label entry only warns: XS-DPCAT-02 DP #3.
136. an inactive SYSTEM code needs no label entry: XS-DPCAT-02 DP #3.

--- test_normalizer_handler (3) ---
137. rows get a suggested code and the merchant key with no Ledger call: XS-DPCAT-02 DP #1 / #2.
138. the statement format is carried on to the duplicate check: LG-STMT-04.
139. a failure gives a reason code on the job, not the exception text: DP-ING-10.

--- TestToLedgerLine (3) ---
140. a PDF row sends a null bank label: XS-DPCAT-04 #1.
141. a row with no suggested code sends none and never a category id: XS-DPCAT-03 step 4.
142. a low-confidence row sends its review reason and no score: XS-IMP-01.

--- TestCategoryCodeSuggestion (3) ---
143. a bank label gives its code and is kept unchanged as the source category: XS-DPCAT-03 / 04.
144. a row nothing matches carries no code instead of uncategorized: XS-DPCAT-03 step 4.
145. the row has no category id field: XS-DPCAT-03 step 5.

--- TestPackageV2 (2) ---
146. the package id is the job id and rows carry no text category: XS-DPCAT-04 #1.
147. rows the Ledger stored as uncategorized are logged by reason and still succeed: XS-DPCAT-05 DP.

--- TestJobStatus (4) ---
148. the owner sees their job: DP-ING-06.
149. another user's job is not found: DP-ING-06 / invariant 5.
150. a client-supplied user header is ignored: DP-ING-06 / invariant 2.
151. no authorizer identity is 401: DP-ING-06.

--- TestCsvColMappingConfirmation (4) ---
152. the owner can confirm their mapping: DP-ING-06.
153. another user's job is not found and is not resumed: DP-ING-06 / invariant 5.
154. no authorizer identity is 401: DP-ING-06.
155. a malformed body is 400 without exception text: DP-ING-06 / CLAUDE.md exception handling.

--- TestGatewayAuthorizer (1) ---
156. routes use the User Profile REQUEST authorizer, not the Cognito sub: DP-ING-06 / D3.

--- TransactionService (2) ---
157. maps categoryId, sourceCategory and merchantKey onto each row: XS-DPCAT-04 #2.
158. PATCHes a categoryId with the remember choice: XS-DPCAT-04 #3 / DP-CAT-01 #2.

--- TransactionDetailPanel (5) ---
159. shows the bank's label: XS-DPCAT-04 #2.
160. hides the bank label when the row has none: XS-DPCAT-04 #2.
161. remembers the merchant by default and emits the choice with the category: DP-CAT-01 #2.
162. unchecked, the change is a one-off: DP-CAT-01 #2.
163. offers "Always use this" only for rows with a merchant key: DP-CAT-01 #2.

--- Transactions (3) ---
164. recategorizes from the panel by category id with the remember choice: XS-DPCAT-04 #3.
165. categorizes every selected row, remembering their merchants by default: DP-CAT-01 #2.
166. highlights pending rows that are still uncategorized: XS-DPCAT-04 #2.

--- DeleteCategoryDialog (3) ---
167. an in-use category can be deleted without choosing a new category: XS-DPCAT-02.
168. moving the transactions to another category is still offered: XS-DPCAT-02.
169. explains that transactions keep the category instead of warning it cannot be undone: XS-DPCAT-02.
