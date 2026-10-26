# Bug name: Refresh used a daily slot even when it returned the cached summary or a fallback

## Problem
"Refresh" (AN-FS-14, 5 a day) always skipped the cache and always used a slot. A refresh with a summary already cached paid for an identical generation, and a refresh that ended in a fallback (timeout, budget block, too few transactions) still cost the user a slot. A normal view also read the counter in a second DynamoDB call after the cache lookup.

### Root cause:
The refresh path incremented the counter before, and instead of, the cache lookup, and never gave the slot back.

### Code with bug:
```python
# src/summary/service.py
if refresh:
    refreshes_remaining = await self._take_refresh(user_id, now, settings)
else:
    cached = await self._cached(user_id, cache_key)
    ...
    "refreshes_remaining": await self._refreshes_remaining(user_id, now, settings),
```

## Solution
1. Every request reads the cache entry and the day's counters in one `BatchGetItem` (`get_cached_summary_and_counters`). A hit is returned for a refresh too, using no slot.
2. On a miss, a refresh takes its slot up front (atomic, so concurrent refreshes can't pass 5).
3. When no AI summary comes out, the slot is given back (`release_increment`); a failed give-back is logged and counted (`SummaryRefreshGiveBackFailed`) and the user loses that slot.

### Fixed Code
```python
cached, counters = await self._cached_and_counters(user_id, cache_key, now)
if cached is not None:
    return ...  # refreshes_remaining from the same read
if refresh:
    refreshes_remaining = await self._take_refresh(user_id, now, settings)
...
if refresh and output is None and refreshes_remaining is not None:
    refreshes_remaining = await self._give_back_refresh(user_id, now, refreshes_remaining)
```
