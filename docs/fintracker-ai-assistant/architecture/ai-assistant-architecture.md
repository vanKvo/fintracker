# AI Assistant Architecture

| Status | Owner | Last reviewed | Applies to | App architecture |
|---|---|---|---|---|
| Proposed (Refactor phase: moving out of Analytics) | Van Vo | 2026-10-18 | main | [FinTracker architecture](../../fintracker-architecture/fintracker-architectural-doc.md) |

This document describes how the AI assistant works: its components and the workflows it owns. Rules that apply to every service are in the app architecture doc and are not repeated here. These include identity, events and invariants. Field-level schemas, prompts, thresholds and acceptance criteria live in the specs, such as [FS: Financial Summary](../../fintracker-analytics/FS-financial-summary-spec.md).

---

## 1. Overview

**Purpose:** the AI assistant is the only FinTracker service that calls an LLM. It turns facts computed by other services into explanations and answers, and keeps all AI risk in one place: prompts, model choice, guardrails, evaluation and LLM cost.

**Responsibilities**
- **Financial Summary (MVP):** generates, validates, caches and audits the AI narrative on the Reports tab, using the facts payload from Analytics.
- **Chat** *(proposed, Launch phase)*: answers user questions with read-only tools and retrieval over system help docs.
- **Tool registry:** the tool definitions the model can see, a per-use-case allowlist, and `execute_tool` as the single place every tool call passes through.
- **Shared AI pipeline:** prompt and model versions, cost guard, output validation, audit and traces.
- **Evaluation:** offline evaluation sets and owner-approved live runs before any prompt, model or schema change ships.
- **External assistants** *(later)*: exposes the same tools to a user's own AI assistant through an MCP gateway.

**Does not do**
- Compute any financial figure. Analytics computes metrics and detectors.
- Read any database. It calls other services' APIs as tools.
- Ingest documents or own the vector store. Knowledge does both; the AI assistant only calls `retrieve`.
- Write financial data. All tools are read-only by default.

**Owns**
- Summary cache, usage counters, audit records, facts snapshots and LLM responses.
- Conversations *(proposed)*.
- The tool catalog, prompts and model configuration (as config in code).
- Evaluation results.

---

## 2. Architecture and workflows

![AI assistant components](images/ai-assistant-components.png)

**How to read the diagram**
- The two **orchestrators** are the only entry points, one per use case. Both run every LLM call through the same **shared AI pipeline**, in order: cost guard → prompt builder → model call → output validator (one retry back to the prompt builder) → audit writer.
- The **Financial Summary** gets its facts from Analytics in one signed request and makes one LLM call. Only **chat** uses the tool registry.
- Every tool call goes through `execute_tool`. It re-checks the use case's allowlist, because the model's tool name is untrusted input, and takes the user from the request context, never from the model.

### Workflows

#### Generate the Financial Summary *(MVP)*

**Trigger:** `GET /summary?period` from the Reports tab, or Refresh (max 5 per user per day) · **Result:** a validated narrative, cached and audited · **On failure:** facts-only summary with a reason code; never a blank panel

![Financial Summary workflow](images/ai-assistant-financial-summary.png)

1. Take the user from the identity authorizer, never from the request body.
2. Request the facts payload and `facts_hash` from Analytics. If Analytics fails, show an error state and don't call the LLM.
3. Look up the cache by user, period, `facts_hash`, prompt version and model. A hit returns at once.
4. Fewer than 10 included transactions → skip the LLM and show "Not enough activity to summarize yet."
5. The cost guard checks per-request, per-user and app-wide limits. It fails closed.
6. Call the pinned model once, with the facts as a JSON data block, `max_tokens` 1,200 and a 25-second deadline. No tool calling in the MVP.
7. Validate in order: JSON schema → grounding (every evidence path and `{{metric_id}}` token must resolve; no numbers in free text) → advice scope (banned terms). One retry is shared across the checks.
8. Write the cache entry, the audit record and an encrypted snapshot of facts and response (30 days). Return numbers from the facts and text from the model.

#### Answer a chat question *(proposed, Launch phase)*

**Trigger:** a message on the chat streaming API · **Result:** a streamed answer with sources · **On failure:** safe fallback, or "I don't know" plus a logged unanswered question

