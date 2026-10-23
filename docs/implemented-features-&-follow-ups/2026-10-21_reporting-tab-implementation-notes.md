# Reporting tab: implementation notes (2026-10-21)

Covers LG-TXT-03, XS-RPTV-01 … -09, AN-RPT-01 … -08, -10, -11, AN-FS-01, -03, -07, -08, -19, -21, -29 (and the removal of AN-FS-30). Spec files were not edited except the Status column of the Requirements Index rows listed at the end.

## Read this first: decisions that differ from the specs

| # | Spec text | What was built | Why | What you may want to change |
|---|---|---|---|---|
| 1 | XS-RPTV-04 / ADR-014 §2: every view is `security_invoker = true`; the migration fails below PostgreSQL 15 | The views run with their **owner's** privileges. The owner is a new `NOLOGIN` role, `ledger_rpt_owner`, that is neither superuser nor `BYPASSRLS`. No PostgreSQL 15 check. | PostgreSQL checks a `security_invoker` view's base tables against the **caller's** privileges, so Analytics' role would need `SELECT` on `ledger.transactions` and the other tables. XS-RPTV-05 forbids exactly that ("`SELECT` on `ledger.transactions` as Analytics' role fails"). The two requirements cannot both hold. Row-Level Security still applies, because the policies read `app.current_user_id` from the session and the owner is subject to them (tests: no context → zero rows; user A never sees user B). | Decide which of -04 and -05 wins and update the spec and ADR-014. I kept -05 (least privilege) and the tenant check, and set XS-RPTV-04 to *In progress*. |
| 2 | LG-TXT-03: "a migration converts existing manual rows and adds a check `amount > 0`" | V29 adds the check as `NOT VALID` (enforced for every new insert and update). The conversion of existing rows is the one-time script `scripts/one-time/2026-10-21_LG-TXT-03_make_transaction_amounts_positive.sql`, which also validates the check. | Migrations are schema-only (your standing rule). | **Run the script right after V29**: until then, an UPDATE of an old negative row (approve, exclude) is rejected by the new check. |
| 3 | XS-RPTV-08: totals "in the primary currency" | The Dashboard passes the user's currency. Budget spend (`spentAmount`) uses `USD`, the only supported currency. | Budget endpoints don't receive the verified settings yet; threading them through every budget controller is a larger change. | Pass `UserSettings` into the budget services when a second currency is supported. |
| 4 | AN-FS-07 / -19 / -29 need balances and user-entered bills | Logic built and tested; **data not wired** (your answer: build logic, defer data). `FactsInput.liquid_savings` and `.checking_balance` are inputs that nothing loads. Emergency fund is `null` with flag `no_emergency_fund_account`; cash timing is skipped (`skipped_detectors: ["cash_timing"]`); every upcoming bill has `source: recurring`. | `rpt_accounts` has no balance (XS-RPTV-03) and there is no bills view. | Decide how balances and bills reach Analytics (a view change needs XS-RPTV-03 and ADR-014 updated first). The three rows are *In progress*. |
| 5 | AN-FS-25 fee refunds: "a refund matches a fee when it is linked to it" | The views don't expose `linked_transaction_id`, so only the fallback match (same merchant and amount within 30 days) runs. | XS-RPTV Appendix A has no such column. | Add the column to `rpt_transactions` (non-breaking, XS-RPTV-09) if the link matters. |
| 6 | AN-FS-07 "new" subscriptions and `due_date` for monthly charges | "New" = the series' first charge is less than three cadences before the period end. Next due = last charge + median interval. Recurring series are looked for in the loaded window (365 days before the period), so an annual charge needs 2+ years of history to be seen. | The spec doesn't define "new". | Adjust in `src/summary/sections/recurring.py`. |
| 7 | AN-FS-29 score | Score basis = how far the projected low is below the $200 threshold (impact is null for this type). | The spec defines the score only for candidates with an impact. | |
| 8 | AN-FS-21 account level | Terraform in `services/fintracker-ai-assistant/infrastructure/terraform`: Budgets 50/80/100%, an auto-applied deny policy at 100%, Cost Anomaly Detection, separate app and evaluation roles (evaluation only through OIDC from the `llm-eval` environment). Tested with `terraform test` on a mocked provider; **not applied to an account.** Dev budget is $10 (architecture doc 6.1; a row was added there). | | Fill `terraform.tfvars`, then apply. Replace the $10 once AN-FS-21's Open Question (budget amount) is answered. |

## What changed, by service

