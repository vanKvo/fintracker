=========================
F2P TESTS (77)
=========================

--- ledger · CardNumberMaskerTest (7) ---
1. luhn-valid runs with or without separators become **** plus the last four: XS-ACCT-05 Happy, Appendix B vectors.
2. luhn-failing and 12-digit runs are left alone: XS-ACCT-05 Alt, Appendix B vectors.
3. a 10-digit phone number and a failing 13-digit order number are unchanged: XS-ACCT-05 Alt.
4. a run inside a longer digit string is not matched: Appendix B word boundaries.
5. an amount or date after the number does not hide it: XS-ACCT-05 Happy.
6. every run in the text is masked, 13 and 19 digits included: Appendix B 13 to 19 digits.
7. null, empty and plain text come back unchanged: XS-ACCT-05 Fail (masking never fails a write).

--- ledger · LogbackConfigTest (1) ---
8. org.jooq and the Ledger loggers are not below INFO outside a dev/test profile block: XS-ACCT-06 Fail (CI check).

--- ledger · AccountServiceTest (1) ---
9. an accountLastFour that is not exactly four digits is rejected naming the field and never the value: XS-ACCT-02 Fail.

--- ledger · AccountLastFourIT (11) ---
10. create with accountLastFour 1234 returns 201 with 1234 and no accountNumber: XS-ACCT-02 Happy.
11. GET returns the Appendix A fields with accountLastFour and no accountNumber: XS-ACCT-03 Happy.
12. a PATCH without accountLastFour keeps it, null clears it, a value replaces it: XS-ACCT-02 Alt.
13. an account created without accountLastFour has none: XS-ACCT-02 Alt.
14. longer, non-digit or card-length values are 400 invalid_argument naming the field, nothing stored, value not returned or logged: XS-ACCT-02 Fail.
15. an invalid accountLastFour on PATCH is 400 and the stored value stays: XS-ACCT-02 Fail.
16. a body with accountNumber is 400 naming accountNumber, on create and PATCH, nothing stored, value not returned or logged: XS-ACCT-02 Fail.
17. any field the contract does not list is 400 naming that field: XS-ACCT-02 Fail.
18. an unknown field named like a card number is not echoed in the response or the log: XS-ACCT-02 Fail.
19. card-number-like text in an account name or owner is stored masked: XS-ACCT-05 Happy.
20. a PATCHed name is masked and non-card digits stay: XS-ACCT-05 Alt.

--- ledger · AccountLastFourMigrationIT (6) ---
21. two users' accounts end with 6789 and 5432 and account_number is gone: XS-ACCT-04 Happy.
22. fewer than four digits and a null end with a null last four: XS-ACCT-04 Alt.
23. the table's relfilenode changes across the migration: XS-ACCT-04 Happy.
24. the old value is gone from the table file on disk: XS-ACCT-04 Happy.
25. RLS is forced again and a session with no user still sees zero rows: XS-ACCT-04 Alt, ADR-002.
26. a failing step stops the migration and the column is not dropped: XS-ACCT-04 Fail.

--- ledger · AccountNumberContractIT (2) ---
27. no Ledger class has a field or record component named like accountNumber: XS-ACCT-03 Fail.
28. no table, view or column in the ledger schema is named like account_number: XS-ACCT-03 Fail.

--- ledger · CardNumberMaskingIT (6) ---
29. an imported merchant with a card number is stored masked: XS-ACCT-05 Happy.
30. luhn-failing runs, phone and order numbers are stored unchanged on import: XS-ACCT-05 Alt.
31. pushing the same package twice stores the masked row once: XS-ACCT-05 Alt, SDR-001 idempotency.
32. a manual entry's merchant and tags are masked: XS-ACCT-05 Happy.
33. tags added later are masked: XS-ACCT-05 Happy.
34. a split of a row stored before masking writes masked children: XS-ACCT-05 Happy.

--- ledger · ProductionLoggingIT (3) ---
35. creating an account writes no jOOQ line and no bound value outside dev/test: XS-ACCT-06 Happy.
36. a log call whose message includes a card number writes it masked: XS-ACCT-06 Happy.
37. DEBUG lines from the Ledger loggers are not written outside dev/test: XS-ACCT-06 Alt.

