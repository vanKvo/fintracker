# ADR-009: Ledger Event Publishing (StatementDeleted) through a Transactional Outbox

## Service Name: fintracker-ledger (app-wide impact: event delivery)

## Status
Accepted (architecture doc D14)

## Date
2026-10-18

## Context
The Ledger must publish events to EventBridge. The first is `StatementDeleted(documentId)` (ADR-005); later ones include `UserDataDeleted` after account deletion.

Two problems have to be solved together:

1. **Connectivity.** The Ledger connects to Aurora over JDBC, so it runs inside the VPC (ADR-003): as a Lambda in dev and on Fargate in prod. A function or task in a private subnet cannot reach EventBridge's API without a NAT gateway or an EventBridge interface endpoint. Dev has neither, by design.
2. **Consistency (the dual-write problem).** Deleting a statement changes the database, and publishing the event is a separate network call. If the Ledger commits the deletion and then crashes, times out or loses the network before publishing, the event is lost and the file is never deleted. Publishing before the commit has the opposite problem: the event announces a deletion that may then roll back.

Key requirements:
- An event must be published **if and only if** the database change commits.
- Dev must stay at near-zero idle cost, so Aurora must still be able to auto-pause (ADR-003).
- The same code path in both profiles (invariant 12).

## Decision
The Ledger publishes every event through a **transactional outbox**:

1. In the same database transaction as the business change, the Ledger inserts a row into `ledger.outbox` (event type, payload, `user_id`, created time, `published_at` null).
2. A small **relay Lambda outside the VPC** reads unpublished rows through the RDS Data API, publishes them to EventBridge, and marks them published.
3. **The relay schedule is configurable.** The default is set by `profile`, and a one-off Terraform variable overrides it for the current stage:
   - **dev, default:** `disabled`. Events wait in the outbox at no cost, and the relay can be invoked once by hand.
   - **dev, testing:** `rate(1 minute)` while testing deletions, then reverted.
   - **dev, invited testers active:** `rate(1 hour)`.
   - **prod:** `rate(1 minute)`.
4. Published rows are deleted after a retention period (e.g., 7 days).

## Alternatives Considered

### EventBridge interface endpoint in the VPC, publish directly from the Ledger
- Pros: Simple code (one SDK call). Low latency. No extra component.
- Cons:
  - About $7.30/month per AZ in every environment.
  - Solves connectivity only. The dual-write problem remains, so a crash between commit and publish still loses the event.
- Rejected as the main mechanism. It is still a valid way to run the relay inside the VPC later.

### NAT gateway, publish directly from the Ledger
- Pros: Simple code. Also gives the Ledger general outbound internet access.
- Cons:
  - About $33/month plus data charges, the largest fixed cost in dev.
  - Same dual-write problem as the endpoint option.
- Rejected for dev. Prod has a NAT gateway anyway, but connectivity is not the reason to choose a publishing pattern.

### Transactional outbox (chosen)
- Pros:
  - The event is committed atomically with the change: no lost events, and no events for changes that rolled back.
  - No endpoint or NAT cost in dev.
  - The same mechanism serves every future Ledger event.
- Cons: see Consequences.

## Consequences
- **Every relay run wakes Aurora in dev.** The database then stays up for the auto-pause timeout (5 minutes, the minimum).
  - A 15-minute schedule would keep it awake about two-thirds of the time (around $25–30/month), which is why dev is `disabled` by default and hourly at most for testers (around $3–4/month).
  - In prod Aurora is always on, so polling adds nothing.
- **Other costs are negligible:** relay invocations and scheduler runs fall inside the free tiers, Data API calls cost cents, and the relay's secret costs about $0.40/month.
- **Delivery is delayed:**
  - Dev: up to the schedule interval, or until the relay is enabled.
  - Prod: up to 1 minute.

  That is acceptable for file cleanup and deletion tracking, but not for events a user waits on, which would need a faster relay trigger.
- **Delivery is at-least-once.** If the relay publishes and then fails before marking the row, the event is sent again. Every consumer is already idempotent (CONOPS 4.3), and the Document service treats deleting an already-deleted file as success (ADR-005).
- **More moving parts:** an outbox table, a relay Lambda, a schedule, and cleanup of old rows. The relay needs a dead-letter path and an alarm on the age of the oldest unpublished row.
- **Row-Level Security needs an exception.** The relay reads every user's outbox rows. It connects with its own database role that is granted access to `ledger.outbox` only, with a policy that lets it see all rows there and no other Ledger table.
- **The relay needs the Data API enabled on the cluster** and a Secrets Manager secret, the same as Analytics and Knowledge.
- **Ordering:** events are published in creation order within one relay run. No consumer may depend on ordering across runs.
- **The relay schedule is listed in the architecture doc's profile table and dev stage presets (6.1).**
- **Revisit when** a Ledger event needs near-real-time delivery. Options then are a shorter prod interval, a relay inside the VPC using an interface endpoint, or a log-based change data capture stream.
