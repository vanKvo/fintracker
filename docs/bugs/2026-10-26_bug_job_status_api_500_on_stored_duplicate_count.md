# Bug name: The job status API answers 500 for every job that carries a duplicate

## Problem

`GET /jobs/{jobId}` returned 500 for any job whose record held a `duplicate` object, which is every job
in `PENDING_DUPLICATE_RESOLUTION` and every `FAILED` job with reason `SERVER_DUPLICATE_DETECTED`. The
upload dialog polls this route, so the user never got the duplicate prompt or the "already uploaded"
message; the poll just failed.

### Root cause

DynamoDB returns every stored number as a `Decimal`. The record keeps `existingTransactionCount` inside
`duplicate`, and the handler passed that dict to `json.dumps`, which cannot serialize a `Decimal`
(`TypeError`). The existing test passed because it replaced the database read with a plain dict of
Python ints, so no test ever read a record back from DynamoDB.

### Code with bug

`services/fintracker-data-pipeline/src/statement_ingestion/status_handler.py`

```python
def _response(status: int, body: dict) -> dict:
    content_type = "application/problem+json" if status >= 400 else "application/json"
    return {"statusCode": status, "headers": {"Content-Type": content_type}, "body": json.dumps(body)}
```

## Solution

Serialize `Decimal` as a JSON number in the response helper (an int when it has no fraction), so any
stored number reaches the client as a number. The LG-STMT Shared Contract already required numbers
("a JSON number, never a string"), so no contract changed.

A test now writes the job through `update_job_status` into a moto table and reads it back through the
handler, so the stored `Decimal` is what the handler sees.

### Fixed Code

```python
def _json_default(value: Any) -> Any:
    """DynamoDB returns every number as a Decimal; the contract wants JSON numbers (LG-STMT Shared Contract)."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _response(status: int, body: dict) -> dict:
    content_type = "application/problem+json" if status >= 400 else "application/json"
    return {"statusCode": status, "headers": {"Content-Type": content_type},
            "body": json.dumps(body, default=_json_default)}
```
