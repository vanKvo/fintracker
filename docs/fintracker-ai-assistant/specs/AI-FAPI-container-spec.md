# AI-FAPI: AI Assistant as a Container

| Field | Value |
|---|---|
| Product | FinTracker AI assistant |
| Prefix | AI-FAPI |
| File | fintracker-ai-assistant/specs/AI-FAPI-container-spec.md |
| Owner | Van Vo |
| Status | Draft |
| Last updated | 2026-10-30 |

---

## 1. Overview

### Problem
The AI assistant is already a FastAPI app behind Mangum (`src/main.py`), but it has no Dockerfile or compose file, so it only runs through `uvicorn` on a developer's machine with a hand-built environment. Three things stop a local end-to-end run:
- Its state is DynamoDB and its chat limits come only from SSM, so chat is refused (`limits_unavailable`) without AWS.
- Its help-doc answers need Knowledge, which cannot be run locally yet (KN-FAPI).
- The settings a local run needs (identity, internal auth mode, budget, endpoint overrides) are scattered across the README, with no single tested set.

### Goals
- One container image runs the existing app with `uvicorn`; the same code and `src.main:handler` run in Lambda.
- With `docker compose up`, a developer can send a chat message and get a streamed answer from the real model, grounded in help docs retrieved from the local Knowledge stack.
- The local setup is safe by construction: every local-only setting refuses to start in AWS, real spend is capped, and no real user data is touched.
- Anything the container needs from other services is optional locally and fails as a clear tool result, not a crash.

### Non-Goals
- No change to chat or Financial Summary behavior, routes, prompts or guardrails.
- No Terraform or deployment change. This spec produces an image and a local stack; where the image is deployed in AWS is a later decision.
- Ledger, Analytics and User Profile are not started. Tools that need them return `unavailable` unless their URLs are configured.
- No local substitute for the model: Bedrock is called for real, with the developer's AWS credentials.
- The manual live evaluation (AI-EVAL-09) runs the chat service in-process and is separate from this container.

### Design Principles
1. **Same artifact everywhere.** The image is the app; local differs by configuration only (app invariant 12).
2. **Local-only settings are guarded.** Each one raises at startup unless `APP_ENV=local`, and the infrastructure tests assert none is set in AWS.
3. **Fail closed, and cheap.** A local run has a small spend cap and a small token allowance by default.
4. **Real model, fake neighbors.** Bedrock and Knowledge are real; Analytics, Ledger and User Profile are absent.
5. **No secrets in the image.** Credentials come from the host at run time.

---

## 2. Workflow

```
[docker build, monorepo root as context] ──► AI-FAPI-01
    │
[Container starts: validates configuration] ──► AI-FAPI-01, AI-FAPI-03
    │
[Local identity, table and limits] ──► AI-FAPI-03, AI-FAPI-04
    │
[Bedrock with host credentials, capped spend] ──► AI-FAPI-05
    │
[Tools: Knowledge real, others unavailable] ──► AI-FAPI-06
    │
[Streamed answer] ──► AI-FAPI-07
    │
[Whole local stack proves it] ──► AI-FAPI-08
```

---

## 3. Requirements Index

| ID | Title | Area | Priority | Status |
|---|---|---|---|---|
| AI-FAPI-01 | The app runs as a container image | Quality | MVP | Proposed |
| AI-FAPI-02 | Health route for the container | Reliability | MVP | Proposed |
| AI-FAPI-03 | Local configuration is one tested set and cannot run in AWS | Security | MVP | Proposed |
| AI-FAPI-04 | Local state is DynamoDB Local with the deployed key schema | Data | MVP | Proposed |
| AI-FAPI-05 | Local runs call the real model with capped spend | Cost | MVP | Proposed |
| AI-FAPI-06 | Other services are optional locally | Reliability | MVP | Proposed |
| AI-FAPI-07 | Chat streams through the container | Quality | MVP | Proposed |
| AI-FAPI-08 | The local stack answers a help question end to end | Quality | MVP | Proposed |

---

## 4. Requirements