### Ledger
- **V29** `transactions_amount_positive_check` (`NOT VALID`) and the one-time conversion script. Manual entry, amount edits and split children store `abs(amount)`; a statement row with an amount `<= 0` is a failed row.
- **V30** `ledger.rpt_transactions`, `rpt_budget_limits`, `rpt_accounts`; index `idx_tx_user_date_active (user_id, tx_date) WHERE status <> 'DELETED'` and `idx_tx_parent`; the `ledger_rpt_owner` role; grants to `analytics_ro` (revokes every earlier base-table grant, then grants the three views). The migration needs a role that can create roles and hand over view ownership (a superuser or `rds_superuser`). `analytics_ro` must exist before the migration for its grants to be set.
- Dashboard income/expenses, `spentAmount` and the yearly spend index read `rpt_transactions` (`counts` in the user's currency). The repository methods take a `currency` argument.
- Shared contract fixture: `src/test/resources/reporting-contract/fixture.sql` (Appendix C). Analytics' integration tests load it.
- Test infrastructure: `AbstractIntegrationTest` creates `analytics_ro` before migrating and raises `max_connections` to 400 (a long run passed the default 100 through cached Spring contexts). About 120 test amounts were made positive.

### Analytics
- `core/database.py`: Data API backend (one transaction, `set_config(..., true)` inside it, retry once after 2 s, savepoint per section, errors by code only) and a local backend for `APP_ENV=local`. A unit test fails the build if any source file names a `ledger.` base table.
- New: `GET /v1/analytics/dashboard/spending-pace`, `GET /v1/analytics/reports?period=` (`monthly_cash_flow`, `categories`, `category_trends`, `top_merchants`, `data_quality`), and one internal route per section (`/internal/v1/analytics/reports/{monthly-cash-flow,categories,category-trends,top-merchants}`, `/dashboard/spending-pace`). A `period` and nothing else is accepted; a `user_id` in the query or body is a 400 and a security log event.
- Removed: `/dashboard`, `/reports/spending`, `/reports/trend` (public and internal) and the safe-to-spend and balance queries. *This month* is gone from `PeriodKey`; the month-to-date range lives in `resolve_month_to_date`.
- The facts engine reads `rpt_transactions` (`TxRow` has `flow`, `counts`, `category_id`, `merchant_key`) and groups by category id when present. AN-FS-08's month-to-date pace rule and the spending-velocity detector (AN-FS-30) are removed. New sections `recurring`, `upcoming_bills`, `emergency_fund`; new detector `cash_timing`; `overall_status` includes the emergency fund.
- CI: `.github/workflows/ci.yml` now checks out the Ledger repo (secret `LEDGER_REPO_TOKEN` while it is private) and runs `mypy src scripts`.

### AI assistant
- Contract copy, validation (new insight types `subscription`, `emergency_fund`, `cash_timing`; new metrics `recurring_monthly_total`, `emergency_fund_months`), prompt `fs-v2`. **Changing the facts schema and the prompt means a passing `full` evaluation run is required before merge (AN-FS-22); I could not run one.**
- Tools re-pointed to Analytics' new routes: `get_spending_pace`, `get_spending_by_category(period)`, `get_monthly_cash_flow`.
- Regenerated the 22 evaluation fixtures (`spending-velocity` and `month-to-date-early` removed; `free-trial` moved to the `extended` tier to keep it at 10).

### UI
- Reports: one period selector at the top (periods with no data disabled) drives the Financial Summary panel (now input-driven, no selector of its own), spending by category and top merchants. Two real charts (income vs. expenses, category trend with a category switcher) replace the mocked savings chart and emergency-fund card. A failed `/reports` keeps the previous charts with an inline error and Retry; the summary loads on its own.
- Dashboard: a spending-pace card that loads on its own and has its own error state.
- Transactions: the list derives the sign from `direction` (the Ledger now stores amounts positive).
- The UI `ng build` still reports the initial-bundle budget error (1.02 MB against a 1.00 MB limit); I did not change the initial bundle.

## Runbook

1. Provision the read-only role before migrating: `CREATE ROLE analytics_ro LOGIN ...` (the cluster owner does this; the migration only sets its grants).
2. Deploy the Ledger (Flyway runs V29 and V30), then immediately run `scripts/one-time/2026-10-21_LG-TXT-03_make_transaction_amounts_positive.sql` as the superuser.
3. Set `DB_CLUSTER_ARN`, `DB_SECRET_ARN`, `DB_NAME` on Analytics (secret for `analytics_ro`). Locally: `APP_ENV=local`, `DATABASE_URL` for `analytics_ro`.
4. Run `scripts/one-time/2026-10-21_LG-CAT-01_backfill_budget_category_id.sql` if not yet done: budgets resolve categories by id first and by name as a fallback.

## Requirements Index statuses set (only the Status column)

- LG-TXT-03, XS-RPTV-01/02/03/05/06/07/08/09, AN-RPT-01 … -08, -10, -11, AN-FS-01/03/08/21: **Implemented**.
- XS-RPTV-04, AN-FS-07/19/29: **In progress** (see the table above). AN-RPT-09 was not in scope and stays *Proposed*, although its internal routes and registry now exist; AI-CHAT-05 does not consume them yet. XS-RPTV-08 mentions budget alerts; the Ledger has no such code to change.

## Verification run

Ledger `mvn verify`: 207 unit tests and 490 integration tests pass. Analytics: 288 tests pass (including the Testcontainers contract tests against the Ledger's migrations), `mypy src` clean. AI assistant: 198 tests pass. UI: 149 tests pass. Terraform: 11 tests pass, `validate` OK.
