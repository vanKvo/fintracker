# Setting Up a Local S3 (LocalStack)

## Description
Explains how to run a local S3 emulator (via Docker) for the Ledger Service's presigned-upload flow (`S3PresignService`), so local dev never signs requests against a real AWS account/bucket — the same rationale as `setup_local_dynamodb.md`, applied to S3. AWS has no first-party local-only S3 (unlike `amazon/dynamodb-local`), so this uses LocalStack instead. No bucket exists until you create it — this guide covers both starting the container and creating the bucket.

## Guideline
Step 1: Start the local S3 (LocalStack) container
Run from the repo root:
```bash
docker compose up -d localstack
```
This starts `localstack/localstack` (pinned to the Community-edition tag `3.8` — `:latest` currently resolves to a build that requires a paid `LOCALSTACK_AUTH_TOKEN` and refuses to start without one) on `http://localhost:4566`, defined in the root `docker-compose.yml`. It persists data to a named Docker volume (`localstack-data`), so it survives container restarts and `docker compose down`.

Step 2: Verify the container is up
```bash
curl -s http://localhost:4566/_localstack/health
```
Look for `"s3": "available"` and `"edition": "community"` in the response.

Step 3: Create the bucket
The container starts empty — nothing provisions this bucket automatically. LocalStack doesn't validate credentials, but the AWS CLI/SDK still requires *something* present; `test`/`test` is LocalStack's documented placeholder convention (never used against real AWS):
```bash
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
  aws --endpoint-url=http://localhost:4566 --region us-east-1 \
  s3 mb s3://statement-bucket-dev
```
This must match `STATEMENTS_BUCKET_NAME` in `services/fintracker-ledger/.env` (host-run path) and in `services/fintracker-ledger/docker-compose.yml` (containerized path) — both are already set to `statement-bucket-dev`.

Step 4: Point the Ledger at the local bucket
`S3PresignService` reads `aws.s3.endpoint-override` (env var `AWS_S3_ENDPOINT_OVERRIDE`). Leaving it unset falls back to the real AWS default credentials provider chain — production behavior is unchanged.
- Running via `mvn spring-boot:run`: `.env` already sets `AWS_S3_ENDPOINT_OVERRIDE=http://localhost:4566`.
- Running via `docker compose up` (the ledger's own or the root aggregator): `docker-compose.yml` already sets `AWS_S3_ENDPOINT_OVERRIDE=http://host.docker.internal:4566` (the container reaches the published host port the same way it reaches the shared local Postgres).

Step 5: Verify the bucket is reachable
```bash
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
  aws --endpoint-url=http://localhost:4566 --region us-east-1 s3 ls
```

Step 6: Reset or tear down
```bash
docker compose restart localstack   # data persists — bucket and objects survive
docker compose down                 # stops and removes the container — data persists (volume kept)
docker compose down -v              # stops the container AND deletes the volume — wipes all data
```
Only `down -v` clears data. If you do wipe it, re-run Step 3 to recreate the bucket before using it again.
