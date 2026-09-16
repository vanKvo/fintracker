=========================
F2P TESTS (59)
=========================

All 59 tests below failed before REQ-5.3 was implemented and pass after it. They failed for two
compounding reasons: the `ledger.budget_templates` / `ledger.budget_template_lines` tables did not
exist (F.1 / F.2 are part of the requirement, not an assumption of the harness), and
`BudgetTemplateService` was a stub. Fixtures write to those tables with a superuser connection so
a bug in the read path cannot mask a bug in the write path.

--- BudgetTemplateCatalogIT (13) ---
1. system templates are visible to every user: A. System & Custom Template Availability — is_system = true templates belong to no user and must be readable by all. The load-bearing RLS test: the V3 isolation predicate `user_id = current_setting(...)` evaluates NULL (false) for every system template, so a policy copied from any other table leaves the catalog permanently and silently empty.
2. a system template reports isSystem true and no owner: F.1 — user_id NULL is the ownership signal; is_system is its denormalized twin, held in sync by chk_budget_templates_system_ownership.
3. a user's own custom templates appear in their catalog: A. System & Custom Template Availability — is_system = false templates are user-owned.
4. another user's custom template is not in the catalog: A. Template Isolation — a custom template belongs to exactly one user; widening SELECT for system templates must not widen it for custom ones.
5. fetching another user's custom template is a 404-class failure: E. getTemplateById @throws ResourceNotFoundException "does not exist or user lacks access" — one answer for both, so a probe cannot confirm an invisible template exists.
6. fetching an unknown template is a 404-class failure: E. getTemplateById @throws ResourceNotFoundException.
7. a fetched template carries its line items with category and default limit: E. getTemplateById — "the detailed template DTO including line item definitions".
8. a template with no lines reports an empty list, never null: E. — lines is a collection, never absent.
9. a template at the 50-line ceiling is returned in full: B. Template Limit Ceiling — 50 is the maximum permitted, so exactly 50 must round-trip.
10. a user with no custom templates still sees the system catalog: A. — the system catalog is the onboarding path; every returned row is either system or the caller's own.
11. GET /budget-templates responds 200 OK with the visible catalog: D. Endpoints.
12. GET /budget-templates/{id} responds 200 OK with the template's lines: D. Endpoints + Success Responses (200 OK).
13. GET /budget-templates/{id} for an unknown template responds 404 from the endpoint, not the router: D. Error Mapping (404 ResourceNotFoundException). Asserts the RFC 9457 problem *type* is `resource-not-found`, not merely the status: with no controller mounted the path 404s anyway as `endpoint-not-found`, so a bare status assertion passed for entirely the wrong reason.

--- BudgetQuickStartIT (23) ---
14. a budget instantiated from a template carries the template's categories and limits: A. Template Line Item Pre-Population.
15. an instantiated budget is ACTIVE and normalized to the first of the month: REQ-5.1 State Initialization + Normalization Rule apply to a templated budget like any other.
16. editing an instantiated budget's line does not change the template: A. Template Isolation — "actions on instantiated budgets never mutate the source template".
17. removing a line from an instantiated budget does not remove it from the template: A. Template Isolation, on the delete path.
18. a budget created from a template is unaffected by later template changes: A. Copy-on-Instantiate — the reverse direction, and the one an implementation storing a template reference instead of copying fails after passing every shallow assertion.
19. two users instantiating the same system template get independent budgets: A. Template Isolation — one shared source, two independent copies with disjoint line identities.
20. an override for a new category is appended to the template's lines: A. Template Line Item Overrides — "append".
21. an override for a template category adjusts its limit rather than duplicating it: A. Template Line Item Overrides — "adjust baseline template values".
22. an override matches a template category case-insensitively: A. Overrides read with REQ-5.2 Category Uniqueness — a case-sensitive merge yields "Rent" and "rent" side by side, producing a budget that violates the uniqueness rule the moment it is written.
23. with no templateId the lines are cloned from the most recent active budget: E. instantiateQuickStartBudget — "If request.getTemplateId() is null, lines are cloned from the user's most recent active budget" (Previous Month Rollover).
24. with no templateId and no prior budget an empty ACTIVE budget is created: E. + REQ-5.1 Template Inheritance — from scratch means lines = [] with status ACTIVE.
25. inherited lines are enriched with spend for a current period: A. Template Line Item Pre-Population — current/past periods sum approved transactions per category.
26. inherited lines report 0.00 spent for a future period: A. Template Line Item Pre-Population — "For future periods, spentAmount initializes to $0.00".
27. template lines plus overrides exceeding 50 is rejected: B. Target Line Ceiling — "merging template items with explicit user override items must not cause total lines to exceed 50".
27b. template lines plus overrides totalling exactly 50 is accepted: B. Target Line Ceiling — the accepting side of the boundary. Added after a mutation check: rejecting at exactly 50 (`>=` where `>` was meant) was caught by 0 of the original 34 tests.
27c. an override adjusting an existing category does not push a 50-line template over the ceiling: B. Target Line Ceiling — the merged result is what counts, not template lines + override count; the two agree everywhere except here.
28. a rejected instantiation persists no budget: B. Target Line Ceiling — the rejection must be effective; a rejected merge leaves no partial budget behind.
29. instantiating from an unknown template is a 404-class failure: D. Error Mapping (404 NOT FOUND).
30. instantiating from another user's custom template is a 404-class failure: D. Error Mapping + A. Template Isolation under multi-tenancy.
31. instantiating into a month whose budget is CLOSED is rejected: D. Error Mapping (422 HistoricalBudgetException) + REQ-5.1 Immutability upon Closure.
32. POST /budgets/quick-start responds 201 Created with the instantiated budget: D. Success Responses — "201 CREATED — Successfully instantiated budget from template".
33. POST /budgets/quick-start with an unknown template responds 404: D. Error Mapping at the HTTP boundary.
34. POST /budgets/quick-start with a 3-decimal override responds 400: D. Error Mapping — "400 BAD REQUEST — Invalid monetary precision (InvalidBudgetException)"; REQ-5.1 B forbids silent rounding.


