> **Tests for:** [LG-BUD-budgets-spec.md](LG-BUD-budgets-spec.md) · **Formerly:** `ledger-budget-tests-01-req.5.1.md`, `-req.5.2.md`, `-req.5.3.md` (merged 2026-10)

=========================
F2P TESTS (199)
=========================

--- BudgetCapacityAndUniquenessIT (4) ---
1. a budget with 51 line items is rejected with LineItemLimitExceededException: B. Constraints — "maximum 50 line items"; one past the ceiling must raise LineItemLimitExceededException (400).
2. a payload containing the same category twice is rejected: B. Category Uniqueness — duplicate category names rejected as validation, not as a raw DB constraint error.
3. a missing categoryId is rejected: B. Category Uniqueness / LG-BUD-02 Non-Empty Category Name — a category is a line's identity, so a line without one is invalid (LG-BUD-05).
4. a payload that is both oversized and duplicated is rejected and persists nothing: B. Constraints — rejection must leave no partial write behind.

--- BudgetControllerIT (12) ---
5. PUT creating a brand new budget responds 201 Created: D. Success Responses — 201 for a brand new monthly budget.
6. PUT updating an existing budget responds 200 OK: D. Success Responses — 200 when an existing monthly budget is updated.
7. POST /{id}/close responds 200 OK and reports the budget as CLOSED: D. Endpoints (POST /budgets/{id}/close) + A. Manual Close.
8. POST /{id}/reopen responds 200 OK and reports the budget as ACTIVE: D. Endpoints (POST /budgets/{id}/reopen) + A. Reopening Exemption.
9. writing to a CLOSED budget responds 422 Unprocessable Entity: D. Error Mappings — 422 for HistoricalBudgetException.
10. an out-of-range limit responds 400 Bad Request: D. Error Mappings — 400 for InvalidBudgetException.
11. error responses are served as application/problem+json: RFC 9457 Problem Details applied to LG-BUD-01's error paths.
12. the problem document carries type, title and a status matching the HTTP status: RFC 9457 well-formedness.
13. an error response never leaks a stack trace: GlobalExceptionHandler contract, tested at LG-BUD-01's new exception types.
14. status is serialized as its name, not as an ordinal: C. Data Impacts — status is a named two-valued state on the wire.
15. closing an unknown budget responds 404 Not Found: E. Interface Details — ResourceNotFoundException when the budget doesn't exist or isn't the user's.
16. the response reports the normalized effective month: B. Normalization Rule, observed at the API boundary.

--- BudgetInvariantsIT (1) ---
17. a written budget round-trips through the read path unchanged: B. Normalization Rule + A. Period Selection & Upsert Behavior.

--- BudgetLifecycleIT (14) ---
18. a budget created for a past period initializes ACTIVE: A. State Initialization — past, present and future all start ACTIVE.
19. an ACTIVE budget for a past period can still be updated: A. Modification Guard — writes keyed on status, not on the month having elapsed.
20. closeBudget transitions ACTIVE to CLOSED: A. Manual Close.
21. closing an already-CLOSED budget is rejected with HistoricalBudgetException: E. closeBudget @throws HistoricalBudgetException if already CLOSED.
22. upserting into a CLOSED budget is rejected with HistoricalBudgetException: A. Immutability upon Closure.
23. a write rejected by the CLOSED guard leaves the stored lines unchanged: A. Immutability upon Closure — the rejection must be effective, not merely thrown.
24. reopenBudget transitions CLOSED back to ACTIVE: A. Reopening Exemption.
25. reopening an already-ACTIVE budget is an idempotent no-op: E. reopenBudget declares only ResourceNotFoundException, so ACTIVE to ACTIVE is not an error.
26. a reopened budget accepts writes again: A. Reopening Exemption — reopening restores write permission, not just a field.
27. closePastBudgets closes months strictly before the cutoff and leaves the cutoff month open: A. Automated Period Closure — "month < current_month".
28. closePastBudgets returns the number of budgets it transitioned: E. closePastBudgets @return — the count actually transitioned.
29. closePastBudgets is idempotent — a second run transitions nothing: A. Automated Period Closure — the monthly scheduler may be retried.
30. reopenBudget on an unknown budget id is a 404-class failure: E. reopenBudget @throws ResourceNotFoundException.
31. full lifecycle: past-period budget is writable, then closed, then reopened, then writable again: A. Modification Guard + Immutability upon Closure + Reopening Exemption, end to end.

