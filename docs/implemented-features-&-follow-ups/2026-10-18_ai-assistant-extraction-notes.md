# AI assistant extraction: notes (2026-10-18)

Moving every LLM concern out of Analytics into a new `services/fintracker-ai-assistant` service, so the code matches architecture decision D4 and invariant 10 ("Only the AI assistant calls an LLM"). It also covers what the architecture doc review found, and the spec updates this needs. Spec files are left for the owner to update.

## What moved

| From `fintracker-analytics` | To `fintracker-ai-assistant` |
|---|---|
| `src/summary/` LLM side: `config`, `llm`, `prompt/`, `generation`, `validation`, `projection`, `fallback`, `cost_guard`, `store`, `audit`, `deletion`, `eval/`, the `GET /summary` + `POST /summary/refresh` orchestration | `src/summary/` (routes now `/v1/ai/summary`, `/v1/ai/summary/refresh`) |
| `src/ai_agent/` (MCP tools, service clients) | `src/tools/` |
| `src/insights/` Bedrock service, models, router (legacy, unmounted since FS-13) | `src/insights/` (still unmounted) |
| `scripts/check_log_redaction.py`, `.github/workflows/llm-eval.yml`, the eval-required CI job | same paths |
| `tests/fixtures/fs/replay/` | same path; `tests/fixtures/fs/*.json` is copied (Analytics keeps the builder and its own copy) |

**What stays in Analytics:** the facts engine (periods, inclusion, sections, detectors, payload, `facts_hash`), `GET /v1/analytics/summary/periods` and `/facts`, the dashboard and report queries, and the merchant × month query. Analytics no longer has a DynamoDB table, Bedrock access, `mcp` or `tenacity`.

## Interface between the two services

- **Analytics internal routes** (`/internal/v1/analytics/...`, served by the analytics-internal API with IAM auth): `summary/facts?period=` (returns `{period, facts, facts_hash}`), `dashboard`, `reports/spending`, `reports/trend`, `insights/merchant-months`. The caller's ARN must match `INTERNAL_ALLOWED_CALLER_ARNS`, and an unset list rejects every call (fail closed). The user comes from `X-Internal-User-Id`, which is read only after the caller check. With `APP_ENV=local` the caller check is skipped.
- **AI assistant → Analytics**: SigV4-signed GETs to `ANALYTICS_INTERNAL_API_URL`. Any failure becomes a generic error. The summary then returns 503 and the LLM is not called.
- **Facts contract**: `fintracker-ai-assistant/src/summary/contract.py` is a consumer-side copy of Analytics' `src/summary/schema.py` (Appendix A). It feeds the eval version key, so a change there requires a passing `full` evaluation (FS-22).
- **UI**: `getSummary` and `refresh` now call `/api/v1/ai/summary` (dev proxy → `localhost:8085`). Periods and facts still call Analytics.
- **Behavior change**: `GET /v1/analytics/summary/periods` no longer returns `refreshes_remaining`, because usage counters belong to the AI assistant. The UI keeps its default of 5 until the first summary response arrives with the real count.

## Architecture doc review findings

The doc is internally consistent and all its links resolve. These gaps are between the doc and the code or other docs:

1. **Analytics doesn't set the user context for RLS** (invariant 4, section 4.2). Its SQL filters by `user_id`, but it never sets `app.current_user_id`. It also connects through SQLAlchemy/asyncpg (`DATABASE_URL`), not the RDS Data API from D5. Both need fixing before Analytics reads Aurora under forced RLS.
2. **Section 4.3, internal-request list**: it doesn't list the AI assistant → User profile call (timezone and currency) that the AI assistant doc's 3.3 table names. That call doesn't exist in code today, because Analytics resolves periods. Either add it to 4.3 or drop it from the AI assistant doc.
3. **AI assistant doc, section 5**: four spec links point to `../../fintracker-analytics/` (`ai-open-chat-spec.md`, `ai-data-access-rules.md`, `ai-evaluation-auditing-spec.md`, `ai-chat-support.md`). Those files live in `docs/fintracker-ai-assistant/`. Its `ai-rag-pipelines-spec.md` link should point to `docs/fintracker-knowledge/`.
4. **Section 11, Superseded**: `fintracker-architecture/fintracker_workflows.md` and `fintracker-analytics/architecture/ai-integration-architecture.md` / `ai-governance-monitoring.md` are still in the tree. Consider an archive folder, so readers and agents don't treat them as current.
5. **Section 2, Ledger "Owns"** lists statement records linked to a `documentId`, which is the target state. Until the Document service ships, the Ledger still holds the storage key. Consider marking it *(proposed)* the way other rows are marked.
6. **The legacy Bedrock insights** (anomalies, subscription creep, now in the AI assistant's `src/insights/`) call an LLM *inside* a tool. That conflicts with section 4.3, where tools are read-only data tools and the AI assistant is the only LLM caller. The Financial Summary detectors replace it (FS-13). Candidate for removal along with the two MCP tools that use it.

## Proposed spec updates (for the owner)

- **FS spec**: route table. Summary and refresh move to `/v1/ai/summary`; periods and facts stay under `/v1/analytics/summary`. The periods response drops `refreshes_remaining`. Appendix C: the summary table belongs to the AI assistant, not Analytics. Requirement ownership follows the AI assistant doc, section 5.
- **FS spec / analytics doc**: name the internal facts route `/internal/v1/analytics/summary/facts`, which returns `facts_hash` alongside the payload.

## Follow-ups not done here

- Create the GitHub repo for `fintracker-ai-assistant`, add it as a remote, and register it with `git submodule add`.
- Terraform: an `ai-assistant` Lambda and the analytics-internal API (D18). Move the summary DynamoDB table, SQS retry queue, SNS topic and Bedrock IAM permissions from the Analytics role to the AI assistant role. Set `INTERNAL_ALLOWED_CALLER_ARNS` on Analytics.
- The GitHub `llm-eval` environment and OIDC trust policy must name the new repo.
- `mypy src/summary` in the AI assistant reports two errors in `store.py`. They existed before the move (unchanged code).
