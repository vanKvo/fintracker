# Bug name: The daily LLM budget could be overshot by concurrent requests and alert twice

## Problem
The AN-FS-21 daily circuit breaker is meant to be a hard stop, but requests arriving together all read "under budget" and all called the LLM, so the day could end above the budget. A 100% alert could fire twice when `budget_alert_pct` was set to 100, and nothing stopped a threshold from alerting again after spend dipped and re-crossed it. The default `daily_budget_usd` was also `5` instead of unset, so a missing configuration failed open.

### Root cause:
Check-then-add: the guard read today's spend, compared it with the budget, and added the cost only after the call. There was no atomic condition and no per-day alert flag.

### Code with bug:
```python
# src/summary/cost_guard.py
if self._store.get_spend(day) >= s.daily_budget_usd:
    return "daily_budget"
...
# after the call
total = self._store.add_spend(utc_day(now), cost)

# src/summary/config.py
daily_budget_usd: Decimal = 5
```

## Solution
Applied SDR-002, reserve then settle.

1. `store.reserve_spend`: one conditional `ADD` of the call's worst-case cost (estimated input + `max_tokens`), allowed only while the new total stays within the budget; otherwise `daily_budget`.
2. `CostGuard.admit`: input size → reserve → per-user counter (a `user_cap` releases the reservation). A validation retry calls `reserve` again.
3. After the call: settle to the actual cost; a read timeout keeps its reservation; an error before processing releases it to $0.
4. Alerts: a crossing found on a write's total sends the alert only if `store.claim_alert` sets that day's `alert_<pct>` flag. `budget_alert_pct` must be 1–99; invalid deployed settings fall back to defaults with no budget, so every LLM call is blocked until they are fixed.
5. `daily_budget_usd` defaults to unset (fail closed).

### Fixed Code
```python
# src/summary/store.py
ConditionExpression="attribute_not_exists(usd) OR usd <= :limit",
ExpressionAttributeValues={":usd": usd, ":limit": budget - usd, ...},
```