--- BudgetMonetaryConstraintIT (6) ---
32. a negative limit is rejected: B. Range Constraint — limitAmount must be >= 0.00.
33. a limit one cent above the upper bound is rejected: B. Range Constraint — limitAmount must be <= 999,999,999.99.
34. a limit with three decimal places is rejected rather than rounded: B. Monetary Precision & Scale — reject 10.005, never silently round.
35. a limit with three decimal places is rejected even when the extra digits are zeros: B. Monetary Precision & Scale — a genuine scale check, not a value-equality check.
36. a null limit is rejected as a validation failure: B. Range Constraint — must surface as InvalidBudgetException, not an NPE or DB error.
37. a wildly out-of-range limit is rejected by the application, not by the database: B. Range Constraint — enforced in the app, not left to DECIMAL(15,2).

--- BudgetPeriodNormalizationIT (5) ---
38. a mid-month date is normalized to the first of that month: B. Normalization Rule — LocalDate.withDayOfMonth(1).
39. two different days in the same month address one and the same budget: A. Period Selection & Upsert Behavior — same month means update, not duplicate.
40. the persisted effective_month column holds the first of the month: B. Normalization Rule — normalization happens "before persistence".
41. at 23:59:59 on the last day of July, August is still a future period and spends nothing: A. Spend Amount Initialization — future periods initialize spentAmount to 0.00.
42. closePastBudgets treats December as before the following January: A. Automated Period Closure across a year boundary.

--- BudgetPersistenceIT (5) ---
43. a newly created budget is stored with status ACTIVE: A. State Initialization + C. Data Impacts, asserted at the column not the returned object.
44. closeBudget persists CLOSED to the status column: A. Manual Close + C. Data Impacts — the transition is durable.
45. an update rejected for one invalid line leaves the previously stored lines untouched: B. Constraints — no partial write on a rejected update.
46. a rejected creation persists neither a budget row nor any line rows: B. Constraints — no phantom budget after a rejected create.
47. an empty budget is stored as a budget row with zero line rows: A. Template Inheritance — lines = [] with status ACTIVE is a real persisted budget.

--- BudgetSpendEnrichmentIT (2) ---
48. each line reports the spending of its own category, not a shared monthly total: A. Spend Amount Initialization — "matching each line item's category".
49. spending in an unbudgeted category is not attributed to another line: A. Spend Amount Initialization — per-category, not per-month.

--- BudgetTenancyIT (4) ---
50. reopening another user's budget fails as not-found, not as forbidden: E. reopenBudget — "does not exist or belong to the user".
51. closing another user's budget fails as not-found: E. closeBudget — the same scoping rule on the other transition.
52. a rejected cross-tenant close leaves the other user's budget untouched: E. tenancy scoping must be effective, not merely reported.
53. closePastBudgets closes elapsed budgets belonging to every user: A. Automated Period Closure is system-wide, not a per-tenant query.

--- BudgetYearListingIT (15) — A.2 Get Budgets ---
54. every budget the user holds in the requested year is returned: A.2 Budgets in a year — "all budgets created within a year for the user".
55. budgets are ordered most recent month first: A.2 Ordering — descending effectiveMonth, so the caller renders a reverse-chronological list without re-sorting.
56. the year window includes January and December and excludes the adjacent months: A.2 Year Boundary — [YYYY-01-01, YYYY-12-01] inclusive; an exclusive upper bound silently drops December.
57. a year the user has no budgets in returns an empty list, never null: A.2 Pure Read — an empty year is an empty list, not an error and not twelve new rows.
58. listing a year creates no budgets: A.2 Pure Read — the load-bearing test; a listing built by looping getBudgetForMonth over twelve months passes every other assertion and fails here.
59. another user's budgets in the same year are not returned: A.2 Tenant Scoping.
60. listed budgets carry per-line spentAmount for elapsed periods: A.2 Spend Enrichment + A.1 Spend Amount Initialization.
61. a listed future-period budget reports 0.00 spent: A.2 Spend Enrichment — the future half of the same rule.
62. the listing reports each budget's own status: A.2 Get Budgets — what lets a client label elapsed periods CLOSED without opening each month in turn.
63. a year outside [1970, 9999] is rejected as a validation failure: E. getBudgetsForYear @throws InvalidBudgetException — a bad year is a client error, not an empty result that looks like success.
64. a null userId is rejected as a validation failure: E. getBudgetsForYear @throws InvalidBudgetException.
65. GET ?year= responds 200 OK with the year's budgets as a JSON array: D. Endpoints — GET /api/v1/budgets?year={YYYY}.
66. GET ?year= for a year with no budgets responds 200 OK with an empty array: D. Success Responses — "never 404".
67. GET with a non-numeric year responds 400 Bad Request: D. Error Mappings — 400 for a non-numeric year.
68. GET with an out-of-range year responds 400 Bad Request: D. Error Mappings — 400 for a year outside [1970, 9999].

