# AI-CHAT implementation notes

| Field | Value |
|---|---|
| Spec | [AI-CHAT-open-chat-spec.md](specs/AI-CHAT-open-chat-spec.md) |
| Tests | [AI-CHAT-open-chat-tests.md](specs/AI-CHAT-open-chat-tests.md) (204 test functions, 250 cases) |
| Code | `services/fintracker-ai-assistant/src/chat/` |
| Date | 2026-10-25 |

What was built, what was not, what must be configured before chat can run, and the spec changes I propose. The spec is read-only for me, so every proposed change is below for you to apply.

---

## 1. What was built

One route, `POST /chat/messages`, that streams newline-delimited JSON events. The flow per message:

1. **Body check** (`router.py`, `service.accept`): empty, over 2,000 characters, extra fields, not JSON → 400 `invalid_argument`. A field naming the caller (`user_id`, `timezone`, …) is also a `context_field_in_body` security event.
2. **Conversation** (`service.prepare`): no ID → a new one; an ID that isn't in the caller's partition → 404, whoever owns it.
3. **Stream starts** with a `status` event that carries the conversation ID, then: in-flight cap → approved model → daily token allowance for the tier → history (last 10 turns).
4. **Tool loop** (`service._converse`): Bedrock Converse with the eight-tool allowlist. At most 8 tool calls, 5 s each, 45 s for the turn. Every call goes through `ChatToolExecutor.run` (`execute.py`): allowlist re-check, strict argument schema, verified context, generic errors to the model.
5. **Post-check** (`validation.py`, `grounding.py`): one JSON object → cited chunks were retrieved → every figure is in a tool result → no banned term. One retry with the errors as data, then a fixed fallback text.
6. **Delivery**: usage added (a failure refuses the answer), audit record, answer in chunks, `sources`, the turn is saved, `done`.

Reused from the Financial Summary rather than copied: the cost guard (one app-wide daily budget, the 80%/100% alerts), the Bedrock client and its error classes, the banned-term list and matcher, the audit writer and its retry queue, the account-deletion handler. Chat's DynamoDB items sit under `USER#<id>` and `AUDIT#<id>`, so the existing deletion handler already covers them (AI-CHAT-14 needed tests, not code).

Changes outside `src/chat/`:

| File | Change |
|---|---|
| `core/identity.py` | Reads the REST API's flat authorizer context as well as the HTTP API's `lambda` node (ADR-012). Flat shape counts only with an `internal_user_id`. |
| `core/request_context.py`, `core/error_handlers.py` | The middleware binds the trace ID; `traceparent_header()` forwards it on internal calls. |
| `core/observability.py` | `span()`: an OpenTelemetry span when the API is installed, nothing otherwise. |
| `tools/clients.py`, `schemas.py`, `exceptions.py` | New: category trends, top merchants, transaction search with totals, Knowledge `retrieve`. The trace ID is forwarded on every signed call. |
| `summary/llm.py` | `_invoke` extracted so chat shares the call, retries-classification and logging; `_classify` is now `classify_error`. |
| `summary/validation.py` | `find_banned_terms()` (public) |
| `main.py` | Chat router, startup model check, `application/x-ndjson` as a text type (else Mangum base64-encodes the stream). |
| `scripts/check_log_redaction.py`, `.github/workflows/ci.yml` | Checks `src/chat`; flags `message`, `answer`, `question`, `history`, `query`, `result(s)`, `chunks`, `arguments`. mypy covers `src/chat`. |

## 2. Not done, or done in part

| Item | Why | Next |
|---|---|---|
| **AI-CHAT-12, negative rating** (status set to *In progress*) | The spec names a negative rating as a trigger but defines no rating endpoint, so there is nothing to call. `build_item(..., reason="negative_rating")` is ready. | Specify the feedback route (turn ID + thumbs), then add it. |
| **AI-CHAT-12, weekly report schedule** | `unanswered.weekly_report_handler` exists and is tested; this service has no IaC for scheduled Lambdas yet. | EventBridge weekly rule when the Terraform for the Lambdas lands. |
| **Chat REST API, Lambda Web Adapter, Fargate listener** | ADR-012 says to spike streaming end to end first. The route is a FastAPI `StreamingResponse`, which streams under uvicorn (Fargate) but is buffered by Mangum. | Do the spike. Python Lambda streaming needs Lambda Web Adapter. |
| **Identity under Lambda Web Adapter** | Identity is read from `scope["aws.event"]`, which only Mangum sets. Under LWA the authorizer context arrives in the `x-amzn-request-context` header, and a client can send that header itself unless the gateway overwrites it. I did not add a header-based path. | Decide how the shared identity library reads the context there, and prove the gateway overwrites the header. |
| **Terraform for chat** | No env, role or SSM wiring was added. | Add the chat model ARN to `model_arns`; give the role access to the Knowledge internal API; allow-list this role in Knowledge's `INTERNAL_ALLOWED_CALLER_ARNS` (KN-RET-01). |
| **UI** | Out of scope here. | See section 4 for the stream contract. |

