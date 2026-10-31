# Plan: Run AI Assistant and Knowledge Locally (RAG Pipeline and AI Chat)

Date: 2026-10-30 · Owner: Van Vo · Status: Proposed
Scope: AI assistant and Knowledge only. Ledger, Analytics, User Profile, Document service and Data pipeline come later.

## 1. Goal

On a laptop, with `docker compose up`:

1. Index the help and system documents into Knowledge (pgvector) using real Bedrock embeddings.
2. Ask the AI assistant questions through `POST /chat/messages` and see answers grounded in those documents, streamed as NDJSON.
3. Run the retrieval golden questions and see pass/fail.

## 2. What the other services are for local

AI chat also calls Ledger and Analytics (tools) and User Profile (goals, settings). Locally those are **not started**. The chat tools that depend on them return a clear "unavailable" tool error, and the test script only asks questions that need `retrieve_help_docs`. If you want financial tools later, point `INTERNAL_BASE_URL_*` at the real services and nothing else changes (see the internal-call standard plan).

## 3. Findings that shape the plan

| # | Finding | Consequence |
|---|---|---|
| 1 | **Knowledge has no runnable entry point.** `retrieval/router.py`, services and repositories exist, but nothing builds the DB engine or wires them together, and there is no ASGI app. | Phase 2 builds a composition root and a FastAPI app. |
| 2 | Knowledge's `DocSource` is a Protocol (`source.py`); the real source reads from S3. | Add `LocalFileSource` reading a mounted folder. |
| 3 | RLS is `FORCE`d with `NOLOGIN` roles `kn_ingest`, `kn_retrieve`, `kn_delete` (migrations V3/V4). Superusers bypass RLS. | Run migrations as the admin user, but connect the app as **non-superuser login roles** that are members of those roles. Otherwise local passes and prod fails. |
| 4 | Embeddings are Titan v2, 1024 dimensions, via Bedrock. | Real AWS credentials with `bedrock:InvokeModel` on Titan are required for indexing and retrieval. No offline substitute, since vectors from a stub would not reflect meaning and would make retrieval tests meaningless. |
| 5 | AI assistant chat uses a Bedrock LLM. Chat limits come **only from SSM** (`chat/config.py`). | Locally: run LocalStack SSM, or add a local-only `CHAT_CONFIG_JSON` override (recommended; see 5.3). |
| 6 | AI assistant state is DynamoDB single table: `USER#<id>` with `SUMMARY#`, `QUOTA#`, `CHAT#`, `TOKENS#` sort keys, and `APP` with `SPEND#<day>`; TTL `expires_at`. | DynamoDB Local plus a table-creation script. |
| 7 | AI assistant asserts config at startup (`src/main.py`) and requires `AUDIT_HASH_SALT` outside local. | Set `AUDIT_HASH_SALT` to any string locally. |
| 8 | Public identity locally: `APP_ENV=local` and `LOCAL_DEV_USER_ID`, guarded by `assert_local_identity_safe()`. | Use as is; later moves to the shared library. |
| 9 | The AI assistant reaches Knowledge's retrieval through the internal API (SigV4 in prod). | Needs the internal-call standard's `local` mode, or an interim `APP_ENV=local` signer skip. Phase 3 below. |

## 4. Local topology

```
              host (your AWS creds, read-only mount of ~/.aws)
                          │ Bedrock (Titan embed, LLM)
 ┌────────────────────────┼─────────────────────────────────┐
 │ docker compose         ▼                                  │
 │  ai-assistant :8001 ──► knowledge-api :8002 ──► postgres (pgvector) :5432
 │       │                      ▲                     ▲
 │       ▼                      │                     │
 │  dynamodb-local :8000   knowledge-index (job)   flyway (migrate, exits)
 └───────────────────────────────────────────────────────────────┘
        curl / test script ──► ai-assistant :8001  (NDJSON)
```

## 5. Phases

### Phase 1: Local data stores (no app changes)

- `local/docker-compose.yml` services: `postgres` (image `pgvector/pgvector:pg16`, volume, healthcheck), `flyway` (runs Knowledge `db/migration`, depends on healthy postgres, exits), `dynamodb-local` (in-memory off, volume on).
- `local/init/10-roles.sql`: create login roles `kn_app_ingest`, `kn_app_retrieve`, `kn_app_delete` with passwords from `.env.local`, each `GRANT`ed the matching `NOLOGIN` role, no superuser, no `BYPASSRLS`.
- `local/scripts/create_chat_table.py`: creates the AI assistant table with the same key schema and TTL attribute as the Terraform definition. A test compares the two so they cannot drift.
- Done when: `docker compose up postgres flyway dynamodb-local` ends with migrations applied, and `psql` as `kn_app_retrieve` sees no rows without `app.user_id` set (RLS works).

### Phase 2: Knowledge runnable (largest piece)

