# Budget Requirements

## Functional Requirements
### REQ-5.1: Create/Update Budget
A. Business Rules:
- Period Selection & Upsert Behavior: The user can create a new budget for past, present, or future periods by specifying a month and year. The user can update an existing budget with 'ACTIVE' status only. If a budget already exists for the normalized target month, submitting a valid payload will update the budget's line items rather than throwing a duplicate error.
- State Initialization: All newly created budgets, whether for past, present, or future periods, shall initialize with status = 'ACTIVE'.
- Modification Guard: Operations (creation or updates) on budgets marked as 'ACTIVE' are permitted. Any write operation attempted against a budget marked as 'CLOSED' shall be rejected with a HistoricalBudgetException (422 Unprocessable Entity).
- Template Inheritance: If the user choose to create budget based on an existing template or from their most recent active budget, line items shall be automatically populated based on the user's selected template. If no template is selected and the user choose to create a budget from scratch, an empty budget with no line items (lines = []) shall be created with status = 'ACTIVE' 
- Spend Amount Initialization: For future periods, spentAmount shall initialize to $0.00. For current or past periods, spentAmount shall automatically query and sum all approved transactions matching each line item's category within that period's date range.
- Automated Period Closure: On the 1st day of every month at 00:00:00 UTC, all active budgets where month < current_month shall be automatically transitioned from status = 'ACTIVE' to status = 'CLOSED'
- Manual Close: A user or system actor can explicitly close an active budget prior to month-end via the close endpoint/method.
- Immutability upon Closure: Once status == 'CLOSED', all subsequent write operations (upsertBudget, addLineItem, updateLineItemLimit, removeLineItem) are blocked and throw HistoricalBudgetException (422 Unprocessable Entity).
- Reopening Exemption: A closed budget can only transition back to ACTIVE through an explicit reopenBudget call

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
- PUT /api/v1/budgets — Create or update budget.
- POST /api/v1/budgets/{id}/close — Transition budget status from ACTIVE to CLOSED.
- POST /api/v1/budgets/{id}/reopen — Transition budget status from CLOSED to ACTIVE.
Headers: Content-Type: application/json, Authorization: Bearer <JWT>
Request Body: UpsertBudgetRequest
Success Responses: 
- 201 CREATED — Returned when a brand new monthly budget is successfully created. 
- 200 OK — Returned when an existing monthly budget is updated, reopened or closed.
Error Mappings:
- 400 BAD REQUEST — Thrown when InvalidBudgetException or LineItemLimitExceededException occurs.
- 422 UNPROCESSABLE ENTITY — Thrown when HistoricalBudgetException occurs (attempted write operation on a CLOSED budget).

