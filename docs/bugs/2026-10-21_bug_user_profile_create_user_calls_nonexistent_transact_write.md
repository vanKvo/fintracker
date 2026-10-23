# Bug name: User registration always fails because create_user calls a DynamoDB method that does not exist

## Problem
`DynamoDBUserRepository.create_user` (User profile) could never write a new user. Every call ended in
`AttributeError: 'DynamoDB' object has no attribute 'transact_write'`, which the `@retry` decorator
retried three times and then re-raised as `RetryError`. The Cognito Post-Confirmation hook calls this
method, so a real sign-up could not create the identity mapping, profile or settings records.

It surfaced while writing the XS-CTX-01 repository tests against moto: no earlier test exercised the
method against a DynamoDB implementation (the unit tests mock the whole repository).

### Root cause:
The boto3 DynamoDB client has `transact_write_items(TransactItems=[...])`. The code called a
non-existent `transact_write(Items=[...])`. Nothing caught it because the method was only ever
reached through mocks, and local users are seeded by `scripts/dev_setup_user.py`, which bypasses it.

### Code with bug:
```python
self._table.meta.client.transact_write(Items=[
    {"Put": {...IDENTITY mapping...}},
    {"Put": {...PROFILE...}},
    {"Put": {...SETTINGS...}},
])
```

## Solution
Call the real API with its real parameter name. Covered by the moto tests in
`tests/integration/test_settings_repository.py`, which register users through `create_user`.

### Fixed Code
```python
self._table.meta.client.transact_write_items(TransactItems=[
    {"Put": {...IDENTITY mapping...}},
    {"Put": {...PROFILE...}},
    {"Put": {...SETTINGS...}},
])
```
