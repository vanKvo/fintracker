# Bug name: Quota and spend TTLs read as host-local midnight

## Problem
The AI assistant's per-user quota items (`QUOTA#<day>`, 2-day TTL) and app-wide spend items (`SPEND#<day>`, 40-day TTL) computed `expires_at` from the UTC day key as if it were midnight in the host's local timezone. On a non-UTC host the TTL moved by the host's UTC offset (e.g. +10 h on a UTC−10 machine). Lambda runs in UTC, so production was unaffected, but any local run, container or Fargate task with `TZ` set wrote wrong expiry times.

### Root cause:
`datetime.fromisoformat("2026-10-08")` returns a naive datetime, and `.timestamp()` on a naive datetime assumes local time.

### Code with bug:
```python
ExpressionAttributeValues={":one": 1, ":cap": cap, ":exp": ttl(datetime.fromisoformat(day), QUOTA_TTL)},
...
ExpressionAttributeValues={":usd": usd, ":exp": ttl(datetime.fromisoformat(day), SPEND_TTL)},
```

## Solution
Anchor the day key to UTC before computing the TTL.

1. Added `_day_start(day)` in `src/summary/store.py`, which returns midnight UTC for a `YYYY-MM-DD` key.
2. Used it for both the quota and spend TTLs.
3. Added a test that sets `TZ=Pacific/Honolulu` and checks that both TTLs equal UTC midnight + keep.

### Fixed Code
```python
def _day_start(day: str) -> datetime:
    """Midnight UTC of a `YYYY-MM-DD` day key. A naive datetime would be read as host-local time."""
    return datetime.fromisoformat(day).replace(tzinfo=timezone.utc)

...":exp": ttl(_day_start(day), QUOTA_TTL)...
...":exp": ttl(_day_start(day), SPEND_TTL)...
```