--- BudgetTemplateCreationIT (23) — A. Custom Template Creation ---
35. a saved template is owned by its creator and is not a system template: A. Custom Template Creation — creation must never be able to produce a globally-visible template.
36. a saved template appears in its owner's catalog and nobody else's: A. + Template Isolation, verified from both sides of the tenancy boundary.
37. reusing a name is rejected with DuplicateTemplateException: B. Template Name Uniqueness.
38. a name differing only in case is a duplicate: B. — "unique per user account (case-insensitive)".
39. a name differing only in surrounding whitespace is a duplicate: B. — whitespace is not a distinguishing feature of a name; without stripping, "  Plan  " and "Plan" become two templates.
40. two different users may each hold a template with the same name: B. — the uniqueness scope is the account, so this must NOT be rejected. The counterweight to 37-39: an implementation using a global unique index passes those three and fails here.
41. a rejected duplicate persists nothing: B. — the rejection must be effective, not merely thrown.
42. a template with exactly 50 lines is accepted: B. Template Limit Ceiling — 50 is the maximum permitted.
43. a template with 51 lines is rejected: B. — one past the ceiling.
44. a template rejected for size persists nothing: B. — no partial write survives the rejection.
45. a blank name is rejected as a validation failure: A. — non-blank name.
46. duplicate categories within one template are rejected case-insensitively: B. Template category uniqueness, matching REQ-5.2.
47. a defaultLimit with three decimal places is rejected rather than rounded: B. Range Constraint + REQ-5.1 B Monetary Precision & Scale — a template default obeys the same rule as a live ceiling.
48. a negative defaultLimit is rejected: B. Range Constraint — lower bound.
49. a defaultLimit of exactly 999999999.99 is accepted: B. Range Constraint — the upper bound is inclusive.
50. a template with no lines is accepted and reports an empty list: A. — an empty template is a legitimate starting point.
51. the supplied line list is not mutated by the service: invariant — the caller's list is an input, not storage the service may edit.
52. POST /budget-templates responds 201 Created with the saved template: D. Success Responses.
53. POST /budget-templates with a duplicate name responds 409 Conflict: D. Error Mapping — 409 DuplicateTemplateException.
54. POST /budget-templates with a blank name responds 400 Bad Request: D. Error Mapping — 400 InvalidBudgetException.
55. saving from a source budget copies that budget's own allocations: F.3b — allocations are read server-side from sourceBudgetId, never taken from the request body.
56. saving from another user's budget responds 404 and stores nothing: F.3b + tenancy — a source budget the caller does not own must neither be readable nor partially copied.
57. a budget saved as a template reproduces its allocations when instantiated: round-trip identity across create -> catalog -> quick-start, exercising the three endpoints as one chain.


=========================
MUTATION CHECK — evidence the suite discriminates
=========================

Per the F2P authoring guide, the reference implementation was broken in six plausible ways and the
suite re-run each time. Results, against the 59 tests above:

  M1  system templates dropped from visibility (the standard RLS predicate copied verbatim)
      -> 18/59 caught
  M2  override merge keyed case-sensitively
      -> 1/59 caught  (overrideMatchesTemplateCategoryCaseInsensitively)
  M3  ResourceNotFoundException swapped for InvalidBudgetException (404 becomes 400)
      -> 6/59 caught
  M4  merged-ceiling off-by-one: reject at exactly 50 instead of 51
      -> 0/59 caught BEFORE tests 27b/27c were added; 2/59 after. This is why they exist.
  M5  name-uniqueness pre-check removed, relying on the partial unique index alone
      -> 0/59. Equivalent mutant: the index still raises, the service still maps it to
         DuplicateTemplateException, so observable behaviour is unchanged. The pre-check exists for
         message quality and to avoid a wasted insert, neither of which is a behavioural contract.
  M6  ownership filter dropped when reading the source budget for "Save as Template"
      -> 0/59. Also an equivalent mutant, and a deliberate one: PostgreSQL RLS independently hides
         another user's budget, so the outcome (404, nothing copied) is unchanged. The suite tests
         the outcome rather than which layer produces it. Worth knowing that the application-layer
         guard has no coverage independent of RLS — if RLS were ever disabled on ledger.budgets,
         no test here would notice.

