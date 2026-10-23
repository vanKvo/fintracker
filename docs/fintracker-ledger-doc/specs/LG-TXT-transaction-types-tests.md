> **Tests for:** [LG-TXT-transaction-types-spec.md](LG-TXT-transaction-types-spec.md) · **Formerly:** `docs/fintracker-ledger-doc/TXT-transaction-types-tests.md` (renamed 2026-10)

=========================
F2P TESTS (98)
=========================

--- TransactionTypeIT (14) ---
1. the database accepts each of the five transaction types: LG-TXT-01 Requirement, Appendix A type.
2. the database rejects any type outside the five, including the legacy PURCHASE/CREDIT/SALE/RETURN: LG-TXT-01 Requirement.
3. the database rejects a transaction with no direction: Appendix A direction (not null).
4. the database rejects a direction other than DEBIT or CREDIT: Appendix A direction enum.
5. the database rejects EXPENSE as money in and INCOME or REFUND as money out: LG-TXT-01 type/direction rule.
6. the database accepts TRANSFER and ADJUSTMENT in either direction: LG-TXT-01 type/direction rule.
7. currency defaults to USD; is_recurring and linked_transaction_id default to null: Appendix A currency, is_recurring, linked_transaction_id.
8. linked_transaction_id must reference an existing transaction: Appendix A linked_transaction_id.
9. deleting the linked transaction clears the link instead of deleting the refund: Appendix A linked_transaction_id.
10. save() persists and reads back type, direction, currency, isRecurring and linkedTransactionId: LG-TXT-01 Happy.
11. bulk insert persists each row's direction and currency: LG-TXT-01 Happy.
12. monthly income counts only INCOME, not refunds, transfers or adjustments: LG-TXT-02 Requirement, Design Principle 2.
13. monthly expenses are EXPENSE minus REFUND and exclude transfers, income and adjustments: LG-TXT-02 Requirement.
14. monthly expenses go negative when refunds exceed expenses: LG-TXT-02 Alt (negative spend).

--- TransactionTypeServiceTest (24) ---
15. each of the five types from a statement row is stored with its direction: LG-TXT-01 Happy.
16. a statement row with no type is reported as a failed row, never defaulted: LG-TXT-01 Fail.
17. a statement row with no direction is reported as a failed row: Appendix A direction (not null).
18. a statement row with a direction other than DEBIT or CREDIT is reported as a failed row: Appendix A direction enum.
19. a statement row's currency defaults to USD when omitted and is kept when supplied: Appendix A currency.
20. a statement row with EXPENSE as money in, or INCOME/REFUND as money out, is reported as a failed row: LG-TXT-01 type/direction rule.
21. a statement row whose currency is not a 3-letter code is reported as a failed row: Appendix A currency.
22. a manual entry stores the requested type, direction and currency: LG-TXT-01 Happy.
23. a manual entry's currency defaults to USD when omitted: Appendix A currency.
24. a manual entry with no type is rejected, never defaulted: LG-TXT-01 Fail.
25. a manual entry with the legacy type PURCHASE is rejected: LG-TXT-01 Requirement.
26. a manual entry with EXPENSE as money in, or INCOME/REFUND as money out, is rejected: LG-TXT-01 type/direction rule.
27. a manual entry stores isRecurring and a link to one of the user's own transactions: Appendix A is_recurring, linked_transaction_id.
28. a manual entry linking to a transaction the user doesn't own is rejected: Appendix A linked_transaction_id.
29. a manual entry with no direction is rejected: Appendix A direction (not null).
30. split children inherit the parent's type, direction and currency: LG-TXT-01 Requirement.
31. changing type and direction together stores both: Appendix A type, direction.
32. changing only the type keeps the stored direction: Appendix A type, direction.
33. a type that conflicts with the stored direction is rejected: LG-TXT-01 type/direction rule.
34. changing the type of another user's transaction is not found: Appendix A type.
35. isRecurring can be set on an existing transaction: Appendix A is_recurring.
36. a transaction can be linked to another of the user's transactions: Appendix A linked_transaction_id.
37. a transaction cannot be linked to itself: Appendix A linked_transaction_id.
38. a link to a transaction the user doesn't own is rejected: Appendix A linked_transaction_id.

--- TransactionServiceTest (1) ---
39. a statement row with the legacy type PURCHASE is reported as a failed row: LG-TXT-01 Requirement.

--- TransactionControllerIT (11) ---
40. POST without a type responds 400 and stores nothing: LG-TXT-01 Fail.
41. POST with EXPENSE as money in, or INCOME/REFUND as money out, responds 400: LG-TXT-01 type/direction rule.
42. POST returns direction, currency, isRecurring and linkedTransactionId: Appendix A.
43. POST linking to a transaction the user doesn't own responds 400: Appendix A linked_transaction_id.
44. GET filters by type and by direction: Appendix A type, direction.
45. PATCH changes type and direction together: Appendix A type, direction.
46. PATCH with a type that conflicts with the stored direction responds 400: LG-TXT-01 type/direction rule.
47. PATCH sets isRecurring and linkedTransactionId: Appendix A is_recurring, linked_transaction_id.
48. PATCH linking a transaction to itself responds 400: Appendix A linked_transaction_id.
49. PATCH with no field to change responds 400: Appendix A.
50. a JSON response exposes the new fields by name: Appendix A.

