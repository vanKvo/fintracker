# Bug name: Analytics dashboard counts each account's balance once per transaction

## Problem
The Analytics dashboard's **total balance** grows with the number of transactions. An account's balance is added once for every posted transaction it has, so busy accounts inflate the total. **Safe to Spend** has the same problem, and also repeats each active bill once per account and per pending transaction.

**Safe to Spend** also never subtracted pending transactions. It looked for the status `PENDING_APPROVAL`, which V4 renamed to `PENDING`, so pending spending always counted as $0.

Example: accounts with $100 and $250, where the first has three posted transactions. The dashboard reported **$550** instead of $350. With $100 of bills and $50 of savings goals, Safe to Spend reported **$450** instead of $200.

### Root cause:
1. **Repeated rows.** Both queries sum a per-account (or per-bill) value after joining in a one-to-many table. A `LEFT JOIN` to transactions produces one row per transaction, so `SUM(a.current_balance)` adds the same balance once per transaction row. In Safe to Spend, the extra joins to bills and transactions multiply the rows again.
2. **Stale status name.** Safe to Spend filtered pending rows on `'PENDING_APPROVAL'`, which no row has had since V4. It also summed raw signed amounts, so once fixed, pending money in would have been subtracted as if it were spending.

### Code with bug:
```sql
-- get_dashboard_overview
SELECT
    COALESCE(SUM(a.current_balance), 0.00) AS total_balance,
    ...
FROM ledger.accounts a
LEFT JOIN ledger.transactions t
    ON t.account_id = a.account_id
    AND t.status = 'POSTED'
WHERE a.user_id = :user_id

-- get_safe_to_spend
SELECT
    COALESCE(SUM(a.current_balance), 0.00) AS total_balance,
    COALESCE(SUM(b.amount), 0.00)          AS active_bills_total,
    COALESCE(SUM(t.amount), 0.00)          AS pending_tx_total
FROM ledger.accounts a
LEFT JOIN ledger.upcoming_bills b
    ON b.user_id = a.user_id AND b.status = 'ACTIVE'
LEFT JOIN ledger.transactions t
    ON t.account_id = a.account_id AND t.status = 'PENDING_APPROVAL'
WHERE a.user_id = :user_id
```

## Solution
Compute each total in its own subquery, so every account, bill and transaction is counted once.

1. `get_dashboard_overview`: the total balance becomes a subquery over `ledger.accounts` alone. The monthly income and spending totals still come from the account-to-transactions join, where one row per transaction is correct.
2. `get_safe_to_spend`: balance, active bills and pending transactions are each summed in their own subquery.
3. `get_safe_to_spend`: pending means status `PENDING` (awaiting approval, so not yet in the balance). Only money out (`DEBIT`) is subtracted, by magnitude, because statement rows are unsigned and manual rows signed. Pending money in isn't added: it isn't spendable until it arrives.
4. Covered by `tests/integration/test_dashboard_balance.py` (Testcontainers Postgres).

### Fixed Code
```sql
-- get_dashboard_overview
SELECT
    (SELECT COALESCE(SUM(current_balance), 0.00)
     FROM ledger.accounts WHERE user_id = :user_id) AS total_balance,
    ...monthly income / expenses unchanged...
FROM ledger.accounts a
LEFT JOIN ledger.transactions t
    ON t.account_id = a.account_id
    AND t.status = 'POSTED'
WHERE a.user_id = :user_id

-- get_safe_to_spend
SELECT
    (SELECT COALESCE(SUM(current_balance), 0.00)
     FROM ledger.accounts WHERE user_id = :user_id)        AS total_balance,
    (SELECT COALESCE(SUM(amount), 0.00)
     FROM ledger.upcoming_bills
     WHERE user_id = :user_id AND status = 'ACTIVE')       AS active_bills_total,
    (SELECT COALESCE(SUM(ABS(t.amount)), 0.00)
     FROM ledger.transactions t
     JOIN ledger.accounts a ON a.account_id = t.account_id
     WHERE a.user_id = :user_id
       AND t.status = 'PENDING'
       AND t.direction = 'DEBIT')                          AS pending_tx_total
```
