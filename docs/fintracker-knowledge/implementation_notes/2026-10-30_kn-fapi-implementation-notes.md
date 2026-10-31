# KN-FAPI: Knowledge as a FastAPI container, implementation notes (2026-10-30)

Covers KN-FAPI-01 to -10 and the Knowledge part of LB-IHTTP-09. Spec Open Questions were answered as proposed: Data API kept for AWS with `postgres` mode behind the same interface (1), port 8087 (2). Only the Status column of the spec's Requirements Index was edited. How to run it: `docs/instructions/knowledge_service_build_test_deploy.md`.

## Status

| Requirement | Status | Evidence |
|---|---|---|
| KN-FAPI-01, -02, -03, -04, -05, -06, -10 | Implemented | Tests pass, including the Testcontainers ones (real pgvector, login roles, RLS) |
| KN-FAPI-07 | In progress | Login roles, RLS as the login role and compose hygiene are tested. **Not run:** the Flyway container, so "V1-V5 applied, re-run applies nothing" and "failed migration stops the app" are unproven |
| KN-FAPI-08 | In progress | The main-group dependencies were installed in a clean virtualenv and the app run with uvicorn: `/health` 200, `/ready` 503 with no database, docs 404, 401 with no caller, `local` plus an AWS marker refuses to start. **Not run:** `docker build`; the image tests in `tests/container/` are written, not executed |
| KN-FAPI-09 | In progress | Compose file validates (`docker compose config`); **not brought up**; no real Bedrock call was made (`scripts/smoke.py` and the `knowledge-index` job make them) |

Why 07-09 are unproven: Docker Desktop could not pull any base image (`python:3.12-slim`, `flyway/flyway:11`); the pulls hung.

## Decisions that differ from, or go beyond, the spec

| # | Spec text | What was built | Why |
|---|---|---|---|
| 1 | KN-FAPI-09: compose starts a `postgres` container | No Postgres container: a `knowledge` database in the host Postgres on :5432, created by `local/setup-local-database.sh`; services are prefixed `knowledge-` | Your request; you already run Postgres locally. Needs pgvector >= 0.8.0 installed there (it was not, when checked). Update the spec and KN-FAPI-07 text |
| 2 | Login roles from an init script on a new database | The same script, run once by the setup script; the roles are cluster-wide in the shared instance | They are named `kn_*`, so they do not clash with the Ledger |
| 3 | KN-FAPI-06: "refuses a database host that is not local" | Local = loopback, `host.docker.internal`, or a single-label name. **Private IPs are not local** | A private address can be an Aurora endpoint inside a VPC |
| 4 | KN-FAPI-02: `run_conformance` passes against the route | The three rows the matrix answers 200 are answered 400 `invalid_argument` (own_answers) | The harness sends no body; a caller that passes the checks reaches body parsing |
| 5 | KN-FAPI-05: no credentials gives 503 `embedding_unavailable` | The embedder no longer retries a missing credential | The retries (1+2+4 s) outlast the 3 s budget and the caller got a 504 |
| 6 | KN-FAPI-08: image builds in CI | Image tests run only with `KNOWLEDGE_IMAGE_TESTS=1`; **no CI job added** | The service repo's CI cannot see the monorepo root the build needs (shared library is a path dependency) |
| 7 | KN-FAPI-04 | `data_api` mode supports one parameter set per statement (enough for retrieval); the index command is `postgres` mode only | The command is local |
| 8 | - | A request body over 64 KB is a 400 without being parsed; JSON logging with the card mask is configured at process start | Production hardening |

## Pending-commit blocks

The two LB-IHTTP-09 blocks for Knowledge in `docs/git/pending_commits.txt` were folded into the KN-FAPI blocks: their files were rewritten for FastAPI. The root `docker-compose.yml` already had uncommitted changes before this work; its block commits those too.

## Existing failures, not caused by this work

Nine tests fail on code this work did not touch: `tests/system_docs/test_runs.py` (4, imports `Manifest` from `models`, which moved to `schemas`), `tests/vector_store/test_rls.py` (2) and `tests/vector_store/test_vector_index.py` (3), the last two still using the old row scope `mine`.
