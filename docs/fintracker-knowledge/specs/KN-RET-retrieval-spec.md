# KN-RET: Retrieval

| Field | Value |
|---|---|
| Product | FinTracker |
| Prefix | KN-RET |
| File | fintracker-knowledge/specs/KN-RET-retrieval-spec.md |
| Owner | Van Vo |
| Status | Draft |
| Last updated | 2026-10-20 |

---

## 1. Overview

### Problem
The AI assistant needs relevant help-doc passages, with sources, to answer how-to questions. This is the only path by which Knowledge text leaves the service, so it is where a wrong user, a bad argument or a leaked chunk would do the most harm. This spec is the contract the AI assistant depends on, and changes to it must be agreed with that service.

### Goals
- p95 latency ≤ 800 ms for `k ≤ 10`, measured at the internal API.
- Zero cross-user chunks returned, proven by tests and by a production alarm.
- Every failure maps to one documented error, so the AI assistant can answer without docs and say so.

### Non-Goals
- Building prompts, generating answers or citing: the AI assistant does (ADR-010).
- Re-ranking, keyword or hybrid search (service decision S6).
- `scope = user` results before user documents ship (KN-UDOC).

### Design Principles
1. **Text in, chunks out.** The caller sends a query string and never sees vectors, SQL or the database.
2. **The user comes from the signed context.** Never from the request body, query or a model's tool argument (invariant 2).
3. **Retrieved text is data.** Chunks are returned in data fields, for the caller to pass to the model as data, never as instructions.
4. **No content in logs.** Query text and chunk text are never logged; only IDs, counts, scores and timings.

---

## 2. Workflow

```
[Signed request from AI assistant execute_tool] ──► KN-RET-01
    │
[Validate scope, k, query] ──► KN-RET-02
    │
[Embed query with active model (KN-CHUNK-02)] ──► KN-RET-03
    │
[One transaction: set user context + vector search + scope filter] ──► KN-RET-04
    │
[Re-check scope and owner of each chunk] ──► KN-RET-05
    │
[Return text, source path, heading, score] ──► KN-RET-06
    │
[Failure at any step → documented error] ──► KN-RET-07
    │
[Metrics, no content] ──► KN-RET-08
```

---

## 3. Requirements Index

| ID | Title | Area | Priority | Status |
|---|---|---|---|---|
| KN-RET-01 | Caller allow-list and user context | Security | MVP | In progress |
| KN-RET-02 | Argument validation | Security | MVP | Implemented |
| KN-RET-03 | Query embedding | AI | MVP | Implemented |
| KN-RET-04 | Scoped vector search | Data | MVP | Implemented |
| KN-RET-05 | Ownership re-check | Security | MVP | Implemented |
| KN-RET-06 | Response contract | Data | MVP | Implemented |
| KN-RET-07 | Errors and timeouts | Reliability | MVP | Implemented |
| KN-RET-08 | Retrieval metrics and log hygiene | Observability | MVP | In progress |

---

## 4. Requirements

### KN-RET-01: Caller allow-list and user context  `Priority: MVP`

