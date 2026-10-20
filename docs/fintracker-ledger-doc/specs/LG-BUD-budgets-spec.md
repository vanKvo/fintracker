# Budget Requirements

## Functional Requirements
### REQ-5.1: Manage Budgets
A. Business Rules:
A.1. Create/Update Budget
- Period Selection & Upsert Behavior: The user can create a new budget for past, present, or future periods by specifying a month and year. The user can update an existing budget with 'ACTIVE' status only. If a budget already exists for the normalized target month, submitting a valid payload will update the budget's line items rather than throwing a duplicate error.
- State Initialization: All newly created budgets, whether for past, present, or future periods, shall initialize with status = 'ACTIVE'.
- Modification Guard: Operations (creation or updates) on budgets marked as 'ACTIVE' are permitted. Any write operation attempted against a budget marked as 'CLOSED' shall be rejected with a HistoricalBudgetException (422 Unprocessable Entity).
- Template Inheritance: If the user choose to create budget based on an existing template or from their most recent active budget, line items shall be automatically populated based on the user's selected template. If no template is selected and the user choose to create a budget from scratch, an empty budget with no line items (lines = []) shall be created with status = 'ACTIVE' 
- Spend Amount Initialization: For future periods, spentAmount shall initialize to $0.00. For current or past periods, spentAmount shall automatically query and sum all approved transactions matching each line item's category within that period's date range.
- Automated Period Closure: On the 1st day of every month at 00:00:00 UTC, all active budgets where month < current_month shall be automatically transitioned from status = 'ACTIVE' to status = 'CLOSED'
- Manual Close: A user or system actor can explicitly close an active budget prior to month-end via the close endpoint/method.
- Immutability upon Closure: Once status == 'CLOSED', all subsequent write operations (upsertBudget, addLineItem, updateLineItemLimit, removeLineItem) are blocked and throw HistoricalBudgetException (422 Unprocessable Entity).
- Reopening Exemption: A closed budget can only transition back to ACTIVE through an explicit reopenBudget call

A.2. Get Budgets
- Budgets in a year: The system get all budgets created within a year for the user.
- Pure Read: Listing a year shall never create a budget. Unlike getBudgetForMonth, which lazily materializes a budget for the requested month, this listing returns only budgets that already exist — a year with no budgets returns an empty list, not twelve newly created ones.
- Tenant Scoping: Only budgets owned by the requesting user are returned; another user's budget for the same month is never visible.
- Ordering: Results are returned in descending effectiveMonth order (most recent month first), so the caller can render a reverse-chronological period list without re-sorting.
- Spend Enrichment: Every returned budget is enriched with spentAmount per line item under the same rules as REQ-5.1 "Spend Amount Initialization" — future periods report $0.00, current and past periods sum approved transactions for that period.
- Year Boundary: A budget belongs to a year when its normalized effectiveMonth falls in [YYYY-01-01, YYYY-12-01] inclusive. December of the preceding year and January of the following year are excluded.

A.3. Delete Budget
- The user can delete a monthly 'ACTIVE' budget only, not a 'CLOSED' budget.
- Deletion Guard: Deleting a budget whose status == 'CLOSED' shall be rejected with a HistoricalBudgetException (422 Unprocessable Entity), consistent with A.1 "Immutability upon Closure" — a closed period is historical record. The budget must be explicitly reopened first.
- Ownership: Deleting a budget that does not exist, or that belongs to another user, shall be rejected with a ResourceNotFoundException (404 Not Found). A user must never be able to distinguish "does not exist" from "is not yours".
- Cascade: Deleting a budget removes its ledger.budget_lines records along with it. No orphaned line items may remain.
- Orphaned Transaction Handling: Deletion removes budget ceilings only. Underlying ledger.transactions records are never altered or deleted, mirroring REQ-5.2 "Orphaned Transaction Handling".
- Non-Idempotent: Deleting an already-deleted budget is a 404, not a silent success — the second caller is acting on a stale view.

