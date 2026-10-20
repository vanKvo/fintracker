# Implementation Plan: FS Financial Summary (MVP)

> **Status (2026-10-09): Phases 0–9 implemented; Phase 10 (Terraform) deferred by owner decision; Phase 11 waits on live runs.**
> The decisions are in `docs/fintracker-analytics/FS-financial-summary-updated.md`. The tests are in `docs/fintracker-analytics/fs-tests-01.md`, and run/config steps in `docs/instructions/run_financial_summary.md`.
> Differences from this plan: the existing `src/ai_agent` MCP tools were kept and moved to the authorizer context instead of being deleted. `/v1/analytics/insights` was unmounted, but its files were kept. The authorizer key stays `internal_user_id`.

Source: `docs/fintracker-analytics/FS-financial-summary-spec.md` (Draft, 2026-10-08, revision with FS-23–FS-30 and Appendix C).
Replaces the first version of this plan; its review questions are now answered in the spec.

**In scope (MVP):** FS-01–06, FS-08–16, FS-18, FS-20–28, FS-30.
**Out of scope (Later):** FS-07, FS-17, FS-19, FS-29. Their payload sections stay `null`; their insight types never get candidates.

---

## 1. Work outside the Analytics service

The spec now depends on four other components. Each one blocks a specific part of Analytics.

| Repo | Change | Needed by | Blocks |
|---|---|---|---|
| Shared Lambda authorizer (in User Profile today: `app/identity/handlers.py::authorizer_handler`) | Return the internal ID under the key `user_id`. Today it returns `internal_user_id`. It also isn't attached to any API Gateway yet (the Data Pipeline uses a Cognito JWT authorizer). | FS-02 | Deployed testing only. Unit tests use a fake request context. |
| `fintracker-ledger` | New migration: nullable `accounts.last_synced_at`. No code writes it yet, because automatic bank sync isn't built. | FS-23 stale flag | Nothing. The flag starts working when a sync feature sets the column. |
| `fintracker-user-profile` | Internal route returning a user's `timezone` and `currency`, authenticated with IAM (SigV4). Today the only internal route uses an API key. | FS-03 timezone, FS-23 primary currency | Facts engine in deployed environments. Tests use a stub. |
| `fintracker-ui` | Financial Summary panel on the Reports page. Remove the mocked narrative/insights. Add an `/api/v1/analytics` proxy entry. | FS-01, FS-13 | Nothing else. |

---

## 2. Architecture

### 2.1 Routes (Analytics Lambda, FastAPI + Mangum)

| Route | Returns | FS |
|---|---|---|
| `GET /v1/analytics/summary/periods` | Each period option with `has_data`, labels ("Sep 2026 vs. Aug 2026"), `refreshes_remaining` | 01, 14 |
| `GET /v1/analytics/summary/facts?period=` | Facts payload only (fast), so the UI can draw numbers first | 13 |
| `GET /v1/analytics/summary?period=` | Facts + AI summary, or facts + fallback with a reason code | 10–15, 21 |
| `POST /v1/analytics/summary/refresh?period=` | Same, skipping the cache; counts toward 5 refreshes and 10 generations per day | 14, 21 |

**Identity (FS-02).** A FastAPI dependency `get_auth_context()` reads `user_id` from the Lambda event's authorizer context (`scope["aws.event"]`, via Mangum). It never looks at headers, query strings or the body. No ID → 401 (RFC 9457), before any query runs. Every existing route (`dashboard`, `reports`) switches to this dependency and loses its `user_id` query parameter.

### 2.2 Generation pipeline (`service.py`)

```
auth ctx → resolve period (user timezone) → facts registry → detectors → facts_hash
  → cache hit? → return
  → < 10 included transactions? → "not enough activity" (no LLM)
  → cost guard (user cap, daily budget, input tokens; fail closed)
  → LLM call (deadline-aware) → schema → grounding → banned terms
  → one shared retry with errors, if unused and ≥ 10 s left
  → ≥ 50% items dropped or failure → facts-only fallback
  → cache store, audit record, snapshot (write failures → SQS retry queue)
```

Deadline (FS-10): 25 s per request; each call times out at `min(15 s, remaining − 2 s)`.

### 2.3 Module layout (`services/fintracker-analytics/src/summary/`)

