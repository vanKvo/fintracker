=========================
F2P TESTS (83)
=========================

--- test_sections (21) ---
1. cash flow covers the last 12 complete months oldest first: AN-RPT-04 Happy.
2. cash flow months without counted rows are zero gaps not dips: AN-RPT-04 Alt.
3. cash flow queries counted rows in the context currency over the trend window: AN-RPT-04 Requirement, AN-RPT-08.
4. categories show amount, previous amount and change: AN-RPT-05 Happy.
5. categories are sorted by amount highest first with ties by name: AN-RPT-05 Requirement.
6. a category with spend only in the comparison period has amount zero: AN-RPT-05 Alt.
7. a category with no previous spend has no percent change: AN-RPT-05 Alt.
8. net refunds larger than spend show a negative amount: AN-RPT-05 Alt.
9. uncategorized spend is its own row: AN-RPT-05 Alt.
10. categories compare the period with its comparison period: AN-RPT-05 Requirement, AN-FS-03.
11. every category has exactly 12 values aligned to the cash flow months: AN-RPT-06 Happy.
12. categories with zero spend in every month are left out: AN-RPT-06 Alt.
13. trends are ordered by total spend: AN-RPT-06 Requirement.
14. a merchant shows net spend, count and share of total spend: AN-RPT-07 Happy.
15. top merchants are capped at 10 with ties broken by name: AN-RPT-07 Alt.
16. fewer than 10 merchants returns as many as exist: AN-RPT-07 Alt.
17. a merchant whose refunds exceed its purchases is left out: AN-RPT-07 Alt.
18. share is null when nothing was spent: AN-RPT-07 Requirement.
19. pending rows and other currencies are reported for the period: AN-RPT-08 Alt.
20. data quality looks only at the selected period: AN-RPT-08 Requirement.
21. every section query reads only counted rows in the context currency: AN-RPT-08 Requirement.

--- test_spending_pace (12) ---
22. spending so far against the same day range last month: AN-RPT-02 Happy.
23. on the 31st the comparison ends on the last day of the shorter previous month: AN-RPT-02 Alt.
24. on the first both ranges cover one day: AN-RPT-02 Alt.
25. no spending last month to date has no percent and a flag: AN-RPT-02 Alt.
26. refunds net against spend through the view flow and only counted rows count: AN-RPT-02 Requirement, AN-RPT-08.
27. the pending count covers rows dated this month: AN-RPT-02 Alt.
28. month to date ranges: AN-RPT-02 Requirement, AN-FS-03.
29. today is the date in the user's timezone: AN-RPT-02 Requirement.
30. tokyo is already on the 21st: AN-RPT-02 Requirement.
31. a missing timezone is 409 user settings incomplete: AN-RPT-02 Fail.
32. a database failure is a retryable 503 for this card only: AN-RPT-02 Fail.
33. any other failure is also a retryable 503: AN-RPT-02 Fail.

--- test_reports_api (11) ---
34. the response has the period, comparison, currency, data quality and four sections: AN-RPT-03 Happy.
35. the default period is last month: AN-RPT-01 Happy.
36. the request is one transaction for the authenticated user: AN-RPT-03 Requirement.
37. an unknown period or any extra parameter is 400 invalid argument: AN-RPT-03 Fail.
38. a failed section is null with a reason and the others still render: AN-RPT-11 Alt.
39. a failed trend section still names its months: AN-RPT-11 Alt.
40. a database failure before any section is 503 database unavailable: AN-RPT-11 Requirement.
41. logs and metrics never carry amounts or merchant names: AN-RPT-11 Fail.
42. latency is recorded per route and section: AN-RPT-11 Happy.
43. each internal route returns the same values as the public section: AN-RPT-09 Happy.
44. an internal call runs for the forwarded user only: AN-RPT-09 Requirement.

--- test_routes_auth (6) ---
45. spending pace uses the authorizer user and ignores forged headers: AN-RPT-02, AN-FS-02.
46. reports use the authorizer user and ignore forged headers: AN-RPT-03, AN-FS-02.
47. routes without an authorizer user are 401 problems: AN-FS-02 Fail.
48. a user id in the query is rejected and not used: AN-RPT-03 Fail, AN-FS-02.
49. removed routes are 404: AN-RPT-10 Fail.
50. the public api has the spending pace and no other dashboard route: AN-RPT-10 Happy.

--- test_internal_routes (11) ---
51. an allowed caller gets the forwarded user's spending pace: AN-RPT-09 Requirement.
52. each section has an internal route for the forwarded user: AN-RPT-09 Requirement.
53. no iam identity is 401 and nothing runs: AN-RPT-09 Fail.
54. a verified caller not on the allowlist is 403 and nothing runs: AN-RPT-09 Fail.
55. a public gateway request with a forged header cannot use internal routes: AN-RPT-09 Fail.
56. an unset allowlist fails closed: AN-RPT-09 Fail.
57. a missing user header is 400: AN-RPT-09 Requirement.
58. a body containing user id is rejected with 400: AN-RPT-09 Fail.
59. internal routes accept a period and no other argument: AN-RPT-09 Alt.
60. removed internal routes are 404: AN-RPT-10 Fail.
61. the merchant month totals route reads the view for the forwarded user and currency: AN-RPT-08, XS-RPTV-07.

--- ReportsService (fintracker-ui) (2) ---
62. loads all four sections in one request for the period: AN-RPT-03 Happy.
63. never sends a user id, timezone or currency: AN-RPT-03, AN-FS-02.

--- Reports (fintracker-ui) (14) ---
64. defaults to last month and labels the period against its comparison: AN-RPT-01 Happy.
65. loads the four chart sections in one request: AN-RPT-03 Happy.
66. reloads the sections when another period is chosen and shows its label: AN-RPT-01 Happy.
67. passes the chosen period to the financial summary panel: AN-RPT-01 Requirement.
68. disables periods with no counted transactions: AN-RPT-01 Alt.
69. shows a gap, not a dip, for a month with no counted rows: AN-RPT-04 Alt.
70. lists every category with its change against the comparison period: AN-RPT-05 Happy.
71. lists the top merchants with count and share of spend: AN-RPT-07 Happy.
72. switches the trend chart between categories without a new request: AN-RPT-06 Alt.
73. says how many rows awaiting approval are not included: AN-RPT-08 Alt.
74. keeps the previous charts with an inline error and a retry button when reports fails: AN-RPT-01 Fail.
75. still loads the financial summary when reports fails: AN-RPT-01 Fail.
76. shows a failed section on its own while the others render: AN-RPT-11 Alt.
77. formats month keys for the chart labels: AN-RPT-04 Requirement.

--- SpendingPaceCard (fintracker-ui) (6) ---
78. shows spending so far against the same days last month: AN-RPT-02 Happy.
79. tells the user how many rows awaiting approval are not included: AN-RPT-02 Alt.
80. omits the pending note when nothing awaits approval: AN-RPT-02 Alt.
81. says so when nothing was spent in the same days last month: AN-RPT-02 Alt.
82. shows an error state with a retry for this card only when the request fails: AN-RPT-02 Fail.
83. never sends a user id, timezone or currency: AN-RPT-02, AN-FS-02.