B. Contraints:
- Maximum active budget line items per budget is 50.
- Normalization Rule: The month must be normalized to the first day of the calendar month (YYYY-MM-01) via LocalDate.withDayOfMonth(1) before persistence.
- Category Uniqueness: The payload must not contain duplicate category names for the same budget ID.
- Range Constraint for limitAmount: Every limitAmount must be greater than or equal to 0.00 and less than or equal to 999,999,999.99.
- Monetary Precision & Scale Constraint: All monetary input fields (limitAmount) must have a maximum scale of 2 decimal places (cents). Any payload containing a monetary amount with more than 2 decimal places (e.g., 10.005) shall be rejected immediately with 400 BAD REQUEST (InvalidBudgetException / validation error) and must not be silently rounded by the backend.

C. Data Impacts:
- State Change: Inserts or updates records in the main budget ledger tables (ledger.budgets and ledger.budget_lines).
- Budget table: Add new column name 'status' in the existing Budget table with check constraint that allows either 'ACTIVE' or 'CLOSED'.

D. REST API Mapping
Location: com.fintracker.ledger.budget.controller.BudgetController
Endpoints: 
- PUT /api/v1/budgets — Create or update budget. (A.1)
- GET /api/v1/budgets?month={YYYY-MM-DD} — Get the budget of a single month. (A.1 / REQ-5.4)
- GET /api/v1/budgets?year={YYYY} — List every existing budget of the user in that calendar year. (A.2)
- DELETE /api/v1/budgets/{id} — Delete an ACTIVE budget and its line items. (A.3)
- POST /api/v1/budgets/{id}/close — Transition budget status from ACTIVE to CLOSED.
- POST /api/v1/budgets/{id}/reopen — Transition budget status from CLOSED to ACTIVE.
Headers: Content-Type: application/json, Authorization: Bearer <JWT>
Request Body: UpsertBudgetRequest (PUT only; GET and DELETE carry no body)
Success Responses: 
- 201 CREATED — Returned when a brand new monthly budget is successfully created. 
- 200 OK — Returned when an existing monthly budget is retrieved, listed, updated, reopened or closed. A year listing with no budgets is 200 OK with an empty array, never 404.
- 204 NO CONTENT — Returned when a budget is successfully deleted. The response carries no body.
Error Mappings:
- 400 BAD REQUEST — Thrown when InvalidBudgetException or LineItemLimitExceededException occurs. Includes a year outside [1970, 9999] and a non-numeric year on the listing endpoint.
- 404 NOT FOUND — Thrown when ResourceNotFoundException occurs (deleting a budget that does not exist or belongs to another user).
- 422 UNPROCESSABLE ENTITY — Thrown when HistoricalBudgetException occurs (attempted write operation on, or deletion of, a CLOSED budget).

E. Interface Details: 
Location: com.fintracker.ledger.budget.service.BudgetService

interface BudgetService {

    /**
     * REQ-5.1 A.2 "Get Budgets": every budget the user already has in the given calendar year,
     * most recent month first, each enriched with per-line spentAmount.
     *
     * This is a pure read: unlike getBudgetForMonth, it never materializes a budget for a month
     * that has none. A year the user has no budgets in yields an empty list.
     *
     * @param userId unique identifier of the requesting user.
     * @param year   four-digit calendar year; budgets with effectiveMonth in
     *               [YYYY-01-01, YYYY-12-01] are returned.
     * @return budgets ordered by effectiveMonth descending; empty when the year has none.
     *
     * @throws InvalidBudgetException if userId is null or year is outside [1970, 9999].
     */
    List<Budget> getBudgetsForYear(UUID userId, int year) throws InvalidBudgetException;

