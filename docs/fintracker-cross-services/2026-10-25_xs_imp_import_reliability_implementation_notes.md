# Import reliability implementation notes (2026-10-25)

Covers DP-ING-09/10/11, XS-IMP-01…04, XS-DPCAT v3, LG-STMT-04 (pipeline pause) and -08, and DP-MAP-01…06.

Specs: [DP-ING](../fintracker-data-pipelines/specs/DP-ING-statement-ingestion-spec.md) · [XS-IMP](specs/XS-IMP-statement-import-contract-spec.md) · [XS-DPCAT](specs/XS-DPCAT-dp-ledger-categories-spec.md) · [LG-STMT](../fintracker-ledger-doc/specs/LG-STMT-statement-upload-spec.md) · [DP-MAP](../fintracker-data-pipelines/specs/DP-MAP-csv-column-mapping-spec.md). Deploy steps: [deploy_import_reliability.md](../instructions/deploy_import_reliability.md).

## Status

| ID | Status | What is left |
|---|---|---|
| DP-ING-09 | Implemented | UI: the column dialog now calls the cancel route (done); nothing else |
| DP-ING-10 | Implemented | — |
| DP-ING-11 | Implemented | Run the one-time page-image cleanup per environment |
| XS-IMP-01 | In progress | The Ledger stores and returns `reviewReason`. The Pending tab highlight ("Check the date and amount…") is UI work, not built |
| XS-IMP-02 | Implemented | The Statements tab showing the failure message (below) |
| XS-IMP-03 | Implemented | — |
| XS-IMP-04 | In progress | Reason codes only, as asked. The UI's catalog of messages and actions (Appendix A wording) is not built |
| XS-DPCAT-02 | In progress | Dead code waiting for your OK to delete; the Ledger's internal user-categories route is retired after the pipeline deploys |
| XS-DPCAT-03, -05, -06, -07 | Implemented | The Pending tab's "From your rule" (UI) |
| XS-DPCAT-04 | In progress | The Pending tab's "This category is no longer available" highlight (UI) |
| LG-STMT-04 | Implemented | — |
| LG-STMT-08 | Implemented | Correcting a wrong client hash (below) |
| DP-MAP-01…04, -06 | Implemented | — |
| DP-MAP-05 | Implemented (phase 1, notify) | Phase 2 (automatic) is "Later" in the spec |

## What was built

**Data pipeline**
- **One failure path (DP-ING-09).** Every Catch goes to a `RecordFailure` task (retried 3 times, then the execution fails visibly; a failed-executions alarm). It sets the job `FAILED` with a reason code and tells the Ledger. `PipelineFailed` and the separate `NoValidTransactions` state are gone. The Gatekeeper task has `TimeoutSeconds = 1800`; the 24 h execution timeout stays as a backstop. `POST /jobs/{jobId}/cancel` sends a task failure `CSV_COL_MAPPING_CANCELLED`. A confirmation after a timeout or cancel answers 409 with that reason code and resumes nothing.
- **Reason codes only (DP-ING-10).** `src/shared/reasons.py` holds the catalog. `update_job_status` refuses a reason outside it, so no handler can store exception text. The status API returns `{jobId, status, reason, failedCount, totalCount}` (plus `mappingProposal` and `duplicate` when they apply). A record written before this change shows `PIPELINE_ERROR` rather than its old text. A fully failed push now raises, so it goes through RecordFailure.
- **Failure notice (XS-IMP-02).** `report_import_failure` is SigV4-signed, retried 4 times with backoff, and logs `LEDGER_FAILURE_NOTICE_FAILED` (alarm) if it never gets through. A 404 or 409 from the Ledger is final, not retried.
- **No stored pages (DP-ING-11).** Pages go to Textract as bytes; a page over 10 MB is rendered again at 150/110/80/60 dpi; a screenshot over the limit is scaled down. The PDF is read once, not once per page. A page that fails 3 times logs `TEXTRACT_PAGE_FAILED` (statement id, page number, error code). The Extractor role lost `s3:PutObject`. One-time script: `scripts/one-time/2026-10-25_DP-ING-11_remove_textract_page_images.py`.
- **Codes, not ids (XS-DPCAT v3).** `CodeSuggester` replaces `CategoryResolver`: bank label through the bank-label table (now with an entry per SYSTEM code), then MerchantCategoryMap, then no code. The Normalizer calls nothing in the Ledger. Rows carry `category_code` and `review_reason`; `needs_review` is gone (the score stays). `scripts/check_category_codes.py` is the deploy check; the category-refresh alarm is removed and a `LEDGER_CATEGORY_DOWNGRADE` alarm added.
- **Duplicates (LG-STMT-04/08).** The Gatekeeper hashes the file itself and asks the Ledger; another statement with that hash ends the import as `SERVER_DUPLICATE_DETECTED` with the existing statement attached; a Ledger that can't answer stops the import (fail closed). New `DuplicateCheck` task (CSV only) fingerprints the parsed statement, asks the Ledger, and records the fingerprint only when there is no match. A match goes to an `AwaitDuplicateResolution` pause on `PENDING_DUPLICATE_RESOLUTION`.
- **Column mappings (DP-MAP).** Header signature, proposal order, personal mapping + vote on confirmation (after the execution resumes, best effort), `BANK_FORMAT_CHANGED`, change-share metric and alarm, promotion notice (SNS, once) with `scripts/promote_bank_mapping.py`, and the `UserAccountDeleted` handler. Baselines are seeded from `infrastructure/seed/bank_mapping_baseline.json`.

