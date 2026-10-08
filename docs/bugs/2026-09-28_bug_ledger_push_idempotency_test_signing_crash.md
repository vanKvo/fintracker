# Bug name: Ledger push idempotency test failing on a SigV4 signing crash

## Problem
`TestReqDp03LedgerPushIdempotency::test_repeated_push_of_same_job_does_not_duplicate_ledger_calls` had been failing since SigV4 signing was added to the Ledger push. The log showed `'NoneType' object has no attribute 'split'` and the test's HTTP mock was never called. The same crash would hit a deployed LedgerPush Lambda whose `LEDGER_API_URL` wasn't set: the job would be recorded as "All transactions failed to push" instead of as a configuration error.

### Root cause:
1. **Signing crash.** `LEDGER_API_URL` is empty in tests, and the test didn't stub `sign_headers`. The request URL was therefore just `/api/v1/ledger/transactions/internal/bulk` with no host. botocore's SigV4 signer read a `None` Host header and crashed. `push_transactions_to_ledger` caught the error and reported every row as failed, so `requests.post` was never called. The other dispatcher tests had been given a signing stub in commit f7221a3; this one had not.
2. **Outdated assertion.** The test expected the pipeline to skip the second push (`call_count == 1`). That pipeline-side dedup was never built. Idempotency is enforced by the Ledger: its `(statement_id, row_fingerprint)` unique index skips duplicate rows and reports them as `skippedDuplicateCount`, which the pipeline counts as success. A retry has to re-send the rows so the Ledger can report them as duplicates.

### Code with bug:
```python
# tests/test_data_pipeline_spec_acceptance.py — no signer stub, no URL, wrong contract
with patch("src.data_dispatcher.service._requests.post", return_value=mock_resp) as mock_post:
    push_transactions_to_ledger("job-1", "user-1", "stmt-1", [tx])
    push_transactions_to_ledger("job-1", "user-1", "stmt-1", [tx])
assert mock_post.call_count == 1

# src/data_dispatcher/service.py — a host-less URL goes straight into signing
url = f"{_LEDGER_API_URL}/api/v1/ledger/transactions/internal/bulk"
```

## Solution
1. Rewrote the test to match the real contract. A retried push re-sends the same row fingerprints, and when the Ledger answers `skippedDuplicateCount=1`, the push counts as fully succeeded. The URL and signer are stubbed.
2. `push_transactions_to_ledger` now raises `LedgerNotConfiguredError` (reason `LEDGER_NOT_CONFIGURED`) before signing when `LEDGER_API_URL` is empty.
3. The LedgerPush handler records the job as FAILED with that reason code, not the raw message, and re-raises the error so Step Functions sees the failure.
4. The new `tests/conftest.py` gives every test a placeholder Ledger URL. Tests of the unconfigured case set it back to empty.

### Fixed Code
```python
# src/data_dispatcher/service.py
if not _LEDGER_API_URL:
    raise LedgerNotConfiguredError("LEDGER_API_URL is not set")

# src/data_dispatcher/handler.py
try:
    result = push_transactions_to_ledger(job_id, user_id, statement_id, transactions)
except PipelineError as e:
    logger.exception("Ledger push could not start", job_id=job_id, reason=e.reason)
    update_job_status(job_id, user_id, PipelineStatus.FAILED, error=e.reason)
    raise
```
