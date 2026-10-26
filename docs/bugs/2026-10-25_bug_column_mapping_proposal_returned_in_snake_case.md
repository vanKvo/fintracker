# Bug name: The job status returned the column mapping proposal in snake_case, but the dialog reads camelCase

## Problem
When a CSV import paused for the column check, `GET /jobs/{jobId}` returned the proposal exactly as the pipeline stored it: `bank_id`, `csv_s3_key`, `unmapped_columns`, `is_known_bank`. The UI's `ColumnMappingProposal` and the column dialog read `bankId`, `csvS3Key`, `unmappedColumns` and `isKnownBank`. `data.proposal.unmappedColumns.length` is a read on `undefined`, and the confirmation request would have sent `bank_id: undefined`.

### Root cause:
`job_status_handler` copied `job["mapping_proposal"]` (the Pydantic model's `model_dump()`, snake_case) into the response. Nothing converted it, and no test covered the shape of the proposal in the status response; the UI tests used hand-written camelCase fixtures.

### Code with bug:
```python
# src/statement_ingestion/status_handler.py
if job.get("mapping_proposal"):
    body["mappingProposal"] = job["mapping_proposal"]
```

## Solution
The status handler converts the stored proposal to the camelCase shape the UI declares, naming each field once. The new DP-MAP fields (`headerSignature`, `source`, `baselineMapped`) go through the same map, so they reach the dialog too. The stored record is unchanged.

### Fixed Code
```python
_PROPOSAL_KEYS = {
    "bank_id": "bankId",
    "csv_s3_key": "csvS3Key",
    "mapped": "mapped",
    "unmapped_columns": "unmappedColumns",
    "is_known_bank": "isKnownBank",
    "header_signature": "headerSignature",
    "source": "source",
    "baseline_mapped": "baselineMapped",
}

def _proposal_for_ui(proposal: dict) -> dict:
    return {ui_key: proposal.get(key) for key, ui_key in _PROPOSAL_KEYS.items() if key in proposal}

# in job_status_handler
if job.get("mapping_proposal"):
    body["mappingProposal"] = _proposal_for_ui(job["mapping_proposal"])
```