## 3. Must be configured before chat answers anything

- **Daily token allowances** (open question 3): `daily_tokens` in the `CHAT_CONFIG_PARAM` SSM JSON, one number each for `free`, `basic`, `pro`. Unset means every turn gets `limits_unavailable`. I did not invent numbers.
- **`KNOWLEDGE_INTERNAL_API_URL`**: help-doc answers fail with "help docs unavailable" without it.
- **The shared daily budget** (`SUMMARY_DAILY_BUDGET_USD` or the summary SSM JSON): unset blocks chat as it blocks the summary.
- **Chat model**: the default `amazon.nova-lite-v1:0` is a placeholder until the AI-EVAL gate picks one. A model must be on `approved_model_ids` (defaults: Nova Lite, Nova 2 Lite, Claude Haiku 4.5) or startup fails. **Do not run live chat evaluations without your approval** (CLAUDE.md); no real Bedrock call was made.
- **Score threshold 0.35** (open question 2) is the default; calibrate it on the golden set.
- **Local run**: `APP_ENV=local`, `LOCAL_DEV_USER_ID`, `LOCAL_DEV_TIMEZONE`, `LOCAL_DEV_CURRENCY`, `LOCAL_DEV_TIER`, plus a table and the settings above.

## 4. Behavior the UI and the spec should know about

- `answer` events are **fragments** (about 120 characters, split on word boundaries). The client appends them in order. A short answer is one event.
- The first event is always `status` with `conversation_id`. Limit and budget errors come as an `error` event right after it, not as an HTTP status.
- The `error` event for `daily_limit_reached` has a `reset_at` (ISO 8601, the next midnight in the user's timezone).
- Fallbacks (Appendix D) arrive as a normal `answer` then `sources` (empty) then `done`; only `timeout` and the limit/busy cases are `error` events.
- The disclaimer "Informational only. Not financial advice." is added by code, only when a data tool returned something. The "this answer may be incomplete" note is added by code when the tool limit was hit.
- A conversation ID returned in the first event stays valid for 30 days after the last completed turn, even if its first turn failed.

## 5. Design decisions worth a second look

- **Final reply is JSON** (`answer`, `cited_chunks`, `out_of_scope`), because a citation has to be checkable. An `out_of_scope` reply is replaced by the fixed refusal, so the refusal text (which contains "investment") never meets the banned-term check.
- **What counts as a figure** (grounding): money, percentages, decimals, numbers with thousands separators, any number of 3+ digits, and small counts followed by a counting word ("12 transactions"). Dates and years, the user's own numbers and numbers in retrieved help-doc text are exempt. A rounded figure matches the value it rounds ("24%" for 23.87). Plain small numbers ("top 3") are not figures. Tune `_COUNT_WORDS` and the rounding rule with the golden set.
- **Fixed fallback instead of asking the model again** when the docs return nothing usable, when every data tool failed, or when the model says out of scope. This saves a model call and removes the chance of an invented answer.
- **`search_transactions`** returns posted, non-excluded money-out rows only. The Ledger has no totals endpoint, so the client pages through up to 1,000 matches and sums them; `totals_complete` is false beyond that. A Ledger summary endpoint would be cheaper and exact.
- **Usage is added after the turn.** A user at 99% of the allowance can finish one more message, bounded by the per-message caps (8 tool calls, 800 output tokens a call, 45 s). A failing usage write refuses the answer.
- **Turn IDs** start with a nanosecond timestamp (`t-<ns>-<hex>`), so turns sort in order even when two share a timestamp.
- **Moto quirk** (not a product bug): after a spend reservation is released to exactly zero, moto stores `0E-8` and rejects the next conditional write. Real DynamoDB does not. One test avoids that sequence.

## 6. Proposed spec changes (for you to apply)

1. **Appendix D**: add `docs_unavailable` ("The help docs are unavailable right now. Please try again in a few minutes.") and `invalid_reply` ("I couldn't put together a reliable answer. Please try asking again."). The code uses them for Knowledge errors and for replies that fail the shape or citation check twice.
2. **Appendix A**: say that `answer` events are fragments to join; that the first event is a `status` with `conversation_id`; that `error` may carry `reset_at`.
3. **AI-CHAT-02**: say that the allowance is checked before the call and the turn's tokens are added after, so one message can pass it by at most the per-message caps.
4. **AI-CHAT-05**: define `search_transactions` as posted, non-excluded money-out rows; say the totals come from paging the Ledger.
5. **AI-CHAT-08**: add the definition of a figure from section 5 so the golden set and the validator agree.
6. **AI-CHAT-09**: say the disclaimer is added by code only when a data tool returned data.
7. **AI-CHAT-12**: add the feedback route that records a negative rating, or drop that trigger.
8. **Open question 1** (when a session ends): the API treats the conversation ID as the session. The UI decides when to start a new one; nothing server-side ends a session.
9. **AI assistant architecture 3.4**: conversations are kept 30 days after the last turn (the table still says "to be set").
