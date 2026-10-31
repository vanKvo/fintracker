# AI Assistant Service

The only FinTracker service that calls an LLM (architecture decision D4). It turns facts computed by other services into explanations, and keeps all AI risk in one place: prompts, model choice, guardrails, evaluation and LLM cost. It computes no financial figure and reads no database; it calls other services' APIs.

Architecture: [`docs/fintracker-ai-assistant/architecture/ai-assistant-architecture.md`](../../docs/fintracker-ai-assistant/architecture/ai-assistant-architecture.md). App-wide rules: [`docs/fintracker-architecture/fintracker-architectural-doc.md`](../../docs/fintracker-architecture/fintracker-architectural-doc.md).

## Project Structure

| Feature | Responsibility |
|---|---|
| `summary/` | Financial Summary (FS spec): facts from Analytics → cache → cost guard → Bedrock → validation → audit. Also the eval runner (`summary/eval/`) and the prompt versions (`summary/prompt/versions/<version>/system.md`, loaded by `prompt/loader.py`) |
| `tools/` | MCP tool surface (read-only, no LLM calls). Tool definitions live here; tool logic stays in the owning service, reached over signed REST (`tools/clients.py`) |
| `core/` | Identity, user context, shared types, errors (`exceptions.py`, `error_handlers.py`), request IDs, SigV4 signing, observability |

Every feature uses the same file names (app doc 9.1): `exceptions.py` (its errors), `schemas.py` (its types: Pydantic request/response/contract models, Protocols, internal results) and `models.py` (its stored records). In `summary/`, `schemas.py` holds the facts payload contract with Analytics (Appendix A, a copy of Analytics' `src/summary/schema.py`) and the LLM output schema (Appendix B); `models.py` holds the DynamoDB items.

## Interfaces

**Public routes** (prefix `/v1/ai`, user from the gateway's identity authorizer)
| Method | Path | Description |
|---|---|---|
| `GET` | `/summary?period=` | Facts + AI summary, or facts + facts-only fallback |
| `POST` | `/summary/refresh?period=` | Same; generates only when nothing is cached for the current data (5 a day, a slot is given back when no AI summary comes out) |

Periods and the facts-only view are Analytics routes (`/v1/analytics/summary/periods`, `/facts`).


**Outbound** (SigV4-signed, user in `X-Internal-User-Id`)
| Target | Route | Used by |
|---|---|---|
| Analytics | `GET /internal/v1/analytics/summary/facts` | Financial Summary |
| Analytics | `GET /internal/v1/analytics/dashboard/spending-pace`, `/reports/categories`, `/reports/monthly-cash-flow` | MCP tools |
| Ledger | `GET /api/v1/ledger/transactions`, `/budgets` | MCP tools |
| User Profile | `GET /profile/internal/goals` | MCP tools |
| Amazon Bedrock | Converse | Summary only |
| EventBridge | `UserDataDeleted` | Account deletion (invariant 11) |

**Event handlers:** `summary.deletion.handle_user_deleted` (`UserAccountDeleted`), `summary.audit.audit_retry_handler` (SQS audit retries).

## Configuration

| Variable | Purpose |
|---|---|
| `ANALYTICS_INTERNAL_API_URL` | Base URL of the analytics-internal API |
| `SUMMARY_TABLE_NAME` | DynamoDB table: cache, counters, spend, audit, snapshots. Required outside local (startup fails); unset locally → every LLM call is blocked (fail closed) |
| `SUMMARY_CONFIG_PARAM` / `SUMMARY_MODEL_ID` / `SUMMARY_DAILY_BUDGET_USD` | Summary settings (SSM JSON, 5-minute cache, read per request), including `prompt_version` |
| `AUDIT_HASH_SALT` | User-ID hashing for audit records. Required outside local |
| `AUDIT_RETRY_QUEUE_URL`, `BUDGET_ALERT_TOPIC_ARN` | Audit retry queue, budget alerts |
| `EVENT_BUS_NAME` | EventBridge bus for `UserDataDeleted`. Required outside local by the deletion handler |
| `LEDGER_API_URL`, `USER_PROFILE_API_URL` | MCP tool clients (SigV4-signed, user in the forwarded context) |
| `APP_ENV=local` + `LOCAL_DEV_USER_ID`, `LOCAL_DEV_TIMEZONE`, `LOCAL_DEV_CURRENCY` | Local identity and settings, no defaults (refused outside local) |

Analytics must list this service's IAM role in its `INTERNAL_ALLOWED_CALLER_ARNS`.

## Quick Start

```bash
poetry install
poetry run pytest                                   # unit + replay tests, no AWS calls
poetry run uvicorn src.main:app --reload --port 8085
poetry run python -m src.tools.server               # MCP server over stdio (APP_ENV=local, LOCAL_DEV_USER_ID, LOCAL_DEV_TIMEZONE, LOCAL_DEV_CURRENCY)
poetry run python -m src.summary.eval --tier dry    # eval token counts and cost estimate, no LLM calls (docs/instructions/run_financial_summary.md)
poetry run python -m src.summary.prompt.loader show fs-v1     # the rendered system prompt
poetry run python -m src.summary.prompt.loader freeze fs-v1   # after its first passing full run
```

**Prompt versions:** each version is a folder in `src/summary/prompt/versions/`, and the folder name is the version (cache key, audit record, eval results). The active one is the `prompt_version` setting. A version is frozen after its first passing `full` evaluation (`freeze` records its hash in `prompts.lock`); from then on a test fails if it changes, so edits go into a new folder (`fs-v2`, …).

Evaluation fixtures (`tests/fixtures/fs/*.json`) are facts payloads built by Analytics' `scripts/build_fs_fixtures.py`; regenerate there and copy them here. `tests/fixtures/fs/replay/` (saved LLM responses) is owned here.
