=========================
F2P TESTS (84)
=========================

--- BudgetCapacityAndUniquenessIT (5) ---
1. a budget with 51 line items is rejected with LineItemLimitExceededException: B. Constraints — "maximum 50 line items"; one past the ceiling must raise LineItemLimitExceededException (400).
2. a payload containing the same category twice is rejected: B. Category Uniqueness — duplicate category names rejected as validation, not as a raw DB constraint error.
3. categories differing only in case are treated as duplicates: B. Category Uniqueness read with REQ-5.2's case-insensitive category matching.
4. a blank category name is rejected: B. Category Uniqueness / REQ-5.2 Non-Empty Category Name — a category is a line's identity, so blank is invalid.
5. a payload that is both oversized and duplicated is rejected and persists nothing: B. Constraints — rejection must leave no partial write behind.

--- BudgetControllerIT (12) ---
6. PUT creating a brand new budget responds 201 Created: D. Success Responses — 201 for a brand new monthly budget.
7. PUT updating an existing budget responds 200 OK: D. Success Responses — 200 when an existing monthly budget is updated.
8. POST /{id}/close responds 200 OK and reports the budget as CLOSED: D. Endpoints (POST /budgets/{id}/close) + A. Manual Close.
9. POST /{id}/reopen responds 200 OK and reports the budget as ACTIVE: D. Endpoints (POST /budgets/{id}/reopen) + A. Reopening Exemption.
10. writing to a CLOSED budget responds 422 Unprocessable Entity: D. Error Mappings — 422 for HistoricalBudgetException.
11. an out-of-range limit responds 400 Bad Request: D. Error Mappings — 400 for InvalidBudgetException.
12. error responses are served as application/problem+json: RFC 9457 Problem Details applied to REQ-5.1's error paths.
13. the problem document carries type, title and a status matching the HTTP status: RFC 9457 well-formedness.
14. an error response never leaks a stack trace: GlobalExceptionHandler contract, tested at REQ-5.1's new exception types.
15. status is serialized as its name, not as an ordinal: C. Data Impacts — status is a named two-valued state on the wire.
16. closing an unknown budget responds 404 Not Found: E. Interface Details — ResourceNotFoundException when the budget doesn't exist or isn't the user's.
17. the response reports the normalized effective month: B. Normalization Rule, observed at the API boundary.

--- BudgetInvariantsIT (1) ---
18. a written budget round-trips through the read path unchanged: B. Normalization Rule + A. Period Selection & Upsert Behavior.

--- BudgetLifecycleIT (14) ---
19. a budget created for a past period initializes ACTIVE: A. State Initialization — past, present and future all start ACTIVE.
20. an ACTIVE budget for a past period can still be updated: A. Modification Guard — writes keyed on status, not on the month having elapsed.
21. closeBudget transitions ACTIVE to CLOSED: A. Manual Close.
22. closing an already-CLOSED budget is rejected with HistoricalBudgetException: E. closeBudget @throws HistoricalBudgetException if already CLOSED.
23. upserting into a CLOSED budget is rejected with HistoricalBudgetException: A. Immutability upon Closure.
24. a write rejected by the CLOSED guard leaves the stored lines unchanged: A. Immutability upon Closure — the rejection must be effective, not merely thrown.
25. reopenBudget transitions CLOSED back to ACTIVE: A. Reopening Exemption.
26. reopening an already-ACTIVE budget is an idempotent no-op: E. reopenBudget declares only ResourceNotFoundException, so ACTIVE to ACTIVE is not an error.
27. a reopened budget accepts writes again: A. Reopening Exemption — reopening restores write permission, not just a field.
28. closePastBudgets closes months strictly before the cutoff and leaves the cutoff month open: A. Automated Period Closure — "month < current_month".
29. closePastBudgets returns the number of budgets it transitioned: E. closePastBudgets @return — the count actually transitioned.
30. closePastBudgets is idempotent — a second run transitions nothing: A. Automated Period Closure — the monthly scheduler may be retried.
31. reopenBudget on an unknown budget id is a 404-class failure: E. reopenBudget @throws ResourceNotFoundException.
32. full lifecycle: past-period budget is writable, then closed, then reopened, then writable again: A. Modification Guard + Immutability upon Closure + Reopening Exemption, end to end.

--- BudgetMonetaryConstraintIT (6) ---
33. a negative limit is rejected: B. Range Constraint — limitAmount must be >= 0.00.
34. a limit one cent above the upper bound is rejected: B. Range Constraint — limitAmount must be <= 999,999,999.99.
35. a limit with three decimal places is rejected rather than rounded: B. Monetary Precision & Scale — reject 10.005, never silently round.
36. a limit with three decimal places is rejected even when the extra digits are zeros: B. Monetary Precision & Scale — a genuine scale check, not a value-equality check.
37. a null limit is rejected as a validation failure: B. Range Constraint — must surface as InvalidBudgetException, not an NPE or DB error.
38. a wildly out-of-range limit is rejected by the application, not by the database: B. Range Constraint — enforced in the app, not left to DECIMAL(15,2).

