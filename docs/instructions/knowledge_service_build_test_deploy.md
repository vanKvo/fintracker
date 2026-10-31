# Build, Test and Deploy the Knowledge Service

## Description
How to build, test and run the Knowledge service (`services/fintracker-knowledge`) on your machine against the shared PostgreSQL container in `infrastructure/local-postgres/` (port `localhost:5432`, also used by the Ledger), and what "deploy" means today. Specs: KN-FAPI (container), KN-VS (database), KN-SDOC (indexing), KN-RET (retrieval).

## Guideline

### Step 1: One-time prerequisites
1. **The shared PostgreSQL container running.** It is defined in `infrastructure/local-postgres/` (image `pgvector/pgvector:pg17`, so pgvector is included). Start it once with `docker compose up -d` from that folder, and check it is `healthy`:
   ```bash
   docker inspect -f '{{.State.Health.Status}}' fintracker-postgres
   ```
   Its first start creates the `fintracker` and `knowledge` databases and the Knowledge login roles. The Homebrew Postgres is not used for this (see `setup_postgresql16_homebrew.md`, which is stopped on this Mac).
2. Docker Desktop, Poetry and Python 3.12+. For real embeddings: AWS credentials in `~/.aws` with `bedrock:InvokeModel` on Titan Text Embeddings V2 in your region.

### Step 2: Configure the passwords
```bash
cd services/fintracker-knowledge
cp .env.local.example .env.local      # git-ignored; set the passwords
```
Set these in `.env.local` to the same values as `infrastructure/local-postgres/.env`:
- `KNOWLEDGE_DB_ADMIN_PASSWORD` and `FLYWAY_PASSWORD`: the container's `POSTGRES_PASSWORD` (the `postgres` superuser, used for migrations only).
- `KNOWLEDGE_DB_RETRIEVE_PASSWORD` and `KNOWLEDGE_DB_INGEST_PASSWORD`: the two `KNOWLEDGE_DB_*_PASSWORD` values the container used to create the login roles `kn_app_retrieve` and `kn_app_ingest`.

The roles are created only on the container's first start. If the values differ, change the roles' passwords inside the container or recreate its volume (this deletes its data). The app never connects as the admin: it uses the login roles, so Row-Level Security applies as in AWS.

`local/setup-local-database.sh` is not used with the container. It is only for a native Postgres on the host.

### Step 3: Build
```bash
poetry install                        # for tests and development
docker compose build                  # the image, context is the monorepo root
```

### Step 4: Test
```bash
poetry run pytest                     # needs Docker (Testcontainers starts its own pgvector); no AWS, no Bedrock
poetry run mypy src
KNOWLEDGE_IMAGE_TESTS=1 poetry run pytest tests/container    # builds the image: non-root, no secrets, /health, local-in-AWS refusal
```
Nine tests fail on the code as it was before this work (`test_runs.py` x4, `test_rls.py` x2, `test_vector_index.py` x3); see `docs/fintracker-knowledge/implementation_notes/2026-10-30_kn-fapi-implementation-notes.md`.

### Step 5: Run the stack locally
```bash
docker compose up -d                  # Flyway applies db/migration once, then the app starts on :8087
curl localhost:8087/health            # 200
curl localhost:8087/ready             # 200 when the database and AWS credentials are fine
```
The containers reach your Postgres as `host.docker.internal:5432`. Mounted read-only: `~/.aws`. Set `AWS_PROFILE` and `AWS_REGION` in your shell if you do not use the default.

Index the help docs and check retrieval (**these make real Bedrock calls and cost money**):
```bash
docker compose --profile index run --rm knowledge-index    # embeds docs/help/**/*.md; a second run skips unchanged files
poetry run python scripts/smoke.py                         # health, 401/403, retrieval, cross-user check
```
Without Docker, the index command also runs from the shell: `poetry run python -m src.system_docs.cli index --root ../../docs` (set the `KNOWLEDGE_DB_*` variables first). It refuses a database host that is not local.

To change a login password, edit `.env.local`, then `ALTER ROLE kn_app_retrieve PASSWORD '...'` (or drop the roles and re-run the setup script). To reset everything: `DROP DATABASE knowledge;` and re-run Steps 2 and 5.

### Step 6: Deploy
There is nothing to deploy to AWS yet: Knowledge has no infrastructure code (KN-FAPI Non-Goals). What exists and what a deployment needs:

| Piece | State |
|---|---|
| Image | Built from `services/fintracker-knowledge/Dockerfile`; the same code runs under Lambda through the `handler` in `src/main.py` |
| Migrations | Flyway, `db/migration/`, as a deploy step with an admin user, never at app start |
| Database roles | `kn_ingest`, `kn_retrieve`, `kn_delete` (NOLOGIN) come from migration V3; credentials are provisioned outside the schema |
| App settings | `AWS_REGION`, `KNOWLEDGE_DB_MODE=data_api`, `KNOWLEDGE_DB_CLUSTER_ARN`, `KNOWLEDGE_DB_RETRIEVE_SECRET_ARN`, `INTERNAL_ALLOWED_CALLER_ARNS`. **Never** set `INTERNAL_AUTH_MODE=local` or `AWS_ENDPOINT_URL` |
| Not built | Aurora (`knowledge` database), API Gateway `knowledge-internal` with IAM auth, S3 event and Step Functions for indexing, alarms, and the CI job that builds and pushes the image |

The next step is the infrastructure spec: Terraform under `services/fintracker-knowledge/infrastructure/terraform` (`dev` profile on pull requests, `prod` on a release tag, as for the other services), including the decision of Lambda container image versus a container service.