![Chat workflow](images/ai-assistant-chat.png)

1. The chat streaming API runs the identity authorizer; the AI assistant reads the `userId` from the authorizer context ([ADR-012](../../fintracker-architecture/architectural_decision_records/ADR-012-chat-streaming-entry-rest-api.md)).
2. Check the subscription tier, the rate limit and the cost guard, then load the conversation history.
3. Send the history and message to the chat model as data, with the chat tool allowlist.
4. Run the tool loop, up to 8 calls, each through `execute_tool`:
   - `retrieve(query, scope=system)` from Knowledge for help-doc questions;
   - read-only data tools in Analytics and the Ledger for questions about the user's own numbers.
5. Post-check the answer: scope, banned terms, and grounding in the tool results and cited sources.
6. Stream the answer with sources, then save the turn and trace.

**Questions about the user's numbers are answered by data tools, never by document search.**

#### Answer from system help docs *(current focus)*

This is the retrieval-augmented part of chat. It is split across two services ([ADR-010](../../fintracker-architecture/architectural_decision_records/ADR-010-rag-retrieval-in-knowledge-service.md); see the [Knowledge architecture](../../fintracker-knowledge/architecture/knowledge-architecture.md)):

| Step | Owner |
|---|---|
| Write help docs in Git; CI uploads changed docs on merge | Developer, CI |
| Chunk, embed, index and replace old chunks (`scope = system`) | Knowledge |
| `retrieve(query, scope=system)` → top chunks with source paths | Knowledge |
| Decide to retrieve, build the prompt, generate with citations, post-check, log unanswered questions | AI assistant |

Unanswered questions are logged so the help docs, and later the allowed user-document types, follow real demand.

#### Evaluate prompt, model and schema changes

**Trigger:**
- every pull request: free replay tests;
- manual, owner-approved runs: live evaluation.

**Result:** a passing `full` run recorded for the exact versions. **On failure:** the merge is blocked.

1. Replay tests feed saved LLM responses through the validator without calling the LLM, on every pull request.
2. A change to prompts, `model_id`, the output schema or the facts payload schema blocks the merge until a passing `full` run exists for those versions.
3. Live runs go in tiers: dry (cost estimate only) → smoke → core → extended → full. Each tier needs the previous one to pass.
4. Each run has a cost cap (default $5) and its own IAM role. It runs only from a protected GitHub environment approved by the owner.

#### Handle account deletion

**Trigger:** `UserAccountDeleted` · **Result:** the user's AI data is gone and `UserDataDeleted` is published · **On failure:** retry from the queue, then the dead-letter queue

1. Delete the user's conversations, summary cache, usage counters, facts snapshots and LLM responses.
2. Keep audit records, but with the user ID replaced by a hash, so they can no longer be linked to the person.
3. Publish `UserDataDeleted(userId, ai-assistant)`.

#### Serve the user's own AI assistant *(later)*

1. A user connects an external assistant through OAuth and approves scopes.
2. The MCP gateway turns the token into a verified user, checks scope and rate limits, and logs the call.
3. The call goes to an MCP adapter in front of the same tool registry and allowlists.

FinTracker sees only the tool calls, not the assistant's answer, so tool correctness is the main quality lever.

---

## 3. Concepts of Operation

### 3.1 Enter: what does this service expose and consume?

| Interface | Type | Caller / producer | Purpose |
|---|---|---|---|
| `GET /summary?period` | Public API (gateway) | Web client | Get the Financial Summary for a period |
| `POST /summary/refresh` | Public API (gateway) | Web client | Regenerate, within the per-user limit |
| Chat streaming API *(proposed)* | Public REST API with response streaming, identity authorizer | Web client | Send a message, receive a streamed answer |
| MCP endpoint *(later)* | Behind the MCP gateway | User's own AI assistant | Read-only tool calls |
| `UserAccountDeleted` | Event consumed | User profile | Delete the user's AI data |
| `UserDataDeleted` | Event published | → User profile | Report deletion complete |

The AI assistant exposes no internal API. Other services don't call it.

### 3.2 Trust: who may call it, and how is each request scoped to a user?