M2's single-test result is expected, not a weakness: it is the only behaviour that mutation
changes. M1 and M3 are broad because visibility and error typing are load-bearing across the suite.
 — resolved, no open deviations
=========================

REQ-5.3 as originally written conflicted with the schema and API that REQ-5.1 and REQ-5.2 had
already established, in seven places. All seven have now been corrected in
ledger-5-budget-spec.md; the implementation and the requirement agree, and nothing below is an
outstanding deviation. Recorded here because the resolutions are decisions, not transcriptions.

1. user_id FOREIGN KEY -> security.users(id)  [F.1] — FK REMOVED FROM THE SPEC.
   No `security` schema exists (V1 creates only `ledger`) and no table in this service references a
   users table; user_id is a bare UUID stamped from X-Internal-User-Id everywhere.

2. effectiveMonth: String (YYYY-MM)  [F.3, F.4] — SPEC NOW YYYY-MM-DD.
   Matches REQ-5.1 B "Normalization Rule", the ledger.budgets.effective_month DATE column, every
   other budget endpoint and the shipped UI.

3. Response field names  [F.4] — SPEC NOW MATCHES THE Budget RECORD.
   lines[].categoryName became lines[].category; totalPlannedLimit and totalSpent were dropped as
   derivable by summing lines and returned by no other budget endpoint. Quick-start creates an
   ordinary budget, so it returns the ordinary budget shape. Template lines keep categoryName /
   defaultLimit: a template default is not a live ceiling, and the distinct naming is what keeps
   the two from being confused at the merge boundary.

4. BudgetTemplateDTO / BudgetDTO  [E] — SPEC NOW SPECIFIES DOMAIN RECORDS.
   BudgetService already returns Budget from every method and CLAUDE.md makes records the DTO
   mechanism; a parallel BudgetDTO would put two representations of a budget across one boundary.

5. Endpoint paths  [D] — SPEC NOW /api/v1/ledger/*.
   Every controller in this service is mounted there. Stated as an explicit "Path Prefix" rule so
   REQ-5.1 and REQ-5.2 inherit it rather than repeating the discrepancy.

6. templateId overloaded across requirements — SPEC NOW NAMES THE COLLISION.
   B carries an explicit constraint: REQ-5.1's templateId identifies an existing *budget* to clone,
   REQ-5.3's identifies a ledger.budget_templates row, neither endpoint accepts the other's
   identifier, and quick-start does not forward a templateId to upsertBudget. The two were left as
   separate concepts rather than unified — unifying them would silently change REQ-5.1's shipped
   behaviour, which the existing suite pins.

7. Custom template creation specified only implicitly — NOW A FIRST-CLASS RULE.
   D named a 409 for "custom template creation" while E listed no creation method, leaving B
   "Template Name Uniqueness" unreachable. A now carries a "Custom Template Creation" business
   rule, D the POST /budget-templates endpoint, E the createCustomTemplate signature, and F.3b its
   payload contract, including the rule that allocations are read server-side from sourceBudgetId
   rather than from the request body.

Additions the original spec omitted entirely, now written down because the implementation must
satisfy them and a re-implementation from the spec alone would otherwise guess:
   - F.1 Row-Level Security. The standard tenant predicate is insufficient for a table whose rows
     may be owner-less; the required SELECT/INSERT/UPDATE/DELETE policies are spelled out, as is
     why copying the usual one empties the catalog silently.
   - F.1 the is_system / user_id CHECK constraint.
   - F.2 the derived user_id column on budget_template_lines.
   - F.5 the template response contract (shape and ordering).
   - A. "Previous Month Rollover" and "Instantiation Delegates to REQ-5.1", both previously only
     implied by E's prose.
   - A. Overrides match template categories case-insensitively, per REQ-5.2 Category Uniqueness.
   - B. Template category name length and per-template uniqueness.


=========================
P2P TESTS
=========================

REQ-5.3 adds no P2P tests of its own: it introduces new tables, a new service and a new controller
rather than changing existing behaviour. The whole pre-existing suite (47 unit + 166 integration)
is the regression guard, and passes unchanged — the relevant evidence being that
instantiateQuickStartBudget delegates to BudgetService.upsertBudget rather than reimplementing
month normalization, the CLOSED write guard, the 50-line ceiling, monetary validation or spend
enrichment. REQ-5.1's and REQ-5.2's suites are therefore the tests that cover those rules on the
quick-start path too.
