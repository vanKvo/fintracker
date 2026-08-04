# Bug name: `dev_setup_user.py` fails with ResourceNotFoundException — no DynamoDB table to write to, and no local dev option

## Problem

Running the documented usage from `scripts/dev_setup_user.py`:
```
python scripts/dev_setup_user.py --sub <cognito_sub> --email <email>
```
failed with:
```
Error: An error occurred (ResourceNotFoundException) when calling the TransactWriteItems operation: Requested resource not found.
```

### Root cause:

The script's `TransactWriteItems` call and item serialization were correct. The problem was that the DynamoDB table it targets, `FinTracker_UserProfile`, **did not exist anywhere in the AWS account**:

```
$ aws dynamodb list-tables --region us-east-1
{
    "TableNames": []
}
```
(confirmed empty across us-east-1, us-west-2, us-east-2, eu-west-1)

No CDK/Terraform in this repo defines this table (unlike the Ledger's Postgres schema, which has Flyway migrations) — it was never provisioned. Separately, `scripts/dev_setup_user.py` and the User Profile Service's own repositories (`app/identity/repository.py`, `app/goals/repository.py`, `app/websocket/repository.py`) all construct their boto3 DynamoDB client/resource with no `endpoint_url` override, so there was also no way to point any of this at a local DynamoDB instead of real AWS — meaning every local test run against this table would have required writing into shared cloud infrastructure, and CLAUDE.md's own documented "Full Local Stack" section (`docker-compose up -d # Start all local infrastructure (PostgreSQL, DynamoDB mock)`) describes a root `docker-compose.yml` that didn't actually exist in this repo.

### Code with bug:

`scripts/dev_setup_user.py` (before fix):
```python
# Initialize the low-level client directly
client = boto3.client("dynamodb")
```
No `endpoint_url`, and `FinTracker_UserProfile` didn't exist in the account this pointed at by default.

## Solution

Rather than provisioning `FinTracker_UserProfile` in shared AWS (unnecessary risk/cost for throwaway dev/test identities, and it still wouldn't give a reusable local dev workflow), added a local DynamoDB option end-to-end:

1. **Added root `docker-compose.yml`** running `amazon/dynamodb-local`, fulfilling what CLAUDE.md's "Full Local Stack" section already claimed existed:
   ```yaml
   services:
     dynamodb-local:
       image: amazon/dynamodb-local:latest
       container_name: fintracker-dynamodb-local
       ports:
         - "8000:8000"
       working_dir: /home/dynamodblocal
       command: "-jar DynamoDBLocal.jar -sharedDb -inMemory"
   ```
   First attempt used a named volume + `-dbPath` for persistence across restarts, but that hit a second, distinct bug: `amazon/dynamodb-local`'s container runs as a non-root user that doesn't have write permission to a fresh named Docker volume, so every real DynamoDB operation (not just table creation) hung/failed with `SQLiteException: [14] unable to open database file` while the container's internal retry loop endlessly reincarnated the connection. Switched to `-inMemory` — this is throwaway dev/test data, so "resets on container restart" is the correct semantics anyway, and it sidesteps the whole class of volume-ownership bugs.

2. **Added `scripts/create_local_dynamodb_table.py`** — an idempotent table creator, since dynamodb-local starts empty on every fresh container and there's still no IaC defining this table. Schema matches what `identity/repository.py`, `goals/repository.py`, and `websocket/repository.py` actually query: `PK`/`SK` composite string primary key, on-demand billing, TTL enabled on the `ttl` attribute (used by websocket connection items). No GSIs — every existing query pattern uses `PK` + `SK begins_with`.

3. **Updated `scripts/dev_setup_user.py`** to support a `DYNAMODB_ENDPOINT_URL` env var. Unset by default (unchanged real-AWS behavior); when set to `http://localhost:8000`, the client targets dynamodb-local with throwaway `"local"/"local"` credentials (dynamodb-local doesn't validate credentials, but boto3 still requires some value to be present):
   ```python
   client_kwargs = {}
   if ENDPOINT_URL:
       client_kwargs = dict(
           endpoint_url=ENDPOINT_URL,
           aws_access_key_id="local",
           aws_secret_access_key="local",
       )
   client = boto3.client("dynamodb", **client_kwargs)
   ```

### Fixed Code

New local dev workflow (also documented in the script's own docstring):
```bash
docker compose up -d dynamodb-local
export DYNAMODB_ENDPOINT_URL=http://localhost:8000
python scripts/create_local_dynamodb_table.py
python scripts/dev_setup_user.py --sub <cognito_sub> --email <email>
```

Verified end-to-end:
- `create_local_dynamodb_table.py` creates the table cleanly against dynamodb-local (TTL enabled, no errors).
- `dev_setup_user.py` writes the identity mapping + PROFILE + SETTINGS transaction successfully (confirmed via `aws dynamodb scan --endpoint-url http://localhost:8000`).
- Re-running `dev_setup_user.py` with the same `--sub` correctly hits the idempotent `TransactionCanceledException` → `"User already exists ... Nothing changed."` path, not a crash.

**Not yet addressed (separate, larger scope):** the actual `app/identity/repository.py`, `app/goals/repository.py`, and `app/websocket/repository.py` in the User Profile Service still construct `boto3.resource("dynamodb")` with no endpoint override, so running the *service itself* locally against dynamodb-local (not just this bootstrap script) would need the same treatment. Also, `FinTracker_UserProfile` still doesn't exist in real AWS at all — provisioning it there (via CDK/Terraform, matching how the Ledger's Postgres schema is managed) is still outstanding if/when a shared dev or staging environment is needed.