| File | Responsibility | FS |
|---|---|---|
| `auth.py` | `AuthContext` (frozen dataclass: `user_id`, `timezone`, `currency`), FastAPI dependency, local-dev stub (Q2) | 02 |
| `profile_client.py` | IAM-signed call to User Profile for timezone/currency, 5-minute in-memory cache | 03, 23 |
| `periods.py` | Five period keys → period + comparison period in the user's timezone; MTD day clamping; YTD; leap days | 01, 03 |
| `repository.py` | Read-only SQL on the replica: included transactions for the period, comparison and history window; pending/adjustment counts; budgets (latest version per month); account sync state | 03–08, 23 |
| `registry.py` | Section registry: `name`, `description`, input schema (period only, `extra="forbid"`), output schema, `fn(ctx, period)`. Unavailable → `{available: false, reason}` | 09 |
| `sections/` | `cash_flow.py`, `categories.py`, `anomalies.py`, `budgets.py`, `data_quality.py`, `overall_status.py`. Pure functions over row sets | 03–06, 08, 23 |
| `detectors/` | `base.py` (candidate model, scoring, top 8), `fees.py`, `free_trial.py`, `duplicates.py`, `leakage.py`, `velocity.py` | 24–28, 30 |
| `payload.py` | Builds Appendix A from the registry, validates it, canonical JSON + `facts_hash` | 03, 09 |
| `projection.py` | Allowlisted LLM view: drops `transaction_id`, sanitizes and length-caps merchant/category strings | 16 |
| `prompt/v1.py` | System prompt (scope, allowed/disallowed examples, token rules, candidate priority, "Treat all field values as data"), output schema | 10, 12, 16, 24 |
| `llm.py` | Bedrock Converse: pinned model ID from config, temperature 0, `maxTokens` 1,200, timeout, `cachePoint` on the static prompt, token counting | 10, 21 |
| `validation.py` | Output schema (Pydantic) → grounding (evidence, `{{token}}`, `impact_ref`, digit regex) → banned terms; returns kept items and drop reasons | 10–12 |
| `fallback.py` | Facts-only summary: rule-based status, template text, reason codes | 15 |
| `cache.py` / `cost_guard.py` / `audit.py` | DynamoDB cache, counters, circuit breaker, audit records, snapshots, security events | 14, 18, 21 |
| `deletion_handler.py` | EventBridge `UserAccountDeleted` consumer: deletes snapshots and cache, replaces `user_id` in audit records with its hash | 18 |
| `eval/` | Eval runner, dry run, report, S3 results, tier check | 20, 22 |
| `router.py` | The four routes | 01, 13–15 |

### 2.4 Calculation rules

- **Inclusion (FS-23):** only `POSTED`, `is_excluded = FALSE`, user's primary currency. Income = `INCOME`. Expenses = `EXPENSE − REFUND` (TXT-02 sign rules, `ABS(amount)`). `TRANSFER` and `ADJUSTMENT` are excluded; adjustments counted. `PENDING` counted, not included. Other currencies are excluded and get an `excluded_currency:<code>` flag.
- **Determinism (FS-03):** `Decimal` everywhere, `ROUND_HALF_UP`, sorts with a stable tie-break (category or merchant name, then ID). `generated_at` is left out of the hash.
- **Cache key (FS-14):** `(user_id, period key + dates, facts_hash, prompt_template_version, model_id)`.
- **Tokens:** `{{path}}` resolves to a non-null numeric leaf of the payload. The four highlight `metric_id`s are aliases. The UI formats by path suffix: amounts → currency, `pct_*`/`savings_rate` → percent, `ratio` → "2.3×".
- **Detector candidates:** each has `evidence` facts paths. `impact_ref` in recommendations points to `insight_candidates[i].impact`.

### 2.5 Storage (Appendix C)

One DynamoDB table `fintracker-analytics` (on demand, customer-managed KMS key, TTL attribute `expires_at`):

| Item | PK / SK | TTL |
|---|---|---|
| Cached summary | `USER#<id>` / `SUMMARY#<period>#<hash>#<prompt_v>#<model>` | 30 days |
| Per-user daily counters | `USER#<id>` / `QUOTA#<yyyy-mm-dd>` (atomic `ADD`, conditional on the cap) | 2 days |
| App daily spend | `APP` / `SPEND#<yyyy-mm-dd>` (atomic `ADD` of estimated cost) | 40 days |
| Payload snapshot / LLM response | `PAYLOAD#<payload_id>` / `SUMMARY#<summary_id>` | 30 days |
| Audit record / security event | `AUDIT#<user_id>` / `<created_at>#<summary_id>`; GSI on `severity` | 365 days |

