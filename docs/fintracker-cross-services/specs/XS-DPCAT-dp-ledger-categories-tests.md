> **Tests for:** [XS-DPCAT-dp-ledger-categories-spec.md](XS-DPCAT-dp-ledger-categories-spec.md) · **Formerly:** `docs/fintracker-cross-services/dp-ledger-categories-tests.md` (renamed 2026-10; merged with `-tests-02`)

=========================
F2P TESTS (171)
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

--- InternalCategoryControllerIT (4) ---
20. GET /system returns every SYSTEM category with its code, display name and active flag: XS-DPCAT-02 system read API.
21. GET /system answers 304 when If-None-Match carries the current ETag: XS-DPCAT-02 ETag.
22. the retired per-user categories route answers 404: XS-DPCAT-02 user read API retired.
23. internal category endpoints reject a caller that is not allow-listed with 401: XS-DPCAT-02 internal-only.

--- InternalCallerFilterTest (1) ---
24. the internal caller filter guards the internal category routes: XS-DPCAT-02 internal-only.

--- RlsResetConnectionIT (1) ---
25. a query without a user context on a connection whose user was reset sees no user rows, on every RLS table: LG-CORE-1.1.

--- TransactionCategoryColumnsIT (3) ---
26. save() round-trips categoryId, sourceCategory and merchantKey: XS-DPCAT-04 source_category.
27. a bulk-inserted PDF row stores a null sourceCategory next to its categoryId and merchantKey: XS-DPCAT-04 source_category.
28. merchant rule lookups are backed by an index on (user_id, merchant_key): DP-CAT-01 #1.

--- StatementIngestCategoryIT (14) ---
29. a SYSTEM code is stored as PENDING with its id, display name, bank label, merchant key and source SUGGESTED: XS-DPCAT-04 #1 / 05 #3.
30. a user rule "Target -> Gifts" beats the bank label Shopping and the suggested code shopping, recorded as USER_RULE: XS-DPCAT-07 step 1.
31. another user's rule never applies: XS-DPCAT-07 step 1 / invariant 5.
32. a rule that points to a deactivated category is skipped and the suggested code decides: XS-DPCAT-07 step 1.
33. a user's own "Food & Drink" category beats the SYSTEM one for a bank row labeled Food & Drink, recorded as USER_CATEGORY: XS-DPCAT-07 step 2.
34. a PDF row with no bank label and no code is stored as uncategorized with no reason: XS-DPCAT-05 #3 / 06 #3.
35. an unknown code is stored as uncategorized with CATEGORY_NOT_FOUND, kept on the row: XS-DPCAT-05 #3 / #4.
36. a code whose SYSTEM category is inactive is stored as uncategorized with CATEGORY_INACTIVE: XS-DPCAT-05 #3 / #4.
37. a code never names a user category, so a user category's name is just an unknown code: XS-DPCAT-05 #3 / invariant 5.
38. rollout: a package that still sends categoryId is checked as before: XS-DPCAT-05 Rollout.
39. LOW_CONFIDENCE_EXTRACTION is stored with the pending row and an unknown reason is stored as null: XS-IMP-01.
40. a retried package reports every row ALREADY_STORED and stores nothing twice: XS-DPCAT-05 #2.
41. a malformed row is reported REJECTED while the rest of the package is stored: XS-DPCAT-05 #6.
42. a package without a packageId is rejected with 400: XS-DPCAT-05 #1.

--- LabelNormalizerTest (4) ---
43. the Appendix A cases normalize as specified: XS-DPCAT-07 / Appendix A.
44. an empty result means no label: XS-DPCAT Appendix A.
45. a null label is no label: XS-DPCAT Appendix A.
46. a stored category name and its display name normalize alike: XS-DPCAT-07 step 2.

