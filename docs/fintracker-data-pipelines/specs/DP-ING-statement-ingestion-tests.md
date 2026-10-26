> **Tests for:** [DP-ING-statement-ingestion-spec.md](DP-ING-statement-ingestion-spec.md) · **Formerly:** `docs/fintracker-data-pipelines/data-pipeline-tests-01.md` (renamed 2026-10)

DP-ING-10's tests (reason codes and the status API shape) are listed in [XS-IMP-statement-import-contract-tests.md](../../fintracker-cross-services/specs/XS-IMP-statement-import-contract-tests.md). DP-ING-06's identity tests on the HTTP routes are listed in [XS-DPCAT-dp-ledger-categories-tests.md](../../fintracker-cross-services/specs/XS-DPCAT-dp-ledger-categories-tests.md).

=========================
F2P TESTS (51)
=========================

--- TestFormatDetection (1, xfail) ---
1. a binary image is not misclassified as CSV: DP-ING-01 A. "Format Detection" — `csv.Sniffer()` false-positives on some binary content. A genuine bug found while writing this suite, not a designed business rule, so it's marked `xfail` rather than a hard failure.

--- TestReqDp01BankSpecificColumnMapping (1) ---
2. a bank exporting non-canonical headers ("Transaction Date"/"Description"/"Debit") gets a proposal that maps them to the canonical fields: DP-ING-01 A. "CSV Bank-Specific Column Mapping", asserted through `propose_column_mapping`.

--- TestReqDp01CsvColMappingConfirmationDialog (3) ---
3. `PipelineStatus` has a `PENDING_CSV_COL_MAPPING_CONFIRMATION` value: DP-ING-01 A. "User Mapping Confirmation Gate" — a CSV job must be able to pause and wait on the user's mapping dialog.
4. `propose_column_mapping` exists on the Gatekeeper service: DP-ING-01 A. "Mapping Transparency".
5. `confirm_column_mapping` exists on the Gatekeeper service: DP-ING-01 E. Interface Details.

--- TestReqDp01TieredPdfExtraction (2) ---
6. `extract_from_text_layer` exists on the Extractor service: DP-ING-01 A. "Text-Layer Fast Path (Tier 1)".
7. `extract_transactions` attempts the text layer before Textract: DP-ING-01 A. "Textract Fallback (Tier 2)".

--- TestReqDp01ConfidenceScoring (1) ---
8. a `NormalizedTransaction` carries a `confidence` field: DP-ING-01 A. "Confidence Scoring".

--- TestReqDp02ParallelPageExtraction (1) ---
9. page extraction uses a thread pool: DP-ING-02 A. "Parallel Page Extraction".

--- TestReqDp02BatchedLedgerPush (1) ---
10. the Ledger push uses the bulk endpoint: DP-ING-02 A. "Batched Ledger Push".

--- TestReqDp03LedgerPushIdempotency (2) ---
11. a retried push resends the same row fingerprints and counts the Ledger's duplicates as success: DP-ING-03 idempotency.
12. a missing Ledger URL is a configuration error, not a signing crash: DP-ING-03.

--- TestReqDp05TenantIdentityVerification (2) ---
13. `get_verified_statement_owner` exists on the Ledger client: DP-ING-05 A. "Verify Tenant Identity at Ingestion" — `user_id`/`account_id` come from the Ledger's record, not S3 metadata.
14. the S3 processor does not read `user-id` or `account-id` off object metadata: DP-ING-05.

--- TestStateMachineDefinition (7) ---
15. the Gatekeeper task times out after 30 minutes: DP-ING-09 Happy.
16. the 24-hour execution timeout stays as a backstop: DP-ING-09.
17. every Catch routes to RecordFailure: DP-ING-09.
18. a timeout is caught, not only task failures: DP-ING-09 Happy.
19. RecordFailure is retried three times, then the execution fails: DP-ING-09 Fail.
20. the old state that recorded nothing is gone: DP-ING-09.
21. RecordFailure receives only what it needs: DP-ING-09 / DP-ING-08.

--- TestCancel (8) ---
22. the owner cancels a paused column check: DP-ING-09 Happy.
23. another user's job answers 404 and nothing is cancelled: DP-ING-09 Alt / invariant 5.
24. a job that is not paused answers 409: DP-ING-09 Alt.
25. a job already failed answers 409 with its reason code: DP-ING-09 Alt.
26. a missing job answers 404: DP-ING-09.
27. no authorizer identity answers 401: DP-ING-09 / DP-ING-06.
28. a task that already ended answers 409, not 500: DP-ING-09 Alt.
29. the route is registered behind the identity authorizer: DP-ING-09 / DP-ING-06.