--- BudgetDeletionIT (15) — A.3 Delete Budget ---
69. an ACTIVE budget is deleted: A.3 — "the user can delete a monthly 'ACTIVE' budget".
70. deleting a CLOSED budget is rejected with HistoricalBudgetException: A.3 Deletion Guard — 422, consistent with A.1 Immutability upon Closure.
71. a rejected deletion leaves the CLOSED budget and its lines intact: A.3 Deletion Guard — the rejection must be effective, not merely thrown.
72. a reopened budget can be deleted: A.3 Deletion Guard + A.1 Reopening Exemption — reopening restores write permission, deletion included.
73. an ACTIVE budget for a past period is deletable: A.3 Deletion Guard keys off status, not off the month having elapsed; a month-based guard passes tests above and fails here.
74. deleting a budget removes its line items: A.3 Cascade — no orphaned budget_lines may remain.
75. deleting a budget leaves the user's transactions untouched: A.3 Orphaned Transaction Handling — a budget is a ceiling, not a container.
76. deleting another user's budget is a 404-class failure and leaves it intact: A.3 Ownership — "does not exist" and "is not yours" must be indistinguishable.
77. deleting an unknown budget id is a 404-class failure: A.3 Ownership.
78. deleting the same budget twice fails the second time: A.3 Non-Idempotent — the second caller is acting on a stale view.
79. a deleted month can be budgeted again from scratch: A.3 + A.1 Period Selection — deletion frees the unique (user_id, effective_month) slot.
80. DELETE /{id} responds 204 No Content with an empty body: D. Success Responses — 204 on successful deletion.
81. DELETE on a CLOSED budget responds 422 Unprocessable Entity: D. Error Mappings — 422 for HistoricalBudgetException on deletion.
82. DELETE on an unknown budget responds 404 Not Found: D. Error Mappings — 404 for ResourceNotFoundException.
83. a rejected DELETE is served as application/problem+json with a matching status: RFC 9457 Problem Details applied to A.3's error paths.

--- BudgetLineServiceIT (14) ---
84. adding a line item persists it under the budget and computes its spentAmount: A. Dynamic Spend Initialization — addLineItem is the entry point that triggers the aggregate lookup, not just a row insert.
85. adding a line for a future period initializes spentAmount to 0.00: A. Dynamic Spend Initialization — "For future periods, spentAmount remains $0.00."
86. a duplicate categoryId is rejected with DuplicateCategoryException: A. Category Uniqueness — a category already on the budget cannot be added again (matched by id, LG-BUD-05).
87. adding a line item beyond the 50-item ceiling is rejected: B. Line Item Ceiling — a single add must not push the budget past 50 lines.
88. an out-of-range limitAmount is rejected: B. Range Constraint for limitAmount — [0.00, 999,999,999.99] enforced on the granular add path.
89. a limitAmount with more than 2 decimal places is rejected, not rounded: B. Monetary Precision & Scale Constraint — reject 10.005, never silently round.
90. adding a line item to a CLOSED budget is rejected with HistoricalBudgetException: A. State Check Guard — "Line item modifications are permitted only if the parent budget's status == 'ACTIVE'."
91. adding a line item to another user's budget is not found: E. addLineItem @throws ResourceNotFoundException — "If the budgetId does not exist or belong to the user."
92. updating a line item's limit persists the new value and recomputes spentAmount: E. updateLineItemLimit — a wholly new granular capability, not exercised by LG-BUD-01's whole-budget upsert.
93. updating a non-existent line item is not found: E. updateLineItemLimit @throws ResourceNotFoundException — "If budgetId or lineId does not exist or belong to user."
94. updating a line item on a CLOSED budget is rejected with HistoricalBudgetException: A. State Check Guard applied to the update path.
95. removing a line item deletes it but leaves the underlying transactions untouched: A. Orphaned Transaction Handling — "does not alter or delete underlying user transactions."
96. removing a line item from a CLOSED budget is rejected with HistoricalBudgetException: A. State Check Guard applied to the remove path.
97. removing a non-existent line item is not found: E. removeLineItem @throws ResourceNotFoundException.

