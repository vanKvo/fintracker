# Bug name: Dashboard data only renders after a window resize

## Problem

The Dashboard page (`fintracker-ui/src/app/features/dashboard/`) loaded its data successfully but
rendered nothing dynamic. Summary stat tiles stayed at their `$0.00` / `0` initial values, all three
charts stayed in their "No data available" empty state, and the Recent Transactions table stayed
empty — even though the network tab showed the Ledger responses arriving with correct payloads.

The values appeared the instant the browser window was resized (or the sidenav toggled), which made
the bug look cosmetic or chart-library related. It is neither: it is a change-detection bug.

### Root cause

The app runs **zoneless**. It is on Angular 21, `angular.json` has no `polyfills` entry, `zone.js`
is not in `package.json`, and `app.config.ts` provides no explicit change-detection provider — so
Angular bootstraps with the zoneless scheduler.

Under zoneless change detection, mutating plain component fields is not a change-detection trigger.
Angular only schedules a render when something notifies its scheduler: a signal write, an
`AsyncPipe` emission, a template event binding firing, `afterNextRender`, or an explicit
`ChangeDetectorRef.markForCheck()` / `ApplicationRef.tick()`.

`ngOnInit` assigned the HTTP results straight onto plain fields (`summaryStats`,
`recentTransactions`, `cashflowChartData`, …) inside a bare `.subscribe()` callback. Nothing in that
path notifies the scheduler, so the new state sat in memory with the DOM still showing the initial
values. Resizing the window happened to trigger a tick through unrelated CDK viewport listeners,
which is why the data "appeared on resize".

A previous fix attempt wrapped the assignments in `NgZone.run()`. **That call is a no-op here.**
Without `zone.js` loaded, the injected `NgZone` is a `NoopNgZone` whose `run()` simply invokes the
callback and notifies no scheduler. The code looked like it addressed the problem while changing
nothing, which is why the symptom survived it.

### Code with bug

```ts
// dashboard.ts
import { Component, OnInit, NgZone } from '@angular/core';

constructor(
  private dashboardService: DashboardService,
  private transactionService: TransactionService,
  private accountService: AccountService,
  private snackBar: MatSnackBar,
  private zone: NgZone
) {}

ngOnInit() {
  forkJoin({ /* aggregations, transactions, accounts */ })
    .subscribe(({ aggregations, transactions, accounts }) => {
      // NoopNgZone.run() in a zoneless app: runs the callback, schedules no render.
      this.zone.run(() => {
        this.summaryStats.numberOfAccounts = accounts.length;
        if (aggregations) {
          this.summaryStats.totalBalance = '$' + (aggregations['Total Balance'] || '0.00');
          // ...
        }
        if (transactions && Array.isArray(transactions)) {
          this.allTransactions = transactions;
          this.applyTimeRangeFilter();
        }
      });
    });
}

onTimeRangeChange(_change: MatSelectChange) {
  this.zone.run(() => this.applyTimeRangeFilter());
}
```

## Solution

Replace the ineffective `NgZone` usage with an explicit notification to the zoneless scheduler via
`ChangeDetectorRef.markForCheck()`, which is the supported escape hatch for publishing state that is
not held in signals.

1. Swap the `NgZone` import and constructor parameter for `ChangeDetectorRef`.
2. Unwrap the `zone.run()` block in `ngOnInit` — the assignments run directly in the subscribe
   callback — and call `this.cdr.markForCheck()` once after all state has been written, so a single
   render publishes stats, charts, and the transactions table together.
3. Drop the `zone.run()` in `onTimeRangeChange`. That handler is invoked from a template event
   binding (`(selectionChange)`), which the zoneless scheduler already treats as a change-detection
   trigger, so no explicit notification is required.

Verified with `ng build --configuration development` — clean build, no diagnostics.

### Fixed Code

```ts
// dashboard.ts
import { Component, OnInit, ChangeDetectorRef } from '@angular/core';

constructor(
  private dashboardService: DashboardService,
  private transactionService: TransactionService,
  private accountService: AccountService,
  private snackBar: MatSnackBar,
  private cdr: ChangeDetectorRef
) {}

ngOnInit() {
  forkJoin({ /* aggregations, transactions, accounts */ })
    .subscribe(({ aggregations, transactions, accounts }) => {
      // This app runs zoneless (Angular 21, no zone.js polyfill), so mutating plain component
      // fields from an HttpClient subscribe callback does not schedule a render on its own.
      // markForCheck() notifies the zoneless change-detection scheduler directly.
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

      this.cdr.markForCheck();
    });
}

onTimeRangeChange(_change: MatSelectChange) {
  // No markForCheck() needed: this runs from a template event binding, which the zoneless
  // scheduler already treats as a change-detection trigger.
  this.applyTimeRangeFilter();
}
```

## Related follow-ups (not fixed here)

- `fintracker-ui/src/app/core/services/idle-timer.service.ts` uses the same `NgZone.run()` pattern
  (lines 52 and 56) and is subject to the same no-op. It is not currently user-visible because
  opening a `MatDialog` and router navigation both schedule their own render, but the calls are
  misleading and should be removed.
- Any other component that assigns HTTP results to plain (non-signal) fields will have this same
  latent bug. The durable fix across the app is to hold view state in `signal()`s, as
  `features/transactions/transactions.ts` already does.
- `dashboard.html:109` uses `routerLink` on the "View All" button, but `RouterLink` is not in the
  component's `imports`, so the attribute is inert and the button does nothing.
