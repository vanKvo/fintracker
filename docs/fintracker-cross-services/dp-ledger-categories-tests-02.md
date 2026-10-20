=========================
F2P TESTS (104)
=========================

--- RlsResetConnectionIT (1) ---
1. a query without a user context on a connection whose user was reset sees no user rows, on every RLS table: REQ-1.1.

--- TransactionCategoryColumnsIT (3) ---
2. save() round-trips categoryId, sourceCategory and merchantKey: DP-LEDGER-CATEGORIES-04 source_category.
3. a bulk-inserted PDF row stores a null sourceCategory next to its categoryId and merchantKey: DP-LEDGER-CATEGORIES-04 source_category.
4. merchant rule lookups are backed by an index on (user_id, merchant_key): REQ-DP-09 #1.

--- StatementIngestCategoryIT (9) ---
5. a SYSTEM category is stored as PENDING with its id, display name, bank label and merchant key: DP-LEDGER-CATEGORIES-04 #1.
6. the user's own active category is accepted and a PDF row keeps a null bank label: DP-LEDGER-CATEGORIES-05 #5.
7. an unknown category is stored as uncategorized with CATEGORY_NOT_FOUND: DP-LEDGER-CATEGORIES-04 #5 / 05 #3.
8. an inactive category is stored as uncategorized with CATEGORY_INACTIVE: DP-LEDGER-CATEGORIES-04 #5 / 05 #4.
9. another user's category is reported as CATEGORY_NOT_FOUND, revealing nothing about it: DP-LEDGER-CATEGORIES-05 #5 / invariant 5.
10. a row without a categoryId is stored as uncategorized with CATEGORY_MISSING: DP-LEDGER-CATEGORIES-04 #5.
11. a retried package reports every row ALREADY_STORED and stores nothing twice: DP-LEDGER-CATEGORIES-05 #2.
12. a malformed row is reported REJECTED while the rest of the package is stored: DP-LEDGER-CATEGORIES-05 #6.
13. a package without a packageId is rejected with 400: DP-LEDGER-CATEGORIES-05 #1.

--- TransactionRecategorizeIT (8) ---
14. PATCH with the user's own categoryId stores that id and its display name: DP-LEDGER-CATEGORIES-04 #3.
15. PATCH with a custom category's name stores that category, not Uncategorized: DP-LEDGER-CATEGORIES-04 #3 (bug fix).
16. PATCH with a SYSTEM categoryId stores it with its display name: DP-LEDGER-CATEGORIES-04 #3.
17. PATCH with another user's categoryId is 404 and changes nothing: DP-LEDGER-CATEGORIES-04 #3 / invariant 5.
18. PATCH with a deactivated category is 400 and changes nothing: DP-LEDGER-CATEGORIES-04 #3.
19. PATCH with an unknown category name is 400 instead of silently saving Uncategorized: DP-LEDGER-CATEGORIES-04 #3 (bug fix).
20. the category picker lists the user's active custom categories next to SYSTEM ones: DP-LEDGER-CATEGORIES-04 #3.
21. split children are filed under the named category's id: DP-LEDGER-CATEGORIES-04 #3.

--- TransactionServiceTest (4) ---
22. updating the category by name stores the resolved category's id and display name: DP-LEDGER-CATEGORIES-04 #3.
23. recategorizing by id stores the category's id and display name: DP-LEDGER-CATEGORIES-04 #3.
24. a manual transaction is filed under the named category's id and display name: DP-LEDGER-CATEGORIES-04.
25. a manual transaction with an unknown category name is rejected and nothing is saved: DP-LEDGER-CATEGORIES-04.

--- ManualTransactionCategoryIT (2) ---
26. a manual transaction in a custom category stores that category's id and display name: DP-LEDGER-CATEGORIES-04.
27. a manual transaction with an unknown category is 400: DP-LEDGER-CATEGORIES-04.

