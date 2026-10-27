# Running the Financial Summary (AN-FS)

How to run the Financial Summary and its evaluation. Spec: `docs/fintracker-analytics/specs/AN-FS-financial-summary-spec.md`.

Two services take part:
- **Analytics** (`services/fintracker-analytics`, port 8084) computes the facts payload and the periods. It never calls an LLM.
- **AI assistant** (`services/fintracker-ai-assistant`, port 8085) calls Bedrock: summary routes, cost guard, cache, audit, and the evaluation CLI.

**The evaluation doesn't need either service running.** It is a command-line tool that sends the fixture files straight to Bedrock.

## Evaluation (AN-FS-20 / AN-FS-22)

### The fixtures
There are 22 fixtures, in `services/fintracker-ai-assistant/tests/fixtures/fs/`. Each `<name>.json` file is one synthetic user's facts payload. `manifest.json` gives each fixture's tier, the insight types it must produce and its injection markers. Each tier includes the tiers before it:

| Tier | Fixtures | Total |
|---|---|---|
| `smoke` | `typical-month` | 1 |
| `core` | + `over-budget`, `injection-merchant`, `duplicate-charge`, `heavy-year` | 5 |
| `extended` | + `no-income`, `no-budgets`, `anomalies-present`, `fee-detected`, `free-trial` | 10 |
| `full-once` | + the other 12, one run each | 22 |
| `full` | the same 22, two runs each (required by FS-22) | 22 |

The fixtures are built from the Analytics facts engine. After changing the facts engine, regenerate them in Analytics (`poetry run python -m scripts.build_fs_fixtures`) and copy them here.

### Step 1: dry run (free, no AWS, nothing stored)
```bash
cd services/fintracker-ai-assistant
poetry install
APP_ENV=local poetry run python -m src.summary.eval --tier dry
```
It is only a cost preview: it is not a tier you have to pass, and it saves nothing to the bucket. It prints the input tokens for each of the 22 fixtures and their total. Then, per tier, it prints the estimated Bedrock cost two ways:
- **Estimated:** one call per fixture, with `max_tokens` as the output.
- **With every validation retry:** the worst case, two calls per fixture.

`full` is priced at 2 runs per fixture, which that tier requires; `full-once` is priced at 1 run per fixture. Prices come from `DEFAULT_PRICES` in `src/summary/config.py`; check them against the AWS Bedrock pricing page. To price another model, add `--model-id amazon.nova-lite-v1:0`.

### Step 2: one fixture against the real model
A live run sends real Bedrock calls and costs money. It is limited in four ways:
- **Before any call:** the run aborts if its worst-case estimate is above `--cap-usd` (default $5), unless you pass `--confirm-over-cap`.
- **Before every call** (the validation retry included): once the actual spend passes the cap, no further call is sent.
- **When no reply comes back:** a call that timed out, or lost its connection after it was sent, is counted at its worst-case cost, because Bedrock may still bill it. An error before Bedrock processed the request (throttling, connection refused) counts as $0.
- **At the AWS account level:** the eval IAM role has its own AWS Budgets deny action (AN-FS-21).

**Intended way: the `LLM evaluation` GitHub workflow** (`services/fintracker-ai-assistant/.github/workflows/llm-eval.yml`, manual, owner-approved). Start it with `tier = smoke` for the one fixture (`typical-month`). The setup steps are in the workflow file's header.

**What's missing before a live run can work:**
1. The CLI refuses live tiers without `EVAL_RESULTS_BUCKET`. It needs the bucket for the tier order and to save results.
2. Deploy the bucket: `terraform apply` in `services/fintracker-ai-assistant/infrastructure/terraform/environments/dev` (module `eval_results`: private, encrypted, TLS-only, not versioned, no expiry; get/put/list for the eval role, get/list for the pull-request read-only role). Set the output `eval_results_bucket` as `EVAL_RESULTS_BUCKET` in the `llm-eval` GitHub environment.
3. Tier order: `smoke` is the first tier and runs without any earlier pass. Each later tier needs the previous tier to have passed for the same prompt version and model, or `--skip-tier-check`.

The CLI is the same if you run it yourself instead of through the workflow:
```bash
export EVAL_RESULTS_BUCKET="fintracker-ai-assistant-dev-eval-results-390240928781"
poetry run python -m src.summary.eval --tier dry                                 # cost preview, stores nothing
poetry run python -m src.summary.eval --tier smoke --cap-usd 0.05 --out smoke.json
poetry run python -m src.summary.eval --tier smoke --fixtures heavy-year --skip-tier-check --cap-usd 0.05  # any one fixture
```
Run outside the workflow, the CLI uses your own AWS credentials, not the eval role. That bypasses the eval role's separate budget and deny action, so keep `--cap-usd` low.

### Step 3: dry run of the full set before paying for it
`--tier dry` (step 1) already prices all 22 fixtures at `full`. Read the `full` line, and its worst case with retries, before you start a `full` run. A live run also prints its own estimate before its first call and aborts if the worst case is above `--cap-usd`.