--- TestLateConfirmation (3) ---
30. a confirmation after a cancel answers 409 with the reason and resumes nothing: DP-ING-09 Alt.
31. a confirmation after the timeout answers 409 with the timeout reason: DP-ING-09 Alt.
32. a confirmation that races the timeout answers 409 and does not mark the job passed: DP-ING-09 Alt.

--- TestPageIsSentAsBytes (2) ---
33. a rendered PDF page goes to Textract as bytes and nothing is written: DP-ING-11 Happy.
34. a screenshot is sent as bytes too: DP-ING-11.

--- TestOversizedPage (3) ---
35. a page over the synchronous limit is rendered again at lower resolution: DP-ING-11.
36. a page that never fits is failed, not sent: DP-ING-11.
37. a large screenshot is shrunk before sending: DP-ING-11.

--- TestFailedPage (2) ---
38. a page failing three times logs the statement, page and error code only: DP-ING-11 Alt.
39. a non-AWS failure is logged by its exception type: DP-ING-11 Alt / DP-ING-08.

--- TestStatementImport (3) ---
40. a scanned 5-page PDF imports with no new objects in the bucket: DP-ING-11 Happy.
41. the PDF is downloaded once, not once per page: DP-ING-11.
42. a page that fails three times leaves one log line and no object, and the rest continue: DP-ING-11 Alt.

--- TestRemoveTextractPageImages (6) ---
43. a dry run lists the page images and deletes nothing: DP-ING-11.
44. applying removes every version of every page image, so no version remains under any statement prefix: DP-ING-11 Alt. *(Not built: the script deletes without version ids, so the versioned bucket keeps every image.)*
45. a page image whose original file was already deleted is removed too: DP-ING-11. *(Not built: replaces "a page-looking object with no original beside it is left alone", which kept exactly these images.)*
46. a user's own upload named `page_1.jpg` directly under a statement prefix is never removed: DP-ING-11.
47. it is safe to run twice: DP-ING-11.
48. more than a thousand page images are deleted in batches: DP-ING-11.

--- upload-statement-modal.spec.ts (2) ---
49. closing the column dialog without confirming cancels the paused import: DP-ING-09 Happy.
50. a failed cancel is not surfaced: the import times out on its own: DP-ING-09.

--- statement.service.spec.ts (1) ---
51. cancelCsvColMapping posts to the cancel route with no body: DP-ING-09.

Not automated (excluded from both counts):
- DP-ING-07 "Least-Privilege IAM Policies" — the IAM statements are in Terraform (`infrastructure/terraform/environments/dev/main.tf`), not exercised by the Python suite. Needs a `terraform plan` policy check or manual review. Kept visible as the `pytest.mark.skip` stub `test_iam_policies_are_least_privilege` in `test_data_pipeline_spec_acceptance.py`.


=========================
P2P TESTS (48)
=========================

--- TestFormatDetection (7) ---
1. PDF magic bytes are recognized: DP-ING-01 A. "Format Detection".
2. non-PDF bytes are not recognized as PDF: DP-ING-01 A. "Format Detection".
3. a `.csv` extension is detected as CSV: DP-ING-01 A. "Format Detection".
4. CSV-shaped content is sniffed as CSV without a `.csv` extension: DP-ING-01 A. "Format Detection".
5. `_detect_format` resolves a `.pdf` file to PDF: DP-ING-01 A. "Format Detection" three-way branch.
6. `_detect_format` resolves a `.csv` file to CSV: DP-ING-01 A. "Format Detection" three-way branch.
7. `_detect_format` falls back to IMAGE for a non-PDF, non-CSV file: DP-ING-01 A. "Format Detection" three-way branch.

--- TestCsvStructuralValidation (4) ---
8. a header row with at least one data row passes: DP-ING-01 A. "CSV Validity Gate".
9. arbitrary bank-specific headers are still structurally valid (the mapping decides the fields): DP-ING-01 A. "CSV Validity Gate".
10. a single-column file is rejected: DP-ING-01 A. "CSV Validity Gate".
11. a CSV with headers but no data rows is rejected: DP-ING-01 A. "CSV Validity Gate" — "at least one data row."

--- TestProposeColumnMapping (3) ---
12. default names match for an unknown bank: DP-ING-01 F. unknown bank format.
13. unmatched headers are reported unmapped: DP-ING-01 A. "Mapping Transparency".
14. a CSV with duplicate header names is rejected: DP-ING-01 A. "CSV Validity Gate".

