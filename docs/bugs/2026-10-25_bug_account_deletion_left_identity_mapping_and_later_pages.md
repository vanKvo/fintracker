# Bug name: Account deletion left the identity mapping and any items past the first Query page

## Problem
Deleting an account (`DELETE /profile`) removed only the `USER#<id>` items on the first Query page (DynamoDB returns at most 1 MB per page) and never removed the `IDENTITY#<sub>` → `userId` mapping. A large account kept some records, and every deleted account kept its identity mapping, breaking app invariant 11 and the User Profile data-retention table.

### Root cause:
`delete_user` ran a single Query and ignored `LastEvaluatedKey`, and it was only given the `userId`, so it had no way to find the mapping.

### Code with bug:
```python
# app/identity/repository.py
resp = self._table.query(KeyConditionExpression=Key("PK").eq(pk))
items = resp.get("Items", [])
with self._table.batch_writer() as batch:
    for item in items:
        batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
```

## Solution
1. `delete_user(user_id, *, cognito_sub)` pages through the whole partition (keys only) and batch-deletes every item.
2. The `IDENTITY#<sub>` mapping is deleted last, so a retry after a partial failure can still resolve the user and finish. Deleting what's already gone is a no-op.
3. `IdentityService.delete_account` passes the `cognito_sub`.

### Fixed Code
```python
with self._table.batch_writer() as batch:
    while True:
        page = self._table.query(**query)
        for item in page.get("Items", []):
            batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
        if "LastEvaluatedKey" not in page:
            break
        query["ExclusiveStartKey"] = page["LastEvaluatedKey"]
self._table.delete_item(Key={"PK": f"IDENTITY#{cognito_sub}", "SK": "MAPPING"})
```
