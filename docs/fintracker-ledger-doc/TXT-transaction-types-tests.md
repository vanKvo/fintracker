=========================
F2P TESTS (51)
=========================

--- TransactionTypeIT (12) ---
1. the database accepts each of the five transaction types: TXT-01 Requirement, Appendix A type.
2. the database rejects any type outside the five, including the legacy PURCHASE/CREDIT/SALE/RETURN: TXT-01 Requirement.
3. the database rejects a transaction with no direction: Appendix A direction (not null).
4. the database rejects a direction other than DEBIT or CREDIT: Appendix A direction enum.
5. currency defaults to USD; is_recurring and linked_transaction_id default to null: Appendix A currency, is_recurring, linked_transaction_id.
6. linked_transaction_id must reference an existing transaction: Appendix A linked_transaction_id.
7. deleting the linked transaction clears the link instead of deleting the refund: Appendix A linked_transaction_id.
8. save() persists and reads back type, direction, currency, isRecurring and linkedTransactionId: TXT-01 Happy.
9. bulk insert persists each row's direction and currency: TXT-01 Happy.
10. monthly income counts only INCOME, not refunds, transfers or adjustments: TXT-02 Requirement, Design Principle 2.
11. monthly expenses are EXPENSE minus REFUND and exclude transfers, income and adjustments: TXT-02 Requirement.
12. monthly expenses go negative when refunds exceed expenses: TXT-02 Alt (negative spend).

--- TransactionTypeServiceTest (12) ---
13. each of the five types from a statement row is stored with its direction: TXT-01 Happy.
14. a statement row with no type defaults to INCOME for a credit and EXPENSE for a debit: TXT-01 Fail.
15. a statement row with no direction is reported as a failed row: Appendix A direction (not null).
16. a statement row with a direction other than DEBIT or CREDIT is reported as a failed row: Appendix A direction enum.
17. a statement row's currency defaults to USD when omitted and is kept when supplied: Appendix A currency.
18. a statement row whose currency is not a 3-letter code is reported as a failed row: Appendix A currency.
19. a manual entry stores the requested type, direction and currency: TXT-01 Happy.
20. a manual entry's currency defaults to USD when omitted: Appendix A currency.
21. a manual entry with no type defaults to INCOME for a credit and EXPENSE for a debit: TXT-01 Fail.
22. a manual entry with the legacy type PURCHASE is rejected: TXT-01 Requirement.
23. a manual entry with no direction is rejected: Appendix A direction (not null).
24. split children inherit the parent's type, direction and currency: TXT-01 Requirement.

--- TransactionServiceTest (1) ---
25. a statement row with the legacy type PURCHASE is reported as a failed row: TXT-01 Requirement.

--- BudgetRefundOffsetIT (7) ---
26. a refund offsets expenses in its category ($150 - $50 = $100): TXT-02 Happy.
27. refunds larger than expenses report a negative net spend: TXT-02 Alt (negative spend).
28. a refund offsets the month it lands in, not the month of the purchase: TXT-02 Requirement.
29. TRANSFER, INCOME and ADJUSTMENT contribute nothing to spending: TXT-02 Requirement, TXT-02 Alt (transfer).
30. a refund in another category does not offset this category: TXT-02 Requirement (per category).
31. a pending refund does not offset spending: TXT-02 Requirement (approved rows only).
32. the yearly budget listing applies the same refund offset: TXT-02 Requirement.

--- BudgetSpendEnrichmentIT (1) ---
33. INCOME transactions are not counted as spending: TXT-02 Requirement.

--- TestTransactionTypeAndDirection (4) ---
34. a charge is normalized as a DEBIT EXPENSE: TXT-01 Fail (default type from direction).
35. a credit is normalized as a CREDIT INCOME with a positive amount: TXT-01 Fail (default type from direction).
36. a normalized row rejects any type outside the five, including SALE/RETURN/PURCHASE/CREDIT: TXT-01 Requirement.
37. a normalized row rejects a direction other than DEBIT or CREDIT: Appendix A direction enum.

--- TestToLedgerLine (2) ---
38. the Ledger line carries type and direction in the Ledger's vocabulary: TXT-01 Requirement.
39. type and direction are sent unchanged, with no translation: TXT-01 Requirement.

--- test_transaction_type_queries (6) ---
40. dashboard income counts only INCOME: TXT-02 Requirement, Design Principle 2.
41. dashboard expenses are EXPENSE minus REFUND: TXT-02 Requirement.
42. dashboard expenses go negative when refunds exceed expenses: TXT-02 Alt (negative spend).
43. the spending report nets refunds per category and counts only INCOME as income: TXT-02 Requirement; docs/bugs/2026-10-06_bug_analytics_reports_queries_fail_on_postgres.md.
44. the monthly trend uses INCOME and net spend: TXT-02 Requirement; docs/bugs/2026-10-06_bug_analytics_reports_queries_fail_on_postgres.md.
45. the AI insights summary nets refunds and skips non-spending types: TXT-02 Requirement.

--- AddTransactionDialog (6) ---
46. the dialog offers exactly the five transaction types: TXT-01 Requirement.
47. the dialog defaults to an EXPENSE going out: TXT-01 Requirement.
48. selecting INCOME, REFUND or EXPENSE sets the matching direction: TXT-01 Alt (refund is a credit).
49. TRANSFER and ADJUSTMENT keep the chosen direction: TXT-01 Requirement.
50. saving sends type and direction with a negative amount for money out: TXT-01 Happy.
51. saving sends a positive amount for money in: TXT-01 Happy.