Config in SSM Parameter Store via Powertools parameters (5-minute cache): model ID, caps, daily budget, per-1K-token prices, banned terms, detector thresholds, fee keywords. Eval results go in a separate versioned S3 bucket with a 90-day lifecycle.

---

## 3. Phases

TDD per CLAUDE.md: each task is a failing-tests commit, then an implementation commit, logged in `docs/git/pending_commits.txt`. One test inventory doc per requirement group in `docs/fintracker-analytics/`, in the bare F2P format.

### Phase 0 — Prerequisites in other repos
| # | Repo | Task | FS |
|---|---|---|---|
| 0.1 | ledger | Migration `V24__Add_Account_Last_Synced_At.sql` (schema only) | 23 |
| 0.2 | user-profile | IAM-authenticated internal settings route (`timezone`, `currency`) | 03, 23 |
| 0.3 | user-profile | Authorizer context key `user_id` (Q1) | 02 |

### Phase 1 — Foundations
| # | Task | FS |
|---|---|---|
| 1.1 | `AuthContext` + dependency: ID from authorizer context only; forged header/query/body ignored; missing → 401 | 02 |
| 1.2 | Move `dashboard` and `reports` routes to the dependency | 02 |
| 1.3 | Profile client (SigV4, timeout, generic errors, cache) | 02, 03 |
| 1.4 | Period resolver (5 periods × comparison rules, timezone boundaries, Mar 31 → Feb 28/29, YTD across leap years) | 01, 03 |
| 1.5 | Registry: period-only input schema; a `user_id` argument → rejected + security event; unavailable shape | 02, 09 |
| 1.6 | Appendix A model, JSON Schema, canonical hash | 03 |

