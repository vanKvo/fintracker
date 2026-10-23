=========================
F2P TESTS (66)
=========================

--- ReportingViewsIT (31) ---
1. a posted expense counts as spend with its positive amount: XS-RPTV-01 Happy.
2. a posted refund has flow refund and offsets spend in its category: XS-RPTV-01 Happy.
3. income has flow income: XS-RPTV-01 Requirement, Appendix B.
4. transfer and adjustment have flow none and never count: XS-RPTV-01 Alt.
5. pending and excluded rows appear with counts false: XS-RPTV-01 Alt.
6. a split parent does not count and its children do, so a split purchase is counted once: XS-RPTV-01 Alt.
7. deleted rows never appear: XS-RPTV-01 Fail.
8. rpt_transactions has exactly the Appendix A columns: XS-RPTV-01 Requirement, Appendix A.
9. a row with no merchant key falls back to the lower-cased merchant name: XS-RPTV-01 Appendix A merchant_key.
10. a budget line returns its month, category id and limit: XS-RPTV-02 Happy.
11. a line without a category id resolves it from the category name ignoring case: XS-RPTV-02 Alt.
12. a line whose name resolves to no category is kept with a null category id: XS-RPTV-02 Fail.
13. rpt_budget_limits has exactly the Appendix A columns: XS-RPTV-02 Requirement, Appendix A.
14. rpt_accounts has exactly the Appendix A columns: XS-RPTV-03 Happy.
15. no reporting view has a column named like name, number, owner or balance: XS-RPTV-03 Fail.
16. an account's latest transaction date is its newest posted one and null with none: XS-RPTV-03 Alt.
17. as the analytics role with user A's context every view returns only user A's rows: XS-RPTV-04 Happy.
18. with no user context set every view returns zero rows: XS-RPTV-04 Alt.
19. the views are owned by a role that is neither superuser nor bypassrls so row-level security still applies: XS-RPTV-04 Requirement (see the 2026-10-21 implementation note).
20. the analytics role can select from the three views: XS-RPTV-05 Happy.
21. the analytics role is refused every ledger base table: XS-RPTV-05 Fail.
22. insert, update and delete through a view are refused for the analytics role: XS-RPTV-05 Fail.
23. the migration revokes base-table grants the role held before: XS-RPTV-05 Requirement.
24. a partial per-user date index exists for rows that are not deleted: XS-RPTV-06 Fail.
25. a one-month aggregate over rpt_transactions for one user uses the new index: XS-RPTV-06 Happy.
26. with 5,000 transactions over 24 months a monthly aggregate runs in under 300 ms at p95: XS-RPTV-06 Alt.
27. Appendix C: user A's September income is 5,000.00: XS-RPTV-09 Appendix C.
28. Appendix C: user A's September spend net of refunds is 1,840.00: XS-RPTV-09 Appendix C.
29. Appendix C: user A has one other-currency row that counts but is filtered by currency: XS-RPTV-09 Appendix C.
30. Appendix C: user A sees none of user B's rows: XS-RPTV-09 Appendix C.
31. Appendix C: a $120 split parent does not count while its $70 and $50 children total 120.00: XS-RPTV-09 Appendix C.

--- ReportingTotalsIT (6) ---
32. dashboard income and expenses equal the reporting view figures for the same month: XS-RPTV-08 Happy.
33. a $10 refund in food lowers both food's budget spend and dashboard expenses by $10: XS-RPTV-08 Alt.
34. a transfer between the user's own accounts changes neither expenses nor income: XS-RPTV-08 Fail.
35. pending and excluded rows count toward nothing: XS-RPTV-08 Requirement.
36. only the primary currency is summed: XS-RPTV-08 Requirement.
37. the per-category and per-month sums add up to the month's expenses: XS-RPTV-08 Requirement.

--- test_reporting_db (Analytics) (9) ---
38. a request is one begin, one set_config, its queries and one commit: XS-RPTV-07 Happy.
39. the user id is a bound parameter and never part of the sql: XS-RPTV-07 Requirement.
40. a failing query rolls the transaction back and re-raises: XS-RPTV-07 Requirement.
41. aurora resuming is retried once after two seconds: XS-RPTV-07 Fail.
42. a second failure is a retryable error without the underlying message: XS-RPTV-07 Fail.
43. a savepoint isolates a failing section: XS-RPTV-07 Requirement, AN-RPT-11.
44. numeric columns come back as decimals not floats: XS-RPTV-07 Requirement.
45. parameters are typed for the data api: XS-RPTV-07 Requirement.
46. no query names a ledger base table: XS-RPTV-07 Fail.

--- test_reporting_contract (Analytics) (20) ---
47. Appendix C: september income and spend net of refunds through analytics' queries: XS-RPTV-09 Appendix C.
48. Appendix C: food spend is 350 less a 40 refund against august: XS-RPTV-09 Appendix C.
49. Appendix C: the other-currency row is flagged and left out of every total: XS-RPTV-09 Appendix C.
50. Appendix C: pending rows are counted and change no total: XS-RPTV-09 Appendix C.
51. Appendix C: a split purchase is counted once: XS-RPTV-09 Appendix C.
52. top merchants group by merchant key and net refunds: XS-RPTV-01 merchant_key.
53. a transfer, an adjustment and a deleted row change no section: XS-RPTV-09 Happy.
54. category trends align with the cash flow months: XS-RPTV-09 Happy.
55. the sections equal what the service returns for the public route: XS-RPTV-09 Happy.
56. spending pace against the same day range of the previous month: XS-RPTV-09 Happy.
57. the facts loader reads rows, budgets and accounts from the views: XS-RPTV-09 Happy.
58. the loader never returns another user's rows: XS-RPTV-04 Happy.
59. period availability counts only counted rows in the currency: XS-RPTV-09 Happy.
60. user A sees none of user B's rows and vice versa: XS-RPTV-04 Happy.
61. a new user with no rows sees nothing: XS-RPTV-04 Alt.
62. the user context is set inside the request's transaction only: XS-RPTV-07 Happy.
63. the read-only role cannot read a ledger base table: XS-RPTV-05 Fail.
64. the read-only role cannot write through a view: XS-RPTV-05 Fail.
65. a failing section does not poison the transaction for the next one: XS-RPTV-07 Requirement.
66. reports p95 is under one second with 5,000 transactions: XS-RPTV-06 Alt, AN-RPT-03 Happy.