    /**
     * REQ-5.1 A.3 "Delete Budget": permanently removes an ACTIVE budget and, by cascade, its
     * line items. Underlying transactions are never touched.
     *
     * @param userId   unique identifier of the requesting user.
     * @param budgetId unique identifier of the budget to delete.
     *
     * @throws ResourceNotFoundException  if the budget does not exist or belongs to another user.
     * @throws HistoricalBudgetException  if the budget's status is CLOSED; it must be reopened first.
     */
    void deleteBudget(UUID userId, UUID budgetId)
        throws ResourceNotFoundException, HistoricalBudgetException;
}


### REQ-5.2: Manage Budget Line Items
A. Business Rules:
- Granular Line Operations: Users shall be able to dynamically add a new line item, update an existing line item's limit, or remove a line item from any ACTIVE budget.
- State Check Guard: Line item modifications are permitted only if the parent budget's status == 'ACTIVE'. If status == 'CLOSED', the service throws a HistoricalBudgetException (422 Unprocessable Entity). 
- Category Uniqueness: A new line item cannot share a category name with an existing line item within the same budget period. Category matching shall be case-insensitive.
- Dynamic Spend Initialization: Adding or updating a category on an ACTIVE budget in a current or past period triggers an aggregate lookup of matching approved transactions within that period to calculate spentAmount. For future periods, spentAmount remains $0.00.
- Orphaned Transaction Handling: Deleting a budget line item removes the budget ceiling constraint for that category but does not alter or delete underlying user transactions.

B. Constraints:
- Line Item Ceiling: Adding a line item must not cause total budget lines to exceed 50 for the target budget instance.
- Range Constraint for limitAmount: Every limitAmount must be greater than or equal to 0.00 and less than or equal to 999,999,999.99.
- Non-Empty Category Name: Category names must be non-null, non-blank, and truncated to a maximum length of 50 characters.
- Monetary Precision & Scale Constraint: All monetary input fields (limitAmount) must have a maximum scale of 2 decimal places (cents). Any payload containing a monetary amount with more than 2 decimal places (e.g., 10.005) shall be rejected immediately with 400 BAD REQUEST (InvalidBudgetException / validation error) and must not be silently rounded by the backend.

C. Data Impacts:
- State Change: Inserts, updates, or deletes individual records in ledger.budget_lines.
- Side Effects: Recalculates aggregate spending and total planned limits in ledger.budgets.

D. REST API Mapping:
Location: com.fintracker.ledger.budget.controller.BudgetLineController
Endpoints:
- POST /api/v1/budgets/{budgetId}/lines — Add a line item.
- PUT /api/v1/budgets/{budgetId}/lines/{lineId} — Update an existing line item limit.
- DELETE /api/v1/budgets/{budgetId}/lines/{lineId} — Remove a line item.
Success Responses:
- 201 CREATED — Line item added successfully.
- 200 OK — Line item updated or deleted successfully.
Error Mapping:
- 400 BAD REQUEST — Thrown when InvalidBudgetException or LineItemLimitExceededException occurs.
- 404 NOT FOUND — Thrown when ResourceNotFoundException occurs (budgetId or lineId not found).
- 409 CONFLICT — Thrown when DuplicateCategoryException occurs.
- 422 UNPROCESSABLE ENTITY — Thrown when HistoricalBudgetException occurs (budget status is CLOSED).

E. Interface Details:
Location: com.fintracker.ledger.budget.service.BudgetLineService


