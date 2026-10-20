=========================
F2P TESTS (13)
=========================

--- TestFormatDetection (1, xfail) ---
1. a binary image is not misclassified as CSV: REQ-DP-01 A. "Format Detection" — `csv.Sniffer()` false-positives on some binary content. A genuine bug found while writing this suite, not a designed business rule, so it's marked `xfail` rather than a hard failure.

--- TestReqDp01BankSpecificColumnMapping (1) ---
2. a bank exporting non-canonical headers ("Transaction Date"/"Description"/"Debit") is accepted: REQ-DP-01 A. "CSV Bank-Specific Column Mapping" — known per-bank variants should map to the canonical fields instead of requiring the literal `date`/`merchant`/`amount` headers.

--- TestReqDp01MappingConfirmationDialog (3) ---
3. `PipelineStatus` has a `PENDING_MAPPING_CONFIRMATION` value: REQ-DP-01 A. "User Mapping Confirmation Gate" — a CSV job must be able to pause and wait on the user's mapping dialog.
4. `propose_column_mapping` exists on the Gatekeeper service: REQ-DP-01 A. "Mapping Transparency" — every found column, mapped or not, must be surfaced to the user before processing continues.
5. `confirm_column_mapping` exists on the Gatekeeper service: REQ-DP-01 E. Interface Details — persists the user's confirmed/corrected mapping and resumes the paused execution.

--- TestReqDp01TieredPdfExtraction (2) ---
6. a text-layer extraction function exists on the Extractor service: REQ-DP-01 A. "Text-Layer Fast Path (Tier 1)" — a digitally-generated PDF should be read directly, without OCR.
7. `extract_transactions` attempts the text layer before Textract: REQ-DP-01 A. "Textract Fallback (Tier 2)" — Tier 2 should only run when Tier 1 can't classify a page; today Textract runs unconditionally for every PDF/Image page.

--- TestReqDp01ConfidenceScoring (1) ---
8. a `NormalizedTransaction` carries a `confidence` field: REQ-DP-01 A. "Confidence Scoring" — every PDF/Image row needs a confidence signal so low-confidence rows can be routed to manual review instead of auto-posted.

--- TestReqDp02ParallelProcessing (2) ---
9. page extraction uses a concurrency primitive: REQ-DP-02 A. "Parallel Page Extraction" — pages are still processed one at a time in a sequential loop.
10. the Ledger push uses a concurrency primitive: REQ-DP-02 A. "Parallel/Batched Ledger Push" — transactions are still pushed one HTTP call at a time.

--- TestReqDp03LedgerPushIdempotency (1) ---
11. re-running the same job does not duplicate Ledger calls: REQ-DP-03 A. "Failure Handling and Idempotency" — a retried Step Functions task or a duplicate S3 event must not re-push transactions that already succeeded.

--- TestReqDp05TenantIdentityVerification (2) ---
12. a `verify_statement_owner` lookup exists on the orchestrator: REQ-DP-05 A. "Verify Tenant Identity at Ingestion" — `user_id`/`account_id` must be resolved from a server-side record, not trusted from S3 metadata directly.
13. the S3 processor does not read `user-id` straight off object metadata: REQ-DP-05 A. — same rule, asserted against the actual `s3_processor_handler` source; today it reads the tag unconditionally.

Not automated (excluded from both counts):
- REQ-DP-07 "Least-Privilege IAM Policies" — `pipeline_stack.py` IAM statements are AWS CDK infrastructure, not exercised by this Python unit-test suite. Needs a `cdk synth` + `cdk.assertions.Template` snapshot test in the infrastructure package, or manual review. Represented as a `pytest.mark.skip` stub (`test_iam_policies_are_least_privilege`) in `test_not_yet_implemented.py` so the gap stays visible in test output.


=========================
P2P TESTS (46)
=========================

--- TestFormatDetection (7) ---
1. PDF magic bytes are recognized: REQ-DP-01 A. "Format Detection".
2. non-PDF bytes are not recognized as PDF: REQ-DP-01 A. "Format Detection".
3. a `.csv` extension is detected as CSV: REQ-DP-01 A. "Format Detection".
4. CSV-shaped content is sniffed as CSV without a `.csv` extension: REQ-DP-01 A. "Format Detection".
5. `_detect_format` resolves a `.pdf` file to PDF: REQ-DP-01 A. "Format Detection" three-way branch.
6. `_detect_format` resolves a `.csv` file to CSV: REQ-DP-01 A. "Format Detection" three-way branch.
7. `_detect_format` falls back to IMAGE for a non-PDF, non-CSV file: REQ-DP-01 A. "Format Detection" three-way branch.

--- TestCsvValidityGate (4) ---
8. required headers with a data row pass validation: REQ-DP-01 A. "CSV Validity Gate".
9. a CSV missing a required header is rejected: REQ-DP-01 A. "CSV Validity Gate".
10. a CSV with headers but no data rows is rejected: REQ-DP-01 A. "CSV Validity Gate" — "at least one data row."
11. header matching is case- and whitespace-tolerant: REQ-DP-01 A. "CSV Validity Gate", read against the existing `_csv_has_valid_transactions` normalization.

--- TestRunGatekeeperCsv (2) ---
12. a valid CSV passes the Gatekeeper end to end: REQ-DP-01 A. "CSV Validity Gate" exercised through `run_gatekeeper`, not just the header-check helper.
13. an invalid CSV fails the Gatekeeper and carries no `csv_s3_key`: REQ-DP-01 A. "CSV Validity Gate" — a rejected CSV must not look like a valid one downstream.

