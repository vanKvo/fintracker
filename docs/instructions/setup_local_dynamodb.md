# Setting Up a Local DynamoDB
## Description
Explains how to run a local DynamoDB (via Docker) for testing the User Profile Service and scripts like `scripts/dev_setup_user.py`, so you don't have to write test data into the real AWS account. No local DynamoDB table exists until you create it — this guide covers both starting the container and creating the table.

## Guideline
Step 1: Start the local DynamoDB container
Run from the repo root:
```bash
docker compose up -d dynamodb-local
```
This starts `amazon/dynamodb-local` on `http://localhost:8000`, defined in the root `docker-compose.yml`. It runs with `-inMemory`, so its data resets every time the container restarts — that's intentional for throwaway dev/test data (avoids a known permission bug where a mounted volume's ownership doesn't match the container's non-root user).

Step 2: Verify the container is up
```bash
curl -s http://localhost:8000
```
A response like `{"__type":"...MissingAuthenticationToken",...}` means the server is up and responding (it's just rejecting the unauthenticated request, which is expected).

Step 3: Create the table
The container starts empty — no CDK/Terraform provisions this table automatically. Run the idempotent creator script (safe to re-run):
```bash
cd scripts
export DYNAMODB_ENDPOINT_URL=http://localhost:8000
poetry run python create_local_dynamodb_table.py
```
This creates `FinTracker_UserProfile` with a `PK`/`SK` composite string primary key, on-demand billing, and TTL enabled on the `ttl` attribute — matching the schema `app/identity/repository.py`, `app/goals/repository.py`, and `app/websocket/repository.py` expect.

Step 4: Point a script at the local table
Any script or service that reads `DYNAMODB_ENDPOINT_URL` will use the local table instead of real AWS when it's set. For example:
```bash
export DYNAMODB_ENDPOINT_URL=http://localhost:8000 (or hard code the endpoint in the script)
poetry run python dev_setup_user.py --sub <cognito_sub> --email <email>
```
Leaving `DYNAMODB_ENDPOINT_URL` unset falls back to real AWS — production behavior is unchanged.

Step 5: Verify the data landed
```bash
aws dynamodb scan --table-name FinTracker_UserProfile --endpoint-url http://localhost:8000 --region us-east-1
```

Step 6: Reset or tear down
```bash
docker compose restart dynamodb-local   # wipes data (in-memory), keeps the container
docker compose down                     # stops and removes the container entirely
```
Since the table is in-memory, either command clears all data — re-run Step 3 to recreate the table before using it again.