E. Interface Details: 
Location: com.fintracker.ledger.budget.service.BudgetService
/**
     * Creates a new budget or updates an existing budget for a specified month.
     * Initializes status as ACTIVE regardless of whether the month is past, present, or future.
     * 
     * @param userId     Unique identifier of the target user account.
     * @param month      Target date representing the budget period (normalized to 1st of month).
     * @param templateId Optional template ID if initializing from a template configuration (nullable).
     * @param lines      List of category limits to establish or overwrite budget lines.
     * @return Budget    The persisted Java record representation of the budget.
     * 
     * @throws InvalidBudgetException       If input parameters violate constraints (range, duplicate categories).
     * @throws HistoricalBudgetException     If attempting a write operation on a CLOSED budget.
     * @throws LineItemLimitExceededException If total line items exceed the maximum permitted limit (50).
     */
    Budget upsertBudget(
        UUID userId, 
        LocalDate month, 
        UUID templateId, 
        List<BudgetLine> lines
    ) throws InvalidBudgetException, HistoricalBudgetException, LineItemLimitExceededException;

    /**
     * Unlocks a closed budget, changing its status from CLOSED to ACTIVE
     * to allow user modifications.
     * 
     * @param userId   Unique identifier of the requesting user.
     * @param budgetId Unique identifier of the target budget.
     * @return Budget  The updated budget domain entity with status set to ACTIVE.
     * 
     * @throws ResourceNotFoundException If the budgetId does not exist or belong to the user.
     */
    Budget reopenBudget(
        UUID userId, 
        UUID budgetId
    ) throws ResourceNotFoundException;

    /**
     * Retrieves or lazily creates a budget for the target month by copying
     * line items from the user's most recent active budget.
     * 
     * @param userId       Unique identifier of the requesting user.
     * @param targetMonth  Target date normalized to the 1st of the month.
     * @return Budget      The existing or newly generated budget with status ACTIVE.
     */
    Budget getOrCreateBudgetFromPrevious(
        UUID userId, 
        LocalDate targetMonth
    ) throws InvalidBudgetException;

    /**
     * Manually transitions a specific active budget to CLOSED status.
     * 
     * @param userId   Unique identifier of the requesting user.
     * @param budgetId Unique identifier of the target budget.
     * @return Budget  The updated budget domain entity with status set to CLOSED.
     * 
     * @throws ResourceNotFoundException If the budgetId does not exist or belong to user.
     * @throws HistoricalBudgetException If the budget is already CLOSED.
     */
    Budget closeBudget(
        UUID userId, 
        UUID budgetId
    ) throws ResourceNotFoundException, HistoricalBudgetException;

    /**
     * Batch transitions all ACTIVE budgets with a period prior to cutoffDate to CLOSED status or batch closes all past active budgets across the system.
     * Designed to be invoked by the month-end background scheduler.
     * 
     * @param cutoffDate Target month threshold (typically start of current month YYYY-MM-01).
     * @return int        The total number of budget records transitioned to CLOSED.
     */
    int closePastBudgets(LocalDate cutoffDate);
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
/**
     * Adds a single line item to an ACTIVE budget and computes initial spent amounts.
     * 
     * @param userId    Unique identifier of the requesting user.
     * @param budgetId  Unique identifier of the target budget.
     * @param lineInput DTO containing the category name and limit amount.
     * @return BudgetLine The persisted Java record representation of the added line item.
     * 
     * @throws ResourceNotFoundException     If the budgetId does not exist or belong to the user.
     * @throws DuplicateCategoryException    If the category already exists in the budget.
     * @throws LineItemLimitExceededException If total lines exceed 50.
     * @throws InvalidBudgetException       If limitAmount violates range constraints [0.00, 999999999.99].
     * @throws HistoricalBudgetException     If budget status is CLOSED.
     */
    BudgetLine addLineItem(
        UUID userId, 
        UUID budgetId, 
        BudgetLineInput lineInput
    ) throws ResourceNotFoundException, DuplicateCategoryException, LineItemLimitExceededException, InvalidBudgetException, HistoricalBudgetException;

    /**
     * Updates the target limit amount of an existing line item on an ACTIVE budget.
     * 
     * @param userId         Unique identifier of the requesting user.
     * @param budgetId       Unique identifier of the target budget.
     * @param lineId         Unique identifier of the line item to modify.
     * @param newLimitAmount The updated target limit amount.
     * @return BudgetLine    The updated line item domain entity.
     * 
     * @throws ResourceNotFoundException If budgetId or lineId does not exist or belong to user.
     * @throws InvalidBudgetException   If newLimitAmount violates range constraints.
     * @throws HistoricalBudgetException If budget status is CLOSED.
     */
    BudgetLine updateLineItemLimit(
        UUID userId, 
        UUID budgetId, 
        UUID lineId, 
        BigDecimal newLimitAmount
    ) throws ResourceNotFoundException, InvalidBudgetException, HistoricalBudgetException;

    /**
     * Removes a line item from an ACTIVE budget.
     * 
     * @param userId   Unique identifier of the requesting user.
     * @param budgetId Unique identifier of the target budget.
     * @param lineId   Unique identifier of the line item to delete.
     * 
     * @throws ResourceNotFoundException If budgetId or lineId does not exist.
     * @throws HistoricalBudgetException If budget status is CLOSED.
     */
    void removeLineItem(
        UUID userId, 
        UUID budgetId, 
        UUID lineId
    ) throws ResourceNotFoundException, HistoricalBudgetException;
}

### REQ-5.3: Quick Start Templates 
A. Business Rules
- System & Custom Template Availability: The system provides predefined global templates (is_system = true, e.g., "Basic Living", "Aggressive Savings") and user-owned custom templates (is_system = false). Users can inspect and select these templates to populate new budget instances.
- Template Isolation & Copy-on-Instantiate: Applying a template acts purely as an initial seed. Copying line item categories and limitAmount values into a target budget creates independent ledger.budget_lines records; actions on instantiated budgets never mutate the source template.
- Template Line Item Pre-Population: When creating a budget from a template for current or past periods, the spentAmount for each inherited template line item shall automatically query and sum approved transactions matching that category within the target period's date range. For future periods, spentAmount initializes to $0.00.
- Template Line Item Overrides: Users may pass custom line items or explicit overrides in the budget creation payload alongside a templateId to append or adjust baseline template values prior to persistence.