--- BudgetPeriodNormalizationIT (5) ---
39. a mid-month date is normalized to the first of that month: B. Normalization Rule — LocalDate.withDayOfMonth(1).
40. two different days in the same month address one and the same budget: A. Period Selection & Upsert Behavior — same month means update, not duplicate.
41. the persisted effective_month column holds the first of the month: B. Normalization Rule — normalization happens "before persistence".
42. at 23:59:59 on the last day of July, August is still a future period and spends nothing: A. Spend Amount Initialization — future periods initialize spentAmount to 0.00.
43. closePastBudgets treats December as before the following January: A. Automated Period Closure across a year boundary.

--- BudgetPersistenceIT (5) ---
44. a newly created budget is stored with status ACTIVE: A. State Initialization + C. Data Impacts, asserted at the column not the returned object.
45. closeBudget persists CLOSED to the status column: A. Manual Close + C. Data Impacts — the transition is durable.
46. an update rejected for one invalid line leaves the previously stored lines untouched: B. Constraints — no partial write on a rejected update.
47. a rejected creation persists neither a budget row nor any line rows: B. Constraints — no phantom budget after a rejected create.
48. an empty budget is stored as a budget row with zero line rows: A. Template Inheritance — lines = [] with status ACTIVE is a real persisted budget.

--- BudgetSpendEnrichmentIT (2) ---
49. each line reports the spending of its own category, not a shared monthly total: A. Spend Amount Initialization — "matching each line item's category".
50. spending in an unbudgeted category is not attributed to another line: A. Spend Amount Initialization — per-category, not per-month.

--- BudgetTenancyIT (4) ---
51. reopening another user's budget fails as not-found, not as forbidden: E. reopenBudget — "does not exist or belong to the user".
52. closing another user's budget fails as not-found: E. closeBudget — the same scoping rule on the other transition.
53. a rejected cross-tenant close leaves the other user's budget untouched: E. tenancy scoping must be effective, not merely reported.
54. closePastBudgets closes elapsed budgets belonging to every user: A. Automated Period Closure is system-wide, not a per-tenant query.

--- BudgetYearListingIT (15) — A.2 Get Budgets ---
55. every budget the user holds in the requested year is returned: A.2 Budgets in a year — "all budgets created within a year for the user".
56. budgets are ordered most recent month first: A.2 Ordering — descending effectiveMonth, so the caller renders a reverse-chronological list without re-sorting.
57. the year window includes January and December and excludes the adjacent months: A.2 Year Boundary — [YYYY-01-01, YYYY-12-01] inclusive; an exclusive upper bound silently drops December.
58. a year the user has no budgets in returns an empty list, never null: A.2 Pure Read — an empty year is an empty list, not an error and not twelve new rows.
59. listing a year creates no budgets: A.2 Pure Read — the load-bearing test; a listing built by looping getBudgetForMonth over twelve months passes every other assertion and fails here.
60. another user's budgets in the same year are not returned: A.2 Tenant Scoping.
61. listed budgets carry per-line spentAmount for elapsed periods: A.2 Spend Enrichment + A.1 Spend Amount Initialization.
62. a listed future-period budget reports 0.00 spent: A.2 Spend Enrichment — the future half of the same rule.
63. the listing reports each budget's own status: A.2 Get Budgets — what lets a client label elapsed periods CLOSED without opening each month in turn.
64. a year outside [1970, 9999] is rejected as a validation failure: E. getBudgetsForYear @throws InvalidBudgetException — a bad year is a client error, not an empty result that looks like success.
65. a null userId is rejected as a validation failure: E. getBudgetsForYear @throws InvalidBudgetException.
66. GET ?year= responds 200 OK with the year's budgets as a JSON array: D. Endpoints — GET /api/v1/budgets?year={YYYY}.
67. GET ?year= for a year with no budgets responds 200 OK with an empty array: D. Success Responses — "never 404".
68. GET with a non-numeric year responds 400 Bad Request: D. Error Mappings — 400 for a non-numeric year.
69. GET with an out-of-range year responds 400 Bad Request: D. Error Mappings — 400 for a year outside [1970, 9999].

