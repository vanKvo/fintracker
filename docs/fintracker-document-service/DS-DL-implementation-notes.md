# DS-DL implementation notes (2026-10-26)

Code: `services/fintracker-document-service/`. Tests: 38 in `docs/fintracker-document-service/specs/DS-DL-document-download-tests.md`.

## Done

- **DS-DL-01, server side.** `GET /documents/{documentId}/download` returns `{url, expiresAt, fileName}`.
  - Owner check: the file is read under the caller's own partition (`USER#<userId>`), so another user's id and an unknown id both miss and give the same 404.
  - Link: presigned S3 GET on the clean bucket, 15 minutes at most (the service refuses a longer configured lifetime). The signed `response-*` overrides serve it with `Cache-Control: private, no-store, no-cache, must-revalidate` and `Content-Disposition: attachment`. The API response carries the same `Cache-Control`.
  - Audit: every request (granted, not found, not ready) writes a record and a structured log line. The link is signed first and returned only after the audit write succeeds, so a failed audit write gives a 503 and no link.
  - 404 for unknown or foreign ids, 409 `document_not_ready` for quarantine, failed scan, or a clean file with no storage key. Unknown scan statuses count as not cleared.
  - User identity comes only from `requestContext.authorizer.lambda.internal_user_id`.

## Not done

- **DS-DL-01 "Alt" criterion** (client reuses the fetched Blob in app state): a UI behavior. It belongs with the Statements tab change in DS-DL-02.
- **DS-DL-02** (retire the Ledger download, Statements tab uses `documentId`): the Ledger has no `documentId` and no uploads exist in the Document service yet. The spec says the Ledger route must keep working until then, so I left it alone.
- **Infrastructure**: no Terraform, API Gateway route or authorizer wiring yet. Needed:
  - Environment: `DOCUMENTS_TABLE_NAME`, `CLEAN_BUCKET_NAME`, optional `DOWNLOAD_LINK_TTL_SECONDS` (default and maximum 900).
  - IAM: `dynamodb:GetItem` and `PutItem` on the table, `s3:GetObject` on the clean bucket's keys (presigning needs it).
  - Handler: `src.main.download_handler`.
- **Audit stream**: the audit log line goes to the logger `fintracker.audit`. The shared `/fintracker/audit` helper from architecture 4.9 does not exist in code yet; route this logger to it when it does.

## Proposed spec changes (spec files are read-only for me)

1. DS-DL-01 should state the metadata contract the upload spec must fill: one record per file under `USER#<userId>` / `DOC#<documentId>` with `file_name`, `content_type`, `size_bytes`, `scan_status` (`PENDING`, `CLEAN`, `FAILED`) and `clean_key`, set only when the scan passes.
2. DS-DL-01 should say what happens when the audit record can't be written: the request fails with 503 and no link is issued.
3. DS-DL-01 Requirement: a file that is clean but has no storage key is treated like quarantine (409).
4. The Requirements Index status of DS-DL-01 is "In progress", not "Implemented", because its "Alt" criterion (UI) is open.