**Requirement:** `POST /internal/retrieve` on `knowledge-internal` accepts only SigV4-signed requests from IAM roles on the caller allow-list (today, only the AI assistant's role). The user is read from the forwarded verified user context.
**Acceptance Criteria:**
- [Happy] A signed request from the AI assistant's role with a user context is accepted.
- [Fail] An unsigned request is rejected by API Gateway IAM auth with 403, before reaching the Lambda.
- [Fail] A signed request from a role not on the allow-list returns 403 `caller_not_allowed`.
- [Fail] A request without a user context returns 401 `user_context_missing`; a `user_id` field in the body is rejected by KN-RET-02, never used.
**Refs:** ADR-004; ADR-011; invariants 2–3

### KN-RET-02: Argument validation  `Priority: MVP`

**Requirement:** The body is validated against the strict schema in Appendix A before any other work. Unknown fields are rejected.
**Acceptance Criteria:**
- [Happy] `{ "query": "How do I confirm a CSV mapping?", "scope": "system", "k": 5 }` passes.
- [Alt] A missing `k` defaults to 5.
- [Fail] `k` < 1 or > 10, a blank query, a query over 1,000 characters, or any extra field returns 400 `invalid_argument` naming the field.
- [Fail] `scope = user` returns 400 `scope_not_enabled` until KN-UDOC ships; any other scope returns 400 `invalid_argument`.
**Refs:** Appendix A

### KN-RET-03: Query embedding  `Priority: MVP`

**Requirement:** The query is embedded with the active embedding model, using the same input format and call as KN-CHUNK-02, without a heading prefix.
**Acceptance Criteria:**
- [Happy] The query vector has the active model's dimension count, and the search uses only chunks with that `embedding_model`.
- [Fail] An embedding failure after KN-CHUNK-02's retries returns 503 `embedding_unavailable`.
**Refs:** KN-CHUNK-02; KN-CHUNK-03

### KN-RET-04: Scoped vector search  `Priority: MVP`

**Requirement:** In one Data API transaction, as role `kn_retrieve`, set `app.current_user_id` and the KN-VS-04 search settings, then select the *k* nearest chunks by cosine distance, filtered by the requested scope and the active model.
**Acceptance Criteria:**
- [Happy] With `scope = system`, results contain only `scope = system` chunks, ordered by ascending distance.
- [Alt] An empty result is a 200 with `"chunks": []`, not an error.
- [Alt] Results include at most 3 chunks from the same document, so one long doc can't fill all *k* slots.
- [Fail] An Aurora failure (including resume from pause in dev) is retried once after 1 s, then returns 503 `database_unavailable`.
**Open Questions:** Is a per-document cap of 3 right, or should it be removed once there are more docs?
**Refs:** KN-VS-03; KN-VS-04; ADR-003

### KN-RET-05: Ownership re-check  `Priority: MVP`

**Requirement:** Before returning, every chunk's `scope` and `user_id` are checked again in application code: `system` chunks must have a null owner, and `user` chunks must belong to the context user. Any mismatch is dropped and counted.
**Acceptance Criteria:**
- [Happy] With correct RLS, nothing is dropped and the mismatch count is 0.
- [Alt] In a test where RLS is disabled and a user B chunk is returned, the response omits it.
- [Fail] Any dropped chunk emits `kn.retrieve.ownership_mismatch` (value ≥ 1, with chunk ID and request ID, no text), and an alarm fires on the first occurrence.
**Refs:** KN-VS-05; architecture doc 3.5 Protect

### KN-RET-06: Response contract  `Priority: MVP`

**Requirement:** A successful response follows Appendix B: chunk text, source path, heading path and score (1 − cosine distance, 0–1, 3 decimals). It never includes vectors, internal IDs other than `chunk_id`, or the owner.
**Acceptance Criteria:**
- [Happy] Each chunk has `chunk_id`, `text`, `source_path`, `heading_path` and `score`, in descending score order.
- [Alt] The response includes `embedding_model` and `index_commit`, so the AI assistant can log which index answered.
- [Fail] A response that fails schema validation in the contract test fails the build.
**Refs:** Appendix B

### KN-RET-07: Errors and timeouts  `Priority: MVP`

**Requirement:** The whole call finishes within 3 s or returns 504 `timeout`. Every error uses the error body in Appendix C with a stable code and a generic message; exception text and stack traces are never returned.
**Acceptance Criteria:**
- [Happy] A slow embedding call over the budget returns 504 `timeout` within 3.2 s.
- [Alt] The AI assistant's contract test treats every code in Appendix C as "no docs available" and answers without docs, saying so.
- [Fail] An unexpected exception returns 500 `internal_error`; the detail goes to logs with the trace ID and request ID only.
**Refs:** Appendix C; AI assistant architecture "If unavailable"

### KN-RET-08: Retrieval metrics and log hygiene  `Priority: MVP`

**Requirement:** Each request logs and emits request ID, caller role, scope, *k*, result count, top score, error code and latency per step (validate, embed, search). Query text and chunk text are never logged.
**Acceptance Criteria:**
- [Happy] A dashboard shows p50/p95 latency, error rate by code and empty-result rate.
- [Alt] An alarm fires when the empty-result rate is above 30% over 1 hour with at least 20 requests.
- [Fail] A log-scan test that sends a unique marker string as the query finds it in no log line.
**Refs:** architecture doc 3.7 Observe

---

## 5. Open Questions (consolidated)

| # | Question | Blocks |
|---|---|---|
| 1 | Is a per-document cap of 3 chunks right, or should it be removed once there are more docs? | KN-RET-04 |

---

## Appendix A: Request

Produced by: AI assistant `execute_tool` (code; arguments may originate from the model and are untrusted).

```json
{
  "query":  "string, 1–1000 chars, required",
  "scope":  "system | user (user rejected until KN-UDOC)",
  "k":      "integer 1–10, default 5"
}
```
No other fields are allowed. The user comes only from the forwarded user context.

---

## Appendix B: Response

Produced by: Knowledge (code).

```json
{
  "chunks": [
    {
      "chunk_id": "6b1e…",
      "text": "To confirm a column mapping, open …",
      "source_path": "help/statements/csv-mapping.md",
      "heading_path": "Statements > CSV mapping > Confirm columns",
      "score": 0.812
    }
  ],
  "embedding_model": "amazon.titan-embed-text-v2:0",
  "index_commit": "9f2c1ab"
}
```

---

## Appendix C: Errors

Body: RFC 9457 `application/problem+json`, as every service (app doc 4.8; [error catalog](../../fintracker-architecture/error-catalog.md)):
`{ "type", "title", "status", "detail", "code", "retryable", "trace_id" }`. `detail` is generic; `request_id` is logged, never returned.

| HTTP | Code | When |
|---|---|---|
| 400 | `invalid_argument` | Schema validation failed |
| 400 | `scope_not_enabled` | `scope = user` before KN-UDOC |
| 401 | `user_context_missing` | No verified user context |
| 403 | `caller_not_allowed` | Role not on the allow-list |
| 503 | `embedding_unavailable` | Bedrock failed after retries |
| 503 | `database_unavailable` | Aurora failed after retry |
| 504 | `timeout` | Over the 3 s budget |
| 500 | `internal_error` | Anything else |