**Ledger**
- V31: `statements.failure_reason`; `transactions.category_source`, `category_issue`, `review_reason`.
- `POST /statements/internal/{id}/import-failure` (204 / 404 / 409 / 400), one conditional UPDATE.
- Failed statements with no transactions are ignored by the three duplicate lookups and removed by `initiateUpload` in its own transaction when the hash or month matches.
- The bulk route takes `categoryCode` and `reviewReason`; `categoryId` still works for the rollout. `IngestCatalog` picks rule → own category by normalized label → code → uncategorized, reading rules and categories once per package, and records the source. `CATEGORY_MISSING` is gone.
- Approving re-checks the category: a row whose category is gone stays PENDING with `categoryIssue = CATEGORY_UNAVAILABLE`; single approve answers 409 `category-unavailable`; bulk approve posts the rest and answers 200 `{notApproved, reason}` (204 when nothing was held back, as before).

**UI** (minimal): `reason` replaces `error`/`errorCode` in the job status; closing the column dialog calls the cancel route.

## Needs your decision

1. **Files to delete** (your rule: ask first). Nothing references them now:
   - `services/fintracker-data-pipeline/src/categories/` (`client.py`, `models.py`, `__init__.py`) and `tests/test_categories_client.py`: the runtime category copy XS-DPCAT-02 removes.
   - `src/gatekeeper/bank_mapping_baseline.py` and `src/gatekeeper/bank_mappings.json`: the old per-bank variant lists DP-MAP replaces. `tests/test_categorizer.py::TestReqDp09ChaseBaselineMapping` reads the JSON, so delete that class with it.
2. **Ledger user-categories route.** `GET /categories/internal/users/{userId}` has no caller after the pipeline deploys. XS-DPCAT-02 says to retire it then; I left it so the old pipeline keeps working during the rollout.
3. **Spec changes I'd propose** (I don't edit specs):
   - XS-IMP Appendix A: add `SERVER_DUPLICATE_DETECTED` and `DUPLICATE_RESOLUTION_TIMEOUT` (the likely-duplicate question expiring). LG-STMT's Shared Contract says `errorCode`; DP-ING-10 says `reason`, which I followed. Both names can't be right.
   - LG-STMT-04 describes the fingerprint two ways: "count, total, earliest and latest dates" (Requested Change) and "combine each row's fingerprint" (Constraints). The pipeline's row fingerprint includes the statement id and row position, so it can never match across statements. I used the first. A CSV and a PDF of one period also match this way.
   - DP-MAP Appendix A: two more item kinds, `STATS#{bank}` (daily confirmation counters, expire after 10 days; needed for the 7-day change share) and `BANK#{bank}` / `PROMOTION_NOTICE#…` (so the owner is told once). The proposal function takes `user_id`. The seed holds one entry per export format with its headers; I wrote the layouts from today's variants plus formats I know (Chase, Bank of America, Discover, US Bank); the rest are best effort and fall back to the nearest baseline.
   - DP-ING-09 says the Gatekeeper pause only. LG-STMT-04's pause has the same 30 minutes, so an unanswered duplicate question ends the same way.
   - XS-IMP-02 mentions `PARTIALLY_COMPLETED` as a statement status. The Ledger has only PROCESSING / COMPLETED / FAILED.
4. **LG-STMT-08, wrong client hash.** When the file's real hash matches nothing but the client sent another, the import continues (and `CLIENT_CONTENT_HASH_MISMATCH` is logged), but the statement keeps the client's hash, so a later upload of the same file is not recognized. The spec says no new Ledger endpoint. Say if you want one to correct it.
5. **A fully failed push now fails the execution** (it used to end the execution as succeeded with the job `FAILED`). That is what lets the Ledger be told. `PARTIALLY_COMPLETED` is unchanged.

## Found on the way
- The job status returned the column mapping proposal in snake_case while the dialog reads camelCase, so the dialog could not have opened against a real pipeline. Fixed in the status handler; see `docs/bugs/2026-10-25_bug_column_mapping_proposal_returned_in_snake_case.md`.

## Not verified
- Nothing ran against real AWS. The state machine is checked structurally (`terraform validate`, template tests), never executed. `terraform plan` was not run.
- The Ledger's ITs ran on Testcontainers Postgres; the pipeline's on moto and mocks; the UI's on Vitest. No browser run of the cancel path.
- The metric filters and alarms exist in Terraform only.
