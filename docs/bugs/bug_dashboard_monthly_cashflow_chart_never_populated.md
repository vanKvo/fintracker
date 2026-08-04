# Bug name: Dashboard Monthly Cashflow chart never populated

## Problem
On the FinTracker dashboard, the "Financial Overview" section's Monthly Cashflow chart always rendered empty, even for a dev user with real transaction data in the Ledger. This was reported alongside a second, unrelated symptom — the Monthly Income/Monthly Expenses/Cash Flow/Net Saving stat cards also showed $0.00, which turned out to be expected behavior (see Root cause) rather than a bug: the Ledger's `/dashboard/aggregations` endpoint scopes those fields strictly to the current calendar month, and the seeded dev transactions predated the current month. That part required adding current-month seed data, not a code fix.

### Root cause:
In `fintracker-ui/src/app/features/dashboard/dashboard.ts`, `computeCharts()` populated `categoryChartData` (pie chart) and `trendChartData` (line chart, itself a hardcoded placeholder) but never assigned `cashflowChartData`. It stayed at its component-level default of `{ labels: [], datasets: [] }` set at declaration, regardless of how much real transaction data was passed in — Chart.js dutifully rendered an empty bar chart every time.

### Code with bug:
```typescript
computeCharts(transactions: any[]) {
  // Pie Chart: Spends by Category
  const spends = transactions.filter(t => t.amount < 0);
  const categoryTotals: Record<string, number> = {};
  spends.forEach(t => {
    categoryTotals[t.category] = (categoryTotals[t.category] || 0) + Math.abs(t.amount);
  });
  this.categoryChartData = {
    labels: Object.keys(categoryTotals),
    datasets: [{
      data: Object.values(categoryTotals),
      backgroundColor: ['#0F62FE', '#78A9FF', '#24A148', '#F1C21B', '#DA1E28', '#8A3FFC'],
      hoverOffset: 4
    }]
  };

  // Trend & Cashflow simplification: Grouping by Week/Month could go here
  // For now, assigning to placeholder structure to prevent crashing
  this.trendChartData = {
    labels: ['Week 1', 'Week 2', 'Week 3', 'Week 4'],
    datasets: [
      { data: [200, 300, 100, 400], label: 'Income', borderColor: '#24A148', backgroundColor: 'rgba(36, 161, 72, 0.1)', fill: true },
      { data: [150, 200, 50, 300], label: 'Expenses', borderColor: '#DA1E28', backgroundColor: 'rgba(218, 30, 40, 0.1)', fill: true }
    ]
  };
}
```
Note `cashflowChartData` is never referenced anywhere in the method — it's the declared-but-unassigned property from `dashboard.ts:37`.

## Solution
Group the same `transactions` array already passed into `computeCharts()` by calendar month (`YYYY-MM`), summing positive amounts as income and absolute value of negative amounts as expenses per month, then assign the result to `cashflowChartData` as a two-dataset bar chart (Income vs. Expenses). Sorting is done on the `YYYY-MM` key (not the formatted display label) to avoid relying on loosely-specified `Date` string parsing.

`trendChartData` remains an intentional hardcoded placeholder — out of scope for this fix, called out separately to the user.

### Fixed Code
```typescript
computeCharts(transactions: any[]) {
  // Pie Chart: Spends by Category
  const spends = transactions.filter(t => t.amount < 0);
  const categoryTotals: Record<string, number> = {};
  spends.forEach(t => {
    categoryTotals[t.category] = (categoryTotals[t.category] || 0) + Math.abs(t.amount);
  });
  this.categoryChartData = {
    labels: Object.keys(categoryTotals),
    datasets: [{
      data: Object.values(categoryTotals),
      backgroundColor: ['#0F62FE', '#78A9FF', '#24A148', '#F1C21B', '#DA1E28', '#8A3FFC'],
      hoverOffset: 4
    }]
  };

  // Bar Chart: Monthly Cashflow (income vs. expenses per month)
  const monthlyTotals: Record<string, { income: number; expenses: number }> = {};
  transactions.forEach(t => {
    if (!t.date) return;
    const d = new Date(t.date);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    if (!monthlyTotals[key]) monthlyTotals[key] = { income: 0, expenses: 0 };
    if (t.amount >= 0) monthlyTotals[key].income += t.amount;
    else monthlyTotals[key].expenses += Math.abs(t.amount);
  });
  const sortedMonthKeys = Object.keys(monthlyTotals).sort();
  this.cashflowChartData = {
    labels: sortedMonthKeys.map(key => {
      const [year, month] = key.split('-').map(Number);
      return new Date(year, month - 1).toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
    }),
    datasets: [
      { data: sortedMonthKeys.map(k => monthlyTotals[k].income), label: 'Income', backgroundColor: '#24A148' },
      { data: sortedMonthKeys.map(k => monthlyTotals[k].expenses), label: 'Expenses', backgroundColor: '#DA1E28' }
    ]
  };

  // Trend simplification: Grouping by Week could go here
  // For now, assigning to placeholder structure to prevent crashing
  this.trendChartData = {
    labels: ['Week 1', 'Week 2', 'Week 3', 'Week 4'],
    datasets: [
      { data: [200, 300, 100, 400], label: 'Income', borderColor: '#24A148', backgroundColor: 'rgba(36, 161, 72, 0.1)', fill: true },
      { data: [150, 200, 50, 300], label: 'Expenses', borderColor: '#DA1E28', backgroundColor: 'rgba(218, 30, 40, 0.1)', fill: true }
    ]
  };
}
```