B. Constraints
- Template Limit Ceiling: A template cannot contain more than 50 line items.
- Target Line Ceiling: Merging template items with explicit user override items must not cause total lines on the created budget to exceed 50.
- Template Name Uniqueness: Custom template names created by a user must be unique per user account (case-insensitive). System template names are globally unique.
- Range Constraint for limitAmount: Every line item limitAmount inside a template must comply with standard monetary rules: scale of 2 decimal places, range [0.00, 999,999,999.99].

C. Data Impacts
- State Changes: Reads from ledger.budget_templates and ledger.budget_template_lines. Inserts new records into ledger.budgets and ledger.budget_lines.
- Side Effects: Calculates aggregate spending for inherited categories from ledger.transactions and initializes total aggregated limits on ledger.budgets.

D. REST API Mapping

Location: com.fintracker.ledger.budget.controller.BudgetTemplateController

Endpoints:
- GET /api/v1/budget-templates — List available system and custom templates.
- GET /api/v1/budget-templates/{templateId} — Get detailed line items of a template.
- POST /api/v1/budgets/quick-start — Create a new budget using a template.

Success Responses:
- 200 OK — Retrieved template list or details.
- 201 CREATED — Successfully instantiated budget from template.

Error Mapping:
- 400 BAD REQUEST — Invalid monetary precision or corrupt template payload (InvalidBudgetException).
- 404 NOT FOUND — Selected templateId does not exist (ResourceNotFoundException).
- 409 CONFLICT — Duplicate template name on custom template creation (DuplicateTemplateException).
- 422 UNPROCESSABLE ENTITY — Attempting to instantiate into a closed budget window or rule violation (HistoricalBudgetException).

E. Interface Details
Location: com.fintracker.ledger.budget.service.BudgetTemplateService
interface BudgetTemplateService {

    /**
     * Fetches all available system default templates and custom templates owned by the user.
     * 
     * @param userId Unique identifier of the requesting user.
     * @return List<BudgetTemplateDTO> List of available templates.
     */
    List<BudgetTemplateDTO> getAvailableTemplates(UUID userId);

    /**
     * Retrieves details and line items for a specific budget template.
     * 
     * @param userId     Unique identifier of the requesting user.
     * @param templateId Unique identifier of the target template.
     * @return BudgetTemplateDTO The detailed template DTO including line item definitions.
     * 
     * @throws ResourceNotFoundException If templateId does not exist or user lacks access.
     */
    BudgetTemplateDTO getTemplateById(UUID userId, UUID templateId) throws ResourceNotFoundException;

    /**
     * Instantiates a new Budget for a specific target month using a Template or Previous Month Rollover.
     * 
     * If request.getTemplateId() is provided, lines are copied from the template.
     * If request.getTemplateId() is null, lines are cloned from the user's most recent active budget.
     * 
     * @param userId  Unique identifier of the requesting user.
     * @param request Payload containing target period, templateId (optional), and custom overrides.
     * @return BudgetDTO The newly created and populated budget instance.
     * 
     * @throws ResourceNotFoundException     If target template or user resource is not found.
     * @throws LineItemLimitExceededException If total lines generated exceed 50 items.
     * @throws InvalidBudgetException       If monetary scale or limits are invalid.
     * @throws HistoricalBudgetException     If the target effective month is closed or read-only.
     */
    BudgetDTO instantiateQuickStartBudget(
        UUID userId, 
        QuickStartBudgetRequest request
    ) throws ResourceNotFoundException, LineItemLimitExceededException, InvalidBudgetException, HistoricalBudgetException;
}

F. Data Contract
================================================================================
DATA CONTRACT: QUICK START TEMPLATES (REQ-5.3)
================================================================================

--- 1. DATABASE SCHEMA CONTRACT: TEMPLATES TABLE ---
Table Name: ledger.budget_templates
Description: Stores global system templates and custom user-created templates.