1. `knowledge/app/container.py`: builds engines per role (`kn_app_ingest`, `kn_app_retrieve`, `kn_app_delete`) from `KNOWLEDGE_DB_*` variables, the embedding service (Bedrock client, region from env), and the services. Fails startup with the variable's name if one is missing.
2. `knowledge/app/main.py`: FastAPI app exposing the existing retrieval router, `/health`, and the internal caller dependency. Mangum handler included so it still deploys as a Lambda later.
3. `knowledge/app/sources/local_file_source.py`: `LocalFileSource(root)` implementing `DocSource` for `*.md` under a mounted folder; document ID from relative path, version from content hash so re-indexing unchanged files is a no-op.
4. `knowledge/app/cli.py`: `python -m app.cli index --source local --path /docs` (and `reindex`, `delete`) calling `system_docs/service.py` and `publisher.py`. Prints counts: documents seen, chunks written, skipped unchanged, failures.
5. Compose: `knowledge-api` and a `knowledge-index` one-shot job; `docs/` mounted read-only. Default documents: the product help content used by chat (the golden-question corpus). **Open:** where does that corpus live in the repo? If it exists only in S3, export a copy into `local/sample_docs/` first.
6. Tests: unit tests for `LocalFileSource` and the composition root with fakes; one integration test against the compose Postgres marked `local`, proving RLS (user B cannot retrieve user A's private chunks; system docs are visible to both).

Done when: after `index`, `POST /retrieval/search` (path per `router.py`) returns ranked chunks with scores for a sample question, and the CLI re-run reports 0 changed.

### Phase 3: Internal auth for the AI-assistant-to-Knowledge call

Preferred: do Phases 1 and 2 of the internal-call standard first (library plus adopt in the AI assistant), then set `INTERNAL_AUTH_MODE=local` in compose. Knowledge adopts the inbound check in the same change.
Interim, if the library is not ready: in the AI assistant's Knowledge client, skip SigV4 when `APP_ENV=local` and send `X-Internal-Caller-Arn`; in Knowledge's new app accept it only when `INTERNAL_AUTH_MODE=local`. Remove when the library lands. Keep the interim as small as possible; it is throwaway.

### Phase 4: AI assistant in compose

Environment (`local/.env.ai`):

| Variable | Value |
|---|---|
| `APP_ENV` | `local` |
| `LOCAL_DEV_USER_ID` | a fixed UUID |
| `LOCAL_DEV_TIMEZONE`, `LOCAL_DEV_CURRENCY`, `LOCAL_DEV_TIER` | e.g. `America/New_York`, `USD`, `free` |
| `AWS_ENDPOINT_URL_DYNAMODB` | `http://dynamodb-local:8000` |
| `AWS_REGION`, credentials | from the host profile mount; **do not** set `AWS_ENDPOINT_URL` globally, or Bedrock calls go to DynamoDB Local |
| `AUDIT_HASH_SALT` | any string |
| `CHAT_CONFIG_JSON` | local override for limits (5.3) |
| `KNOWLEDGE_BASE_URL` | `http://knowledge-api:8002` (exact variable per `tools/clients.py`) |

5.3 Chat limits: add `CHAT_CONFIG_JSON` support in `chat/config.py`, **honored only when `APP_ENV=local`** (startup error otherwise, same pattern as `assert_local_identity_safe`). Alternative: LocalStack with `AWS_ENDPOINT_URL_SSM` and a seed script; heavier and one more container for one config blob.

Tools that call Ledger, Analytics and User Profile: fail soft as described in section 2. If they currently raise unhandled errors, wrap them to return a tool error so the model can say it cannot reach that data. Check `chat/tools.py`.

Done when: `curl -N -X POST localhost:8001/chat/messages -d '{"message":"How do I upload a statement?"}'` streams NDJSON, the answer cites retrieved help content, and a second request in the same conversation sees the first (DynamoDB history).

### Phase 5: Test the RAG pipeline and chat

`local/scripts/rag_smoke.py` runs in three layers, each reporting pass/fail:

1. **Index:** document count and chunk count match the CLI output; re-index is idempotent.
2. **Retrieval (no LLM):** for each golden question, call Knowledge search; expected source document appears in the top *k* (k=3 as a start). Reports hit rate and the rank of each expected document.
3. **Chat (LLM):** for each golden question, call chat; assert the NDJSON stream is well-formed and ends with a completion event, the answer is non-empty, and the retrieval tool was called (visible in the stream or logs). Answer quality is reviewed by reading the printed output, not auto-graded at first.

Also check: quota and token counters appear in DynamoDB Local after chats (`QUOTA#`, `TOKENS#`), and the `SPEND#<day>` item moves.

Golden questions: reuse the set already defined for retrieval in the Knowledge specs if present; otherwise start with 10 written from the help corpus. **Open:** locate the existing set.

## 6. Prerequisites and cost

- Docker with Compose v2, about 4 GB free RAM.
- AWS credentials with Bedrock access in a region that has Titan Text Embeddings v2 and the chat model; model access enabled in the console.
- Each run costs real Bedrock tokens. Indexing the help corpus once is small; the smoke test is a few dozen calls. Chat limits in `CHAT_CONFIG_JSON` should be low so a loop cannot run up spend.
- Never commit `.env.local`; add it to `.gitignore`.

## 7. Risks

| Risk | Mitigation |
|---|---|
| RLS passes locally only because of a superuser | Non-superuser login roles in Phase 1, plus the RLS integration test |
| `AWS_ENDPOINT_URL` leaking onto Bedrock | Only service-specific endpoint variables; compose test calls Bedrock |
| Local table drifts from Terraform | Test that compares key schema and TTL attribute |
| Local-only overrides reachable in AWS | Each override raises at startup unless `APP_ENV=local`; Terraform infra tests assert none are set |
| Golden questions pass on retrieval but chat answers poorly | Layers 2 and 3 are reported separately so failures are attributable |

## 8. Order and effort

1. Phase 1 (data stores): small.
2. Phase 2 (Knowledge app, CLI, local source): the bulk of the work.
3. Phase 3 (auth), in parallel with Phase 2 if the library is ready.
4. Phase 4 (AI assistant compose, config override): small to medium.
5. Phase 5 (smoke script): small.

## 9. Open questions

1. Where is the help and system-document corpus, and is it in the repo?
2. Where is the existing golden-question set?
3. Exact search route and the Knowledge client variable names (confirm against `retrieval/router.py` and `tools/clients.py` before Phase 2; this plan used the names from the earlier read).
4. Should the compose file live at the repo root (`local/`) or per service? Proposed: repo root, since it spans two services.
