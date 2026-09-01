# Bug name: Selecting a past month on the Budgets page labels it ACTIVE

## Problem

On the Budgets page, clicking a past month in the left-hand month list makes an **ACTIVE** status
badge appear for that month. Per REQ-5.1 "Automated Period Closure", a budget whose period has
already elapsed should read **CLOSED** — only current and future periods are ACTIVE.

The badge is not merely a display artifact: the row really is `status = 'ACTIVE'` in
`ledger.budgets`, so the budget also stays writable and the "reopen" affordance is hidden. The
wrong state persists until the next 1st of the month, when the scheduled closure job runs.

### Root cause

`GET /api/v1/ledger/budgets?month=` is **not a pure read**. `BudgetController.getBudget` delegates
to `BudgetServiceImpl.getBudgetForMonth` → `getOrCreateBudgetFromPrevious`, which lazily
*materializes* a budget row (cloning line items from the user's most recent active budget) whenever
the requested month has none.

That lazy-create path hardcoded `BudgetStatus.ACTIVE` regardless of the requested period. The UI's
month list is a client-generated rolling window spanning 12 months back through 3 months forward
([`budgets.ts` `buildMonthOptions()`](../../fintracker-ui/src/app/features/budgets/budgets.ts)), so
simply *browsing* to any of those past months minted a fresh ACTIVE budget for an elapsed period.

`BudgetPeriodCloser` — the only thing that would have corrected the status — runs on
`cron = "0 0 0 1 * *"`, i.e. once at the start of each month. A row auto-created for a past month
therefore advertised itself as ACTIVE for the remainder of the current month.

Note this is specific to the **lazy-create** path. Explicit creation via `upsertBudget` (the
Create Budget dialog) correctly stays ACTIVE for any period — REQ-5.1 "State Initialization" pins
that deliberately, so a user backfilling a past month can still edit what they just created.

### Code with bug

`services/fintracker-ledger/src/main/java/com/fintracker/ledger/budget/service/impl/BudgetServiceImpl.java`

```java
private Budget createFromPrevious(UUID userId, LocalDate newMonth) {
    var templateLines = budgetRepository.findLatestActiveByUserId(userId)
            .map(previous -> {
                log.info("Cloning most recent active budget {} as base for month={}",
                        previous.budgetId(), newMonth);
                return cloneLines(previous.lines());
            })
            .orElseGet(List::of);

    try {
        var saved = budgetRepository.save(
                // Always ACTIVE — even when newMonth has already elapsed.
                new Budget(null, userId, newMonth, 1, BudgetStatus.ACTIVE, null, templateLines, null));
        ...
```

## Solution

Derive the birth status of a *lazily* created budget from its period instead of hardcoding it: a
month strictly before the current month is created `CLOSED`, the current month and any future month
`ACTIVE`. This puts the auto-created row directly into the state `closePastBudgets` would already
have left it in, so a read of history no longer produces observable, incorrect state.

Steps:

1. Add `lazyCreateStatusFor(LocalDate)` to `BudgetServiceImpl`, comparing the normalized month
   against `currentMonth()` — which resolves through the injected `Clock`, keeping the
   classification deterministic and zone-independent (never `LocalDate.now()`).
2. Use it as the status argument in `createFromPrevious`. `upsertBudget`'s explicit-create branch is
   deliberately left on `BudgetStatus.ACTIVE`, per REQ-5.1 "State Initialization".
3. No UI change is needed: `budgets.html` renders the badge straight off `budget.status`, and the
   "reopen" button is already driven by `isClosed`. Both become correct once the server returns the
   right status.

Regression coverage added to `BudgetLifecycleIT`:

- `lazilyCreatedPastPeriodBudgetInitializesClosed` — asserts both the returned model and the
  `ledger.budgets.status` column directly, so a bug in the read path cannot mask one in the write
  path.
- `lazilyCreatedCurrentAndFuturePeriodBudgetsInitializeActive` — pins that the fix keys off the
  month having elapsed, not off the budget having been auto-created.
- `lazilyCreatedClosedBudgetCanBeReopened` — a lazily created CLOSED budget is not a dead end;
  REQ-5.1 "Reopening Exemption" still applies, which is what the UI's reopen button drives.

Full budget suite: 125 tests, 0 failures.

### Fixed Code

```java
/**
 * The status a <em>lazily</em> created budget is born in — the one materialized by a read of a
 * month that has no budget yet, which no user explicitly asked for.
 *
 * <p>REQ-5.1 "State Initialization" pins <em>explicitly</em> created budgets (upsertBudget) to
 * ACTIVE for any period, so a user deliberately backfilling a past month can still edit it.
 * A system-materialized row has no such intent behind it, and stamping it ACTIVE contradicts
 * REQ-5.1 "Automated Period Closure": the closure job only runs on the 1st of the month, so a
 * row auto-created for an elapsed month would advertise itself as ACTIVE — and render an
 * ACTIVE badge in the UI — until the next month boundary. Creating it in the state the closure
 * job would already have left it in keeps read-only browsing of history free of side effects
 * the user can observe.
 */
private BudgetStatus lazyCreateStatusFor(LocalDate normalizedMonth) {
    return normalizedMonth.isBefore(currentMonth()) ? BudgetStatus.CLOSED : BudgetStatus.ACTIVE;
}

private Budget createFromPrevious(UUID userId, LocalDate newMonth) {
    var templateLines = budgetRepository.findLatestActiveByUserId(userId)
            .map(previous -> {
                log.info("Cloning most recent active budget {} as base for month={}",
                        previous.budgetId(), newMonth);
                return cloneLines(previous.lines());
            })
            .orElseGet(List::of);

    try {
        var saved = budgetRepository.save(
                new Budget(null, userId, newMonth, 1, lazyCreateStatusFor(newMonth), null,
                        templateLines, null));
        ...
```