--- TestRunGatekeeperResourceCaps (2) ---
14. a file over the size cap is rejected with `FileTooLargeError` before further processing: REQ-DP-04 "Cap Resource Consumption Per Upload" — enforced before any paid inference runs.
15. an unreadable image is rejected with `UnsupportedFormatError`: REQ-DP-01 F. Error Handling — `UNSUPPORTED_FORMAT`, closing the previously-uncaught `PIL.UnidentifiedImageError` path.

--- TestParseCsvTransactions (3) ---
16. a valid CSV produces the expected transactions: REQ-DP-01 A. "CSV Transaction Parsing" — the confirmed dead-end fix; a valid CSV must actually produce transactions.
17. one bad row is skipped without failing the file: REQ-DP-01 F. Error Handling — `CSV_ROW_PARSE_ERROR`.
18. a CSV missing required columns raises `InvalidCsvFormatError`: REQ-DP-01 A. "CSV Transaction Parsing" defensive guard, in case the file changes between the Gatekeeper and Extractor steps.

--- TestIngestionHandlerCsvRouting (3) ---
19. a CSV job produces non-zero transactions through the handler: REQ-DP-01 A. "CSV Transaction Parsing" — the end-to-end regression test for the confirmed bug (`csv_s3_key` produced but never consumed).
20. a CSV job never calls Textract: REQ-DP-01 D. Pipeline Stage Mapping — CSV and OCR are separate paths; CSV must not pay for or depend on Textract.
21. a missing `csv_s3_key` on a CSV-formatted job fails the job instead of silently producing zero transactions: REQ-DP-03 A. "Failure Handling" applied to the Extractor stage.

--- TestIngestionHandlerErrorHandling (1) ---
22. an extraction failure records job status FAILED and re-raises: REQ-DP-03 A. "Failure Handling and Idempotency" — "any failure updates the job status to FAILED with a reason, instead of leaving the job stuck."

--- TestLedgerPushJobStatus (3) ---
23. a fully successful push marks the job COMPLETED: REQ-DP-02 F. Error Handling baseline — the happy path must still work after the status-logic fix.
24. a partially successful push marks the job PARTIALLY_COMPLETED, not COMPLETED: the confirmed bug fix — job status previously ignored `all_succeeded` and always reported COMPLETED.
25. a fully failed push marks the job FAILED, not COMPLETED: same fix, the total-failure case.

--- TestGatekeeperHandlerStatus (3) ---
26. a job with valid pages is marked GATEKEEPER_PASSED: REQ-DP-01 A. page classification, observed at the handler.
27. a job with no valid pages is marked FAILED, not silently passed forward: REQ-DP-01 F. Error Handling — `NO_VALID_PAGES`.
28. a Gatekeeper exception records job status FAILED (with the error message) and re-raises: REQ-DP-03 A. "Failure Handling and Idempotency" applied to the Gatekeeper stage.

--- TestTenantScopingHeader (2) ---
29. the `X-Internal-User-Id` header is forwarded on every Ledger push: REQ-DP-06 "Tenant Scoping on the Ledger Push" — the Ledger's `UserContextFilter` needs a verified per-request identity to scope against, not just a shared API key.
30. the internal API key is still present alongside the new tenant header: REQ-DP-06 — the fix must add scoping without removing the existing service-to-service auth.

--- TestPiiLogHygiene (1) ---
31. a failed push does not log the raw transaction body (merchant, amount, account number): REQ-DP-08 "PII and Log Hygiene" — "restrict them to IDs, counts, and status — never raw transaction content."

--- TestCleanMerchant (4, pre-existing) ---
32. a trailing `#12345` reference is stripped: normalizer merchant-cleaning baseline.
33. a `*MARKETPLACE` suffix is preserved (only `#`/`*`+digits are stripped): normalizer merchant-cleaning baseline.
34. merchant names are lowercased: normalizer merchant-cleaning baseline.
35. repeated internal whitespace collapses to one space: normalizer merchant-cleaning baseline.

--- TestParseAmount (3, pre-existing) ---
36. a standard `$1,234.56` string parses to `Decimal("1234.56")`: normalizer amount-parsing baseline.
37. a parenthesized amount parses as a negative (credit): normalizer amount-parsing baseline.
38. a non-numeric amount returns `None` rather than raising: normalizer amount-parsing baseline.

--- TestRegexCategorize (5, pre-existing) ---
39. "uber eats" matches before the broader "uber" pattern: categorizer regex-map ordering.
40. a plain "uber" trip matches the rideshare pattern: categorizer regex-map baseline.
41. "amazon" matches the general-retail pattern: categorizer regex-map baseline.
42. "amzn mktp" matches the same general-retail pattern: categorizer regex-map baseline.
43. an unrecognized merchant returns no regex match, falling through to the registry/Comprehend chain: categorizer regex-map baseline.

--- TestNormalizeAndCategorize (3, pre-existing) ---
44. a Regex-matched merchant never triggers a DynamoDB registry lookup: categorizer lookup-order baseline ("Regex Map (free, sub-millisecond)" first).
45. a registry-cached merchant never triggers Comprehend: categorizer lookup-order baseline (cache before paid fallback).
46. a transaction with an unparsable amount is skipped, not included with a garbage value: normalizer baseline — "Unparsable amount, skipping."
