=========================
F2P TESTS (15)
=========================

--- TestReqDp09NoPaidClassifier (3) ---
1. the categorizer module has no Comprehend client: REQ-DP-09 A. "No Paid Classifier".
2. the categorizer no longer looks up or writes a shared merchant cache: REQ-DP-09 A. "No Shared Learning".
3. an unknown merchant with no bank category is Uncategorized with source NONE: REQ-DP-09 A. "Uncategorized Last".

--- TestReqDp09BankCategory (5) ---
4. a bank label is translated to a FinTracker category with source BANK: REQ-DP-09 A. "Bank Category First".
5. the bank category wins over a regex match: REQ-DP-09 A. "Bank Category First".
6. bank label matching ignores case and surrounding whitespace: REQ-DP-09 B. "never make an import fail".
7. an unknown bank label falls back to the regex list: REQ-DP-09 A. "Known-Merchant List Second".
8. a blank bank label falls back to Uncategorized: REQ-DP-09 F. Error Handling.

--- TestReqDp09LedgerLabels (2) ---
9. every regex category is a Ledger category label: REQ-DP-09 B. "names the Ledger already recognizes".
10. every bank translation is a Ledger category label: REQ-DP-09 B. "names the Ledger already recognizes".

--- TestReqDp09CsvCategoryColumn (2) ---
11. a CSV category column is carried on each parsed row: REQ-DP-09 D. `parse_csv_transactions`.
12. a CSV without a category column yields no bank category: REQ-DP-09 F. Error Handling.

--- TestReqDp09NormalizerUsesBankCategory (1) ---
13. a row's bank category drives its normalized category: REQ-DP-09 D. `normalize_and_categorize`.

--- TestReqDp09ChaseBaselineMapping (1) ---
14. Chase's baseline maps its Category column, not Type, to category: REQ-DP-09 C. Data Impacts.

--- TestRegexCategorize (1) ---
15. uber eats resolves to Dining/Delivery ahead of uber: REQ-DP-09 B. "names the Ledger already recognizes".

=========================
P2P TESTS (1)
=========================

--- TestNormalizeAndCategorize (1) ---
1. a regex-matched merchant is categorized without any AWS call: REQ-DP-09 A. "Known-Merchant List Second".