--- BudgetLineControllerIT (13) ---
98. POST /lines adding a new line item responds 201 Created: D. Success Responses — "201 CREATED — Line item added successfully."
99. POST /lines with a duplicate category responds 409 Conflict: D. Error Mapping — "409 CONFLICT — DuplicateCategoryException."
100. POST /lines with an out-of-range limitAmount responds 400 Bad Request: D. Error Mapping — "400 BAD REQUEST — InvalidBudgetException."
101. POST /lines on a CLOSED budget responds 422 Unprocessable Entity: D. Error Mapping — "422 UNPROCESSABLE ENTITY — HistoricalBudgetException."
102. POST /lines against an unknown budget responds 404 Not Found: D. Error Mapping — "404 NOT FOUND — budgetId or lineId not found."
103. PUT /lines/{lineId} updating a limit responds 200 OK: D. Success Responses — "200 OK — Line item updated ... successfully."
104. PUT /lines/{lineId} against an unknown line responds 404 Not Found: D. Error Mapping applied to the update endpoint.
105. DELETE /lines/{lineId} removing a line item responds 200 OK: D. Success Responses — "200 OK — Line item ... deleted successfully."
106. DELETE /lines/{lineId} on a CLOSED budget responds 422 Unprocessable Entity: D. Error Mapping applied to the delete endpoint.
107. DELETE /lines/{lineId} against an unknown line responds 404 Not Found: D. Error Mapping applied to the delete endpoint.
108. PUT /lines/{lineId} on a CLOSED budget responds 422 Unprocessable Entity, served as application/problem+json: D. Error Mapping — the update endpoint had only service-level guard coverage before; this closes the REST-layer gap, RFC 9457 included.
109. PUT /lines/{lineId} with an out-of-range limitAmount responds 400 Bad Request, served as application/problem+json: D. Error Mapping — the update endpoint's monetary validation had no controller-level assertion before.
110. POST /lines without a categoryId responds 400 Bad Request: B. Non-Empty Category Name — a line must name a category (LG-BUD-05).

--- BudgetLineBoundaryAndTenancyIT (6) ---
111. a limitAmount one cent above the upper bound is rejected: B. Range Constraint for limitAmount — the upper edge, not just a mid-range negative value.
112. a missing categoryId is rejected, not silently dropped: B. Non-Empty Category Name — a line must name a category (LG-BUD-05).
113. updating a line item to an out-of-range limitAmount is rejected and leaves the original value intact: B. Range Constraint — a rejected update must not partially apply.
114. updating a line item to a limitAmount with more than 2 decimal places is rejected, not rounded: B. Monetary Precision & Scale Constraint — the update path had no scale-violation coverage before.
115. updating a line item on another user's budget is not found, not a silent no-op: E. updateLineItemLimit @throws ResourceNotFoundException — tenancy scoping, previously only asserted for addLineItem.
116. removing a line item from another user's budget is not found, not a silent no-op: E. removeLineItem @throws ResourceNotFoundException — tenancy scoping, previously only asserted for addLineItem.