### REQ-5.3: Quick Start Templates 
A. Business Rules
- System & Custom Template Availability: The system provides predefined global templates (is_system = true, e.g., "Basic Living", "Aggressive Savings") and user-owned custom templates (is_system = false). Users can inspect and select these templates to populate new budget instances.
- Template Isolation & Copy-on-Instantiate: Applying a template acts purely as an initial seed. Copying line item categories and limitAmount values into a target budget creates independent ledger.budget_lines records; actions on instantiated budgets never mutate the source template.
- Template Line Item Pre-Population: When creating a budget from a template for current or past periods, the spentAmount for each inherited template line item shall automatically query and sum approved transactions matching that category within the target period's date range. For future periods, spentAmount initializes to $0.00.
- Template Line Item Overrides: Users may pass custom line items or explicit overrides in the budget creation payload alongside a templateId to append or adjust baseline template values prior to persistence. An override whose category matches a template line adjusts that line's limit; an override whose category is new appends a line. Matching is case-insensitive, consistent with REQ-5.2 "Category Uniqueness" — a case-sensitive merge would produce "Rent" and "rent" side by side and build a budget that violates that rule the moment it is written.
- Previous Month Rollover: If no templateId is supplied, line items are cloned from the user's most recent ACTIVE budget, which is REQ-5.1 "Template Inheritance". If the user has no prior budget, an empty ACTIVE budget is created (lines = []).
- Custom Template Creation ("Save as Template"): A user can save a set of category allocations as a reusable custom template they own. Only custom templates can be created this way; the predefined system catalog is seeded by database migration and is read-only to every user, including its owner-less rows. Where the request identifies a source budget, the allocations shall be read from that budget server-side rather than taken from the request body, so a template can never be stored with figures the source budget does not contain.
- Instantiation Delegates to REQ-5.1: Instantiating a budget from a template applies every REQ-5.1 rule unchanged — month normalization, State Initialization, the Modification Guard, Immutability upon Closure, the 50-line ceiling, monetary range and scale, and Spend Amount Initialization. REQ-5.3 adds template resolution and the override merge; it does not restate or vary any REQ-5.1 rule.

B. Constraints
- Template Limit Ceiling: A template cannot contain more than 50 line items.
- Target Line Ceiling: Merging template items with explicit user override items must not cause total lines on the created budget to exceed 50.
- Template Name Uniqueness: Custom template names created by a user must be unique per user account (case-insensitive). System template names are globally unique.
- Range Constraint for limitAmount: Every line item limitAmount inside a template must comply with standard monetary rules: scale of 2 decimal places, range [0.00, 999,999,999.99]. Inside a template the field is named defaultLimit (a starting suggestion); it becomes limitAmount (a live ceiling) only once copied onto a budget.
- Template Category Name: Non-null, non-blank, maximum 50 characters, matching REQ-5.2 "Non-Empty Category Name". Categories within one template must be unique case-insensitively.
- templateId Is Not REQ-5.1's templateId: REQ-5.1's upsertBudget takes a templateId identifying an existing *budget* of the same user to clone. REQ-5.3's templateId identifies a ledger.budget_templates row. These are distinct concepts that share a name; neither endpoint accepts the other's identifier, and a REQ-5.3 templateId submitted to PUT /budgets shall be rejected as an unknown template (400 InvalidBudgetException). Quick-start resolves its own line items and does not forward a templateId to upsertBudget.

C. Data Impacts
- State Changes: Reads from ledger.budget_templates and ledger.budget_template_lines. Inserts new records into ledger.budgets and ledger.budget_lines.
- Side Effects: Calculates aggregate spending for inherited categories from ledger.transactions and initializes total aggregated limits on ledger.budgets.

D. REST API Mapping

Location: com.fintracker.ledger.budget.controller.BudgetTemplateController

Endpoints:
- GET /api/v1/ledger/budget-templates — List available system and custom templates.
- GET /api/v1/ledger/budget-templates/{templateId} — Get detailed line items of a template.
- POST /api/v1/ledger/budget-templates — Save a custom template ("Save as Template").
- POST /api/v1/ledger/budgets/quick-start — Create a new budget using a template.