--- ui · last-four.spec (6) ---
38. a pasted card number keeps only its last four digits: XS-ACCT-01 Fail.
39. non-digits are dropped and short input stays as typed: XS-ACCT-01.
40. an empty value or exactly four digits is valid: XS-ACCT-01.
41. the table text is •••• plus the last four, or — when there is none: XS-ACCT-01 Happy, Alt.
42. only a 400 invalid_argument naming accountLastFour counts as a last-four rejection: XS-ACCT-01 Fail.
43. the field error reads "Enter only the last 4 digits.": XS-ACCT-01 Fail.

--- ui · Accounts page last four (7) ---
44. the table shows •••• 6789 and — and never a full number: XS-ACCT-01 Happy, Alt.
45. inline edit opens with the stored last four or an empty field, limited to four characters: XS-ACCT-01 Happy, Alt.
46. a pasted 4111 1111 1111 1111 keeps 1111 and the full value is never sent: XS-ACCT-01 Fail.
47. an unchanged value is left out of the request and an emptied one is sent as null: XS-ACCT-01 Alt, XS-ACCT-02 Alt.
48. an empty field on an account with none is left out of the request: XS-ACCT-01 Alt.
49. fewer than four digits is not sent and the error shows under the field: XS-ACCT-01 Fail.
50. a 400 invalid_argument naming accountLastFour shows the field error: XS-ACCT-01 Fail.

--- analytics · test_log_masking (4) ---
51. luhn-valid runs are masked in text: XS-ACCT-06 Happy, Appendix B vectors.
52. other digit runs are left alone: XS-ACCT-06, Appendix B vectors.
53. a number followed by an amount is still masked: XS-ACCT-06.
54. a log call whose message includes 4111111111111111 writes ****1111: XS-ACCT-06 Happy.

--- ai-assistant · test_log_masking (4) ---
55. luhn-valid runs are masked in text: XS-ACCT-06 Happy, Appendix B vectors.
56. other digit runs are left alone: XS-ACCT-06, Appendix B vectors.
57. a number followed by an amount is still masked: XS-ACCT-06.
58. a log call whose message includes 4111111111111111 writes ****1111: XS-ACCT-06 Happy.

--- data-pipeline · test_log_masking (4) ---
59. luhn-valid runs are masked in text: XS-ACCT-06 Happy, Appendix B vectors.
60. other digit runs are left alone: XS-ACCT-06, Appendix B vectors.
61. a number followed by an amount is still masked: XS-ACCT-06.
62. a log call whose message includes 4111111111111111 writes ****1111: XS-ACCT-06 Happy.

--- user-profile · test_log_masking (5) ---
63. luhn-valid runs are masked in text: XS-ACCT-06 Happy, Appendix B vectors.
64. other digit runs are left alone: XS-ACCT-06, Appendix B vectors.
65. a number followed by an amount is still masked: XS-ACCT-06.
66. a log call whose message includes 4111111111111111 writes ****1111: XS-ACCT-06 Happy.
67. a standard-library logger is masked before any handler sees it: XS-ACCT-06.

--- document-service · test_log_masking (5) ---
68. luhn-valid runs are masked in text: XS-ACCT-06 Happy, Appendix B vectors.
69. other digit runs are left alone: XS-ACCT-06, Appendix B vectors.
70. a number followed by an amount is still masked: XS-ACCT-06.
71. a log call whose message includes 4111111111111111 writes ****1111: XS-ACCT-06 Happy.
72. a standard-library logger is masked before any handler sees it: XS-ACCT-06.

--- knowledge · test_log_masking (5) ---
73. luhn-valid runs are masked in text: XS-ACCT-06 Happy, Appendix B vectors.
74. other digit runs are left alone: XS-ACCT-06, Appendix B vectors.
75. a number followed by an amount is still masked: XS-ACCT-06.
76. a log call whose message includes 4111111111111111 writes ****1111: XS-ACCT-06 Happy.
77. a standard-library logger is masked before any handler sees it: XS-ACCT-06.