--- BudgetTemplateCatalogIT (13) ---
117. system templates are visible to every user: A. System & Custom Template Availability — is_system = true templates belong to no user and must be readable by all. The load-bearing RLS test: the V3 isolation predicate `user_id = current_setting(...)` evaluates NULL (false) for every system template, so a policy copied from any other table leaves the catalog permanently and silently empty.
118. a system template reports isSystem true and no owner: F.1 — user_id NULL is the ownership signal; is_system is its denormalized twin, held in sync by chk_budget_templates_system_ownership.
119. a user's own custom templates appear in their catalog: A. System & Custom Template Availability — is_system = false templates are user-owned.
120. another user's custom template is not in the catalog: A. Template Isolation — a custom template belongs to exactly one user; widening SELECT for system templates must not widen it for custom ones.
121. fetching another user's custom template is a 404-class failure: E. getTemplateById @throws ResourceNotFoundException "does not exist or user lacks access" — one answer for both, so a probe cannot confirm an invisible template exists.
122. fetching an unknown template is a 404-class failure: E. getTemplateById @throws ResourceNotFoundException.
123. a fetched template carries its line items with category and default limit: E. getTemplateById — "the detailed template DTO including line item definitions".
124. a template with no lines reports an empty list, never null: E. — lines is a collection, never absent.
125. a template at the 50-line ceiling is returned in full: B. Template Limit Ceiling — 50 is the maximum permitted, so exactly 50 must round-trip.
126. a user with no custom templates still sees the system catalog: A. — the system catalog is the onboarding path; every returned row is either system or the caller's own.
127. GET /budget-templates responds 200 OK with the visible catalog: D. Endpoints.
128. GET /budget-templates/{id} responds 200 OK with the template's lines: D. Endpoints + Success Responses (200 OK).
129. GET /budget-templates/{id} for an unknown template responds 404 from the endpoint, not the router: D. Error Mapping (404 ResourceNotFoundException). Asserts the RFC 9457 problem *type* is `resource-not-found`, not merely the status: with no controller mounted the path 404s anyway as `endpoint-not-found`, so a bare status assertion passed for entirely the wrong reason.

--- BudgetQuickStartIT (23) ---
130. a budget instantiated from a template carries the template's categories and limits: A. Template Line Item Pre-Population.
131. an instantiated budget is ACTIVE and normalized to the first of the month: LG-BUD-01 State Initialization + Normalization Rule apply to a templated budget like any other.
132. editing an instantiated budget's line does not change the template: A. Template Isolation — "actions on instantiated budgets never mutate the source template".
133. removing a line from an instantiated budget does not remove it from the template: A. Template Isolation, on the delete path.
134. a budget created from a template is unaffected by later template changes: A. Copy-on-Instantiate — the reverse direction, and the one an implementation storing a template reference instead of copying fails after passing every shallow assertion.
135. two users instantiating the same system template get independent budgets: A. Template Isolation — one shared source, two independent copies with disjoint line identities.
136. an override for a new category is appended to the template's lines: A. Template Line Item Overrides — "append".
137. an override for a template category adjusts its limit rather than duplicating it: A. Template Line Item Overrides — "adjust baseline template values".
138. an override matches a template category by categoryId: A. Overrides read with LG-BUD-02 Category Uniqueness — a merge must not produce two lines for one category (LG-BUD-05).
139. with no templateId the lines are cloned from the most recent active budget: E. instantiateQuickStartBudget — "If request.getTemplateId() is null, lines are cloned from the user's most recent active budget" (Previous Month Rollover).
140. with no templateId and no prior budget an empty ACTIVE budget is created: E. + LG-BUD-01 Template Inheritance — from scratch means lines = [] with status ACTIVE.
141. inherited lines are enriched with spend for a current period: A. Template Line Item Pre-Population — current/past periods sum approved transactions per category.
142. inherited lines report 0.00 spent for a future period: A. Template Line Item Pre-Population — "For future periods, spentAmount initializes to $0.00".
143. template lines plus overrides exceeding 50 is rejected: B. Target Line Ceiling — "merging template items with explicit user override items must not cause total lines to exceed 50".
144. template lines plus overrides totalling exactly 50 is accepted: B. Target Line Ceiling — the accepting side of the boundary. Added after a mutation check: rejecting at exactly 50 (`>=` where `>` was meant) was caught by 0 of the original 34 tests.
145. an override adjusting an existing category does not push a 50-line template over the ceiling: B. Target Line Ceiling — the merged result is what counts, not template lines + override count; the two agree everywhere except here.
146. a rejected instantiation persists no budget: B. Target Line Ceiling — the rejection must be effective; a rejected merge leaves no partial budget behind.
147. instantiating from an unknown template is a 404-class failure: D. Error Mapping (404 NOT FOUND).
148. instantiating from another user's custom template is a 404-class failure: D. Error Mapping + A. Template Isolation under multi-tenancy.
149. instantiating into a month whose budget is CLOSED is rejected: D. Error Mapping (422 HistoricalBudgetException) + LG-BUD-01 Immutability upon Closure.
150. POST /budgets/quick-start responds 201 Created with the instantiated budget: D. Success Responses — "201 CREATED — Successfully instantiated budget from template".
151. POST /budgets/quick-start with an unknown template responds 404: D. Error Mapping at the HTTP boundary.
152. POST /budgets/quick-start with a 3-decimal override responds 400: D. Error Mapping — "400 BAD REQUEST — Invalid monetary precision (InvalidBudgetException)"; LG-BUD-01 B forbids silent rounding.