--- MerchantRuleIT (9) ---
28. remember=true saves the rule and files the user's other pending uncategorized rows from that merchant: REQ-DP-09 #2.
29. without remember the change is a one-off with no rule and no other row changes: REQ-DP-09 #2.
30. remembering a merchant again replaces its rule, keeping one rule per merchant: REQ-DP-09 #1.
31. a rule never touches another user's transactions and RLS hides it from them: REQ-DP-09 #1 / #4.
32. remember on a transaction without a merchant key recategorizes it and saves no rule: REQ-DP-09 #2.
33. bulk CATEGORIZE files every selected row and remembers the merchant when asked: REQ-DP-09 #2.
34. bulk CATEGORIZE without a categoryId is 400: REQ-DP-09 #2.
35. the internal user categories endpoint returns the user's merchant rules: DP-LEDGER-CATEGORIES-02 / REQ-DP-09 #1.
36. the merchant rules table forces row-level security: REQ-DP-09 #1.

--- TestSeed (6) ---
37. the JSON seed equals the SQL seed: DP-LEDGER-CATEGORIES-06 #1.
38. the pipeline's SQL seed matches the documented seed: DP-LEDGER-CATEGORIES-06 #1.
39. the seed parser unescapes quotes and ignores trailing comments: DP-LEDGER-CATEGORIES-06 #1.
40. every seed code is a Ledger SYSTEM code: DP-LEDGER-CATEGORIES-06 #1.
41. the test's code list mirrors the Ledger's SYSTEM seed: DP-LEDGER-CATEGORIES-01.
42. every regex pattern compiles: DP-LEDGER-CATEGORIES-06 #1.

--- TestMatching (6) ---
43. merchant text is uppercased with whitespace collapsed and punctuation kept: DP-LEDGER-CATEGORIES-06 #1.
44. contains, regex and exact patterns each match as named: DP-LEDGER-CATEGORIES-06 #1.
45. the lowest priority number wins when several patterns match: DP-LEDGER-CATEGORIES-06 #1.
46. inactive patterns are skipped: DP-LEDGER-CATEGORIES-06 #1.
47. patterns whose code is not an active SYSTEM code are skipped: DP-LEDGER-CATEGORIES-03 #3.
48. an ambiguous bare Target stays unmatched while TARGET.COM is shopping: DP-LEDGER-CATEGORIES-06 #2 / #3.

--- TestRepository (2) ---
49. patterns load with one DynamoDB query and are cached: DP-LEDGER-CATEGORIES-06 #1.
50. the pattern cache expires after five minutes: DP-LEDGER-CATEGORIES-06 #1.

--- TestSystemCategoryCache (7) ---
51. the first call fetches the SYSTEM categories and keeps the copy: DP-LEDGER-CATEGORIES-02 DP #1.
52. within five minutes the copy is reused without a request: DP-LEDGER-CATEGORIES-02 DP #2.
53. after five minutes a 304 keeps the copy: DP-LEDGER-CATEGORIES-02 DP #2.
54. a 200 replaces the whole copy: DP-LEDGER-CATEGORIES-02 DP #2.
55. a failed refresh keeps the last copy and logs an alertable error: DP-LEDGER-CATEGORIES-02 DP #3.
56. with no copy and a failed fetch uploads are not processed: DP-LEDGER-CATEGORIES-02 DP #3.
57. force_refresh checks the Ledger even within five minutes: DP-LEDGER-CATEGORIES-02 DP #5.

--- TestUserCategories (2) ---
58. the user's categories and merchant rules are fetched as that user: DP-LEDGER-CATEGORIES-02 DP #4.
59. a failed user fetch stops the upload rather than ignoring the user's rules: DP-LEDGER-CATEGORIES-02 DP #4.

--- TestNormalization (2) ---
60. bank labels normalize like category codes: DP-LEDGER-CATEGORIES-03 step 1.
61. the merchant key drops order ids, store numbers and POS prefixes: REQ-DP-09 #1.

--- TestResolutionOrder (10) ---
62. the user's merchant rule wins over the bank label and the merchant map: REQ-DP-09 #1.
63. a rule whose category is inactive is ignored: REQ-DP-09 #1.
64. a rule can point at a SYSTEM category: REQ-DP-09 #1.
65. a bank label matching the user's own category comes before SYSTEM: DP-LEDGER-CATEGORIES-03 step 2.
66. the bank label table maps to a SYSTEM code: DP-LEDGER-CATEGORIES-03 step 3.
67. a bank label equal to a SYSTEM code is used directly: DP-LEDGER-CATEGORIES-03 step 4.
68. an unknown bank label falls through to the merchant map: DP-LEDGER-CATEGORIES-06.
69. a PDF row without a label uses the merchant map: DP-LEDGER-CATEGORIES-06.
70. no match is uncategorized: DP-LEDGER-CATEGORIES-03 step 5 / 06 #3.
71. an inactive SYSTEM category is no match: DP-LEDGER-CATEGORIES-03 step 3.