--- BudgetDeletionIT (15) — A.3 Delete Budget ---
70. an ACTIVE budget is deleted: A.3 — "the user can delete a monthly 'ACTIVE' budget".
71. deleting a CLOSED budget is rejected with HistoricalBudgetException: A.3 Deletion Guard — 422, consistent with A.1 Immutability upon Closure.
72. a rejected deletion leaves the CLOSED budget and its lines intact: A.3 Deletion Guard — the rejection must be effective, not merely thrown.
73. a reopened budget can be deleted: A.3 Deletion Guard + A.1 Reopening Exemption — reopening restores write permission, deletion included.
74. an ACTIVE budget for a past period is deletable: A.3 Deletion Guard keys off status, not off the month having elapsed; a month-based guard passes tests above and fails here.
75. deleting a budget removes its line items: A.3 Cascade — no orphaned budget_lines may remain.
76. deleting a budget leaves the user's transactions untouched: A.3 Orphaned Transaction Handling — a budget is a ceiling, not a container.
77. deleting another user's budget is a 404-class failure and leaves it intact: A.3 Ownership — "does not exist" and "is not yours" must be indistinguishable.
78. deleting an unknown budget id is a 404-class failure: A.3 Ownership.
79. deleting the same budget twice fails the second time: A.3 Non-Idempotent — the second caller is acting on a stale view.
80. a deleted month can be budgeted again from scratch: A.3 + A.1 Period Selection — deletion frees the unique (user_id, effective_month) slot.
81. DELETE /{id} responds 204 No Content with an empty body: D. Success Responses — 204 on successful deletion.
82. DELETE on a CLOSED budget responds 422 Unprocessable Entity: D. Error Mappings — 422 for HistoricalBudgetException on deletion.
83. DELETE on an unknown budget responds 404 Not Found: D. Error Mappings — 404 for ResourceNotFoundException.
84. a rejected DELETE is served as application/problem+json with a matching status: RFC 9457 Problem Details applied to A.3's error paths.


=========================
P2P TESTS (28)
=========================

--- BudgetCapacityAndUniquenessIT (2) ---
1. a budget with exactly 50 line items is accepted: B. Constraints — 50 is the maximum permitted, so exactly 50 must succeed.
2. with no template and no lines, an empty ACTIVE budget is created: A. Template Inheritance — from scratch means lines = [] with status ACTIVE.

--- BudgetInvariantsIT (5) ---
3. applying the same payload twice is idempotent: A. Period Selection & Upsert Behavior — a repeat update converges rather than erroring or accumulating.
4. the caller's list of lines is not mutated: E. upsertBudget contract hygiene — no in-place sorting or de-duplication of the caller's list.
5. mutating the caller's list after the call does not change stored state: E. upsertBudget contract hygiene — persistence is by value, not by reference.
6. line ordering is stable across identical requests: E. Budget return contract — identical requests return identically ordered lines.
7. property: any legal payload is accepted and round-trips exactly: B. Constraints as a property — 1 to 50 lines, [0.00, 999999999.99] at scale 2.

--- BudgetLifecycleIT (2) ---
8. a budget created for the current month initializes ACTIVE: A. State Initialization.
9. a budget created for a future period initializes ACTIVE: A. State Initialization.

--- BudgetMonetaryConstraintIT (4) ---
10. a limit of exactly 0.00 is accepted: B. Range Constraint — the lower bound is inclusive; 0.00 means "budget nothing", not "no budget".
11. a limit of exactly 999999999.99 is accepted: B. Range Constraint — the upper bound is inclusive.
12. a limit with one decimal place is accepted: B. Monetary Precision & Scale — "maximum scale of 2", so fewer decimals is legal.
13. an accepted limit is persisted at its exact value: B. Monetary Precision & Scale — an accepted amount reaches the column intact.

--- BudgetPeriodNormalizationIT (2) ---
14. a leap day normalizes to the first of February: B. Normalization Rule — must not depend on fixed-month-length arithmetic.
15. at midnight on 1 August, August is the current period and its spending is summed: A. Spend Amount Initialization — current periods sum approved transactions.

--- BudgetPersistenceIT (2) ---
16. the database rejects a status value outside ACTIVE and CLOSED: C. Data Impacts — the status CHECK constraint, enforced by the database.
17. an upsert replaces the line set rather than accumulating onto it: E. upsertBudget — lines "establish or overwrite" the budget's whole line set.

--- BudgetSpendEnrichmentIT (9) ---
18. PENDING transactions are not counted: A. Spend Amount Initialization — only "approved" transactions count.
19. transactions flagged is_excluded are not counted: A. Spend Amount Initialization — user-excluded transactions don't consume budget.
20. CREDIT transactions are not counted as spending: A. Spend Amount Initialization — a refund frees budget, it doesn't consume it.
21. a split parent is not counted alongside its children: A. Spend Amount Initialization — no double counting once a transaction is split.
22. a category with no transactions reports 0.00, never null: A. Spend Amount Initialization — spentAmount is non-nullable.
23. category matching between line and transaction is case-insensitive: A. Spend Amount Initialization + REQ-5.2 case-insensitive category matching.
24. the period range includes the first and last day of the month and excludes its neighbours: A. Spend Amount Initialization — "within that period's date range".
25. spentAmount reflects transactions added after the budget was created: A. Spend Amount Initialization — computed per request, never stored.
26. another user's spending in the same category and month is not counted: A. Spend Amount Initialization under multi-tenant scoping.

--- BudgetTenancyIT (1) ---
27. two users hold independent budgets for the same month: A. Period Selection — budget uniqueness is per user account.

--- BudgetYearListingIT (1) — A.2 Get Budgets ---
28. GET ?month= still responds with a single budget object, not an array: D. Endpoints — ?month= and ?year= share one URL, so routing must key off which parameter is present; this pins that adding ?year= did not break the single-month read.