# Bug name: Dashboard showed fabricated demo data for a brand-new user instead of a zero state

## Problem

Logging in as a genuinely new user (an account with zero accounts/transactions/budgets in
Postgres) showed a fully populated Dashboard — non-zero balances, populated charts, a "Recent
Transactions" table, and an "Upcoming Bills" list — instead of the correct $0.00 / empty-state
view. The figures were plausible-looking but entirely fabricated, making it impossible to tell
from the UI alone whether a user had real data or none at all.

Found while manually verifying multi-tenant data isolation: after creating a second local user
with zero seeded ledger data (see `docs/instructions/dev_setup_user.py_create_new_user.md`), its
Dashboard rendered as if it belonged to an active account.

### Root cause

`dashboard.ts` fetched the real, correctly-scoped Ledger endpoints (`getDashboardAggregations()`,
`getTransactions()`, `getAccounts()`), but treated **"the call failed"** and **"the call
succeeded with zero rows"** as the same condition:

```ts
const liveTransactions = Array.isArray(transactions) ? transactions : null;
const hasLiveData = !!aggregations && !!liveTransactions && liveTransactions.length > 0;
```

A brand-new account legitimately returns a successful, empty array. `liveTransactions.length ===
0` collapsed `hasLiveData` to `false` exactly as a network failure would, and
`environment.useDemoDataFallback` (`true` in the dev environment, intended only to keep demo
walkthroughs from showing a blank page) then populated the entire page from a synthetic dataset
generator (`dashboard-demo-data.ts`) — indistinguishable from real data in the rendered markup.

### Code with bug

```ts
// dashboard.ts
ngOnInit() {
  forkJoin({
    aggregations: this.dashboardService.getDashboardAggregations().pipe(catchError(() => of(null))),
    transactions: this.transactionService.getTransactions().pipe(catchError(() => of(null))),
    accounts: this.accountService.getAccounts().pipe(catchError(() => of([])))
  }).subscribe(({ aggregations, transactions, accounts }) => {
    const liveTransactions = Array.isArray(transactions) ? transactions : null;
    const hasLiveData = !!aggregations && !!liveTransactions && liveTransactions.length > 0;

    if (!hasLiveData && environment.useDemoDataFallback) {
      this.applyDemoData();   // fires for a real empty ledger, not just a failed request
      this.cdr.markForCheck();
      return;
    }
    // ...
  });
}
```

## Solution

Removed the demo-data fallback entirely rather than trying to special-case it further — a
finance app must never show fabricated figures a user could mistake for their own money, and the
underlying conflation (failed vs. empty) was the actual defect worth fixing regardless.

1. Deleted `dashboard-demo-data.ts` and the `useDemoDataFallback` flag from
   `environment.interface.ts` / `environment.ts` / `environment.production.ts`.
2. Track each section's fetch outcome independently (`summaryLoadFailed`,
   `transactionsLoadFailed`, `billsLoadFailed`) instead of one combined "nothing to show"
   boolean, so a real failure and a real empty result render differently — an error banner with
   a "Try Again" retry vs. a "No transactions yet" / "No upcoming bills" empty state, matching
   the pattern already established on the Budgets page (`hasLoadError` vs. `hasNoBudgets`).
3. On failure, surface the backend's actual RFC 9457 `detail` message (`err?.error?.detail`)
   instead of a hardcoded string, consistent with `budgets.ts`.
4. Added `.empty-state` / `.empty-state.error` sections to `dashboard.html`/`dashboard.scss` for
   the Financial Summary, Upcoming Bills, and Recent Transactions cards.

Verified with a Playwright e2e test (`fintracker-ui/e2e/fresh-user-empty-state.spec.ts`) that
signs in as a freshly generated user id (guaranteed zero Postgres rows) and asserts the Dashboard
renders `$0.00` tiles, "No transactions yet", and "No upcoming bills" — with no load-error banner
for what is a successful, merely-empty response.

### Fixed Code

```ts
// dashboard.ts
private loadDashboard() {
  let aggregationsError: any = null;
  let transactionsError: any = null;

  forkJoin({
    aggregations: this.dashboardService.getDashboardAggregations().pipe(
      catchError(err => { aggregationsError = err; return of(null); })
    ),
    transactions: this.transactionService.getTransactions().pipe(
      catchError(err => { transactionsError = err; return of(null); })
    ),
    accounts: this.accountService.getAccounts().pipe(catchError(() => of([])))
  }).subscribe(({ aggregations, transactions, accounts }) => {
    this.summaryStats.numberOfAccounts = accounts.length;

    if (aggregations) {
      this.summaryLoadFailed = false;
      // ... populate summaryStats from real aggregations ...
    } else {
      this.summaryLoadFailed = true;
      const message = aggregationsError?.error?.detail || 'Failed to load dashboard summary.';
      this.snackBar.open(message, 'Dismiss', { duration: 5000 });
    }

    if (Array.isArray(transactions)) {
      this.transactionsLoadFailed = false;
      this.allTransactions = transactions;   // correctly [] for a real empty ledger
      this.applyTimeRangeFilter();
    } else {
      this.transactionsLoadFailed = true;
      this.allTransactions = [];
      this.applyTimeRangeFilter();
      const message = transactionsError?.error?.detail || 'Failed to load transactions.';
      this.snackBar.open(message, 'Dismiss', { duration: 5000 });
    }

    this.loadBills();
    this.cdr.markForCheck();
  });
}
```

```html
<!-- dashboard.html -->
@if (transactionsLoadFailed) {
  <div class="empty-state error">
    <mat-icon class="empty-icon">cloud_off</mat-icon>
    <p class="empty-title">Couldn't load transactions</p>
    <button class="empty-action-btn" (click)="loadDashboard()">Try Again</button>
  </div>
} @else if (recentTransactions.length === 0) {
  <div class="empty-state">
    <mat-icon class="empty-icon">receipt_long</mat-icon>
    <p class="empty-title">No transactions yet</p>
    <button class="empty-action-btn" routerLink="/transactions">Add Transaction</button>
  </div>
} @else {
  <!-- real transactions table -->
}
```

## Related fix found while adding the new empty-state CTAs

While adding the "Add Transaction" button to the new empty state, found that the page's
pre-existing "View All" button (`routerLink="/transactions"`) was inert — `RouterLink` was never
in `Dashboard`'s standalone `imports` array, so Angular compiled the plain-attribute `routerLink`
without ever instantiating the directive; clicking it did nothing. Verified with a throwaway
Playwright script (`page.getByText('View All').click()` followed by `page.url()`) before and
after adding `RouterLink` to `imports`, confirming the URL only changed once the import was
added. Fixed alongside this bug rather than filed separately, since it would have made the new
"Add Transaction" button equally inert.

## Related follow-ups (not fixed here)

- Every other standalone component in the app should be audited for the same
  `routerLink`-without-`RouterLink`-import pattern; this was only caught here because the new
  empty-state CTA needed it to work.