### AI-FAPI-01: The app runs as a container image  `Priority: MVP`

**Requirement:** A `Dockerfile` builds one image that runs `uvicorn src.main:app` on port 8085, as a non-root user. The build context is the monorepo root, because the shared internal HTTP library is a path dependency. The image holds no credentials, `.env` files, evaluation results or test fixtures. `src.main:handler` (Mangum) stays the Lambda entry point, unchanged.
**Acceptance Criteria:**
- [Happy] The image builds in CI and starts with the local settings of AI-FAPI-03; the startup checks of `main.py` (`assert_local_identity_safe`, `load_internal_http_settings`, `assert_required_env`, `assert_chat_ready`) all run in the container.
- [Alt] A CI step lists the image's files and fails if it finds `.env*`, `.aws`, `eval/` results or `tests/`.
- [Fail] The container refuses to start when a required variable is missing outside local, naming the variable and not its value.
- [Fail] The process runs as a non-root user (checked in the container test).
**Refs:** UP-FAPI-11 (pattern); LB-PKG; app invariant 12

### AI-FAPI-02: Health route for the container  `Priority: MVP`

**Requirement:** `GET /health` returns 200 `{"status": "ok"}` without calling any dependency, so a container runtime can tell the process is up. It carries no user data, needs no identity, and is not added to any API Gateway route list.
**Acceptance Criteria:**
- [Happy] `GET /health` returns 200 in under 100 ms with DynamoDB Local, Knowledge and Bedrock all unreachable.
- [Alt] The compose health check uses it.
- [Fail] `GET /health` is absent from the deployed route lists (checked by the infrastructure tests that list public routes).
**Refs:** KN-FAPI-08

### AI-FAPI-03: Local configuration is one tested set and cannot run in AWS  `Priority: MVP`

**Requirement:** The compose file sets the full local configuration of Appendix A and nothing else: `APP_ENV=local` with `LOCAL_DEV_USER_ID`, `LOCAL_DEV_TIMEZONE`, `LOCAL_DEV_CURRENCY` and `LOCAL_DEV_TIER`; `INTERNAL_AUTH_MODE=local`; the local caller; `AUDIT_HASH_SALT`; and the endpoint and budget settings of AI-FAPI-04 and -05. Chat limits, which are SSM-only today, can be given locally through `CHAT_CONFIG_JSON` (JSON with the same keys as the SSM parameter), honored only when `APP_ENV=local`. A test compares the compose file's variables to the list in Appendix A, so documentation and compose cannot drift.
**Acceptance Criteria:**
- [Happy] With the compose settings, `POST /chat/messages` is accepted as the local user and the tier's `daily_tokens` from `CHAT_CONFIG_JSON` applies.
- [Alt] `CHAT_CONFIG_JSON` is read once per turn like the SSM value, and an invalid value falls back to the defaults, which block chat (`limits_unavailable`), as invalid SSM does.
- [Fail] `CHAT_CONFIG_JSON` set while `APP_ENV` is not `local` stops the process at startup, as `LOCAL_DEV_USER_ID` does.
- [Fail] `INTERNAL_AUTH_MODE=local` with an AWS runtime marker set stops the process (LB-IHTTP-02).
- [Fail] An infrastructure test fails if any local-only variable (`APP_ENV=local`, `LOCAL_DEV_*`, `CHAT_CONFIG_JSON`, `INTERNAL_AUTH_MODE`) appears in the deployed configuration.
**Refs:** FS-02; LB-IHTTP-01, LB-IHTTP-02; AI-CHAT Appendix C; Appendix A

### AI-FAPI-04: Local state is DynamoDB Local with the deployed key schema  `Priority: MVP`

