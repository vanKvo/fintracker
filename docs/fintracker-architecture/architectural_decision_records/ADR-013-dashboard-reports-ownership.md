# ADR-013: The Ledger Serves the Dashboard; Analytics Serves Reports

## Service Name: app-wide (Ledger, Analytics, Frontend)

## Status
Accepted (architecture doc D21)

## Date
2026-10-20

## Context
The Ledger and Analytics both implemented Dashboard totals. The two copies already disagreed: the Analytics version counted each account's balance once per transaction ([bug of 2026-10-08](../../bugs/2026-10-08_bug_analytics_dashboard_balance_counted_per_transaction.md)) while the Ledger's was right. The Dashboard and Reports also both offered "this month" and "last month", so the same figure could appear on two tabs from two code paths.

Key requirements:
- One owner for each figure, and the same number wherever it appears.
- Numbers the user just changed (a new transaction, a bill marked paid) show up immediately.
- The Dashboard still works when Analytics is down.
- Keep both tabs simple: the Dashboard is a glance at now; Reports explains change over time.

## Decision
**Split by tab, by time.** The Dashboard owns the current month; Reports owns completed periods.

**Why:** It meets every key requirement: one owner per figure, the Ledger shows its own writes at once, and the Dashboard keeps working without Analytics. The one Analytics card on the Dashboard is acceptable because it loads on its own, so an outage costs only that card.

1. **Dashboard (current month only, no period selector):** the Ledger serves every card except spending pace (this month so far vs the same days last month), which Analytics serves and the client loads separately. The card list is in app doc 5 "Open the Dashboard".
2. **Reports (Analytics):** Financial Summary, income vs expenses (12 months), spending by category vs the comparison period, category trends (12 months), top merchants. Periods: Last month (default), Last 3 months, Year to date, Last 12 months. *This month* is not offered.
3. **One definition:** income and spending are computed from the Ledger's reporting views by both services, so a month's figure matches across tabs ([ADR-014](ADR-014-ledger-reporting-views.md)).
4. **Rule for new figures:** a figure belongs to the Ledger when it uses only Ledger records, covers one current period or a balance, needs no history across periods, and must reflect writes immediately. Otherwise it belongs to Analytics.

## Alternatives Considered

### Analytics serves both tabs
- Pros: Every derived figure comes from one service; no split rule to apply.
- Cons:
  - The whole Dashboard fails when Analytics is down, which breaks a key requirement.
  - Writes show immediately only while Analytics reads the Ledger directly; if it later copies data, the Dashboard runs seconds behind.
- Rejected: It makes the glance-at-now tab depend on the service built for history.

### Ledger serves both tabs
- Pros: The Dashboard is unaffected by an Analytics outage, and writes show immediately.
- Cons:
  - Trends, comparisons and merchant rankings would run in the Ledger, the system of record.
  - Analytics shrinks to producing only the Financial Summary facts.
- Rejected: It moves cross-period analysis into the system of record to avoid a problem the split already avoids.

## Consequences

- **Analytics' Dashboard queries are removed,** along with the bug they carried. Each Dashboard figure now has a single code path in the Ledger.
- **The Dashboard is not fully independent of Analytics.** If Analytics is down, the spending-pace card fails; every other card still loads.
- **The shared definition has to hold.** Both services compute income and spending from the same Ledger views; if either drifts, the two-copies bug returns.
- **Users lose two views:** *This month* in Reports, and past months on the Dashboard.
- **The spending-velocity detector (AN-FS-30) is removed.** It ran only for *This month*; the Dashboard's spending pace now covers month-to-date pace.
- **The Ledger now needs the user's timezone** to decide which month is current. It reads it from the verified user context ([ADR-015](ADR-015-settings-in-verified-context.md)).

## Revisit when
- Users ask to view past months on the Dashboard rather than in Reports.

## Related
- [ADR-014](ADR-014-ledger-reporting-views.md): the shared counting rules.
- [ADR-015](ADR-015-settings-in-verified-context.md): where timezone and currency come from.
- App architecture doc: 2 Services, 4.6 Recover, 5 "Open the Dashboard", 7.1 D21.
- Service docs: [Ledger](../../fintracker-ledger-doc/architecture/ledger-architecture.md), [Analytics](../../fintracker-analytics/architecture/analytics-architecture.md). Spec: AN-FS-01, AN-FS-30.
