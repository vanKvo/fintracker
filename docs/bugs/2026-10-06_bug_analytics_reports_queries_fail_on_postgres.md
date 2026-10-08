# Bug name: Analytics spending report and monthly trend queries fail on every call

## Problem
Found while adding TXT-02 integration tests for the Analytics Service. Both report endpoints fail on every request against a real Postgres. Users never get a report.

- **Spending report** (`get_spending_report`): fails with `asyncpg.exceptions.DataError: invalid input for query argument $2: '2026-10-01'`.
- **Monthly trend** (`get_monthly_trend`): fails with `GroupingError: subquery uses ungrouped column "t.tx_date" from outer query`.

There were no repository tests against a real database, so neither failure had been caught.

### Root cause:
1. **Spending report.** The router passes `date_from`/`date_to` through as ISO strings. asyncpg binds parameters strictly by type: once Postgres infers that a parameter compared with a `DATE` column is a date, it rejects a Python `str`.
2. **Monthly trend.** The budget-limit subquery refers to `t.tx_date`, which is ungrouped, from inside a `GROUP BY month` query. Postgres rejects this even when grouping by `date_trunc('month', t.tx_date)`. A second fault is in the lookback window: `INTERVAL ':months months'` places the bind parameter inside a string literal, so it is never bound as a value.

### Code with bug:
```python
# src/reports/repository.py — get_spending_report
{"user_id": user_id, "date_from": date_from, "date_to": date_to},

# src/reports/repository.py — get_monthly_trend
COALESCE((
    SELECT SUM(bl.limit_amount)
    ...
      AND b.effective_month = date_trunc('month', t.tx_date)
), 0) AS budget_limit
FROM ledger.transactions t
...
  AND t.tx_date >= date_trunc('month', NOW()) - INTERVAL ':months months'
GROUP BY month, a.user_id
```

## Solution
Bind real `date` objects, and aggregate the trend per month before looking up budgets.

1. Spending report: convert the ISO strings with `date.fromisoformat` before binding.
2. Monthly trend: aggregate the transactions per month in a CTE (`monthly`), then look up each month's budget limit against the CTE's plain `month_start` column.
3. Monthly trend: bind the lookback as `make_interval(months => :months)`.
4. Covered by `tests/integration/test_transaction_type_queries.py` (Testcontainers Postgres), which also covers the TXT-02 type changes in the same queries.

### Fixed Code
```python
# get_spending_report
{"user_id": user_id, "date_from": date.fromisoformat(date_from), "date_to": date.fromisoformat(date_to)},

# get_monthly_trend
WITH monthly AS (
    SELECT
        date_trunc('month', t.tx_date)::date AS month_start,
        a.user_id,
        SUM(CASE WHEN t.type = 'INCOME' THEN ABS(t.amount) ELSE 0 END) AS income,
        SUM(CASE WHEN NOT t.is_excluded THEN CASE t.type
            WHEN 'EXPENSE' THEN ABS(t.amount)
            WHEN 'REFUND'  THEN -ABS(t.amount)
            ELSE 0 END ELSE 0 END) AS expenses
    FROM ledger.transactions t
    JOIN ledger.accounts a ON a.account_id = t.account_id
    WHERE a.user_id = :user_id
      AND t.status = 'POSTED'
      AND t.tx_date >= date_trunc('month', NOW()) - make_interval(months => :months)
    GROUP BY 1, 2
)
SELECT
    to_char(m.month_start, 'YYYY-MM') AS month,
    COALESCE(m.income, 0)   AS income,
    COALESCE(m.expenses, 0) AS expenses,
    COALESCE((
        SELECT SUM(bl.limit_amount)
        FROM ledger.budgets b
        JOIN ledger.budget_lines bl ON bl.budget_id = b.budget_id
        WHERE b.user_id = m.user_id
          AND b.effective_month = m.month_start
    ), 0) AS budget_limit
FROM monthly m
ORDER BY m.month_start ASC
```
