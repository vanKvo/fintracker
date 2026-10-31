# KN-FAPI: Knowledge as a FastAPI Container

| Field | Value |
|---|---|
| Product | FinTracker |
| Prefix | KN-FAPI |
| File | fintracker-knowledge/specs/KN-FAPI-fastapi-container-spec.md |
| Owner | Van Vo |
| Status | Draft |
| Last updated | 2026-10-30 |

---

## 1. Overview

### Problem
Knowledge has the vector store, chunking, embedding, indexing and retrieval code, but nothing that runs it. Retrieval is one Lambda-style handler that takes an API Gateway event dictionary, there is no FastAPI app, no database connection setup, no way to index documents except from S3, and no Dockerfile. As a result the AI assistant's help-doc answers cannot be tried on a laptop, and the only tests of the HTTP behavior build raw events by hand. Every other Python service (Analytics, AI assistant, User Profile) is a FastAPI app that also runs as a container.

### Goals
- `POST /internal/retrieve` is served by one FastAPI app with the same URL, status codes, error codes and body as KN-RET today.
- One container image runs the app with `uvicorn`; the same code runs in Lambda behind Mangum.
- With `docker compose up`, the database, migrations, a local document index and the app start, and the AI assistant can retrieve help-doc chunks from it.
- Row-Level Security is enforced the same way locally as in AWS: the app connects as a role that cannot bypass it.
- A local run uses the recorded embeddings of KN-CHUNK-05 (replay mode) and holds no AWS credentials, so it can answer the golden questions and nothing else, and cannot call Bedrock. Real retrieval quality is measured only by the owner's live evaluation (KN-CHUNK-05).

### Non-Goals
- No new retrieval behavior: KN-RET stays the contract. No `scope = user` (KN-UDOC), no change to chunking or ranking.
- AWS infrastructure for Knowledge (Aurora, API Gateway `knowledge-internal`, S3 events, Step Functions, alarms) is not built here. It is a later spec; this one gives it an app and an image to deploy.
- The account-deletion consumer (KN-DEL) and the `GET /internal/index-status` route (KN-SDOC) are not part of this spec.
- No invented vectors. The local stack uses replay mode (KN-FAPI-05), which serves only real vectors recorded by the owner's live evaluation; a stub model would make local retrieval results meaningless.
- The internal-call checks themselves are the shared library's (LB-IHTTP); this spec only wires them.

### Design Principles
1. **Same artifact everywhere.** Local, CI and AWS run the same code (app invariant 12). Local differs by configuration only, and every local-only setting refuses to start in AWS.
2. **Security is not a local switch.** Local mode may replace the signature check. It may never replace Row-Level Security or the caller allow-list.
3. **Routes are thin.** A router parses the request and calls `RetrievalService`. Rules stay in the services.
4. **Fail the start, not the first request.** Missing or unsafe configuration stops the process with the setting's name and no value.
5. **No content in logs.** Unchanged from KN-RET-08.

---

## 2. Workflow

```
[Request reaches the app] ──► KN-FAPI-01
    │
[Who is calling? which user?] ──► KN-FAPI-02
    │
[Services resolved on first use; startup checks] ──► KN-FAPI-03, KN-FAPI-05
    │
[One transaction as kn_retrieve, RLS applies] ──► KN-FAPI-04
    │
[Same answers and errors as before] ──► KN-FAPI-10

[Local stack: docker compose up]
    ├─ database migrations and restricted roles ──► KN-FAPI-07
    ├─ index docs/help into the database ──► KN-FAPI-06
    ├─ app container + health ──► KN-FAPI-08
    └─ end-to-end proof, with the AI assistant ──► KN-FAPI-09
```

---

## 3. Requirements Index

| ID | Title | Area | Priority | Status |
|---|---|---|---|---|
| KN-FAPI-01 | One FastAPI app serves every HTTP route | Data | MVP | Implemented |
| KN-FAPI-02 | The route uses the standard caller check and user context | Security | MVP | Implemented |
| KN-FAPI-03 | Services come from dependencies and startup checks | Quality | MVP | Implemented |
| KN-FAPI-05 | The embedding client is built from configuration | AI | MVP | Implemented |
| KN-FAPI-04 | Database access is per role, with RLS enforced | Security | MVP | Implemented |
| KN-FAPI-07 | Migrations and restricted roles are separate, one-shot steps | Reliability | MVP | In progress |
| KN-FAPI-06 | A local index command reads documents from a folder | Data | MVP | Implemented |
| KN-FAPI-08 | The service runs as a container with health checks | Quality | MVP | In progress |
| KN-FAPI-09 | The local stack proves retrieval end to end | Quality | MVP | In progress |
| KN-FAPI-10 | Behavior is unchanged after the move | Quality | MVP | Implemented |

