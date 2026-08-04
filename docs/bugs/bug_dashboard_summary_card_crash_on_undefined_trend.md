# Bug name: Dashboard summary cards crash on undefined `card.trend`

## Problem
The "Financial Overview" summary cards (Total Balance, Monthly Income, Monthly Expenses) on the dashboard would fail to render with real data — reported as data "not showing up" on first visit, and "all data gone" after navigating to another page and back. Since Angular destroys and recreates the `Dashboard` component on every route (re)activation (no custom `RouteReuseStrategy` is configured — see `fintracker-ui/src/app/app.routes.ts` and `app.config.ts`), this crash occurs identically and deterministically on every mount, not just the first.

### Root cause:
`fintracker-ui/src/app/features/dashboard/dashboard.html:17-19` (before fix) evaluated `card.trend.startsWith('+')`, but `card.trend` is never set anywhere in `dashboard.ts`'s `summaryCards` construction (`ngOnInit`, lines 60-64) — every card object only has `title`, `amount`, `icon`, and `color`. The moment `summaryCards` is populated with real aggregation data and Angular re-renders the `@for` loop, this throws `TypeError: Cannot read properties of undefined (reading 'startsWith')`. Angular's change detection for the component runs as one synchronous pass; an uncaught exception partway through aborts the rest of that pass, which can leave the summary cards, charts, and transactions table — all set in the same `ngOnInit` subscribe callback and flushed in the same change-detection cycle — unrendered or stuck showing stale/empty state.

### Code with bug:
```html
<mat-card-content>
  <div class="amount">{{card.amount}}</div>
  <div class="trend" [ngClass]="card.trend.startsWith('+') ? 'positive' : 'negative'">
    {{card.trend}} vs last month
  </div>
</mat-card-content>
```
```typescript
this.summaryCards = Array.isArray(aggregations) ? aggregations : [
   { title: 'Total Balance', amount: '$' + (aggregations['Total Balance'] || '0.00'), icon: 'account_balance', color: 'primary-blue' },
   { title: 'Monthly Income', amount: '$' + (aggregations['Monthly Income'] || '0.00'), icon: 'trending_up', color: 'status-success' },
   { title: 'Monthly Expenses', amount: '$' + (aggregations['Monthly Expenses'] || '0.00'), icon: 'trending_down', color: 'status-error' }
];
```

## Solution
The Ledger's `/dashboard/aggregations` endpoint (`DashboardSummary`) doesn't currently return a period-over-period comparison, so there's no real value to back a "trend vs last month" figure — fabricating one would be worse than omitting it. Guard the template to only render the trend line when `card.trend` is actually present, so the binding never crashes and the feature can be wired up later once the backend provides real trend data, without another template change.

### Fixed Code
```html
<mat-card-content>
  <div class="amount">{{card.amount}}</div>
  @if (card.trend) {
    <div class="trend" [ngClass]="card.trend.startsWith('+') ? 'positive' : 'negative'">
      {{card.trend}} vs last month
    </div>
  }
</mat-card-content>
```