--- InternalTransactionControllerTest (1) ---
51. a statement row with no type responds 400 and never reaches the service: LG-TXT-01 Fail.

--- BudgetRefundOffsetIT (7) ---
52. a refund offsets expenses in its category ($150 - $50 = $100): LG-TXT-02 Happy.
53. refunds larger than expenses report a negative net spend: LG-TXT-02 Alt (negative spend).
54. a refund offsets the month it lands in, not the month of the purchase: LG-TXT-02 Requirement.
55. TRANSFER, INCOME and ADJUSTMENT contribute nothing to spending: LG-TXT-02 Requirement, LG-TXT-02 Alt (transfer).
56. a refund in another category does not offset this category: LG-TXT-02 Requirement (per category).
57. a pending refund does not offset spending: LG-TXT-02 Requirement (approved rows only).
58. the yearly budget listing applies the same refund offset: LG-TXT-02 Requirement.

--- BudgetSpendEnrichmentIT (1) ---
59. INCOME transactions are not counted as spending: LG-TXT-02 Requirement.

--- TestTransactionTypeAndDirection (6) ---
60. a charge is normalized as a DEBIT EXPENSE: DP-TXT interim behavior (type from direction).
61. a credit is normalized as a CREDIT INCOME with a positive amount: DP-TXT interim behavior (type from direction).
62. a normalized row rejects any type outside the five, including SALE/RETURN/PURCHASE/CREDIT: LG-TXT-01 Requirement.
63. a normalized row rejects a direction other than DEBIT or CREDIT: Appendix A direction enum.
64. a normalized row rejects EXPENSE as money in and INCOME or REFUND as money out: LG-TXT-01 type/direction rule.
65. a normalized TRANSFER or ADJUSTMENT accepts either direction: LG-TXT-01 type/direction rule.

--- TestToLedgerLine (2) ---
66. the Ledger line carries type and direction in the Ledger's vocabulary: LG-TXT-01 Requirement.
67. type and direction are sent unchanged, with no translation: LG-TXT-01 Requirement.

--- test_transaction_type_queries (6) ---
68. dashboard income counts only INCOME: LG-TXT-02 Requirement, Design Principle 2.
69. dashboard expenses are EXPENSE minus REFUND: LG-TXT-02 Requirement.
70. dashboard expenses go negative when refunds exceed expenses: LG-TXT-02 Alt (negative spend).
71. the spending report nets refunds per category and counts only INCOME as income: LG-TXT-02 Requirement; docs/bugs/2026-10-06_bug_analytics_reports_queries_fail_on_postgres.md.
72. the monthly trend uses INCOME and net spend: LG-TXT-02 Requirement; docs/bugs/2026-10-06_bug_analytics_reports_queries_fail_on_postgres.md.
73. the AI insights summary nets refunds and skips non-spending types: LG-TXT-02 Requirement.

--- AddTransactionDialog (8) ---
74. the dialog offers exactly the five transaction types: LG-TXT-01 Requirement.
75. the dialog defaults to an EXPENSE going out: LG-TXT-01 Requirement.
76. selecting INCOME, REFUND or EXPENSE sets the matching direction: LG-TXT-01 Alt (refund is a credit).
77. the direction is locked for EXPENSE, INCOME and REFUND: LG-TXT-01 type/direction rule.
78. the direction is user-chosen for TRANSFER and ADJUSTMENT: LG-TXT-01 type/direction rule.
79. TRANSFER and ADJUSTMENT keep the chosen direction: LG-TXT-01 Requirement.
80. saving sends type and direction with a negative amount for money out: LG-TXT-01 Happy.
81. saving sends a positive amount for money in: LG-TXT-01 Happy.

--- TransactionService (3) ---
82. each listed row carries type, direction, currency, isRecurring and linkedTransactionId: Appendix A.
83. type and direction filters are sent as query parameters: Appendix A type, direction.
84. an update sends type, direction, isRecurring and linkedTransactionId: Appendix A.

--- AmountSignConventionTest (8) ---
85. a manual entry of -40.00 EXPENSE is stored as 40.00 DEBIT: LG-TXT-03 Happy.
86. a manual entry that is already positive is stored unchanged: LG-TXT-03 Happy.
87. every type is stored positive whatever the input sign: LG-TXT-03 Requirement.
88. a positive EXPENSE entry with direction CREDIT is rejected under the type/direction rule: LG-TXT-03 Fail.
89. editing an amount to a negative value stores its absolute value: LG-TXT-03 Requirement.
90. split children are stored positive however the amounts were signed: LG-TXT-03 Requirement.
91. a statement row arrives positive and is stored unchanged: LG-TXT-03 Happy.
92. a statement row with a negative amount is reported as a failed row: LG-TXT-03 Requirement.

--- AmountSignConventionIT (5) ---
93. the database accepts a positive amount: LG-TXT-03 Requirement.
94. the database rejects an insert with a negative amount: LG-TXT-03 Fail.
95. the database rejects an insert with a zero amount: LG-TXT-03 Fail.
96. the database rejects an update to a negative or zero amount: LG-TXT-03 Fail.
97. the one-time script makes every signed manual row positive, leaves positive rows and totals unchanged, and validates the check: LG-TXT-03 Alt.

--- TransactionService (fintracker-ui, 2026-10-21 additions) (1) ---
98. a stored positive DEBIT amount is shown as negative and a CREDIT amount as positive: LG-TXT-03 Requirement.
