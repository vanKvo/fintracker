# Bug name: Create Budget fails with a 500 error under a lazy-create race

## Problem

Clicking **Create Budget** in the Budgets page sometimes fails: the dialog closes, a "Failed to create budget." toast appears, and no budget shows up for the selected month. The backend log shows an unhandled `DuplicateKeyException` on `ledger.budgets` for `PUT /api/v1/ledger/budgets`, even though this was the *first* attempt to create a budget for that month.

Reproduced directly against the Ledger service by firing two concurrent `PUT /api/v1/ledger/budgets` requests for a month with no existing budget:

```
$ for i in 1 2; do curl -s -o /dev/null -w "%{http_code} " -X PUT \
    http://localhost:8081/api/v1/ledger/budgets \
    -H "X-Internal-User-Id: <user>" \
    -d '{"effectiveMonth":"2034-03-01","lines":[{"category":"Groceries","limitAmount":500}]}' & done; wait
201 500
```

### Root cause: `UNIQUE (user_id, effective_month, version)` doesn't enforce "one budget per month" — and lets two concurrent creates both try `version = 1`

`GET /api/v1/ledger/budgets?month=...` lazily auto-creates a budget for any month the user visits (`getOrCreateBudgetFromPrevious`). If the user clicks a month in the sidebar and then immediately opens **Create Budget** for that same month (the dialog defaults to the currently selected month) before the GET's insert has committed, two independent code paths race to create the same month's budget:

- `Budgets.selectMonth()` → `GET` → `BudgetServiceImpl.createFromPrevious()`
- `Budgets.openCreateBudgetDialog()` → `PUT` → `BudgetServiceImpl.upsertBudget()`

Both call `findByUserAndMonth()` first, both see "not found" (neither has committed yet), and both proceed to `INSERT ... version = 1`. The table's unique constraint is `UNIQUE (user_id, effective_month, version)` — a composite key that includes `version` — so it does **not** guard "at most one budget per user per month" (two rows for the same month with different `version` values are perfectly legal under it). It only rejects the second insert because, in this race, *both* inserts happen to carry `version = 1`. The losing request's `jOOQ` insert throws `DataIntegrityViolationException`, which isn't mapped by `GlobalExceptionHandler`, so it falls through to the generic `500 Internal Server Error` handler — and the request the user actually clicked can be the one that loses.

### Code with bug

`services/fintracker-ledger/src/main/resources/db/migration/V1__Initial_Schema.sql`:
```sql
CREATE TABLE ledger.budgets (
    budget_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID NOT NULL,
    effective_month DATE NOT NULL,
    version        INT  DEFAULT 1,
    created_at     TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, effective_month, version)   -- version defeats the "one per month" intent
);
```

`BudgetServiceImpl.upsertBudget()` / `createFromPrevious()` — read-then-write with no protection against a concurrent writer inserting between the read and the write:
```java
var existing = budgetRepository.findByUserAndMonth(userId, normalizedMonth);
if (existing.isPresent()) { ... }

var newBudget = new Budget(null, userId, normalizedMonth, 1, BudgetStatus.ACTIVE, null, effectiveLines, null);
var saved = budgetRepository.save(newBudget);   // throws DuplicateKeyException if another
                                                 // request just inserted this month's budget
```

## Solution

1. **Fix the constraint** to actually express the domain invariant from REQ-5.1 ("If a budget already exists for the normalized target month, submitting a valid payload will update ... rather than throwing a duplicate error"): unique on `(user_id, effective_month)`, not `(user_id, effective_month, version)`. New migration `V9__Fix_Budgets_Month_Uniqueness.sql`.
2. **Make the create path race-safe**: catch `DataIntegrityViolationException` around the insert in both `upsertBudget()` and `createFromPrevious()`. If the insert is rejected because another request just created this month's budget, treat it the same as if the read above had found it — apply the submitted lines as an update (`upsertBudget`) or simply return the winner's row unmodified (`createFromPrevious`, since a read must never overwrite data). This turns the race from a crash into the correct, spec-defined upsert behavior.

### Fixed Code

`services/fintracker-ledger/src/main/resources/db/migration/V9__Fix_Budgets_Month_Uniqueness.sql`:
```sql
ALTER TABLE ledger.budgets
    DROP CONSTRAINT budgets_user_id_effective_month_version_key;

ALTER TABLE ledger.budgets
    ADD CONSTRAINT budgets_user_id_effective_month_key UNIQUE (user_id, effective_month);
```

`BudgetServiceImpl.upsertBudget()`:
```java
var newBudget = new Budget(null, userId, normalizedMonth, 1, BudgetStatus.ACTIVE, null, effectiveLines, null);
try {
    var saved = budgetRepository.save(newBudget);
    log.info("Created new budget. budgetId={} userId={} month={} lineCount={}",
            saved.budgetId(), userId, normalizedMonth, effectiveLines.size());
    return enrichWithSpending(saved, userId, normalizedMonth);
} catch (DataIntegrityViolationException raceLoss) {
    // Another request (e.g. a concurrent lazy-create via GET) created this month's budget
    // first — the unique (user_id, effective_month) constraint rejected our insert. REQ-5.1
    // treats this the same as if we had seen it during the read above: fall back to update.
    log.info("Lost the create race for month={} userId={}; applying payload as an update.",
            normalizedMonth, userId);
    var budget = budgetRepository.findByUserAndMonth(userId, normalizedMonth)
            .orElseThrow(() -> raceLoss);
    rejectIfClosed(budget);
    budgetRepository.updateLines(budget.budgetId(), effectiveLines);
    return enrichWithSpending(
            budgetRepository.findById(budget.budgetId()).orElseThrow(
                    () -> new ResourceNotFoundException("Budget", budget.budgetId())),
            userId, normalizedMonth);
}
```

`BudgetServiceImpl.createFromPrevious()`:
```java
try {
    var saved = budgetRepository.save(
            new Budget(null, userId, newMonth, 1, BudgetStatus.ACTIVE, null, templateLines, null));
    log.info("Lazily created budget. budgetId={} userId={} month={} lineCount={}",
            saved.budgetId(), userId, newMonth, templateLines.size());
    return enrichWithSpending(saved, userId, newMonth);
} catch (DataIntegrityViolationException raceLoss) {
    // Another concurrent request (e.g. an explicit PUT) created this month's budget first.
    // A read should never overwrite that — just return what won the race.
    log.info("Lost the lazy-create race for month={} userId={}; returning the existing budget.",
            newMonth, userId);
    return budgetRepository.findByUserAndMonth(userId, newMonth)
            .map(b -> enrichWithSpending(b, userId, newMonth))
            .orElseThrow(() -> raceLoss);
}
```

Verified by repeating the two-way concurrent `PUT` reproduction above 10x — all requests now return `201`/`200`, no `500`s. Full `budget` test package (120 tests) still passes.

### Note: a related, lower-priority race

Stress-testing with three-way (rather than two-way) concurrent creates for the same brand-new month occasionally surfaces a second, independent race in `JooqBudgetRepository.updateLines()` (`budget_lines_budget_id_category_key` violation) — its delete-then-insert isn't safe against two callers rewriting the same budget's lines at the same instant. This isn't reachable through normal single-user UI interaction (it needs 3+ simultaneous identical writes to the same budget) and is out of scope for this fix, but worth a follow-up if concurrent multi-tab editing of the same budget's lines becomes a supported scenario.
