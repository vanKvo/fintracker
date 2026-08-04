=========================
F2P TESTS (54)
=========================

--- GoldenCapacityAndUniquenessIT (5) ---
1. a budget with 51 line items is rejected with LineItemLimitExceededException: B. Constraints — "maximum 50 line items"; one past the ceiling must raise LineItemLimitExceededException (400).
2. a payload containing the same category twice is rejected: B. Category Uniqueness — duplicate category names rejected as validation, not as a raw DB constraint error.
3. categories differing only in case are treated as duplicates: B. Category Uniqueness read with REQ-5.2's case-insensitive category matching.
4. a blank category name is rejected: B. Category Uniqueness / REQ-5.2 Non-Empty Category Name — a category is a line's identity, so blank is invalid.
5. a payload that is both oversized and duplicated is rejected and persists nothing: B. Constraints — rejection must leave no partial write behind.

--- GoldenControllerIT (12) ---
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

--- GoldenInvariantsIT (1) ---
18. a written budget round-trips through the read path unchanged: B. Normalization Rule + A. Period Selection & Upsert Behavior.

--- GoldenLifecycleIT (14) ---
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

--- GoldenMonetaryConstraintIT (6) ---
33. a negative limit is rejected: B. Range Constraint — limitAmount must be >= 0.00.
34. a limit one cent above the upper bound is rejected: B. Range Constraint — limitAmount must be <= 999,999,999.99.
35. a limit with three decimal places is rejected rather than rounded: B. Monetary Precision & Scale — reject 10.005, never silently round.
36. a limit with three decimal places is rejected even when the extra digits are zeros: B. Monetary Precision & Scale — a genuine scale check, not a value-equality check.
37. a null limit is rejected as a validation failure: B. Range Constraint — must surface as InvalidBudgetException, not an NPE or DB error.
38. a wildly out-of-range limit is rejected by the application, not by the database: B. Range Constraint — enforced in the app, not left to DECIMAL(15,2).

--- GoldenPeriodNormalizationIT (5) ---
39. a mid-month date is normalized to the first of that month: B. Normalization Rule — LocalDate.withDayOfMonth(1).
40. two different days in the same month address one and the same budget: A. Period Selection & Upsert Behavior — same month means update, not duplicate.
41. the persisted effective_month column holds the first of the month: B. Normalization Rule — normalization happens "before persistence".
42. at 23:59:59 on the last day of July, August is still a future period and spends nothing: A. Spend Amount Initialization — future periods initialize spentAmount to 0.00.
43. closePastBudgets treats December as before the following January: A. Automated Period Closure across a year boundary.

--- GoldenPersistenceIT (5) ---
44. a newly created budget is stored with status ACTIVE: A. State Initialization + C. Data Impacts, asserted at the column not the returned object.
45. closeBudget persists CLOSED to the status column: A. Manual Close + C. Data Impacts — the transition is durable.
46. an update rejected for one invalid line leaves the previously stored lines untouched: B. Constraints — no partial write on a rejected update.
47. a rejected creation persists neither a budget row nor any line rows: B. Constraints — no phantom budget after a rejected create.
48. an empty budget is stored as a budget row with zero line rows: A. Template Inheritance — lines = [] with status ACTIVE is a real persisted budget.

--- GoldenSpendEnrichmentIT (2) ---
49. each line reports the spending of its own category, not a shared monthly total: A. Spend Amount Initialization — "matching each line item's category".
50. spending in an unbudgeted category is not attributed to another line: A. Spend Amount Initialization — per-category, not per-month.

--- GoldenTenancyIT (4) ---
51. reopening another user's budget fails as not-found, not as forbidden: E. reopenBudget — "does not exist or belong to the user".
52. closing another user's budget fails as not-found: E. closeBudget — the same scoping rule on the other transition.
53. a rejected cross-tenant close leaves the other user's budget untouched: E. tenancy scoping must be effective, not merely reported.
54. closePastBudgets closes elapsed budgets belonging to every user: A. Automated Period Closure is system-wide, not a per-tenant query.


=========================
P2P TESTS (27)
=========================

--- GoldenCapacityAndUniquenessIT (2) ---
1. a budget with exactly 50 line items is accepted: B. Constraints — 50 is the maximum permitted, so exactly 50 must succeed.
2. with no template and no lines, an empty ACTIVE budget is created: A. Template Inheritance — from scratch means lines = [] with status ACTIVE.

--- GoldenInvariantsIT (5) ---
3. applying the same payload twice is idempotent: A. Period Selection & Upsert Behavior — a repeat update converges rather than erroring or accumulating.
4. the caller's list of lines is not mutated: E. upsertBudget contract hygiene — no in-place sorting or de-duplication of the caller's list.
5. mutating the caller's list after the call does not change stored state: E. upsertBudget contract hygiene — persistence is by value, not by reference.
6. line ordering is stable across identical requests: E. Budget return contract — identical requests return identically ordered lines.
7. property: any legal payload is accepted and round-trips exactly: B. Constraints as a property — 1 to 50 lines, [0.00, 999999999.99] at scale 2.

--- GoldenLifecycleIT (2) ---
8. a budget created for the current month initializes ACTIVE: A. State Initialization.
9. a budget created for a future period initializes ACTIVE: A. State Initialization.

--- GoldenMonetaryConstraintIT (4) ---
10. a limit of exactly 0.00 is accepted: B. Range Constraint — the lower bound is inclusive; 0.00 means "budget nothing", not "no budget".
11. a limit of exactly 999999999.99 is accepted: B. Range Constraint — the upper bound is inclusive.
12. a limit with one decimal place is accepted: B. Monetary Precision & Scale — "maximum scale of 2", so fewer decimals is legal.
13. an accepted limit is persisted at its exact value: B. Monetary Precision & Scale — an accepted amount reaches the column intact.

--- GoldenPeriodNormalizationIT (2) ---
14. a leap day normalizes to the first of February: B. Normalization Rule — must not depend on fixed-month-length arithmetic.
15. at midnight on 1 August, August is the current period and its spending is summed: A. Spend Amount Initialization — current periods sum approved transactions.

--- GoldenPersistenceIT (2) ---
16. the database rejects a status value outside ACTIVE and CLOSED: C. Data Impacts — the status CHECK constraint, enforced by the database.
17. an upsert replaces the line set rather than accumulating onto it: E. upsertBudget — lines "establish or overwrite" the budget's whole line set.

--- GoldenSpendEnrichmentIT (9) ---
18. PENDING transactions are not counted: A. Spend Amount Initialization — only "approved" transactions count.
19. transactions flagged is_excluded are not counted: A. Spend Amount Initialization — user-excluded transactions don't consume budget.
20. CREDIT transactions are not counted as spending: A. Spend Amount Initialization — a refund frees budget, it doesn't consume it.
21. a split parent is not counted alongside its children: A. Spend Amount Initialization — no double counting once a transaction is split.
22. a category with no transactions reports 0.00, never null: A. Spend Amount Initialization — spentAmount is non-nullable.
23. category matching between line and transaction is case-insensitive: A. Spend Amount Initialization + REQ-5.2 case-insensitive category matching.
24. the period range includes the first and last day of the month and excludes its neighbours: A. Spend Amount Initialization — "within that period's date range".
25. spentAmount reflects transactions added after the budget was created: A. Spend Amount Initialization — computed per request, never stored.
26. another user's spending in the same category and month is not counted: A. Spend Amount Initialization under multi-tenant scoping.

--- GoldenTenancyIT (1) ---
27. two users hold independent budgets for the same month: A. Period Selection — budget uniqueness is per user account.