### Phase 2 — Facts sections
| # | Task | FS |
|---|---|---|
| 2.1 | Repository SQL + Testcontainers tests on the real Ledger schema (types, refunds, pending, excluded, deleted, other users' rows, other currencies) | 03, 23 |
| 2.2 | `data_quality`: counts, `no_comparison_data`, `stale_account`, `incomplete_period`, `excluded_currency`, `skipped_detectors` | 03, 23 |
| 2.3 | Cash flow + savings rate (null on zero income / zero comparison) | 04 |
| 2.4 | Categories: top 3, increases/decreases with materiality, uncategorized > 15% flag | 05 |
| 2.5 | Anomalies (merchant or category median, top 5, 60-day history rule) + new merchants | 06 |
| 2.6 | Budgets: per-month sum, complete vs MTD pace rules, `unbudgeted_total`, `no_budgets` | 08 |
| 2.7 | `overall_status` rule table; same inputs → byte-identical payload | 03 |

### Phase 3 — Detectors (positive + negative fixture per detector)
| # | Task | FS |
|---|---|---|
| 3.1 | Framework: candidate model, score ranking, top 8, missing data → `skipped_detectors`, errors logged and skipped | 24 |
| 3.2 | Fees (category `fees` or keyword on description; refunded fees excluded; 3-month average impact) | 25 |
| 3.3 | Free trial ($0–$1 earlier charge, 5–35 days before) | 26 |
| 3.4 | Duplicates (same merchant/amount ≤ 48 h, no refund, not a repeat pattern) | 27 |
| 3.5 | Leakage (< $20, ≥ 10 transactions, ≥ $100/month, top 2) | 28 |
| 3.6 | Spending velocity (MTD only, ≥ 7 days, budget or 3-month median baseline) | 30 |

### Phase 4 — Validation and fallback (no LLM; hand-written replay responses)
| # | Task | FS |
|---|---|---|
| 4.1 | Output schema: enums, max lengths, 3/5/3 caps | 10 |
| 4.2 | Grounding: evidence, tokens, `impact_ref`; digit regex; cascade drops; ≥ 50% → discard | 11 |
| 4.3 | Banned-term scan; hide recommendations if all removed | 12 |
| 4.4 | Fallback: template summary, reason codes, < 10 transactions path, facts failure → error | 15 |

### Phase 5 — LLM
| # | Task | FS |
|---|---|---|
| 5.1 | Projection + sanitization (control chars, length caps, data fields only) | 16 |
| 5.2 | Prompt builder: calls every registered function, embeds one validated JSON block; prompt v1 | 09, 10, 12, 24 |
| 5.3 | Bedrock client: pinned model, temp 0, `maxTokens`, `cachePoint`, timeouts, generic errors | 10, 21 |
| 5.4 | Orchestration: shared retry, deadline, ≥ 10 s rule, injection fixture → item unaffected or dropped | 10, 11, 16 |

### Phase 6 — Cache, cost guard, audit
| # | Task | FS |
|---|---|---|
| 6.1 | Cache + refresh limit (5/day) | 14 |
| 6.2 | Cost guard: input > 8,000 tokens, 10 generations/user/day, daily budget (80% alert, 100% breaker until 00:00 UTC), store down → fail closed; `blocked:<reason>` | 21 |
| 6.3 | Audit record, encrypted snapshot/response, security events, SQS retry + metric on write failure | 18 |
| 6.4 | Redaction check: runtime test with sentinel values (logs must not contain them) + AST lint of `logger.*` calls, run in CI | 18 |
| 6.5 | `UserAccountDeleted` consumer | 18 |

### Phase 7 — API and cleanup
| # | Task | FS |
|---|---|---|
| 7.1 | Four routes + orchestrator wiring | 01, 13–15 |
| 7.2 | Remove `/v1/analytics/insights`, the `insights/` feature and the `ai_agent/` MCP server (needs your OK, Q4) | 02, 13 |

### Phase 8 — UI (`fintracker-ui`)
| # | Task | FS |
|---|---|---|
| 8.1 | `FinancialSummaryService` (HTTP), proxy entry | 01 |
| 8.2 | Period dropdown: default *Last month*, disabled options + tooltip, labels, "Month to date" badge | 01 |
| 8.3 | Panel layout, sorted insights, "Why?" expander, hidden empty sections, disclaimer | 12, 13 |
| 8.4 | Token pipe (currency/percent/ratio, user currency + locale) | 13 |
| 8.5 | Data caveats from flags with fixed templates; `account_ref` → nickname from the accounts API | 13, 23 |
| 8.6 | States: skeleton, facts first, fallback note + Retry, error keeps previous summary, "Generated …", Refresh limit | 01, 13–15 |
| 8.7 | Remove mocked narrative/insights from `reports.service.ts`; Vitest + Playwright (API mocked) | 13 |

### Phase 9 — Evaluation and CI (Analytics repo)
| # | Task | FS |
|---|---|---|
| 9.1 | ≥ 20 fixtures in `tests/fixtures/fs/` + `manifest.yaml` (tier, required insight types); one per candidate type; injection fixtures | 20, 24 |
| 9.2 | Eval runner: tiers, `runs_per_fixture` (`full` = 2), pass criteria, token/cost report, comparison with the last passing run, S3 results | 20 |
| 9.3 | Dry run, tier-order check, per-run cap with `confirm_over_cap`, mid-run stop | 22 |
| 9.4 | `ci.yml` (PR): pytest incl. replay tests, mypy, redaction check, `eval-required` check keyed by a hash of prompt templates, model ID, output schema and facts schema; reads S3 with a read-only role (no Bedrock) | 18, 22 |
| 9.5 | `llm-eval.yml` (`workflow_dispatch`, environment `llm-eval`) | 22 |

### Phase 10 — Infrastructure (Terraform, `services/fintracker-analytics/infrastructure/terraform/`)
| # | Task | FS |
|---|---|---|
| 10.1 | DynamoDB table, KMS key, SQS retry queue, SSM parameters, eval results bucket | 14, 18, 20, 21 |
| 10.2 | IAM roles: prod / dev / eval Bedrock roles (InvokeModel on the pinned model only); eval role trust = GitHub OIDC from environment `llm-eval` only; read-only CI role for the results bucket | 21, 22 |
| 10.3 | AWS Budgets 50/80/100% + Budgets action attaching a deny policy to the Bedrock roles at 100%; Cost Anomaly Detection; SNS alert topic (80% daily budget) | 21 |
| 10.4 | EventBridge rule for `UserAccountDeleted` → deletion handler | 18 |
| 10.5 | Lambda + HTTP API with the shared authorizer (scope depends on Q5) | 02 |
| 10.6 | Manual (you): create the `llm-eval` GitHub environment with yourself as required reviewer; branch protection requiring `eval-required` | 22 |

### Phase 11 — Model selection and budgets (after implementation)
| # | Task | FS |
|---|---|---|
| 11.1 | dry → smoke → core on Nova Micro; move to Nova Lite → Nova 2 Lite → Haiku 4.5 only on a `core` failure; re-check prices; pin the winner | 10, 20 |
| 11.2 | Token budget = measured `core` average + 20% | 20 |
| 11.3 | Monthly and daily LLM budget: **open question, set from real test measurements** | 21 |

Suggested order: Phases 1–5 can run without any AWS resources (all tests use stubs and replay responses). Phases 6, 9 and 10 need the Terraform resources. Phase 0 can run in parallel with Phase 1.

---

## 4. Questions

Each has a recommended answer; the plan assumes it unless you say otherwise.

| # | Question | Recommendation |
|---|---|---|
| Q1 | The current authorizer returns `internal_user_id`, and the spec reads `user_id`. Also, with an HTTP API the context lands at `requestContext.authorizer.lambda.<key>`, not `requestContext.authorizer.<key>` (REST API). Which key and API type? | Rename the key to `user_id` in the shared authorizer. Use an HTTP API like the Data Pipeline. Analytics reads `authorizer.lambda.user_id`, behind one adapter function. |
| Q2 | How does a locally run Analytics (uvicorn, no authorizer) get a user ID? | A local-only stub that builds the request context from an environment variable `LOCAL_DEV_USER_ID`, never from a header. It turns on only when `APP_ENV=local`, and startup fails if it's set in any other environment. |
| Q3 | Timezone and primary currency: fetch them from User Profile per request (IAM route, cached), or have the authorizer add them to the request context? | IAM-signed internal route in User Profile with a 5-minute cache in Analytics. This keeps the authorizer to identity only. |
| Q4 | FS-02 and FS-13 mean removing the old insights endpoint and changing all tools. May I delete these files when the panel ships: `src/insights/` (4 files) + `tests/insights/`, and `src/ai_agent/` (`server.py`, `mcp_instance.py`, `tools.py`, `clients.py`) + `tests/ai_agent/`, and drop the `mcp` dependency? The MCP server isn't deployed, and FS-09's adapter replaces it later. | Yes, delete both. Otherwise `ai_agent` needs a refactor to the auth context and IAM calls with no current user. |
| Q5 | Terraform scope: only the FS resources, or the whole Analytics deployment (Lambda, HTTP API, VPC access to the read replica, secrets)? Nothing deploys Analytics today. | The whole service, so FS can actually run in dev. |
| Q6 | Is `transactions.description` the raw bank description for statement rows? FS-25 matches fee keywords on it. | Verify during Phase 3.2. If it isn't populated, use category `fees` + merchant keywords. |
| Q7 | FS-24 gives `score` 0–1 but no formula per detector. | `score = min(1, impact / $100)`, `duplicate_charge` fixed at 0.9 (its impact is null). Both configurable. |
| Q8 | FS-28 on multi-month periods: is "10 or more transactions" and "$100 or more" per month or per period? | Per month (period totals ÷ number of months). |
| Q9 | FS-23 `incomplete_period`: which accounts are checked? | Only accounts created before the period start that have at least one transaction before the period end. |
| Q10 | Fees refunded in the period (FS-25): how are refunds matched to fees? | `linked_transaction_id` first; otherwise a same-merchant, same-amount refund within 30 days. |
| Q11 | Token counting before the call (FS-21): Bedrock's CountTokens API may not support the Nova models. | Use CountTokens where supported. Otherwise use a conservative local estimate (characters ÷ 3), checked against measured counts in eval runs. |
| **Q-Budget** | Monthly and daily LLM budget (FS-21 Open Question). | **Left open.** Set from dry/smoke/core measurements after implementation. |

---

## 5. Remaining spec gaps (for you to decide; spec not edited)

1. **FS-08 vs FS-09:** FS-08 says `budgets` is `null` with no budgets; FS-09 says an unavailable section returns `{available: false, reason}`. Proposal: registry functions return the `available: false` shape, and the payload stores `null` plus the flag.
2. **FS-02 vs current authorizer:** key name and context path (Q1).
3. **Appendix B insight types** still include `subscription`, `emergency_fund` and `cash_timing`, which depend on Later sections. The schema allows them, but grounding will always drop them. Same treatment as the highlight IDs: remove until FS-07/FS-19/FS-29 ship.
4. **FS-15** "fewer than 10 transactions": state that it counts transactions after the FS-23 inclusion rules (`data_quality.transaction_count`).
5. **FS-24 score** has no defined formula (Q7).