--- BudgetTemplateCreationIT (23) — A. Custom Template Creation ---
153. a saved template is owned by its creator and is not a system template: A. Custom Template Creation — creation must never be able to produce a globally-visible template.
154. a saved template appears in its owner's catalog and nobody else's: A. + Template Isolation, verified from both sides of the tenancy boundary.
155. reusing a name is rejected with DuplicateTemplateException: B. Template Name Uniqueness.
156. a name differing only in case is a duplicate: B. — "unique per user account (case-insensitive)".
157. a name differing only in surrounding whitespace is a duplicate: B. — whitespace is not a distinguishing feature of a name; without stripping, "  Plan  " and "Plan" become two templates.
158. two different users may each hold a template with the same name: B. — the uniqueness scope is the account, so this must NOT be rejected. The counterweight to 37-39: an implementation using a global unique index passes those three and fails here.
159. a rejected duplicate persists nothing: B. — the rejection must be effective, not merely thrown.
160. a template with exactly 50 lines is accepted: B. Template Limit Ceiling — 50 is the maximum permitted.
161. a template with 51 lines is rejected: B. — one past the ceiling.
162. a template rejected for size persists nothing: B. — no partial write survives the rejection.
163. a blank name is rejected as a validation failure: A. — non-blank name.
164. duplicate categories within one template are rejected: B. Template category uniqueness, matching LG-BUD-02 (by categoryId, LG-BUD-05).
165. a defaultLimit with three decimal places is rejected rather than rounded: B. Range Constraint + LG-BUD-01 B Monetary Precision & Scale — a template default obeys the same rule as a live ceiling.
166. a negative defaultLimit is rejected: B. Range Constraint — lower bound.
167. a defaultLimit of exactly 999999999.99 is accepted: B. Range Constraint — the upper bound is inclusive.
168. a template with no lines is accepted and reports an empty list: A. — an empty template is a legitimate starting point.
169. the supplied line list is not mutated by the service: invariant — the caller's list is an input, not storage the service may edit.
170. POST /budget-templates responds 201 Created with the saved template: D. Success Responses.
171. POST /budget-templates with a duplicate name responds 409 Conflict: D. Error Mapping — 409 DuplicateTemplateException.
172. POST /budget-templates with a blank name responds 400 Bad Request: D. Error Mapping — 400 InvalidBudgetException.
173. saving from a source budget copies that budget's own allocations: F.3b — allocations are read server-side from sourceBudgetId, never taken from the request body.
174. saving from another user's budget responds 404 and stores nothing: F.3b + tenancy — a source budget the caller does not own must neither be readable nor partially copied.
175. a budget saved as a template reproduces its allocations when instantiated: round-trip identity across create -> catalog -> quick-start, exercising the three endpoints as one chain.