**Requirement:** The compose file starts DynamoDB Local with a persistent volume, and a one-shot step creates the AI assistant table with the same key schema (`PK`, `SK`) and TTL attribute (`expires_at`) as the deployed table. The container reaches it through `AWS_ENDPOINT_URL_DYNAMODB` only; the global `AWS_ENDPOINT_URL` is refused at startup. `SUMMARY_TABLE_NAME` is set, so the real `ChatStore` is used and conversation history, token usage, spend and audit records are written and can be read back. The audit retry queue and the budget alert topic are left unset.
**Acceptance Criteria:**
- [Happy] After one chat turn, DynamoDB Local holds the conversation, the turn, a `TOKENS#<day>` item for the user, the `SPEND#<day>` item and the audit record.
- [Alt] A second message in the same `conversation_id` sees the first (history is read back).
- [Alt] A test compares the table-creation step to the deployed table definition's key schema and TTL attribute, so they cannot drift.
- [Fail] `AWS_ENDPOINT_URL` set at startup stops the process, naming the variable, because it would send Bedrock calls to DynamoDB Local.
- [Fail] If DynamoDB Local is down, a chat request ends in the existing store-unavailable behavior (fail closed, no model call), not a stack trace.
**Open Questions:** Where is the deployed table defined? The AI assistant's Terraform has no table module, so the drift test needs a single source for the key schema.
**Refs:** AI-CHAT-03, AI-CHAT-13; `chat/store.py`, `summary/store.py`

### AI-FAPI-05: Local runs call the real model with capped spend  `Priority: MVP`