--- IngestCatalogTest (15) ---
47. the user's merchant rule wins over the bank label and the suggested code: XS-DPCAT-07 step 1.
48. a rule that points at a deactivated category is skipped and the next step decides: XS-DPCAT-07 step 1.
49. a rule may point at a SYSTEM category: XS-DPCAT-07 step 1.
50. a row with no merchant key can match no rule: XS-DPCAT-07 step 1.
51. a bank label equal to the user's own category name files the row under it, not the SYSTEM one: XS-DPCAT-07 step 2.
52. an inactive user category of that name does not match: XS-DPCAT-07 step 2.
53. a blank bank label matches nothing: XS-DPCAT-07 step 2.
54. a suggested active SYSTEM code files the row under that category: XS-DPCAT-07 step 3.
55. a code no SYSTEM category has is downgraded as CATEGORY_NOT_FOUND: XS-DPCAT-05 #3.
56. a code whose SYSTEM category is inactive is downgraded as CATEGORY_INACTIVE: XS-DPCAT-05 #3.
57. a code only names SYSTEM categories: XS-DPCAT-05 #3.
58. no suggestion is plain uncategorized with no reason: XS-DPCAT-05 #3.
59. rollout: a category id from a pipeline that doesn't send codes yet is checked as before: XS-DPCAT-05 Rollout.
60. rollout: when a row carries both, the code is used: XS-DPCAT-05 Rollout.
61. the catalog refuses to build without the uncategorized SYSTEM category: XS-DPCAT-01.

--- TransactionServiceImportTest (category choice) (5) ---
62. a suggested code is stored as the category with source SUGGESTED: XS-DPCAT-07.
63. the user's merchant rule beats the suggestion and is recorded as USER_RULE: XS-DPCAT-07 step 1.
64. a code the Ledger can't use is stored as uncategorized and the result says why: XS-DPCAT-05 #3 / #5.
65. a row with no suggestion is plain uncategorized with no reason: XS-DPCAT-05 #3.
66. the user's rules and categories are read once per package, not once per row: XS-DPCAT-07.

--- TransactionServiceImportTest (approval re-check) (4) ---
67. a category that is still valid is posted: XS-DPCAT-04 #4.
68. a category deactivated while the row was pending keeps it PENDING, flagged CATEGORY_UNAVAILABLE, and the approval is refused: XS-DPCAT-04 #4.
69. a bulk approval posts the valid rows, leaves the unavailable ones pending and reports them: XS-DPCAT-04 #4.
70. a row with no category id (an old row) is not re-checked: XS-DPCAT-04 #4.

--- ApprovalCategoryRecheckIT (6) ---
71. a row whose category is still valid is posted: XS-DPCAT-04 #4.
72. a row whose category was deactivated while pending stays PENDING, flagged CATEGORY_UNAVAILABLE, with a 409: XS-DPCAT-04 #4.
73. the flag is on the transaction the Pending tab reads: XS-DPCAT-04 #4.
74. a bulk approval posts the valid rows, leaves the unavailable one pending and lists it: XS-DPCAT-04 #4.
75. a bulk approval where every row is valid is still 204: XS-DPCAT-04 #4.
76. choosing another category clears the flag, and the row can then be approved: XS-DPCAT-04 #4.

--- TransactionRecategorizeIT (8) ---
77. PATCH with the user's own categoryId stores that id and its display name: XS-DPCAT-04 #3.
78. PATCH with a custom category's name stores that category, not Uncategorized: XS-DPCAT-04 #3 (bug fix).
79. PATCH with a SYSTEM categoryId stores it with its display name: XS-DPCAT-04 #3.
80. PATCH with another user's categoryId is 404 and changes nothing: XS-DPCAT-04 #3 / invariant 5.
81. PATCH with a deactivated category is 400 and changes nothing: XS-DPCAT-04 #3.
82. PATCH with an unknown category name is 400 instead of silently saving Uncategorized: XS-DPCAT-04 #3 (bug fix).
83. the category picker lists the user's active custom categories next to SYSTEM ones: XS-DPCAT-04 #3.
84. split children are filed under the named category's id: XS-DPCAT-04 #3.

--- TransactionServiceTest (4) ---
85. updating the category by name stores the resolved category's id and display name: XS-DPCAT-04 #3.
86. recategorizing by id stores the category's id and display name: XS-DPCAT-04 #3.
87. a manual transaction is filed under the named category's id and display name: XS-DPCAT-04.
88. a manual transaction with an unknown category name is rejected and nothing is saved: XS-DPCAT-04.

