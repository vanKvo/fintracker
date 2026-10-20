# SDR-001: Analytics Computes on Read and Stores No Data

## Service Name: fintracker-analytics

## Status
Proposed (Analytics architecture doc S6)

## Date
2026-10-20

## Context
Analytics serves the Dashboard's spending pace, four Reports charts and the Financial Summary facts. Each could be computed from the Ledger's data on every request, or precomputed into tables Analytics owns. The choice decides whether Analytics needs a database, event consumers and a deletion handler, so it must be settled before implementation.

Key requirements:
- Reports and the Dashboard show the same number for the same month.
- A new or edited transaction shows up in Reports without a manual refresh.
- Dev idle cost stays near zero; nothing keeps Aurora awake.
- Account deletion removes every copy of a user's financial data.

## Options

- **Compute on read** *(chosen)*: every request runs indexed SQL aggregates over the Ledger's reporting views ([ADR-014](../../../fintracker-architecture/architectural_decision_records/ADR-014-ledger-reporting-views.md)). Analytics stores nothing.
- **Event-fed aggregates**: Analytics keeps monthly totals per user and category in its own schema, updated from Ledger transaction events and served from there.

## Trade-offs

| Dimension | Compute on read | Event-fed aggregates | Edge |
|---|---|---|---|
| **Freshness** | Immediate | Behind by the outbox relay schedule: dev default `disabled`, prod about 1 minute (ADR-009) | Compute on read |
| **Same number as the Dashboard** | Same views, same query rules | A second copy that must agree with the Ledger | Compute on read |
| **What has to be built** | Queries only | Event types, queue, consumer, tables, backfill, rebuild on a missed event, `UserAccountDeleted` handler | Compute on read |
| **Query cost per Reports page** | 4 aggregate queries over at most a few thousand rows, using the `(user_id, tx_date)` index | 4 lookups of precomputed rows | Aggregates, slightly |

## Decision
**Compute on read, in both profiles.** Analytics has no tables, no cache and no event consumers.

1. Widget sections run `GROUP BY` queries in the database and return small results.
2. Detectors read row-level data with only the columns they use, paged by date.
3. Each request runs its queries in one Data API transaction (app doc D5).

## Consequences
- **No data to protect, back up or delete:** account deletion needs no Analytics handler, and recovery is a redeploy.
- **Every page load touches Aurora:** in dev this wakes a paused database, which happens anyway for any app use.
- **Query time grows with history:** a user with years of transactions makes Reports slower. The partial index keeps each query to one user's date range.

## Revisit when
- Reports `p95` latency or Analytics' share of Aurora capacity becomes material in production metrics.
- Bank sync multiplies transaction volume per user.

Either way, add event-fed monthly aggregates for the slow sections only, keeping the reporting views as the source of truth.

## Related
- [ADR-014](../../../fintracker-architecture/architectural_decision_records/ADR-014-ledger-reporting-views.md): how Analytics reads Ledger data.
- [ADR-009](../../../fintracker-architecture/architectural_decision_records/ADR-009-ledger-event-publishing-outbox.md): Ledger events and the relay schedule.
- [Analytics architecture](../analytics-architecture.md): section 2 "How Analytics reads Ledger data", 3.4 Store.
