# Bug name: Date-only transaction dates parsed as UTC, shifting 1st-of-month rows into the previous month

## Problem

On the Dashboard, transactions dated the **1st of a month** were excluded from that month's figures
and counted against the previous month instead. Because the 1st is when rent and the first payroll
deposit post, this silently moved the two largest rows of every month into the wrong bucket.

Visible symptoms:

- "Monthly Income" read `$0.00` early in a month, because the only paycheck so far (the 1st) had
  been attributed to the previous month.
- "Monthly Expenses" was understated by the full rent amount.
- The Cashflow and Spending Trend charts showed a spike in the wrong month, and a phantom bucket
  appeared before the first real month of data.

The bug is timezone-dependent: it appears in any timezone with a negative UTC offset (all of the
Americas) and is invisible in UTC or ahead-of-UTC timezones, which is why it survived review.

### Root cause

The Ledger returns `txDate` as a **date-only** string, `"YYYY-MM-DD"`. Per ECMA-262, `new Date()`
parses a date-only ISO string as **UTC midnight**, whereas a date-time string without an offset is
parsed as local time. So in `America/Los_Angeles` (UTC-7):

```js
new Date('2026-08-01')          // → 2026-07-31T17:00:00 local
new Date(2026, 7, 1)            // → 2026-08-01T00:00:00 local
```

`getDateRangeForSelection()` builds its `start` / `end` boundaries with the **local-time**
`Date(year, month, day)` constructor, while `applyTimeRangeFilter()` and `computeCharts()` parsed
each transaction with `new Date(t.date)` — **UTC**. Comparing a UTC-parsed instant against a
local-time boundary shifts every date-only value backwards by the UTC offset, which is enough to
push midnight on the 1st into the previous month.

This was found while verifying a generated dataset: a run seeded with eight months of data produced
a spurious ninth month before the range started, and the current month reported zero income.

### Code with bug

```ts
// dashboard.ts
private applyTimeRangeFilter() {
  const { start, end } = this.getDateRangeForSelection(this.selectedTimeRange); // local-time boundaries
  const inRange = this.allTransactions.filter(t => {
    if (!t.date) return false;
    const d = new Date(t.date);        // UTC midnight — off by the UTC offset
    return d >= start && d <= end;
  });

  const sorted = [...inRange].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
  this.recentTransactions = sorted.slice(0, 4);
  this.computeCharts(inRange);
}

computeCharts(transactions: any[]) {
  transactions.forEach(t => {
    if (!t.date) return;
    const d = new Date(t.date);        // same defect, so the month buckets inherit it
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    // ...
  });
}
```

## Solution

Parse date-only strings explicitly in the local timezone so both sides of every comparison live on
the same clock.

1. Add a `parseLocalDate()` helper that matches `YYYY-MM-DD` and builds the date with the local-time
   `Date(year, monthIndex, day)` constructor. Strings that are not date-only (full timestamps, which
   already carry an offset) fall through to the default parse, which is correct for them.
2. Route every transaction-date read through it — the range filter, the recency sort, and the
   month-bucket key in `computeCharts()`.
3. Apply the same helper to bill due dates in `daysUntil()`, which had the same defect and could
   report a bill as due one day earlier than it is.
4. Mirror the helper in `dashboard-demo-data.ts`, whose `buildDemoAggregations()` compared
   `new Date(t.date)` against a local month start.

Verified by generating eight months of transactions and asserting each month's income and expense
totals against their planned values: every month now reconciles exactly, no phantom month appears
before the range, and no transaction is dated in the future.

### Fixed Code

```ts
// dashboard.ts
/**
 * Parses the Ledger's date-only `txDate` ("YYYY-MM-DD") in the LOCAL timezone.
 *
 * `new Date('2026-08-01')` is specified to parse a date-only string as UTC midnight, which in
 * any negative-offset timezone resolves to 2026-07-31 locally. Every range boundary below is
 * built from local-time constructors, so the mismatch pushed each 1st-of-month transaction —
 * rent and the first paycheck, the two largest rows — into the previous month's bucket.
 */
private parseLocalDate(value: string): Date {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) {
    // Full timestamps already carry an offset, so the default parse is correct for them.
    return new Date(value);
  }
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}

private applyTimeRangeFilter() {
  const { start, end } = this.getDateRangeForSelection(this.selectedTimeRange);
  const inRange = this.allTransactions.filter(t => {
    if (!t.date) return false;
    const d = this.parseLocalDate(t.date);
    return d >= start && d <= end;
  });

  const sorted = [...inRange].sort(
    (a, b) => this.parseLocalDate(b.date).getTime() - this.parseLocalDate(a.date).getTime()
  );
  this.recentTransactions = sorted.slice(0, 4);
  this.computeCharts(inRange);
}

computeCharts(transactions: any[]) {
  transactions.forEach(t => {
    if (!t.date) return;
    const d = this.parseLocalDate(t.date);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    // ...
  });
}
```

## Related follow-ups (not fixed here)

- Any other feature parsing the Ledger's date-only fields with bare `new Date(...)` has the same
  defect. `features/transactions/` and `features/budgets/` should be audited for it.
- The durable fix is a single shared date utility in `core/` rather than a private helper per
  component, so the correct parse is the path of least resistance for new code.
- Angular's `date` pipe is **not** affected: it special-cases ISO date-only strings and constructs
  them in local time, which is why the rendered dates in the table always looked right even while
  the bucketing was wrong.