- **Summary routes:** the user comes from the gateway's identity authorizer (`requestContext.authorizer.lambda.internal_user_id`). Client-supplied user IDs are ignored.
- **Chat:** the chat streaming API runs the same identity authorizer, so the user comes from its authorizer context, as on the summary routes (ADR-012).
- **Local development:** `LOCAL_DEV_USER_ID` is honoured only when `APP_ENV=local`.
- **Tools:**
  - No tool takes a user ID.
  - The user travels in the request context and is forwarded with each signed internal request (SigV4).
  - Tool names and arguments from the model are untrusted. `execute_tool` re-checks the allowlist and validates arguments against strict schemas: enums, capped ranges (at most 24 months), no extra fields.
- **Model access:** only this service's IAM roles may invoke generation models. Production, dev and evaluation use separate roles, each with its own AWS Budgets deny action.

### 3.3 Flow: how does it depend on other services?

| Depends on | How | Why | If unavailable |
|---|---|---|---|
| Analytics | Signed internal request | Facts payload (summary); section tools (chat) | Summary: error state, no LLM call. Chat: tool error returned to the model as a generic message |
| Knowledge | Signed internal request | `retrieve(scope=system)` for help-doc answers | Chat answers without docs and says so |
| Ledger | Signed internal request | Read-only data tools (chat) | Generic tool error; the model may answer partially |
| User profile | Signed internal request, cached 5 min | Timezone, primary currency | Use the cached value; behavior on a cache miss is still to be specified |
| Amazon Bedrock | AWS SDK (IAM) | LLM and chat model | Facts-only fallback (summary); safe fallback (chat) |
| EventBridge / SQS | Events | Account deletion | Retries from its own queue |

The tool transport is signed REST for now, the same in both profiles. An MCP layer would be added in front of the tool registry only for external assistants (app doc, open decisions).

### 3.4 Store: what data does it keep, and for how long?

| Data | Store | Retention | On account deletion |
|---|---|---|---|
| Summary cache | DynamoDB | Until facts, prompt version or model change | Deleted |
| Usage counters (per-user, app-wide daily) | DynamoDB | Daily windows | Deleted |
| Audit records (IDs, versions, tokens, outcome; no financial values) | DynamoDB | 12 months | User ID replaced by a hash |
| Facts snapshots + LLM responses | DynamoDB, encrypted | 30 days (TTL) | Deleted within the deletion window |
| Conversations *(proposed)* | DynamoDB | To be set before chat launches | Deleted |
| Evaluation results | S3, versioned | 90 days | Not user data (fixtures only) |

### 3.5 Protect: what does this service guard beyond the app-level rules?

- **Least data:** only the allowlisted facts payload reaches the model. It contains no account numbers, raw descriptions, names, emails, bank names or account nicknames.
- **Prompt injection:** merchant, category and chat strings are passed as JSON data fields. They are length-capped and stripped of control characters, and the system prompt says to treat all field values as data. An injection fixture is part of the evaluation set.
- **Grounding:**
  - The model writes interpretation only.
  - Figures appear as `{{metric_id}}` tokens that the UI fills from the facts.
  - Any free-text number is rejected, and insights must cite existing evidence paths.
- **Advice scope:**
  - Budgeting behaviors only; no investment, tax, credit or loan advice.
  - A banned-term check runs after generation.
  - The UI always shows "Informational only. Not financial advice."
- **Logging:** audit records and logs hold references and metadata only. A CI check fails the build if a log statement includes facts-payload fields or model text.
- **Cost controls never fail open:**
  - Limits apply per request, per user (10 generations a day) and app-wide (a daily circuit breaker).
  - At the account level, an AWS Budgets action denies Bedrock access.
- **Paid evaluation runs need the owner:** live runs can be started only by the owner, through a protected CI environment. No Bedrock credentials exist anywhere else.

### 3.6 Recover: how does it fail, and how does it recover?

- **Deadlines:** 25 seconds per summary request, and each LLM call times out at min(15 s, remaining time − 2 s). With less than 10 seconds left there is no retry.
- **One shared retry** for schema and grounding failures, then the facts-only fallback. Every fallback records a reason code (`fallback:<reason>`, `blocked:<reason>`).
- **Partial validation:** an insight with an unresolvable reference is dropped; if at least half the items are dropped, the whole summary falls back.
- **Audit write failure:** the summary is still returned. The write is retried asynchronously through SQS and counted in a metric.
- **Idempotent consumers:** deleting data that is already gone succeeds.