*IDs are not in numeric order in the index because the table follows the workflow order.*

---

## 4. Requirements

### KN-FAPI-01: One FastAPI app serves every HTTP route  `Priority: MVP`

**Requirement:** `src/main.py` exposes `app` (FastAPI) and `handler` (Mangum). Routes are in Appendix A: `POST /internal/retrieve` with the request, response and errors of KN-RET Appendices A–C, and the two operational routes `GET /health` and `GET /ready` (KN-FAPI-08). The retrieval router lives in `src/retrieval/router.py` as a FastAPI `APIRouter`; the event-dictionary handler is removed once KN-FAPI-10 passes.
**Acceptance Criteria:**
- [Happy] `POST /internal/retrieve` with `{ "query": "How do I confirm a CSV mapping?", "scope": "system", "k": 5 }` from an allowed caller returns 200 with the Appendix B shape of KN-RET.
- [Alt] A path that does not exist returns 404 `not_found`, and a known path with another method returns 405 `method_not_allowed`, both as problem+json.
- [Alt] `/docs`, `/redoc` and `/openapi.json` are served only when `INTERNAL_AUTH_MODE=local`.
- [Fail] A body that is not JSON returns 400 `invalid_argument`, not FastAPI's default 422. Every KN-RET-02 validation failure keeps its 400 and field name.
**Refs:** KN-RET-02, KN-RET-06, KN-RET-07; Appendix A

### KN-FAPI-02: The route uses the standard caller check and user context  `Priority: MVP`

**Requirement:** `POST /internal/retrieve` depends on the shared library's `require_internal_caller` and then `get_internal_user(require=("user",))` (LB-IHTTP-05, -06), replacing the raw-event adapter in `core/internal_auth.py`. The caller is decided before the body or any user header is read. The user comes only from `X-Internal-User-Id`, never from the body.
**Acceptance Criteria:**
- [Happy] An allowed caller with a valid user ID is served.
- [Alt] The library's conformance suite (`run_conformance`) passes against the real route.
- [Fail] No verified caller returns 401 `unauthorized`; a caller off the list, or an unset list, returns 403 `caller_not_allowed`; the user headers are not read in either case.
- [Fail] A missing user ID returns 401 `user_context_missing`; a non-UUID returns 400 `invalid_argument` without echoing the value; a `user_id` field in the body is rejected by KN-RET-02.
**Refs:** KN-RET-01; LB-IHTTP-05, LB-IHTTP-06, LB-IHTTP-08, LB-IHTTP-09

### KN-FAPI-03: Services come from dependencies and startup checks  `Priority: MVP`

**Requirement:** `RetrievalService` and its parts (embedder, `PostgresChunkSearch`, metrics, config) come from FastAPI dependencies backed by one container object that builds each part once per process, on first use. At startup the app validates the library settings (`load_settings()`, LB-IHTTP-01/02) and the required variables of Appendix B for the selected database mode, and stops with the variable's name (never its value) if one is missing.
**Acceptance Criteria:**
- [Happy] A test replaces the service with `app.dependency_overrides` and runs the route with no AWS client or database connection created.
- [Alt] Two requests in one process get the same service instance.
- [Fail] A start without a required variable raises with the variable's name; with `INTERNAL_AUTH_MODE=iam` and `INTERNAL_ALLOWED_CALLER_ARNS` unset it still starts and every call is a 403 (fail closed).
- [Fail] `INTERNAL_AUTH_MODE=local` with an AWS runtime marker set stops the process (LB-IHTTP-02).
**Refs:** UP-FAPI-06; AI assistant `summary/config.py::assert_required_env`

### KN-FAPI-05: The embedding client is built from configuration  `Priority: MVP`