Path Prefix: every controller in this service is mounted under /api/v1/ledger/*, so these endpoints are too. The same prefix applies to REQ-5.1 and REQ-5.2.

Headers: Content-Type: application/json, Authorization: Bearer <JWT>

Success Responses:
- 200 OK — Retrieved template list or details. A user with no custom templates still receives the system catalog; an entirely empty catalog is 200 OK with an empty array, never 404.
- 201 CREATED — Successfully instantiated budget from template, or successfully saved a custom template.

Error Mapping:
- 400 BAD REQUEST — Invalid monetary precision, blank or oversized template name, duplicate categories within one payload, or corrupt template payload (InvalidBudgetException); more than 50 line items (LineItemLimitExceededException).
- 404 NOT FOUND — Selected templateId does not exist, or is another user's custom template (ResourceNotFoundException). The two cases are deliberately indistinguishable, so a probe cannot confirm that an invisible template exists.
- 409 CONFLICT — Duplicate template name on custom template creation (DuplicateTemplateException).
- 422 UNPROCESSABLE ENTITY — Attempting to instantiate into a closed budget window or rule violation (HistoricalBudgetException).

E. Interface Details
Location: com.fintracker.ledger.budget.service.BudgetTemplateService

Return types are the module's domain records (Budget, BudgetTemplate), not a parallel DTO layer.
BudgetService already returns Budget from every method, and CLAUDE.md makes Java Records the DTO
and value-object mechanism; a separate BudgetDTO would put two representations of a budget across
the same boundary.

interface BudgetTemplateService {

    /**
     * Fetches all system templates plus the custom templates owned by the user, system templates
     * first, then alphabetically within each group.
     *
     * System templates are owner-less and readable by every user; custom templates are readable
     * only by their owner. Both ownership models are served by this one listing.
     *
     * @param userId Unique identifier of the requesting user.
     * @return List<BudgetTemplate> the visible catalog; empty when none exist, never null.
     *
     * @throws InvalidBudgetException If userId is null.
     */
    List<BudgetTemplate> getAvailableTemplates(UUID userId);

    /**
     * Retrieves details and line items for a specific budget template.
     *
     * @param userId     Unique identifier of the requesting user.
     * @param templateId Unique identifier of the target template.
     * @return BudgetTemplate The template including its line item definitions (never null lines).
     *
     * @throws ResourceNotFoundException If templateId does not exist, or is another user's custom
     *         template. Both produce the same failure so an id probe reveals nothing.
     */
    BudgetTemplate getTemplateById(UUID userId, UUID templateId);

    /**
     * Instantiates a new Budget for a target month from a template, or by Previous Month Rollover.
     *
     * If request.templateId() is provided, lines are copied from that template. If it is null,
     * lines are cloned from the user's most recent ACTIVE budget. Copies are independent
     * ledger.budget_lines rows in both directions: later edits to the budget never reach the
     * template, and later edits to the template never reach budgets already created from it.
     *
     * Every REQ-5.1 rule applies to the result unchanged (see A. Instantiation Delegates to
     * REQ-5.1).
     *
     * @param userId  Unique identifier of the requesting user.
     * @param request Payload containing target period, templateId (optional), and custom overrides.
     * @return Budget The newly created and populated budget instance.
     *
     * @throws ResourceNotFoundException      If the target template is not found or not visible.
     * @throws LineItemLimitExceededException If template lines merged with overrides exceed 50.
     * @throws InvalidBudgetException         If monetary scale or limits are invalid.
     * @throws HistoricalBudgetException      If the target month's budget exists and is CLOSED.
     */
    Budget instantiateQuickStartBudget(UUID userId, QuickStartBudgetRequest request);

    /**
     * Saves a set of category allocations as a reusable custom template owned by the user —
     * the "Save as Template" path. Only custom templates can be created here; the system catalog
     * is seeded by migration and cannot be written through the application.
     *
     * @param userId      Unique identifier of the owning user.
     * @param name        Unique per user, case-insensitive; non-blank, max 100 characters.
     * @param description Optional, max 255 characters.
     * @param lines       Allocations to store; at most 50, categories unique case-insensitively.
     * @return BudgetTemplate The persisted custom template.
     *
     * @throws DuplicateTemplateException     If the user already owns a template with this name.
     * @throws LineItemLimitExceededException If more than 50 lines are supplied.
     * @throws InvalidBudgetException         If the name is blank or oversized, categories repeat,
     *                                        or a limit violates the monetary range or scale.
     */
    BudgetTemplate createCustomTemplate(UUID userId, String name, String description,
                                        List<BudgetTemplateLine> lines);
}