### 3.7 Observe: how do we know it is healthy?

- **Key metrics:**
  - fallback rate by reason;
  - validation failures and guardrail hits;
  - tokens and cost per user and per tier;
  - latency;
  - tool error rate (chat).
- **Security events** (a rejected user-ID argument, the tool-call limit exceeded, guardrail hits) are logged with `severity: security` and searchable by user.
- **Budget alerts:** app-wide spend at 80% sends an alert, and at 100% trips the circuit breaker. AWS Budgets alerts at 50%, 80% and 100%, plus Cost Anomaly Detection.
- **Later:** one trace schema across summary, chat and external use (OpenTelemetry GenAI conventions), online evaluations on sampled traces, and dashboards per use case (FS-17).

---

## 4. Service decisions

| # | Decision | Choice | Why | Revisit when | Status |
|---|---|---|---|---|---|
| S1 | Summary generation | One LLM call with the facts payload inline; no tool calling | Fixed data needs; cheaper, faster, easier to test than an agent | Facts payload grows beyond about 20 KB (switch to tools through the same registry) | Accepted |
| S2 | Numbers vs. text | Code computes every figure; the model writes interpretation with `{{metric_id}}` tokens | Removes arithmetic errors and invented numbers | Never | Accepted |
| S3 | Summary model | Cheapest Bedrock model that passes the evaluation set, pinned by version ID (tried in order: Nova Micro → Nova Lite → Nova 2 Lite → Claude Haiku 4.5) | Narrating precomputed facts is light work | Evaluation results or prices change | Accepted |
| S4 | Failure behavior | Validate, retry once, then the facts-only fallback | The panel is never blank or wrong | Never | Accepted |
| S5 | Tool registry | One registry of read-only tools with per-use-case allowlists, re-checked at execution; adapters for Bedrock tools and MCP | One choke point for safety, audit and reuse by chat and external assistants | Never | Accepted |
| S6 | Live evaluation | Manual, tiered, cost-capped, owner-approved; free replay tests on every pull request | Quality gate without surprise bills | Team grows beyond one owner | Accepted |
| S7 | Compute | Streaming Lambda in dev; Fargate behind an internal ALB in prod; both behind the chat REST API (ADR-012) | Near-zero idle cost in dev; no cold starts or 15-minute limit in prod (app doc D11) | Dev cold starts block testing | Accepted |

---

## 5. Related documents

- **App architecture:** [FinTracker architecture](../../fintracker-architecture/fintracker-architectural-doc.md). See D4 (only the AI assistant calls an LLM), D11 (compute per profile) and the open decision on tool transport.
- **Specs:**
  - [FS: Financial Summary](../../fintracker-analytics/FS-financial-summary-spec.md). This service owns FS-09 (prompt side), FS-10–FS-12, FS-14–FS-18, FS-20–FS-22 and FS-02 for its own routes. Analytics owns the facts engine and detectors.
  - Chat and RAG specs: [ai-open-chat-spec.md](../../fintracker-analytics/ai-open-chat-spec.md), [ai-rag-pipelines-spec.md](../../fintracker-analytics/ai-rag-pipelines-spec.md) (its user-data retrieval items are deferred with user documents).
  - Guardrails and evaluation: [ai-data-access-rules.md](../../fintracker-analytics/ai-data-access-rules.md), [ai-evaluation-auditing-spec.md](../../fintracker-analytics/ai-evaluation-auditing-spec.md).
  - External assistant *(later)*: [ai-chat-support.md](../../fintracker-analytics/ai-chat-support.md).
- **Knowledge** (retrieval half of RAG): [knowledge-architecture.md](../../fintracker-knowledge/architecture/knowledge-architecture.md).
- **Superseded:** [ai-integration-architecture.md](../../fintracker-analytics/architecture/ai-integration-architecture.md) and [ai-governance-monitoring.md](../../fintracker-analytics/architecture/ai-governance-monitoring.md). They were written when AI lived in Analytics, and their content is folded into this document.
- **Diagram sources:** `images/` (an editable SVG for every PNG).
