# SDR-002: Reserve LLM Spend Atomically Before Each Call

## Service Name: fintracker-ai-assistant

## Status
Accepted (AI assistant architecture doc S9)

## Date
2026-10-25

## Context
AN-FS-21 calls the app-wide daily circuit breaker the real-time hard stop. The cost guard read today's spend, compared it with the budget, and added the cost only after the call. Requests arriving together all read "under budget" and all went ahead. Example: budget $10.00, spent $9.95, about $0.02 per call; 20 concurrent requests all read $9.95 and the day ends at about $10.35. Timed-out calls also added nothing (SDR-001).

Key requirements:
- Spend never goes over the daily budget because of concurrency.
- Calls that may have been billed are counted, even with no reply.
- Fail closed: if the store is down, no call goes out (AN-FS-21).

## Options

- **Reserve, then settle** *(chosen)*: before the call, one conditional atomic add of the worst-case cost; after it, add (actual − reserved).
- **Soft breaker, documented**: keep check-then-add and state the overshoot bound (concurrency × worst-case cost per call).

## Trade-offs

| Dimension | Reserve, then settle | Soft breaker | Edge |
|---|---|---|---|
| **Overshoot** | None from concurrency; a call can't exceed its reservation because of `max_tokens` | Up to concurrency × worst-case cost (20 × $0.02 = $0.40 in the example) | Reserve |
| **Timed-out calls** | Counted at the reserved amount | Not counted at all | Reserve |
| **DynamoDB writes per call** | 2 (reserve, settle) on one item per day | 1, plus 1 read | Soft, slightly |
| **Spec wording** | "Hard stop" stays true | "Hard stop" must be renamed | Reserve |

## Decision
**Reserve, then settle, in both profiles.**

1. **Reserve:** `UpdateItem` on `APP / SPEND#<day>` with `ADD usd :reserve` and the condition `attribute_not_exists(usd) OR usd <= :budget_minus_reserve`. `:reserve` = cost of estimated input tokens + `max_tokens` output. A failed condition is `daily_budget`; any other store error is `budget_store_down`.
2. **Order in the guard:** input size → reserve spend → per-user generation counter. If the generation counter is at its cap, the reservation is released (add −reserve).
3. **Settle:** after a reply, add (actual − reserved). The retry reserves again before its own call.
4. **No reply:** a read timeout keeps the full reservation, because Bedrock may have processed the call. An error before processing (still failing after the SDR-001 retries, which reuse the reservation) settles to 0.
5. **Alerts:** threshold crossings are checked on the total returned by the reserve write. Each threshold's alert is sent only by the request whose conditional write sets `alert_<pct>` on the same item, so it fires once per day. `budget_alert_pct` must be 1–99.

## Consequences
- The breaker can trip slightly early, because reservations count `max_tokens` until they settle. At $0.02 per call this is cents.
- A crash between reserve and settle over-counts by one reservation; it expires with the day.
- All spend writes go to one item per day. At this traffic that is far below DynamoDB's per-item limit.

## Revisit when
- Peak traffic approaches about 500 LLM calls per second (one hot item).
- The budget moves to per-tier or per-tenant pools.

## Related
- [AN-FS spec](../../../fintracker-analytics/specs/AN-FS-financial-summary-spec.md): AN-FS-21.
- [SDR-001](SDR-001-bedrock-call-timeouts.md): why timed-out calls keep their reservation.
- [AI assistant architecture](../ai-assistant-architecture.md): 3.5 Protect.
