> **Tests for:** [DP-CAT-categorization-spec.md](DP-CAT-categorization-spec.md) · **Formerly:** `docs/fintracker-data-pipelines/data-pipeline-tests-02.md` (renamed 2026-10)

=========================
F2P TESTS (14)
=========================

--- TestReqDp09NoPaidClassifier (3) ---
1. the categorizer module has no Comprehend client: DP-CAT-01 A. "No Paid Classifier".
2. the categorizer no longer looks up or writes a shared merchant cache: DP-CAT-01 A. "No Shared Learning".
3. an unknown merchant with no bank category is Uncategorized with source NONE: DP-CAT-01 A. "Uncategorized Last".

--- TestReqDp09BankCategory (5) ---
4. a bank label is translated to a FinTracker category with source BANK: DP-CAT-01 A. "Bank Category First".
5. the bank category wins over a regex match: DP-CAT-01 A. "Bank Category First".
6. bank label matching ignores case and surrounding whitespace: DP-CAT-01 B. "never make an import fail".
7. an unknown bank label falls back to the regex list: DP-CAT-01 A. "Known-Merchant List Second".
8. a blank bank label falls back to Uncategorized: DP-CAT-01 F. Error Handling.

--- TestReqDp09LedgerLabels (2) ---
9. every regex category is a Ledger category label: DP-CAT-01 B. "names the Ledger already recognizes".
10. every bank translation is a Ledger category label: DP-CAT-01 B. "names the Ledger already recognizes".

--- TestReqDp09CsvCategoryColumn (2) ---
11. a CSV category column is carried on each parsed row: DP-CAT-01 D. `parse_csv_transactions`.
12. a CSV without a category column yields no bank category: DP-CAT-01 F. Error Handling.

--- TestReqDp09NormalizerUsesBankCategory (1) ---
13. a row's bank category drives its normalized category: DP-CAT-01 D. `normalize_and_categorize`.

--- TestRegexCategorize (1) ---
14. uber eats resolves to Dining/Delivery ahead of uber: DP-CAT-01 B. "names the Ledger already recognizes".

=========================
P2P TESTS (1)
=========================

--- TestNormalizeAndCategorize (1) ---
1. a regex-matched merchant is categorized without any AWS call: DP-CAT-01 A. "Known-Merchant List Second".
