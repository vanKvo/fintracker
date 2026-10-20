# Running the Financial Summary (FS)

How to run and configure the Financial Summary in `services/fintracker-analytics` and the Reports page panel in `fintracker-ui`. Spec: `docs/fintracker-analytics/FS-financial-summary-updated.md`.

## Before the first run
1. **Ledger migration V24** (`accounts.last_synced_at`) must be applied to the database Analytics reads. The facts query selects that column, so Analytics fails on a database without it. Running the Ledger once (`mvn spring-boot:run`) applies it.
2. **User Profile internal settings route** (`GET /profile/internal/users/{userId}/settings`, IAM auth) must be deployed for deployed environments. Its handler is `app.identity.internal_handlers.internal_settings_handler`; set `INTERNAL_ALLOWED_CALLER_ARNS` to the Analytics Lambda role's assumed-role ARN prefix.

## Local run (no AWS)
```bash
cd services/fintracker-analytics
export DATABASE_URL=postgresql+asyncpg://<user>:<pass>@localhost:5432/fintracker
export APP_ENV=local
export LOCAL_DEV_USER_ID=<an internal user ID that owns accounts in the local database>
poetry run uvicorn src.main:app --reload --port 8084
```
The UI proxies `/api/v1/analytics` to `localhost:8084` (`fintracker-ui/proxy.conf.json`).

Without `SUMMARY_TABLE_NAME`, the facts and periods work, but every summary shows the facts-only fallback with reason `budget_store_down`. The LLM is never called without a usage store (FS-21 fails closed). `LOCAL_DEV_USER_ID` outside `APP_ENV=local` stops the service at startup (FS-02).

Optional local settings: `LOCAL_DEV_TIMEZONE` (default `America/New_York`), `LOCAL_DEV_CURRENCY` (default `USD`).

## Environment variables (deployed)
| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Read replica |
| `USER_PROFILE_API_URL` | Base URL for the IAM-signed settings call |
| `SUMMARY_TABLE_NAME` | DynamoDB table (PK/SK strings, TTL attribute `expires_at`, customer-managed KMS key) |
| `SUMMARY_CONFIG_PARAM` | SSM parameter holding JSON settings (see below) |
| `AUDIT_RETRY_QUEUE_URL` | SQS queue for failed audit/snapshot writes; consumer `src.summary.audit.audit_retry_handler` |
| `BUDGET_ALERT_TOPIC_ARN` | SNS topic for the 80% / 100% daily budget alerts |
| `AUDIT_HASH_SALT` | Salt for hashed user IDs kept after account deletion (secret) |
| `BEDROCK_REGION` | Optional; defaults to `AWS_REGION` |

The account-deletion consumer is `src.summary.deletion.handle_user_deleted`, triggered by an EventBridge rule for `UserAccountDeleted`.

## Settings (SSM JSON, all optional)
```json
{
  "model_id": "amazon.nova-micro-v1:0",
  "daily_budget_usd": null,
  "token_budget": null,
  "per_user_daily_generations": 10,
  "per_user_daily_refreshes": 5,
  "max_input_tokens": 8000,
  "max_tokens": 1200,
  "banned_terms": ["invest in", "stock", "crypto", "guaranteed", "refinance", "tax deduction", "credit score", "loan"]
}
```
- `daily_budget_usd` is still an open question (FS-21). While it is unset, every LLM call is blocked with `daily_budget`. Set it to test generation.
- `token_budget` is still an open question (FS-20). While it is unset, evaluation runs skip the token-budget criterion.
- Per-1K-token prices live in `src/summary/config.py` (`DEFAULT_PRICES`). Check them against the AWS Bedrock pricing page.

## Evaluation (FS-20 / FS-22)
```bash
poetry run python -m src.summary.eval --tier dry      # free: tokens and estimated cost per tier
poetry run python -m scripts.build_fs_fixtures       # regenerate fixtures after facts-engine changes
```
Live tiers run only from the `LLM evaluation` GitHub workflow. Setup is in the header of `.github/workflows/llm-eval.yml`. Make the CI job `eval-required` a required status check on `main`.