**Requirement:** `KNOWLEDGE_EMBEDDER` selects the embedder: `bedrock` (default) or `replay`. In `replay` mode, set with `KNOWLEDGE_REPLAY_DIR`, the client answers from `recording.json.gz` (KN-CHUNK-05) and no AWS client is created, so no credentials are needed or used; it can embed only the recorded golden and negative questions and the snapshot chunks. In `bedrock` mode the Bedrock runtime client used by `Embedder` is built in the container from `AWS_REGION` and the default credential chain, with its own connect and read timeouts that fit inside KN-RET-07's 3 s budget and no SDK retries (KN-CHUNK-02 owns retries). Only service-specific endpoint overrides are honored; a global `AWS_ENDPOINT_URL` is refused at startup because it would send Bedrock calls to a local stand-in.
**Acceptance Criteria:**
- [Happy] With valid AWS credentials the container embeds a query with the active model (`active_embedding_model`, 1,024 dimensions).
- [Alt] The embedding model ID is read from config (KN-CHUNK Appendix A), never hard-coded in the container.
- [Fail] `AWS_ENDPOINT_URL` set at startup stops the process with a message naming the variable.
- [Fail] No credentials: the first query returns 503 `embedding_unavailable` (KN-RET-03); the app still starts and `/health` is 200, `/ready` is 503 (KN-FAPI-08).
- [Alt] **Replay:** a recorded question is embedded without any AWS call; `/ready` is 200 when the recording loads, with no credentials.
- [Fail] **Replay:** a text that is not in the recording returns 503 `embedding_unavailable` at once (no retries), and the log names `replay_miss`.
- [Fail] `KNOWLEDGE_EMBEDDER=replay` without `KNOWLEDGE_REPLAY_DIR`, or with an AWS runtime variable set (Lambda, ECS), stops the process naming the variable.
**Refs:** KN-CHUNK-02, KN-CHUNK-05; KN-RET-03, KN-RET-07

### KN-FAPI-04: Database access is per role, with RLS enforced  `Priority: MVP`