--- TestConfirmColumnMapping (3) ---
15. confirming resumes the paused execution: DP-ING-01 A. "User Mapping Confirmation Gate".
16. a mapping missing a canonical field is rejected: DP-ING-01 A. "CSV Validity Gate".
17. a job with no pending confirmation raises the timeout error: DP-ING-09 Alt.

--- TestRunGatekeeperCsv (3) ---
18. a valid CSV requires column mapping confirmation: DP-ING-01 A. "User Mapping Confirmation Gate".
19. a CSV without a bank id is rejected: DP-ING-01 A. "CSV Bank-Specific Column Mapping".
20. a structurally invalid CSV is rejected by the Gatekeeper: DP-ING-01 A. "CSV Validity Gate".

--- TestRunGatekeeperResourceCaps (2) ---
21. a file over the size cap is rejected with `FileTooLargeError` before further processing: DP-ING-04.
22. an unreadable image is rejected with `UnsupportedFormatError`: DP-ING-01 F. `UNSUPPORTED_FORMAT`.

--- TestParseCsvTransactions (4) ---
23. a valid CSV produces the expected transactions: DP-ING-01 A. "CSV Transaction Parsing".
24. one bad row is skipped without failing the file: DP-ING-01 F. `CSV_ROW_PARSE_ERROR`.
25. a confirmed mapping missing a canonical field raises `InvalidCsvFormatError`: DP-ING-01 A. "CSV Transaction Parsing".
26. a confirmed mapping naming a column the file doesn't have raises `InvalidCsvFormatError`: DP-ING-01 A. "CSV Transaction Parsing".

--- TestIngestionHandlerCsvRouting (3) ---
27. a CSV job produces non-zero transactions through the handler: DP-ING-01 A. "CSV Transaction Parsing".
28. a CSV job never calls Textract: DP-ING-01 D. Pipeline Stage Mapping.
29. a malformed Gatekeeper output fails the job instead of producing zero transactions: DP-ING-03.

--- TestIngestionHandlerErrorHandling (1) ---
30. an extraction failure records job status FAILED and re-raises: DP-ING-03 / DP-ING-09.

--- TestLedgerPushJobStatus (3) ---
31. a fully successful push marks the job COMPLETED: DP-ING-02 F.
32. a partially successful push marks the job PARTIALLY_COMPLETED, not COMPLETED: DP-ING-02 F. `PARTIAL_LEDGER_PUSH_FAILURE`.
33. a fully failed push marks the job FAILED, not COMPLETED: DP-ING-02 F / DP-ING-09.

--- TestLedgerNotConfigured (1) ---
34. a missing Ledger URL marks the job FAILED with a reason code: DP-ING-10.

--- TestGatekeeperHandlerStatus (3) ---
35. a PDF marks the job GATEKEEPER_PASSED and resolves the task: DP-ING-01.
36. a CSV needing confirmation marks the job pending and does not resolve the task: DP-ING-01 A. "User Mapping Confirmation Gate".
37. a Gatekeeper exception records job status FAILED with its reason code, not the message, and re-raises: DP-ING-09 / DP-ING-10.

--- TestTenantScopingHeader (2) ---
38. the `X-Internal-User-Id` header is forwarded on every Ledger push: DP-ING-06.
39. the push posts to the bulk endpoint with the statement id: DP-ING-06 / DP-ING-02.

--- TestPiiLogHygiene (1) ---
40. a failed push does not log the raw transaction body (merchant, amount, account number): DP-ING-08.

--- TestCleanMerchant (4) ---
41. a trailing `#12345` reference is stripped: normalizer merchant-cleaning baseline.
42. a `*` + digits reference is stripped: normalizer merchant-cleaning baseline.
43. merchant names are lowercased: normalizer merchant-cleaning baseline.
44. repeated internal whitespace collapses to one space: normalizer merchant-cleaning baseline.

--- TestParseAmount (3) ---
45. a standard `$1,234.56` string parses to `Decimal("1234.56")`: normalizer amount-parsing baseline.
46. a parenthesized amount parses as a negative (credit): normalizer amount-parsing baseline.
47. a non-numeric amount returns `None` rather than raising: normalizer amount-parsing baseline.

--- TestNormalizeAndCategorize (2) ---
48. a merchant-map match gives the row its suggested code, and an unparsable amount is skipped rather than included with a garbage value: normalizer baseline (XS-DPCAT-03), two tests.