--- ManualTransactionCategoryIT (2) ---
89. a manual transaction in a custom category stores that category's id and display name: XS-DPCAT-04.
90. a manual transaction with an unknown category is 400: XS-DPCAT-04.

--- MerchantRuleIT (9) ---
91. remember=true saves the rule and files the user's other pending uncategorized rows from that merchant: DP-CAT-01 #2.
92. without remember the change is a one-off with no rule and no other row changes: DP-CAT-01 #2.
93. remembering a merchant again replaces its rule, keeping one rule per merchant: DP-CAT-01 #1.
94. a rule never touches another user's transactions and RLS hides it from them: DP-CAT-01 #1 / #4.
95. remember on a transaction without a merchant key recategorizes it and saves no rule: DP-CAT-01 #2.
96. bulk CATEGORIZE files every selected row and remembers the merchant when asked: DP-CAT-01 #2.
97. bulk CATEGORIZE without a categoryId is 400: DP-CAT-01 #2.
98. the internal user categories endpoint returns the user's merchant rules: XS-DPCAT-02 / DP-CAT-01 #1. *(Removed with the route when XS-DPCAT-02 retires it.)*
99. the merchant rules table forces row-level security: DP-CAT-01 #1.

--- TestSeed (6) ---
100. the JSON seed equals the SQL seed: XS-DPCAT-06 #1.
101. the pipeline's SQL seed matches the documented seed: XS-DPCAT-06 #1.
102. the seed parser unescapes quotes and ignores trailing comments: XS-DPCAT-06 #1.
103. every seed code is a Ledger SYSTEM code: XS-DPCAT-06 #1.
104. the test's code list mirrors the Ledger's SYSTEM seed: XS-DPCAT-01.
105. every regex pattern compiles: XS-DPCAT-06 #1.

--- TestMatching (6) ---
106. merchant text is uppercased with whitespace collapsed and punctuation kept: XS-DPCAT-06 #1.
107. contains, regex and exact patterns each match as named: XS-DPCAT-06 #1.
108. the lowest priority number wins when several patterns match: XS-DPCAT-06 #1.
109. inactive patterns are skipped: XS-DPCAT-06 #1.
110. patterns whose code is not an active SYSTEM code are skipped: XS-DPCAT-03 #3.
111. an ambiguous bare Target stays unmatched while TARGET.COM is shopping: XS-DPCAT-06 #2 / #3.

--- TestRepository (2) ---
112. patterns load with one DynamoDB query and are cached: XS-DPCAT-06 #1.
113. the pattern cache expires after five minutes: XS-DPCAT-06 #1.

--- TestNormalization (2) ---
114. the Appendix A label cases (Café, --Travel--, blank, Gas/Automotive) normalize as the Ledger does: XS-DPCAT-03 step 1 / Appendix A.
115. the merchant key drops order ids, store numbers and POS prefixes: DP-CAT-01 #1.

--- TestSuggestionOrder (8) ---
116. a bank label in the table suggests its code: XS-DPCAT-03 step 2.
117. a label equal to a code's own label suggests that code: XS-DPCAT-03 step 2.
118. the bank label wins over the merchant map: XS-DPCAT-03 steps 2-3.
119. an unknown bank label falls through to the merchant map: XS-DPCAT-03 step 3 / 06.
120. a PDF row without a label uses the merchant map: XS-DPCAT-03 / 06.
121. a blank label is no label: XS-DPCAT-03 Appendix A.
122. no match suggests no code instead of uncategorized: XS-DPCAT-03 step 4 / 06 #3.
123. the user's own categories and rules are not known to the pipeline: XS-DPCAT-02 DP #1 / 07.

--- TestNoCategoryCopyInThePipeline (3) ---
124. the hard-coded regex list is gone: XS-DPCAT-06 #1.
125. there is no resolver over a cached copy of the Ledger's categories any more: XS-DPCAT-02 DP #1.
126. the Normalizer no longer imports the categories client or refresh: XS-DPCAT-02 DP #1.

--- TestBankLabelTable (4) ---
127. every table value is a Ledger SYSTEM code: XS-DPCAT-03.
128. keys are already normalized: XS-DPCAT-03 step 1.
129. every active SYSTEM code has an entry for its own label: XS-DPCAT-03.
130. uncategorized has no entry, since no suggestion is how the pipeline says it: XS-DPCAT-01.