--- BudgetCategoryIdMatchingIT (24) ---
176. spend counts a transaction by its categoryId even when its category text differs: LG-BUD-05 Updating Budget feature to use categoryId.
177. a transaction with the same category text but another categoryId is not counted: LG-BUD-05.
178. a transaction with no categoryId is not counted even if its text matches: LG-BUD-05.
179. a year listing matches spend by categoryId: LG-BUD-05.
180. adding a line item computes its spend by categoryId: LG-BUD-05.
181. a saved line exposes its categoryId and the category's display name: LG-BUD-05/#4.
182. a saved line is stored against the category's id: LG-BUD-05 Budget feature update (Data Contracts).
183. the same categoryId twice in one payload is rejected as a duplicate: LG-BUD-05.
184. budget_lines.category_id is a real foreign key to categories: LG-BUD-05 Budget feature update (Data Contracts).
185. renaming a category shows the new name on the budget line and keeps its spend: #7/LG-BUD-05.
186. a new category may take a name a renamed category used to have: #7/LG-BUD-05.
187. a user can budget their own custom category: #1/LG-BUD-05.
188. a budget payload with another user's category is not found: #2/LG-BUD-05, Error Handling row c.
189. a budget payload with an unknown categoryId is not found: Error Handling row c.
190. adding a line with another user's category is not found and stores nothing: #2/LG-BUD-05, Error Handling row c.
191. every line of the seeded system templates points at a SYSTEM category: LG-BUD-05 Migration & backfill.
192. a quick-start budget from a system template carries the categories' ids: LG-BUD-05.
193. a custom template stores its lines against the categories' ids: LG-BUD-05.
194. a template line named after a renamed category shows the new name: #7/LG-BUD-05.
195. a template cannot be saved with another user's category: #2/LG-BUD-05.
196. a budget rolled over from the previous month keeps the lines' categoryIds: LG-BUD-05.
197. POST /lines answers with the line's categoryId and display name: LG-BUD-05.
198. POST /lines with only a category name and no categoryId responds 400: LG-BUD-05.
199. POST /lines with another user's categoryId responds 404: Error Handling row c.

=========================
P2P TESTS (32)
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

--- BudgetSpendEnrichmentIT (8) ---
18. PENDING transactions are not counted: A. Spend Amount Initialization — only "approved" transactions count.
19. transactions flagged is_excluded are not counted: A. Spend Amount Initialization — user-excluded transactions don't consume budget.
20. CREDIT transactions are not counted as spending: A. Spend Amount Initialization — a refund frees budget, it doesn't consume it.
21. a split parent is not counted alongside its children: A. Spend Amount Initialization — no double counting once a transaction is split.
22. a category with no transactions reports 0.00, never null: A. Spend Amount Initialization — spentAmount is non-nullable.
23. the period range includes the first and last day of the month and excludes its neighbours: A. Spend Amount Initialization — "within that period's date range".
24. spentAmount reflects transactions added after the budget was created: A. Spend Amount Initialization — computed per request, never stored.
25. another user's spending in the same category and month is not counted: A. Spend Amount Initialization under multi-tenant scoping.

--- BudgetTenancyIT (1) ---
26. two users hold independent budgets for the same month: A. Period Selection — budget uniqueness is per user account.

--- BudgetYearListingIT (1) — A.2 Get Budgets ---
27. GET ?month= still responds with a single budget object, not an array: D. Endpoints — ?month= and ?year= share one URL, so routing must key off which parameter is present; this pins that adding ?year= did not break the single-month read.

--- BudgetLineBoundaryAndTenancyIT (5) ---
28. a limitAmount of exactly 0.00 (inclusive lower bound) is accepted: B. Range Constraint for limitAmount — the lower bound is inclusive; 0.00 means "cap this category at nothing," not "no line."
29. a limitAmount of exactly 999,999,999.99 (inclusive upper bound) is accepted: B. Range Constraint for limitAmount — the upper bound is inclusive.
30. adding the 50th line item onto a budget already holding 49 succeeds: B. Line Item Ceiling — "must not cause total budget lines to exceed 50," so exactly 50 must succeed.
31. the same category name is allowed on two different budget periods for the same user: A. Category Uniqueness — "within the same budget period" scopes uniqueness per budget instance, not per user.
32. a category freed up by removal can be re-added within the same budget: A. Orphaned Transaction Handling / Granular Line Operations — a deleted line's category is not permanently reserved.