**Requirement:** The container calls Bedrock with the developer's AWS credentials, mounted read-only from the host profile; no credentials are written into the image or the compose file. The compose settings give a small shared daily budget (`SUMMARY_DAILY_BUDGET_USD`, default `1.00`) and small `daily_tokens` per tier, so a loop cannot run up spend; the cost guard blocks at the cap exactly as in AWS. The chat model comes from `CHAT_MODEL_ID` and must be on the approved list and have a price row, or every call is blocked.
**Acceptance Criteria:**
- [Happy] With valid credentials and the default model, a chat turn gets an answer and the spend counter moves by the priced cost.
- [Alt] A turn that would pass the budget ends with the existing `service_busy` event and no further model call.
- [Fail] With no credentials, the turn ends with `service_busy` or `error`, never a stack trace, and `/health` stays 200.
- [Fail] A `CHAT_MODEL_ID` with no `DEFAULT_PRICES` row blocks every call and says so in the log (cost can't be priced), not silently.
**Open Questions:** Approved chat model IDs are bare IDs (`anthropic.claude-haiku-4-5-20251001-v1:0`) while `DEFAULT_PRICES` is keyed on inference-profile IDs (`us.anthropic.…`), so only the Nova Lite default is both approved and priced. Align the approved list and the price table (proposed: use inference-profile IDs in both), before anything but Nova Lite can run locally.
**Refs:** AI-CHAT-15; AN-FS-21; `summary/cost_guard.py`

### AI-FAPI-06: Other services are optional locally  `Priority: MVP`

**Requirement:** `INTERNAL_BASE_URL_KNOWLEDGE` points at the local Knowledge stack. `INTERNAL_BASE_URL_ANALYTICS`, `_LEDGER` and `_USER_PROFILE` may be unset locally (the startup check allows it only when `APP_ENV=local`). A tool whose service URL is unset returns an `unavailable` tool error through the existing tool-error path (AI-CHAT-04), and the model's answer says it cannot reach that data. The model is never given a fabricated figure.
**Acceptance Criteria:**
- [Happy] With only Knowledge configured, a question answered by `retrieve_help_docs` returns an answer with `sources`.
- [Alt] A question that needs spending data ("How much did I spend on dining last month?") ends with an answer that says the data is unavailable, no figure, and the audit outcome shows the tool as failed.
- [Fail] An unset URL never raises an unhandled exception out of the tool loop; the turn does not end in `internal_error` because of it.
- [Fail] If Knowledge is unreachable, the turn follows AI-CHAT's "no docs" behavior (Appendix D) and says so, as in AWS.
**Refs:** AI-CHAT-04, AI-CHAT-07; KN-RET-07 ("no docs available")

### AI-FAPI-07: Chat streams through the container  `Priority: MVP`

**Requirement:** `POST /chat/messages` served by `uvicorn` in the container streams `application/x-ndjson` events (`status`, `answer`, `sources`, `done`, or `error`) as they are produced, with `Cache-Control: no-store` and `X-Accel-Buffering: no`, so a developer sees the stream with `curl -N`.
**Acceptance Criteria:**
- [Happy] `curl -N` shows the first event before the last, and the stream ends with `done`.
- [Alt] A 400 for a bad body and a 404 for an unknown `conversation_id` come before any model call, as problem+json.
- [Fail] A failure after the stream starts is an `error` event with a code (`timeout`, `service_busy`, `internal_error`), never a broken connection with a stack trace.
**Refs:** AI-CHAT-01, AI-CHAT-14; chat router

### AI-FAPI-08: The local stack answers a help question end to end  `Priority: MVP`

**Requirement:** The service's `docker-compose.yml`, included from the root compose, starts `dynamodb-local`, the table step and `ai-assistant`, on the same network as the Knowledge stack (KN-FAPI-09). A smoke script sends golden how-to questions through `POST /chat/messages` and checks the stream.
**Acceptance Criteria:**
- [Happy] "How do I confirm a CSV column mapping?" returns a stream that ends in `done`, with `sources` listing `help/statements/csv-mapping.md` and a non-empty answer.
- [Alt] After the run, the token and spend counters in DynamoDB Local have moved and an audit record exists for each turn, with no message or answer text in it.
- [Alt] A negative question ("How do I turn on two-factor authentication?") ends with the `no_docs` fallback and no source.
- [Fail] With the Knowledge stack stopped, the same question ends with the `no_docs` fallback and the service stays up.
- [Fail] The smoke script stops and reports the cost so far if the budget cap is reached.
**Refs:** KN-FAPI-09; AI-CHAT Appendix D; AI-EVAL-09 (the evaluation of answer quality)

---

## 5. Open Questions (consolidated)

| # | Question | Blocks |
|---|---|---|
| 1 | Where is the deployed AI assistant table defined, so the local table step can be tested against it? | AI-FAPI-04 |
| 2 | Align the approved chat model IDs with the price table (inference-profile IDs in both)? Without it only Nova Lite runs locally. | AI-FAPI-05 |

---

## Appendix A: Local configuration

Set in the compose file only. Every row marked "local only" stops the process if set outside `APP_ENV=local` or inside an AWS runtime.

| Variable | Local value | Notes |
|---|---|---|
| `APP_ENV` | `local` | Local only |
| `LOCAL_DEV_USER_ID` | a fixed UUID | Local only |
| `LOCAL_DEV_TIMEZONE`, `LOCAL_DEV_CURRENCY` | `America/New_York`, `USD` | Local only |
| `LOCAL_DEV_TIER` | `free` | Local only |
| `INTERNAL_AUTH_MODE` | `local` | Local only; never set by IaC |
| `INTERNAL_LOCAL_CALLER_ARN` | `arn:local:ai-assistant` | Must be on Knowledge's list in compose |
| `INTERNAL_BASE_URL_KNOWLEDGE` | `http://knowledge-api:8087` | Real |
| `INTERNAL_BASE_URL_ANALYTICS`, `_LEDGER`, `_USER_PROFILE` | unset | Tools return `unavailable` |
| `SUMMARY_TABLE_NAME` | the local table name | |
| `AWS_ENDPOINT_URL_DYNAMODB` | `http://dynamodb-local:8000` | Never the global `AWS_ENDPOINT_URL` |
| `AWS_REGION`, credentials | from the mounted host profile | Not in the image |
| `AUDIT_HASH_SALT` | any string | |
| `SUMMARY_DAILY_BUDGET_USD` | `1.00` | Shared by summary and chat |
| `CHAT_MODEL_ID` | an approved, priced model | AI-FAPI-05 |
| `CHAT_CONFIG_JSON` | e.g. `{"daily_tokens": {"free": 20000}}` | Local only; same keys as the SSM parameter |

---

## Change Log

| Change | Reason |
|---|---|
| New spec | Give the AI assistant a container image and a tested local stack, so chat can be run end to end on Docker with the real model and the local Knowledge service |