--- TestDeployCheck (5) ---
131. matching tables pass clean: XS-DPCAT-02 DP #3.
132. a label code missing from the Ledger fails the deploy: XS-DPCAT-02 DP #3.
133. a merchant code inactive in the Ledger fails the deploy: XS-DPCAT-02 DP #3.
134. an active SYSTEM code with no label entry only warns: XS-DPCAT-02 DP #3.
135. an inactive SYSTEM code needs no label entry: XS-DPCAT-02 DP #3.

--- test_normalizer_handler (3) ---
136. rows get a suggested code and the merchant key with no Ledger call: XS-DPCAT-02 DP #1 / #2.
137. the statement format is carried on to the duplicate check: LG-STMT-04.
138. a failure gives a reason code on the job, not the exception text: DP-ING-10.

--- TestToLedgerLine (3) ---
139. a PDF row sends a null bank label: XS-DPCAT-04 #1.
140. a row with no suggested code sends none and never a category id: XS-DPCAT-03 step 4.
141. a low-confidence row sends its review reason and no score: XS-IMP-01.

--- TestCategoryCodeSuggestion (3) ---
142. a bank label gives its code and is kept unchanged as the source category: XS-DPCAT-03 / 04.
143. a row nothing matches carries no code instead of uncategorized: XS-DPCAT-03 step 4.
144. the row has no category id field: XS-DPCAT-03 step 5.

--- TestPackageV2 (2) ---
145. the package id is the job id and rows carry no text category: XS-DPCAT-04 #1.
146. rows the Ledger stored as uncategorized are logged by reason and still succeed: XS-DPCAT-05 DP.

--- TestJobStatus (4) ---
147. the owner sees their job: DP-ING-06.
148. another user's job is not found: DP-ING-06 / invariant 5.
149. a client-supplied user header is ignored: DP-ING-06 / invariant 2.
150. no authorizer identity is 401: DP-ING-06.

--- TestCsvColMappingConfirmation (4) ---
151. the owner can confirm their mapping: DP-ING-06.
152. another user's job is not found and is not resumed: DP-ING-06 / invariant 5.
153. no authorizer identity is 401: DP-ING-06.
154. a malformed body is 400 without exception text: DP-ING-06 / CLAUDE.md exception handling.

--- TestGatewayAuthorizer (1) ---
155. routes use the User Profile REQUEST authorizer, not the Cognito sub: DP-ING-06 / D3.

--- TransactionService (2) ---
156. maps categoryId, sourceCategory and merchantKey onto each row: XS-DPCAT-04 #2.
157. PATCHes a categoryId with the remember choice: XS-DPCAT-04 #3 / DP-CAT-01 #2.

--- TransactionDetailPanel (5) ---
158. shows the bank's label: XS-DPCAT-04 #2.
159. hides the bank label when the row has none: XS-DPCAT-04 #2.
160. remembers the merchant by default and emits the choice with the category: DP-CAT-01 #2.
161. unchecked, the change is a one-off: DP-CAT-01 #2.
162. offers "Always use this" only for rows with a merchant key: DP-CAT-01 #2.

--- Transactions (3) ---
163. recategorizes from the panel by category id with the remember choice: XS-DPCAT-04 #3.
164. categorizes every selected row, remembering their merchants by default: DP-CAT-01 #2.
165. highlights pending rows that are still uncategorized: XS-DPCAT-04 #2.

--- DeleteCategoryDialog (3) ---
166. an in-use category can be deleted without choosing a new category: XS-DPCAT-02.
167. moving the transactions to another category is still offered: XS-DPCAT-02.
168. explains that transactions keep the category instead of warning it cannot be undone: XS-DPCAT-02.

--- Transactions — category hints (3) ---
169. "This category is no longer available" shows on a pending row whose category is gone: XS-DPCAT-04 #3.
170. "From your rule" shows on a pending row a merchant rule categorized: XS-DPCAT-07.
171. an unavailable category is shown ahead of "From your rule": XS-DPCAT-04 #3.