F. Data Contract (REQ-5.3)
--- 1. DATABASE SCHEMA CONTRACT: TEMPLATES TABLE ---
Table Name: ledger.budget_templates
Description: Stores global system templates and custom user-created templates.

Column: id | Type: UUID | Constraints: PRIMARY KEY, DEFAULT gen_random_uuid() | Description: Unique identifier for the template.
Column: user_id | Type: UUID | Constraints: NULLABLE | Description: Owner user ID; NULL indicates a system template. No foreign key: this service has no users table and every tenant-scoped table (ledger.budgets, ledger.transactions, ledger.accounts) stores user_id as a bare UUID stamped from the X-Internal-User-Id identity.
Column: name | Type: VARCHAR(100) | Constraints: NOT NULL | Description: Display name of the template.
Column: description | Type: VARCHAR(255) | Constraints: NULLABLE | Description: Brief summary of the budget template strategy.
Column: is_system | Type: BOOLEAN | Constraints: NOT NULL, DEFAULT false | Description: Flag set to true for globally available templates.
Column: created_at | Type: TIMESTAMPTZ | Constraints: NOT NULL, DEFAULT CURRENT_TIMESTAMP | Description: Record creation timestamp.
Column: updated_at | Type: TIMESTAMPTZ | Constraints: NOT NULL, DEFAULT CURRENT_TIMESTAMP | Description: Record update timestamp.

Constraint: UNIQUE INDEX uq_system_template_name ON ledger.budget_templates(LOWER(name)) WHERE user_id IS NULL
Constraint: UNIQUE INDEX uq_custom_template_name ON ledger.budget_templates(user_id, LOWER(name)) WHERE user_id IS NOT NULL
Constraint: CHECK ((is_system AND user_id IS NULL) OR (NOT is_system AND user_id IS NOT NULL)) | Description: user_id is the ownership signal and is_system is its denormalized twin; without this they can disagree, and a row with is_system = true AND a non-null user_id would be readable by every user while claiming private ownership.

Row-Level Security: these are the first tables in the schema with two ownership models, so the
standard tenant predicate used everywhere else — USING (user_id = current_setting('app.current_user_id', true)::uuid)
— is NOT sufficient. A system template has user_id IS NULL, and `NULL = <uuid>` evaluates to NULL,
which RLS treats as false; copying that predicate would hide the entire system catalog from every
user with no error to explain it. Required policies:
  - SELECT: USING (user_id IS NULL OR user_id = current_setting('app.current_user_id', true)::uuid)
  - INSERT: WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid) — rejects a
    null owner, so no request-scoped session can manufacture a system template.
  - UPDATE / DELETE: USING and WITH CHECK on ownership only — the system catalog is read-only to
    the application.
