# ADR-013: The Ledger Serves the Dashboard; Analytics Serves Reports

## Service Name: app-wide (Ledger, Analytics, Frontend)

## Status
Accepted (architecture doc D21)

## Date
2026-10-20

## Context
The Ledger and Analytics both implemented Dashboard totals. The two copies already disagreed: the Analytics version counted each account's balance once per transaction (bug of 2026-10-08) while the Ledger's was right. The Dashboard and Reports also both offered "this month" and "last month", so the same figure could appear on two tabs from two code paths.

Key requirements:
- One owner for each figure, and the same number wherever it appears.
- Numbers the user just changed (a new transaction, a bill marked paid) show up immediately.
- The Dashboard still works when Analytics is down.
- Keep both tabs simple: the Dashboard is a glance at now; Reports explains change over time.

## Options

- **Split by tab** *(chosen)*: the Dashboard shows the current month, served by the Ledger except one Analytics card. Reports shows completed periods, served by Analytics.
- **Analytics serves both tabs**: every derived figure comes from Analytics, including Dashboard totals.
- **Ledger serves both tabs**: Analytics only produces the Financial Summary facts.

## Trade-offs

| Dimension | Split by tab | Analytics serves both | Ledger serves both | Edge |
|---|---|---|---|---|
| **Reflects a write immediately** | Yes for every Ledger widget | Yes while it reads the Ledger directly; seconds behind if Analytics later copies data | Yes | Split / Ledger |
| **Dashboard when Analytics is down** | Only the spending-pace card fails | Whole Dashboard fails | Unaffected | Split / Ledger |
| **Cross-period work in the system of record** | None | None | Trends, comparisons and merchant rankings in the Ledger | Split / Analytics |
| **Duplicate logic** | None: one owner per widget, shared counting rules ([ADR-014](ADR-014-ledger-reporting-views.md)) | None | None | Tie |

## Decision
**Split by tab, by time.** The Dashboard owns the current month; Reports owns completed periods.

1. **Dashboard (current month only, no period selector):**
   - Ledger: data-through date with the pending count, summary cards (total balance, income, expenses, net), budget alerts, this month's bills with paid or unpaid status, recent transactions.
   - Analytics: spending pace (this month so far vs the same days last month), loaded separately so a failure affects only that card.
2. **Reports (Analytics):** Financial Summary, income vs expenses (12 months), spending by category vs the comparison period, category trends (12 months), top merchants. Periods: Last month (default), Last 3 months, Year to date, Last 12 months. *This month* is not offered.
3. **One definition:** income and spending are computed from the Ledger's reporting views by both services, so a month's figure matches across tabs.
4. **Rule for new figures:** a figure belongs to the Ledger when it uses only Ledger records, covers one current period or a balance, needs no history across periods, and must reflect writes immediately. Otherwise it belongs to Analytics.

## Consequences
- **Analytics' Dashboard queries are removed,** along with the bug they carried.
- **The Ledger needs the user's timezone** to decide which month is current. It reads it from the verified user context ([ADR-015](ADR-015-settings-in-verified-context.md)).
- **The spending-velocity detector (FS-30) is removed:** it ran only for *This month*. The Dashboard's spending pace covers month-to-date pace.
- **UI follow-up:** `fintracker-ui-features.md` still lists Safe to Spend, the Action Hub, an emergency-fund calculator, export and *This Month* in Reports. It must be updated to these widget lists before the UI is implemented from it.

## Revisit when
- Users ask to view past months on the Dashboard rather than in Reports.

## Related
- [ADR-014](ADR-014-ledger-reporting-views.md): the shared counting rules.
- [ADR-015](ADR-015-settings-in-verified-context.md): where timezone and currency come from.
- App architecture doc: 2 Services, 4.6 Recover, 5 "Open the Dashboard", 7.1 D21.
- Service docs: [Ledger](../../fintracker-ledger-doc/architecture/ledger-architecture.md), [Analytics](../../fintracker-analytics/architecture/analytics-architecture.md). Spec: FS-01, FS-30.
