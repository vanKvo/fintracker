# Transactions Requirements

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
A. Business Rules:
- System & Custom Template Availability: The system shall provide predefined system templates (e.g., "Basic Living", "Aggressive Savings") and allow users to select from their own saved custom templates to quickly populate a new budget.
- Template Customization: Applying a template serves as an initial baseline; line item categories and limitAmount values copied from a template remain fully customizable prior to budget creation.
- Template Selection & Fallback: When a user selects a template, all associated template line items are copied into the target budget period. If no template is selected (templateId is null), the budget must be initialized with explicit line items provided in the request payload.

Template Line Item Pre-Population: When creating a budget from a template for current or past periods, the spentAmount for each inherited template line item shall automatically query and sum approved transactions matching that category within the target period's date range. For future periods, spentAmount initializes to $0.00.

Template Immutability Isolation: Modifying or customizing line items when instantiating a budget from a template shall not mutate or alter the original underlying template definition.

B. Method Signature: Internal to getBudgetForMonth.  
C. Business Rules & Constraints:
- Source Resolution: The system queries the database to find the most recent previous budget record configured for the user. If no previous records are found, the copy step is skipped.
D. System Behavior & Data Impact:
- State Change: Clones the prior month's active category items and limitAmount values, saving them into a new Budget row aligned to the target effectiveMonth.
E. Edge Cases & Error Handling:
- Validation Failures: If the source data contains a corrupt field format, the copy transaction fails, and the system throws 'Invalid Budget'.

## REQ-5.3: Get Budget Progress and Pacing (Depends on REQ-5.1 & Transaction Module)
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