The same asymmetry applies to ledger.budget_template_lines, whose user_id is derived from its
parent template by trigger (nullable, because a system template's lines have no owner).

--- 2. DATABASE SCHEMA CONTRACT: TEMPLATE LINE ITEMS TABLE ---
Table Name: ledger.budget_template_lines
Description: Stores default category allocations associated with a template.

Column: id | Type: UUID | Constraints: PRIMARY KEY, DEFAULT gen_random_uuid() | Description: Unique line item identifier.
Column: template_id | Type: UUID | Constraints: NOT NULL, FOREIGN KEY -> ledger.budget_templates(id) ON DELETE CASCADE | Description: Foreign key to parent template.
Column: user_id | Type: UUID | Constraints: NULLABLE | Description: Denormalized from the parent template by a BEFORE INSERT trigger so RLS is a single-column check, matching ledger.budget_lines. NULL for a system template's lines, which have no owner.
Column: category_name | Type: VARCHAR(50) | Constraints: NOT NULL | Description: Name of the line item category.
Column: default_limit | Type: NUMERIC(11,2) | Constraints: NOT NULL, CHECK (default_limit >= 0.00 AND default_limit <= 999999999.99) | Description: Predefined budget limit ceiling for the line item.
Column: created_at | Type: TIMESTAMPTZ | Constraints: NOT NULL, DEFAULT CURRENT_TIMESTAMP | Description: Record creation timestamp.

Constraint: UNIQUE INDEX uq_template_category ON ledger.budget_template_lines(template_id, LOWER(category_name))

--- 3. PAYLOAD CONTRACT: QUICK START BUDGET REQUEST ---
Target Endpoint: POST /api/v1/budgets/quick-start
Request Format: JSON

Field: effectiveMonth | Type: String (YYYY-MM-DD) | Required: Yes | Constraints: Normalized to the first of the month per REQ-5.1 B "Normalization Rule"; target month must not have a CLOSED budget | Example: "2026-09-01" | Note: the same LocalDate format every other budget endpoint and the ledger.budgets.effective_month DATE column use. A YYYY-MM-only form would give one module two wire formats for the same concept.
Field: templateId | Type: UUID (String) | Required: No | Constraints: Must exist in ledger.budget_templates if provided | Example: "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
Field: totalBudgetCap | Type: Numeric | Required: No | Constraints: Max scale 2, range [0.00, 999999999.99] | Example: 5000.00
Field: customOverrides | Type: Array[Object] | Required: No | Constraints: Max total lines including template items <= 50 | Example: [{"categoryName": "Subscriptions", "limitAmount": 50.00}]
Field: customOverrides[].categoryName | Type: String | Required: Yes | Constraints: Non-blank, max length 50 chars | Example: "Subscriptions"
Field: customOverrides[].limitAmount | Type: Numeric | Required: Yes | Constraints: Max scale 2, range [0.00, 999999999.99] | Example: 50.00

--- 3b. PAYLOAD CONTRACT: CREATE CUSTOM TEMPLATE REQUEST ("Save as Template") ---
Target Endpoint: POST /api/v1/ledger/budget-templates
Request Format: JSON

Field: name | Type: String | Required: Yes | Constraints: Non-blank, max 100 chars, unique per user case-insensitively | Example: "August 2026 plan"
Field: description | Type: String | Required: No | Constraints: Max 255 chars | Example: "Post-raise allocations"
Field: sourceBudgetId | Type: UUID (String) | Required: No | Constraints: Must be a budget owned by the user | Example: "c0a80121-8930-11ee-b9d1-0242ac120002"
Field: lines | Type: Array[Object] | Required: No | Constraints: Max 50, categories unique case-insensitively | Example: [{"categoryName": "Groceries", "defaultLimit": 500.00}]
Field: lines[].categoryName | Type: String | Required: Yes | Constraints: Non-blank, max 50 chars | Example: "Groceries"
Field: lines[].defaultLimit | Type: Numeric | Required: Yes | Constraints: Max scale 2, range [0.00, 999999999.99] | Example: 500.00

Resolution order: explicit `lines` take precedence; otherwise the allocations are read server-side
from `sourceBudgetId`; with neither, an empty template is created. Reading from the source budget
rather than the request body is what prevents a template being stored with figures that budget does
not contain. A sourceBudgetId belonging to another user is a 404, never a 403.

--- 4. PAYLOAD CONTRACT: BUDGET RESPONSE ---
Response Status: 201 CREATED
Response Format: JSON
Shape: identical to the Budget returned by every REQ-5.1 endpoint. Quick-start creates an ordinary
budget; a differently-shaped response for the same resource would force clients to branch on how a
budget happened to be created. totalPlannedLimit and totalSpent are NOT returned — they are
derivable by summing lines, and no other budget endpoint returns them.

Field: budgetId | Type: UUID (String) | Constraints: Non-null | Example: "c0a80121-8930-11ee-b9d1-0242ac120002"
Field: userId | Type: UUID (String) | Constraints: Non-null | Example: "3fa85f64-5717-4562-b3fc-2c963f66afa6"
Field: effectiveMonth | Type: String (YYYY-MM-DD) | Constraints: Non-null, always the first of the month | Example: "2026-09-01"
Field: status | Type: String (Enum) | Constraints: Values = ['ACTIVE', 'CLOSED'] | Example: "ACTIVE"
Field: lines | Type: Array[Object] | Constraints: Array of generated budget lines | Example: See line item structure below
Field: lines[].lineId | Type: UUID (String) | Constraints: Non-null; a fresh identity per instantiation, never the template line's id | Example: "f1d828a2-8930-11ee-b9d1-0242ac120002"
Field: lines[].category | Type: String | Constraints: Non-null, case-preserved, max 50 chars | Example: "Housing / Rent / Mortgage" | Note: named `category` on a budget line and `categoryName` on a template line — the two are different things and the naming keeps them from being confused at the merge boundary.
Field: lines[].limitAmount | Type: Numeric | Constraints: Scale 2 | Example: 1500.00
Field: lines[].spentAmount | Type: Numeric | Constraints: Scale 2, default 0.00 for future periods | Example: 0.00

## REQ-5.4: Get Budget Progress and Pacing (Depends on REQ-5.1 & Transaction Module)
A. Purpose: Active pacing charts calculate and supply metrics comparing current actual spending run rates against monthly thresholds to help users make better financial decisions.  
B. Method Signature: getBudgetForMonth(userId: UUID, month: LocalDate) → Budget  
- Inputs: userId: UUID (The owning user ID) month: LocalDate (The target calendar month)
- Outputs: The fully enriched Budget object including computed spentAmount values for every budget line.
C. Business Rules & Constraints:
- Spent Enrichment Calculation: The system must compute the expense sum dynamically for each category using: spentAmount = TransactionService.sumMonthlyExpenses(userId, monthStart, monthEnd)}
- Pacing Ratio Rule: Pacing is calculated as: Pacing = spentAmount/limitAmount compared against the expected time progress of the current month.
D. System Behavior & Data Impact:
- State Change: Read-only calculation.
- Side Effects: Overwrites the default BigDecimal.ZERO on the returned schema transfer objects with the live, calculated expenses.
E. Edge Cases & Error Handling:
- Empty Budget Instance: If no budget exists for the requested month, it returns null or triggers the Auto-Template Copying process (REQ-5.2.1) depending on user interaction.Category Spend without Limit: If a category contains transactions but has a budget limit of 0.00, the pacing progress is flagged as exceeding the limit immediately.

