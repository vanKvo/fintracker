# Deploying import reliability (dev)

Covers DP-ING-09/10/11, XS-IMP-01…04, XS-DPCAT v3, LG-STMT-04/08 and DP-MAP. Deploy in this order. The Ledger goes first: it accepts both the old package (`categoryId`) and the new one (`categoryCode`), so the old pipeline keeps working until the new one is out.

## 1. Ledger

1. **Back up the dev database** (`pg_dump -Fc -d fintracker > before_import_reliability.dump`).
2. **Migrate.** V31 is schema-only: `statements.failure_reason`, and `transactions.category_source`, `category_issue`, `review_reason` with CHECK constraints.
3. **Allow the new callers.** Set `LEDGER_INTERNAL_ALLOWED_CALLER_ARNS` to the pipeline's `ledger_allowed_caller_arns` output after step 2.3 (S3 processor, Gatekeeper, DuplicateCheck, RecordFailure, LedgerPush). The Normalizer role no longer calls the Ledger and can come off the list.
4. **Smoke test** (allow-listed caller):
   - `POST /api/v1/ledger/statements/internal/{unknown id}/import-failure` with `{"reasonCode": "PIPELINE_ERROR"}` answers 404; with `{"reasonCode": "bad text"}` answers 400.
   - `POST /api/v1/ledger/transactions/internal/bulk` with one row carrying `"categoryCode": "groceries"` stores it under Groceries.

## 2. Data pipeline

1. Build the Lambda package (see the Terraform README).
2. **Check the codes** against the Ledger you just deployed: `INTERNAL_BASE_URL_LEDGER=<ledger url> python -m scripts.check_category_codes`. It must exit 0. Warnings (an active SYSTEM code with no bank-label entry) don't block.
3. In `terraform.tfvars`: nothing is required. Optional: `pause_timeout_seconds` (default 1800), `mapping_promotion_*` (3 users, 80%, 30 days), `alarm_sns_topic_arn`.
4. `terraform plan` should show: five new Lambdas (cancel, RecordFailure, DuplicateCheck, DuplicatePause, UserAccountDeleted), the cancel route, the new states in the state machine, the bank mapping baseline items, the SNS topic and the new alarms; it should also show the removed `CategoryRefreshFailed` filter and alarm, the Normalizer losing `INTERNAL_BASE_URL_LEDGER`, and the Extractor losing `s3:PutObject`.
5. `terraform apply`, then copy `ledger_allowed_caller_arns` into the Ledger (step 1.3) and restart it.
6. **Subscribe** to the `mapping_promotion_topic_arn` SNS topic to hear when users agree on a new column mapping. Promote with `python -m scripts.promote_bank_mapping --bank … --signature … --mapping-hash …` (the notice has the exact command).
7. **Remove the page images** earlier runs left, once per environment:
   ```bash
   python scripts/one-time/2026-10-25_DP-ING-11_remove_textract_page_images.py --bucket <statements bucket>          # dry run
   python scripts/one-time/2026-10-25_DP-ING-11_remove_textract_page_images.py --bucket <statements bucket> --apply
   ```
8. Once the new pipeline is live and no old one is running, retire the Ledger's `GET /categories/internal/users/{userId}` route (XS-DPCAT-02).

## 3. UI

Deploy the UI build: it reads `reason` instead of `error`/`errorCode` from the job status and calls `POST /jobs/{jobId}/cancel` when the column dialog is closed.

## 4. End-to-end check

1. **Cancel.** Upload a CSV, close the column dialog. Within a minute the job is `FAILED` / `CSV_COL_MAPPING_CANCELLED` and the Statements tab shows the statement `Failed`.
2. **Timeout.** Upload a CSV and leave the page. After 30 minutes the job is `FAILED` / `CSV_COL_MAPPING_CONFIRMATION_TIMEOUT`.
3. **Retry.** Upload the same CSV again after step 1 or 2: no duplicate prompt, one statement for the month.
4. **Late confirmation.** `POST /jobs/{id}/csv-col-mapping-confirmation` after step 1 answers 409 with `type` `CSV_COL_MAPPING_CANCELLED`.
5. **Duplicate.** Upload a CSV, approve it, then upload a different export of the same period. The job pauses on `PENDING_DUPLICATE_RESOLUTION` with the existing statement.
6. **Categories.** Upload a Chase CSV: rows labelled "Bills & Utilities" arrive as Utilities; a row for a merchant with a saved rule arrives under the user's category.
7. **Scan.** Upload a scanned PDF: no `…/page_N.jpg` objects appear in the bucket.