Column: id | Type: UUID | Constraints: PRIMARY KEY, DEFAULT gen_random_uuid() | Description: Unique identifier for the template.
Column: user_id | Type: UUID | Constraints: NULLABLE, FOREIGN KEY -> security.users(id) | Description: Owner user ID; NULL indicates a system template.
Column: name | Type: VARCHAR(100) | Constraints: NOT NULL | Description: Display name of the template.
Column: description | Type: VARCHAR(255) | Constraints: NULLABLE | Description: Brief summary of the budget template strategy.
Column: is_system | Type: BOOLEAN | Constraints: NOT NULL, DEFAULT false | Description: Flag set to true for globally available templates.
Column: created_at | Type: TIMESTAMPTZ | Constraints: NOT NULL, DEFAULT CURRENT_TIMESTAMP | Description: Record creation timestamp.
Column: updated_at | Type: TIMESTAMPTZ | Constraints: NOT NULL, DEFAULT CURRENT_TIMESTAMP | Description: Record update timestamp.

Constraint: UNIQUE INDEX uq_user_template_name ON ledger.budget_templates(LOWER(name)) WHERE user_id IS NULL
Constraint: UNIQUE INDEX uq_custom_template_name ON ledger.budget_templates(user_id, LOWER(name)) WHERE user_id IS NOT NULL

--- 2. DATABASE SCHEMA CONTRACT: TEMPLATE LINE ITEMS TABLE ---
Table Name: ledger.budget_template_lines
Description: Stores default category allocations associated with a template.

Column: id | Type: UUID | Constraints: PRIMARY KEY, DEFAULT gen_random_uuid() | Description: Unique line item identifier.
Column: template_id | Type: UUID | Constraints: NOT NULL, FOREIGN KEY -> ledger.budget_templates(id) ON DELETE CASCADE | Description: Foreign key to parent template.
Column: category_name | Type: VARCHAR(50) | Constraints: NOT NULL | Description: Name of the line item category.
Column: default_limit | Type: NUMERIC(11,2) | Constraints: NOT NULL, CHECK (default_limit >= 0.00 AND default_limit <= 999999999.99) | Description: Predefined budget limit ceiling for the line item.
Column: created_at | Type: TIMESTAMPTZ | Constraints: NOT NULL, DEFAULT CURRENT_TIMESTAMP | Description: Record creation timestamp.

Constraint: UNIQUE INDEX uq_template_category ON ledger.budget_template_lines(template_id, LOWER(category_name))

--- 3. PAYLOAD CONTRACT: QUICK START BUDGET REQUEST ---
Target Endpoint: POST /api/v1/budgets/quick-start
Request Format: JSON

Field: effectiveMonth | Type: String (YYYY-MM) | Required: Yes | Constraints: Valid YearMonth string, non-closed month | Example: "2026-09"
Field: templateId | Type: UUID (String) | Required: No | Constraints: Must exist in ledger.budget_templates if provided | Example: "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
Field: totalBudgetCap | Type: Numeric | Required: No | Constraints: Max scale 2, range [0.00, 999999999.99] | Example: 5000.00
Field: customOverrides | Type: Array[Object] | Required: No | Constraints: Max total lines including template items <= 50 | Example: [{"categoryName": "Subscriptions", "limitAmount": 50.00}]
Field: customOverrides[].categoryName | Type: String | Required: Yes | Constraints: Non-blank, max length 50 chars | Example: "Subscriptions"
Field: customOverrides[].limitAmount | Type: Numeric | Required: Yes | Constraints: Max scale 2, range [0.00, 999999999.99] | Example: 50.00

--- 4. PAYLOAD CONTRACT: BUDGET RESPONSE DTO ---
Response Status: 201 CREATED
Response Format: JSON

Field: budgetId | Type: UUID (String) | Constraints: Non-null | Example: "c0a80121-8930-11ee-b9d1-0242ac120002"
Field: userId | Type: UUID (String) | Constraints: Non-null | Example: "3fa85f64-5717-4562-b3fc-2c963f66afa6"
Field: effectiveMonth | Type: String (YYYY-MM) | Constraints: Non-null | Example: "2026-09"
Field: status | Type: String (Enum) | Constraints: Values = ['ACTIVE', 'CLOSED'] | Example: "ACTIVE"
Field: totalPlannedLimit | Type: Numeric | Constraints: Sum of line item limitAmounts | Example: 5050.00
Field: totalSpent | Type: Numeric | Constraints: Calculated aggregate from matching transactions | Example: 0.00
Field: lines | Type: Array[Object] | Constraints: Array of generated budget lines | Example: See line item structure below
Field: lines[].lineId | Type: UUID (String) | Constraints: Non-null | Example: "f1d828a2-8930-11ee-b9d1-0242ac120002"
Field: lines[].categoryName | Type: String | Constraints: Non-null, case-preserved | Example: "Housing / Rent / Mortgage"
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