--- 5. PAYLOAD CONTRACT: BUDGET TEMPLATE RESPONSE ---
Response Status: 200 OK (list and detail), 201 CREATED (save as template)
Response Format: JSON

Field: templateId | Type: UUID (String) | Constraints: Non-null | Example: "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
Field: userId | Type: UUID (String) | Constraints: Null for system templates | Example: null
Field: name | Type: String | Constraints: Non-null | Example: "Basic Living"
Field: description | Type: String | Constraints: Nullable | Example: "Essential monthly expenses for a typical household."
Field: isSystem | Type: Boolean | Constraints: Non-null; true exactly when userId is null | Example: true
Field: lines | Type: Array[Object] | Constraints: Non-null; empty array when the template has none | Example: See below
Field: lines[].lineId | Type: UUID (String) | Constraints: Non-null | Example: "f1d828a2-8930-11ee-b9d1-0242ac120002"
Field: lines[].templateId | Type: UUID (String) | Constraints: Non-null | Example: "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
Field: lines[].categoryName | Type: String | Constraints: Non-null, max 50 chars | Example: "Rent/Mortgage"
Field: lines[].defaultLimit | Type: Numeric | Constraints: Scale 2, range [0.00, 999999999.99] | Example: 1500.00

Ordering: system templates first, then by name case-insensitively within each group — the system
catalog is the onboarding path for a user who has none of their own.
