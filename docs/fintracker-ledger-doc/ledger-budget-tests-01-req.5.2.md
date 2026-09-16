=========================
F2P TESTS (33)
=========================

--- BudgetLineServiceIT (14) ---
1. adding a line item persists it under the budget and computes its spentAmount: A. Dynamic Spend Initialization — addLineItem is the entry point that triggers the aggregate lookup, not just a row insert.
2. adding a line for a future period initializes spentAmount to 0.00: A. Dynamic Spend Initialization — "For future periods, spentAmount remains $0.00."
3. a duplicate category (case-insensitive) is rejected with DuplicateCategoryException: A. Category Uniqueness — "Category matching shall be case-insensitive."
4. adding a line item beyond the 50-item ceiling is rejected: B. Line Item Ceiling — a single add must not push the budget past 50 lines.
5. an out-of-range limitAmount is rejected: B. Range Constraint for limitAmount — [0.00, 999,999,999.99] enforced on the granular add path.
6. a limitAmount with more than 2 decimal places is rejected, not rounded: B. Monetary Precision & Scale Constraint — reject 10.005, never silently round.
7. adding a line item to a CLOSED budget is rejected with HistoricalBudgetException: A. State Check Guard — "Line item modifications are permitted only if the parent budget's status == 'ACTIVE'."
8. adding a line item to another user's budget is not found: E. addLineItem @throws ResourceNotFoundException — "If the budgetId does not exist or belong to the user."
9. updating a line item's limit persists the new value and recomputes spentAmount: E. updateLineItemLimit — a wholly new granular capability, not exercised by REQ-5.1's whole-budget upsert.
10. updating a non-existent line item is not found: E. updateLineItemLimit @throws ResourceNotFoundException — "If budgetId or lineId does not exist or belong to user."
11. updating a line item on a CLOSED budget is rejected with HistoricalBudgetException: A. State Check Guard applied to the update path.
12. removing a line item deletes it but leaves the underlying transactions untouched: A. Orphaned Transaction Handling — "does not alter or delete underlying user transactions."
13. removing a line item from a CLOSED budget is rejected with HistoricalBudgetException: A. State Check Guard applied to the remove path.
14. removing a non-existent line item is not found: E. removeLineItem @throws ResourceNotFoundException.

--- BudgetLineControllerIT (13) ---
15. POST /lines adding a new line item responds 201 Created: D. Success Responses — "201 CREATED — Line item added successfully."
16. POST /lines with a duplicate category responds 409 Conflict: D. Error Mapping — "409 CONFLICT — DuplicateCategoryException."
17. POST /lines with an out-of-range limitAmount responds 400 Bad Request: D. Error Mapping — "400 BAD REQUEST — InvalidBudgetException."
18. POST /lines on a CLOSED budget responds 422 Unprocessable Entity: D. Error Mapping — "422 UNPROCESSABLE ENTITY — HistoricalBudgetException."
19. POST /lines against an unknown budget responds 404 Not Found: D. Error Mapping — "404 NOT FOUND — budgetId or lineId not found."
20. PUT /lines/{lineId} updating a limit responds 200 OK: D. Success Responses — "200 OK — Line item updated ... successfully."
21. PUT /lines/{lineId} against an unknown line responds 404 Not Found: D. Error Mapping applied to the update endpoint.
22. DELETE /lines/{lineId} removing a line item responds 200 OK: D. Success Responses — "200 OK — Line item ... deleted successfully."
23. DELETE /lines/{lineId} on a CLOSED budget responds 422 Unprocessable Entity: D. Error Mapping applied to the delete endpoint.
24. DELETE /lines/{lineId} against an unknown line responds 404 Not Found: D. Error Mapping applied to the delete endpoint.
25. PUT /lines/{lineId} on a CLOSED budget responds 422 Unprocessable Entity, served as application/problem+json: D. Error Mapping — the update endpoint had only service-level guard coverage before; this closes the REST-layer gap, RFC 9457 included.
26. PUT /lines/{lineId} with an out-of-range limitAmount responds 400 Bad Request, served as application/problem+json: D. Error Mapping — the update endpoint's monetary validation had no controller-level assertion before.
27. POST /lines with a blank category responds 400 Bad Request: B. Non-Empty Category Name — "Category names must be non-null, non-blank" mapped to the REST boundary.

--- BudgetLineBoundaryAndTenancyIT (6) ---
28. a limitAmount one cent above the upper bound is rejected: B. Range Constraint for limitAmount — the upper edge, not just a mid-range negative value.
29. a blank category name is rejected, not silently dropped: B. Non-Empty Category Name — "must be non-null, non-blank."
30. updating a line item to an out-of-range limitAmount is rejected and leaves the original value intact: B. Range Constraint — a rejected update must not partially apply.
31. updating a line item to a limitAmount with more than 2 decimal places is rejected, not rounded: B. Monetary Precision & Scale Constraint — the update path had no scale-violation coverage before.
32. updating a line item on another user's budget is not found, not a silent no-op: E. updateLineItemLimit @throws ResourceNotFoundException — tenancy scoping, previously only asserted for addLineItem.
33. removing a line item from another user's budget is not found, not a silent no-op: E. removeLineItem @throws ResourceNotFoundException — tenancy scoping, previously only asserted for addLineItem.


=========================
P2P TESTS (6)
=========================

--- BudgetLineServiceIT (1) ---
1. a category longer than 50 characters is truncated, not rejected: B. Non-Empty Category Name — "truncated to a maximum length of 50 characters," an accept-path normalization, not a rejection.

--- BudgetLineBoundaryAndTenancyIT (5) ---
2. a limitAmount of exactly 0.00 (inclusive lower bound) is accepted: B. Range Constraint for limitAmount — the lower bound is inclusive; 0.00 means "cap this category at nothing," not "no line."
3. a limitAmount of exactly 999,999,999.99 (inclusive upper bound) is accepted: B. Range Constraint for limitAmount — the upper bound is inclusive.
4. adding the 50th line item onto a budget already holding 49 succeeds: B. Line Item Ceiling — "must not cause total budget lines to exceed 50," so exactly 50 must succeed.
5. the same category name is allowed on two different budget periods for the same user: A. Category Uniqueness — "within the same budget period" scopes uniqueness per budget instance, not per user.
6. a category freed up by removal can be re-added within the same budget: A. Orphaned Transaction Handling / Granular Line Operations — a deleted line's category is not permanently reserved.