### Measuring latency for the call timeout (AN-FS-10, AN-FS-20)
- Every call logs `llm_latency_ms`. Each report row has `calls[]`, one entry per attempt: `attempt`, `outcome`, `latency_ms` (our time), `bedrock_latency_ms` (Bedrock's own), `output_tokens`, `truncated`, `started_at`. Rows also keep the `summary`, or the `raw_responses` of a failed run.
- `totals.llm_latency_ms.<model_id>` has `calls`, `p50`, `p95`, `p99` and `p99_usable` (true from 200 calls), over successful calls only. `totals.bedrock_latency_ms` is the same for Bedrock's time; `call_outcomes` counts attempts per outcome; `truncated_calls` and `max_output_tokens_per_call` show whether `max_tokens` is too low.
- Live runs default to `--deadline-s 62`, so each call gets a 60 s timeout and the slow tail is measured rather than cut off at the production timeout (the spec allows this off the request path). Pass `--deadline-s 25` to see what production would do.
- 200 calls: about `--tier full --runs-per-fixture 10` (22 × 10 = 220 generations; retries add calls). On Nova Micro this is a few cents; check the dry-run line first.
- Then set `call_timeout_cap_s` in the SSM settings to about 1.5 × the p99, converted to seconds.

## Running the services locally (no AWS)
```bash
# Analytics: facts and periods
cd services/fintracker-analytics
export DATABASE_URL=postgresql+asyncpg://<user>:<pass>@localhost:5432/fintracker
export APP_ENV=local LOCAL_DEV_USER_ID=<internal user ID with accounts> \
       LOCAL_DEV_TIMEZONE=America/New_York LOCAL_DEV_CURRENCY=USD   # required, no defaults (XS-CTX-05)
poetry run uvicorn src.main:app --reload --port 8084

# AI assistant: summary routes
cd services/fintracker-ai-assistant
export APP_ENV=local LOCAL_DEV_USER_ID=<same ID> LOCAL_DEV_TIMEZONE=America/New_York LOCAL_DEV_CURRENCY=USD
export ANALYTICS_INTERNAL_API_URL=http://localhost:8084
poetry run uvicorn src.main:app --reload --port 8085
```
- Ledger migration V24 (`accounts.last_synced_at`) must be applied to the database Analytics reads; running the Ledger once applies it.
- Without `SUMMARY_TABLE_NAME` the AI assistant never calls Bedrock: every summary is the facts-only fallback with reason `budget_store_down` (AN-FS-21 fails closed). Locally that is the expected result, so use the evaluation above to test generation.
- `LOCAL_DEV_USER_ID` outside `APP_ENV=local` stops the service at startup (AN-FS-02).
- The UI proxies `/api/v1/analytics` to `localhost:8084` (`fintracker-ui/proxy.conf.json`).

## Deployed configuration (AI assistant)
| Variable | Purpose |
|---|---|
| `ANALYTICS_INTERNAL_API_URL` | Analytics internal API (facts route, SigV4-signed) |
| `SUMMARY_TABLE_NAME` | DynamoDB table: cache, counters, spend, audit, snapshots (TTL `expires_at`, customer-managed KMS key). Required outside local |
| `SUMMARY_CONFIG_PARAM` | SSM parameter holding JSON settings (see below) |
| `SUMMARY_DAILY_BUDGET_USD`, `SUMMARY_MODEL_ID` | Used when the SSM JSON doesn't set them |
| `AUDIT_HASH_SALT` | Salt for hashed user IDs kept after account deletion (secret). Required outside local |
| `AUDIT_RETRY_QUEUE_URL` | SQS queue for failed audit and snapshot writes; consumer `src.summary.audit.audit_retry_handler` |
| `BUDGET_ALERT_TOPIC_ARN` | SNS topic for the `budget_alert_pct` and 100% daily budget alerts |
| `EVENT_BUS_NAME` | EventBridge bus for `UserDataDeleted` (account deletion consumer `src.summary.deletion.handle_user_deleted`) |
| `BEDROCK_REGION` | Optional; defaults to `AWS_REGION` |

The Lambda timeout is 29 s (Terraform output `lambda_timeout_s`): a 25 s request deadline inside the gateway's 30 s limit.

## Settings (SSM JSON, all optional)
```json
{
  "model_id": "amazon.nova-micro-v1:0",
  "prompt_version": "fs-v1",
  "daily_budget_usd": null,
  "budget_alert_pct": 80,
  "token_budget": null,
  "call_timeout_cap_s": null,
  "per_user_daily_generations": 10,
  "per_user_daily_refreshes": 5,
  "max_input_tokens": 8000,
  "max_tokens": 1200,
  "llm_retry_attempts": 2,
  "breaker_failure_threshold": 5,
  "breaker_open_s": 60
}
```
- `daily_budget_usd` is still an open question (AN-FS-21). While it is unset, every LLM call is blocked with `daily_budget`. Before each call, the call's worst-case cost is reserved against it, then settled to the actual cost.
- `budget_alert_pct` must be between 1 and 99. Any invalid setting makes the service block every LLM call until it is fixed (metric `SummaryConfigInvalid`).
- `call_timeout_cap_s` stays unset until latency has been measured (see above). Until then each call gets the remaining deadline minus 2 s.
- `token_budget` is still an open question (AN-FS-20). While it is unset, evaluation runs skip the token-budget criterion.
- `banned_terms` replaces the default list in `src/summary/config.py`.