**Requirement:** The container builds one connection factory per database role it needs: `kn_retrieve` for the API, and `kn_ingest` for the index command (KN-FAPI-06). `KNOWLEDGE_DB_MODE` selects `postgres` (a direct TCP connection with a login role that is a member of the `NOLOGIN` role, used locally and in CI) or `data_api` (RDS Data API with the role's secret, used in AWS); both give `PostgresChunkSearch` the same transaction-per-call interface. At startup in `postgres` mode the app checks that the connected user is not a superuser and does not have `BYPASSRLS`, and refuses to start otherwise.
**Acceptance Criteria:**
- [Happy] In `postgres` mode, a search sets `app.current_user_id` and the HNSW settings in the same transaction as the query (KN-VS-03, -04) and returns the Appendix B shape.
- [Alt] The `data_api` factory is exercised by a unit test with a fake client; no AWS call is made in CI.
- [Fail] Starting `postgres` mode with a superuser or a `BYPASSRLS` role exits at startup, naming the role (not the password).
- [Fail] A database error surfaces as 503 `database_unavailable` after the one retry of KN-RET-04; the driver message is never returned or logged.
- [Fail] Through the running app, a chunk owned by user A is not returned to user B (a seeded `scope = user` row; KN-RET-05's mismatch count stays 0).
**Open Questions:** In AWS, does Knowledge keep the Data API (KN-VS) from a Lambda, or move to a direct connection from a VPC container? Proposed: keep the Data API; this spec only guarantees both modes work behind one interface.
**Refs:** KN-VS-03, KN-VS-04, KN-VS-05; KN-RET-04, KN-RET-05; Open Question 1

### KN-FAPI-07: Migrations and restricted roles are separate, one-shot steps  `Priority: MVP`

**Requirement:** Database migrations run as a separate, one-shot step with an administrative user, before the app starts and never from the app. The app and the index command connect as login roles that are members of the matching restricted roles, with no superuser and no `BYPASSRLS`. Role passwords are never stored in tracked files. If the migration step fails, neither the app nor the index command starts. How the database is provided and the roles are created is in the build, test and deploy instructions, not here.
**Acceptance Criteria:**
- [Happy] After the migration step, V1–V5 are applied and the login roles exist.
- [Alt] Running the migration step again applies nothing new and succeeds.
- [Fail] Connected as the retrieve login role without a user context set, no `scope = user` rows are visible (RLS holds), and `kn_index_runs` cannot be read.
- [Fail] If a migration fails, the app does not start.
- [Fail] A test fails if a file holding secrets is tracked, or if a password literal appears in a tracked stack, SQL or script file.
**Refs:** KN-VS-01, KN-VS-02, KN-VS-05; README "Run them as a separate deploy step"

### KN-FAPI-06: A local index command reads documents from a folder  `Priority: MVP`

**Requirement:** `python -m src.system_docs.cli index --root <folder>` indexes every Markdown file under `<root>/help/`, embedding with the configured embedder (KN-FAPI-05; replay locally, real Bedrock only through the owner-only guard of KN-CHUNK-05), using `SystemDocsIndexer` and a new `LocalDocSource` (`DocSource` implementation: `list_paths()` and `read(path)` over a folder). Paths are relative to the root (`help/statements/csv-mapping.md`), the same form as S3 keys and the golden set. `rebuild` re-indexes everything; `status` prints counts. The source commit is `--commit` or, by default, the repository's short commit with `-dirty` when the docs have uncommitted changes. The command opens the `kn_ingest` role and refuses a database host that is not local.
**Acceptance Criteria:**
- [Happy] Indexing `docs/` writes the 12 help documents; the output lists documents seen, chunks written, skipped unchanged and failures.
- [Alt] A second run with no changes writes 0 chunks and reports every document as skipped (KN-SDOC hash skip).
- [Alt] A changed file replaces only its own chunks, atomically (KN-SDOC).
- [Alt] Only `help/**/*.md` is read; other files under the root are ignored, and a path with `..` is rejected (as the publisher does).
- [Fail] A Bedrock failure after retries leaves that document's previous chunks in place, exits non-zero and names the document.
- [Fail] A database host that is not local exits before any Bedrock call.
- [Fail] With `KNOWLEDGE_EMBEDDER=bedrock`, the command refuses to start unless the owner guard of KN-CHUNK-05 allows it (not from a test, not with an agent marker, a named profile and a terminal).
**Refs:** KN-SDOC-01 to -05; `system_docs/source.py`, `service.py`; KN-CHUNK-05 (the live evaluation indexes the snapshot with the same indexer, into a throwaway database)

### KN-FAPI-08: The service runs as a container with health checks  `Priority: MVP`

**Requirement:** A `Dockerfile` builds one image that runs `uvicorn src.main:app` on port 8087, as a non-root user, from the monorepo root as build context (the shared library is a path dependency). `GET /health` answers 200 without touching any dependency. `GET /ready` answers 200 only when the database answers a trivial query as `kn_retrieve` and the embedding client is configured, else 503. Neither route carries user data, and neither is added to any API Gateway route list.
**Acceptance Criteria:**
- [Happy] The image builds in CI, starts with local settings, and `/health` returns 200 within 10 s.
- [Alt] `/ready` returns 200 when the database is up and 503 `database_unavailable` when it is stopped, while `/health` stays 200.
- [Alt] The image contains no `.env*`, AWS credential file or test data (checked by a CI step that lists the image files).
- [Fail] The process runs as a non-root user (checked in the container test).
- [Fail] The image's default command refuses to start `INTERNAL_AUTH_MODE=local` if an AWS runtime marker is set.
**Refs:** UP-FAPI-11 (Dockerfile pattern); LB-IHTTP-02

### KN-FAPI-09: The local stack proves retrieval end to end  `Priority: MVP`

**Requirement:** One command starts the local stack: the migration step (KN-FAPI-07), the app (KN-FAPI-08) and, on demand, the index command (KN-FAPI-06) reading the recorded snapshot (`tests/fixtures/rag/`) read-only. The local stack reaches the database the developer already runs and holds no AWS credentials: it embeds in replay mode (KN-FAPI-05), mounts no `~/.aws`, and so can answer the golden questions only. Local authentication mode and the local caller are set only in the local stack's own configuration; the allowed callers are set to the AI assistant's local caller so the 403 path stays testable. A smoke script checks the stack through HTTP. The commands and files are in the build, test and deploy instructions, not here.
**Acceptance Criteria:**
- [Happy] After indexing, a request for "How do I confirm a CSV column mapping?" with the AI assistant's caller header and a user ID returns chunks whose first `source_path` is `help/statements/csv-mapping.md`.
- [Alt] The AI assistant's chat (AI-FAPI-08) retrieves from this stack through its configured Knowledge address.
- [Alt] The smoke script runs the cross-user check: a `scope = user` row seeded for user A is absent from user B's results.
- [Fail] A request with no caller header returns 401, and a caller not on the list returns 403.
- [Fail] A question that is not in the recording returns 503 `embedding_unavailable`; the smoke script reports it and stops, not a stack trace.
- [Fail] A test fails if the compose file mounts `~/.aws` or sets an AWS credential or profile variable.
**Refs:** KN-RET-01, KN-RET-05; AI-FAPI-08; plan `implementation_plans/2026-10-30_local_ai_assistant_knowledge.md`

### KN-FAPI-10: Behavior is unchanged after the move  `Priority: MVP`

**Requirement:** Before the event-dictionary handler is removed, the existing handler tests (`tests/retrieval/`) are kept as cases that run against the FastAPI route: same request, same status, same error `code`, same body. The log-scan test of KN-RET-08 and the ownership-mismatch test of KN-RET-05 run against the app. No deployed behavior exists yet (no infrastructure), so the move changes nothing in AWS.
**Acceptance Criteria:**
- [Happy] All recorded cases pass against the app with no edits to expected values.
- [Alt] The metrics lines (`RequestMetrics`, `kn.retrieve.ownership_mismatch`) are unchanged in name and fields.
- [Fail] A unique marker sent as the query appears in no log line produced by a request through the app.
- [Fail] A case whose expected value had to change is listed in the Change Log with the reason, or the change is reverted.
**Refs:** KN-RET-05, KN-RET-07, KN-RET-08; UP-FAPI-12

---

## 5. Open Questions (consolidated)

| # | Question | Blocks |
|---|---|---|
| 1 | In AWS, does Knowledge keep the RDS Data API (from a Lambda) or use a direct connection (from a VPC container)? Proposed: keep the Data API; local and CI use `postgres` mode behind the same interface. The deployed shape of this image (Lambda container image or a container service) is decided with the infrastructure spec. | KN-FAPI-04 |
| 2 | Port 8087 for Knowledge (8085 AI assistant, 8086 User Profile)? Proposed: yes. | KN-FAPI-08 |

---

## Appendix A: Routes

| Method and path | API | Success | Failures | Notes |
|---|---|---|---|---|
| `POST /internal/retrieve` | internal | 200 | 400, 401, 403, 503, 504, 500 | Contract: KN-RET Appendices A–C |
| `GET /health` | none (not routed by API Gateway) | 200 | none | No dependency calls |
| `GET /ready` | none (not routed by API Gateway) | 200 | 503 | Database and embedding client |

## Appendix B: Settings (proposed names)

| Variable | Values | Notes |
|---|---|---|
| `INTERNAL_AUTH_MODE` | `iam` (default), `local` | `local` only in compose; never set by IaC |
| `INTERNAL_ALLOWED_CALLER_ARNS` | comma-separated role ARN prefixes | Unset rejects every call |
| `KNOWLEDGE_DB_MODE` | `data_api`, `postgres` | Required |
| `KNOWLEDGE_DB_HOST`, `_PORT`, `_NAME` | | `postgres` mode |
| `KNOWLEDGE_DB_RETRIEVE_USER`, `_PASSWORD`; `KNOWLEDGE_DB_INGEST_USER`, `_PASSWORD` | | `postgres` mode; never in tracked files |
| `KNOWLEDGE_DB_CLUSTER_ARN`, `KNOWLEDGE_DB_RETRIEVE_SECRET_ARN` | | `data_api` mode |
| `AWS_REGION` | region with the embedding model | Credentials from the default chain |
| `active_embedding_model` | KN-CHUNK Appendix A | Config, not env |

---

## Change Log

| Change | Reason |
|---|---|
| Moved how-to details (database provisioning, compose services, env file) out of KN-FAPI-07 and -09 into the build, test and deploy instructions | The spec states behavior only; those details change with the environment |
| New spec | Give Knowledge a FastAPI app, a container image and a local stack so retrieval and indexing can be run and tested on Docker |
