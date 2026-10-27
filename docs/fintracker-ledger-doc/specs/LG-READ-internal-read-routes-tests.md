=========================
F2P TESTS (31)
=========================

--- InternalReadRoutesIT (20) ---
1. a signed call returns only the calling user's data: LG-READ-01 Happy.
2. a call without the caller header, or from a role off the allow-list, is rejected before any query: LG-READ-01 Fail.
3. a query parameter that names the user, timezone or currency is rejected as invalid_argument: LG-READ-01 Fail.
4. a user whose timezone is not set gets the user_settings_incomplete answer: LG-READ-01 / XS-CTX-05.
5. 40 matches return the 25 newest rows with the count and sum of all 40: LG-READ-02 Happy.
6. a row is date, merchant, category and amount as a 2-place string, and nothing else: LG-READ Appendix A / Design Principle 3.
7. pending, excluded, refund, income and split-parent rows are not in the rows or the totals: LG-READ-02 Alt.
8. no match returns no rows, a count of 0 and a total of 0.00: LG-READ-02 Alt.
9. the merchant filter is a case-insensitive substring, and % and _ in it are plain characters: LG-READ-02.
10. the category filter takes the name of the user's category or a SYSTEM category: LG-READ-02.
11. another user's category and an unknown category are 400 invalid_argument naming the category: LG-READ-02 Fail.
12. end defaults to today and start to 12 months before it: LG-READ-02.
13. start and end are inclusive: LG-READ-02.
14. a range over 24 months, start after end, a bad date or a merchant over 50 characters is 400 naming the field: LG-READ-02 Fail.
15. the request's merchant text is never logged: LG-READ-04 Fail.
16. every line's spent equals the Budgets tab's figure, and remaining is limit minus spent: LG-READ-03 Happy.
17. an over-limit line has a negative remaining: LG-READ-03 Alt.
18. a month with no budget is 404 budget_not_found, and the read creates nothing: LG-READ-03 Alt.
19. a future month, a month over 24 months back or a malformed month is 400 invalid_argument: LG-READ-03 Fail.
20. another user's budget is not visible: that user's month is a 404: LG-READ-03 / invariant 5.

--- DatabaseUnavailableHandlerTest (3) ---
21. a connection failure is 503 database_unavailable with retryable true and no detail from the cause: LG-READ-04 Fail.
22. a jOOQ error with a connection SQLSTATE is 503: LG-READ-04 Fail.
23. a constraint violation is still a generic 500, not an availability problem: LG-READ-04.

--- InternalCallerFilterTest (1) ---
24. the filter is registered for the budgets internal prefix as well as the other internal prefixes: LG-READ-01.

--- TestLedgerRoutesAreInternal (1) ---
25. no Ledger path in the AI assistant's clients is a public route: LG-READ-01 Fail.

--- TestGetBudgetStatus (4) ---
26. the client reads the internal status route with a year and month: LG-READ-03.
27. the client maps the lines with remaining from the Ledger: LG-READ-03.
28. no budget for the month returns none, not an error: LG-READ-03 Alt.
29. any other failure is a generic client error: LG-READ-04 Fail.

--- test_tools (2) ---
30. list_transactions reads the Ledger's internal search: LG-READ-01 / AI-CHAT-05.
31. list_transactions has no account, status or paging parameter: LG-READ-02.
