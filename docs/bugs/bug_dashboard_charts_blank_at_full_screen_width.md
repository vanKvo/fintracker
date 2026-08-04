# Bug name: Dashboard shows no data until the browser window is resized

## Problem
After navigating to the Dashboard (from Transactions, Statements, or any other page) or after a full page refresh, none of the fetched data renders — summary stats, charts, and the recent transactions table all stay empty/at their initial defaults. Resizing the browser window — in either direction, not specifically toward or away from full screen, and not tied to any particular breakpoint — makes the already-fetched data appear immediately.

An earlier pass at this bug (see git history for this file) incorrectly attributed it to a `mat-sidenav-content` layout/`ResizeObserver` race specific to full-screen widths, and "fixed" it by forcing each Chart.js canvas to `.resize()` after computing chart data. That fix didn't address the real cause — the fact that *all* data was affected (not just charts), that it also happened on a cold page refresh (no prior route/layout state to race against), and that literally any resize in either direction fixed it (not just crossing a layout breakpoint) all pointed to something more fundamental than canvas sizing.

### Root cause:
This Angular app runs without `zone.js` — it isn't listed in `package.json`, there's no `zone.js` polyfill entry in `angular.json`, and `src/app/app.config.ts` doesn't call `provideZonelessChangeDetection()` either. In this configuration, Angular's own template event bindings (`(click)`, `(selectionChange)`, etc.) and router navigation still trigger change detection through Angular's own internal notification path, but a plain RxJS `.subscribe()` callback resolving from an `HttpClient` call does **not** — there's no zone.js left to patch the underlying async completion and notify Angular that a re-render is needed.

`Dashboard.ngOnInit()` (`fintracker-ui/src/app/features/dashboard/dashboard.ts`) fetches aggregations/transactions/accounts via `forkJoin(...).subscribe(...)` and mutates plain component fields (`summaryStats`, `recentTransactions`, `categoryChartData`, etc.) directly inside that callback. Those mutations happen correctly in memory, but nothing tells Angular to re-render — so the DOM keeps showing whatever it rendered on the initial (pre-data) pass. The reason a **window resize in either direction** fixes it: `mat-sidenav-container` (wrapping every route in `fintracker-ui/src/app/shared/layout/layout.html`) uses Angular CDK's `ViewportRuler` internally to track viewport size, and CDK is written to explicitly re-enter the Angular zone (`ngZone.run(...)`) when it emits — regardless of zone.js being present. That one `ngZone.run()` call is enough to trigger a global change-detection tick, which finally flushes the already-populated (but never rendered) Dashboard state to the DOM. This has nothing to do with chart canvas sizing specifically.

This same gap already exists elsewhere in the codebase and was worked around correctly: `fintracker-ui/src/app/core/services/idle-timer.service.ts` explicitly wraps its `setTimeout` callbacks in `this.zone.run(...)` for exactly this reason. `Dashboard` didn't follow that same pattern.

### Code with bug:
```typescript
ngOnInit() {
  forkJoin({
    aggregations: this.dashboardService.getDashboardAggregations().pipe(catchError(() => of(null))),
    transactions: this.transactionService.getTransactions().pipe(catchError(() => of(null))),
    accounts: this.accountService.getAccounts().pipe(catchError(() => of([])))
  }).subscribe(({ aggregations, transactions, accounts }) => {
    this.summaryStats.numberOfAccounts = accounts.length;
    // ...sets summaryStats, recentTransactions, calls computeCharts()...
    // None of this notifies Angular's change-detection scheduler in a zoneless app.
  });
}
```

## Solution
Wrap the state-mutating body of the `subscribe()` callback in `NgZone.run(...)`, matching the existing pattern already established in `IdleTimerService`. This explicitly notifies Angular that a re-render is needed once the async HTTP data arrives, without depending on an unrelated resize event to do it indirectly. The time-range `<mat-select>` change handler is wrapped the same way, defensively, since it wasn't otherwise possible to confirm via live browser testing (no Chrome DevTools MCP server available in this session) which exact internal Angular code paths do or don't auto-trigger a render in this no-zone.js, no-explicit-zoneless-provider configuration.

The earlier, incorrect `chart.resize()` workaround (and its now-unnecessary `@ViewChildren(BaseChartDirective)` query) was removed — it never addressed the actual cause, since Angular's `[data]` input binding on each `<canvas baseChart>` was itself never being re-evaluated without a CD tick, so calling `.resize()` on a chart still holding stale/empty data wouldn't have shown real data either.

### Fixed Code
```typescript
constructor(
  private dashboardService: DashboardService,
  private transactionService: TransactionService,
  private accountService: AccountService,
  private snackBar: MatSnackBar,
  private zone: NgZone
) {}

ngOnInit() {
  forkJoin({
    aggregations: this.dashboardService.getDashboardAggregations().pipe(catchError(() => of(null))),
    transactions: this.transactionService.getTransactions().pipe(catchError(() => of(null))),
    accounts: this.accountService.getAccounts().pipe(catchError(() => of([])))
  }).subscribe(({ aggregations, transactions, accounts }) => {
    this.zone.run(() => {
      this.summaryStats.numberOfAccounts = accounts.length;

      if (aggregations) {
        this.summaryStats.totalBalance = '$' + (aggregations['Total Balance'] || '0.00');
        this.summaryStats.monthlyIncome = '$' + (aggregations['Monthly Income'] || '0.00');
        this.summaryStats.monthlyExpenses = '$' + (aggregations['Monthly Expenses'] || '0.00');
      } else {
        this.snackBar.open('Dashboard data failed to load.', 'Dismiss', { duration: 5000 });
      }

      if (transactions && Array.isArray(transactions)) {
        this.allTransactions = transactions;
        this.applyTimeRangeFilter();
      } else {
        this.snackBar.open('Transactions failed to load.', 'Dismiss', { duration: 5000 });
      }
    });
  });
}

onTimeRangeChange(_change: MatSelectChange) {
  this.zone.run(() => this.applyTimeRangeFilter());
}
```

## Follow-up worth flagging
This is very likely a systemic gap, not specific to Dashboard — any other page in `fintracker-ui` that fetches data via a plain `HttpClient`/service `.subscribe()` call and mutates plain component fields (rather than using the `async` pipe or signals) is likely susceptible to the same "data fetched but never rendered until an unrelated event forces a tick" symptom. Worth an audit of `Transactions`, `Statements`, `Budgets`, and `Settings` for the same pattern. The most durable long-term fix would be adopting Angular signals (`toSignal()` for the HTTP calls) or explicitly enabling `provideZonelessChangeDetection()`, which sets up Angular's own coalescing scheduler instead of requiring manual `NgZone.run()` calls scattered through the codebase.