--- TestRefreshOnMissingCode (3) ---
72. a mapped code missing from the copy forces one refresh: DP-LEDGER-CATEGORIES-02 DP #5.
73. a code still missing after the refresh falls back to uncategorized: DP-LEDGER-CATEGORIES-02 DP #5.
74. no uncategorized category at all stops the upload: DP-LEDGER-CATEGORIES-01.

--- TestNoHardCodedCategories (3) ---
75. the hard-coded regex list is gone: DP-LEDGER-CATEGORIES-06 #1.
76. every bank label maps to a Ledger SYSTEM code: DP-LEDGER-CATEGORIES-03.
77. bank table keys are already normalized: DP-LEDGER-CATEGORIES-03 step 1.

--- test_normalizer_handler (2) ---
78. rows are resolved with the cached categories and the user's own: DP-LEDGER-CATEGORIES-02 DP #4.
79. unavailable categories fail the job with the CATEGORIES_UNAVAILABLE reason code: DP-LEDGER-CATEGORIES-02 DP #3.

--- TestToLedgerLine (1) ---
80. a PDF row sends a null bank label: DP-LEDGER-CATEGORIES-04 #1.

--- TestPackageV2 (2) ---
81. the package id is the job id and rows carry no text category: DP-LEDGER-CATEGORIES-04 #1.
82. rows the Ledger stored as uncategorized are logged by reason and still succeed: DP-LEDGER-CATEGORIES-05 DP.

--- TestJobStatus (4) ---
83. the owner sees their job: REQ-DP-06.
84. another user's job is not found: REQ-DP-06 / invariant 5.
85. a client-supplied user header is ignored: REQ-DP-06 / invariant 2.
86. no authorizer identity is 401: REQ-DP-06.

--- TestCsvColMappingConfirmation (4) ---
87. the owner can confirm their mapping: REQ-DP-06.
88. another user's job is not found and is not resumed: REQ-DP-06 / invariant 5.
89. no authorizer identity is 401: REQ-DP-06.
90. a malformed body is 400 without exception text: REQ-DP-06 / CLAUDE.md exception handling.

--- TestGatewayAuthorizer (1) ---
91. routes use the User Profile REQUEST authorizer, not the Cognito sub: REQ-DP-06 / D3.

--- TransactionService (2) ---
92. maps categoryId, sourceCategory and merchantKey onto each row: DP-LEDGER-CATEGORIES-04 #2.
93. PATCHes a categoryId with the remember choice: DP-LEDGER-CATEGORIES-04 #3 / REQ-DP-09 #2.

--- TransactionDetailPanel (5) ---
94. shows the bank's label: DP-LEDGER-CATEGORIES-04 #2.
95. hides the bank label when the row has none: DP-LEDGER-CATEGORIES-04 #2.
96. remembers the merchant by default and emits the choice with the category: REQ-DP-09 #2.
97. unchecked, the change is a one-off: REQ-DP-09 #2.
98. offers "Always use this" only for rows with a merchant key: REQ-DP-09 #2.

--- Transactions (3) ---
99. recategorizes from the panel by category id with the remember choice: DP-LEDGER-CATEGORIES-04 #3.
100. categorizes every selected row, remembering their merchants by default: REQ-DP-09 #2.
101. highlights pending rows that are still uncategorized: DP-LEDGER-CATEGORIES-04 #2.

--- DeleteCategoryDialog (3) ---
102. an in-use category can be deleted without choosing a new category: DP-LEDGER-CATEGORIES-02.
103. moving the transactions to another category is still offered: DP-LEDGER-CATEGORIES-02.
104. explains that transactions keep the category instead of warning it cannot be undone: DP-LEDGER-CATEGORIES-02.
