Implementation Plan: DP–Ledger Category Integration
Context
docs/integration/dp-ledger-categories-spec.md (sections 01–06) defines how the Data Pipeline (DP) and Ledger agree on categories: SYSTEM categories get a stable code, the Ledger exposes category read APIs that the DP caches, the DP resolves every row to a real category_id, and PDF rows are matched against a merchant pattern table.

Review happens only in the Ledger (spec 04). The DP sends every processed row as PENDING. The user reviews, recategorizes and approves in the Ledger, and approval moves a row to POSTED. Budgets already count only POSTED rows.

User decisions (2026-09-28):

SYSTEM others is renamed to uncategorized.
SYSTEM dining is renamed to Food & Drink:
Stored name food_&_drink, so the display name is "Food & Drink".
Code food-and-drink, using spec 03's normalization. Chase's "Food & Drink" label then matches the SYSTEM code directly.
The CSV column-mapping confirmation is renamed from "MappingConfirmation" to CsvColMappingConfirmation everywhere.
The failing TestReqDp03LedgerPushIdempotency test is fixed.
MerchantCategoryMap is a DP DynamoDB table seeded from docs/sql/merchant_category_map_seed.sql, using Ledger codes (healthcare, not health).
spec-02's per-user "Always use this for " rules are included.
Budgets keep matching on category text.
source_category is nullable: PDF rows have no bank label.
Goal: a DP + Ledger pair that deploys and runs cleanly end to end.

Starting point: DP branch req-dp-09-categorization (Comprehend removed; bank label → Ledger label; hard-coded regex). This plan replaces labels with category_id and replaces the regex list with MerchantCategoryMap.

Answers to review questions
The row fingerprint does not become ledger.transactions.transaction_id. That column stays the Ledger-generated UUID primary key. The spec's "unique transaction ID" in the package is the DP's rowFingerprint, an idempotency key. It already has its own column (row_fingerprint CHAR(64), V12) and is unique per statement: (statement_id, row_fingerprint). It is a SHA-256 of statement ID, row index, date, merchant, amount and type, so a retried package produces the same value. The Ledger detects ALREADY_STORED from that index; no change to transaction_id.
CLAUDE.md. Output files go in the appropriate existing folder (e.g. docs/instructions/, docs/bugs/, docs/integration/). There is no outputs/ folder.
Seed codes. The seed will use existing Ledger codes. Only health is off (4 rows) and becomes healthcare. The other codes (dining, groceries, shopping, subscriptions, transportation, utilities) already exist. A converter test fails on any code the Ledger doesn't have.
Mapping confirmation is not category approval. It is the CSV column mapping step: which CSV column is date, merchant or amount, used for banks the system doesn't recognize. It is still needed and has nothing to do with spec 04. Current code:
DP: the Gatekeeper waitForTaskToken pause (src/gatekeeper/handler.py, service.py::confirm_column_mapping), src/gatekeeper/mapping_confirmation_handler.py, and the POST /jobs/{jobId}/mapping-confirmation route.
UI: MappingConfirmationDialog.
Keep it. Fix its missing ownership check (T13).
Yes: user-profile owns the sub → internal-user-id mapping. DynamoDB IDENTITY#<cognito_sub> → internal_user_id (app/identity/repository.py). It also already ships a Lambda REQUEST authorizer (app/identity/handlers.py::authorizer_handler) that verifies the token and returns context.internal_user_id. The fix: the DP HTTP API uses that authorizer instead of its own JWT authorizer, and maps X-Internal-User-Id from $context.authorizer.internal_user_id (T13).
Why TestReqDp03LedgerPushIdempotency fails. There are two problems.
(a) The immediate crash. The test never stubs sign_headers, and LEDGER_API_URL is unset in tests, so the URL has no host. botocore then crashes on a None Host header ('NoneType' object has no attribute 'split'). push_transactions_to_ledger catches the error and returns "all failed", so requests.post is never called and call_count is 0. It broke when SigV4 signing was added (f7221a3): the other dispatcher tests got _passthrough_sign, but this one did not.
(b) The assertion itself is outdated. It expects the DP to skip the second push (call_count == 1), a DP-side dedup that was never built. Idempotency lives in the Ledger: ON CONFLICT (statement_id, row_fingerprint) DO NOTHING, reported as skippedDuplicateCount, which the DP counts as success. A retry must re-send so the Ledger can report the duplicates.
Fix (T0e):
Rewrite the test to the real contract: both pushes send identical fingerprints, and a second response of skippedDuplicateCount=1 gives all_succeeded with success_count == total.
Stub the signer and URL.
Also fail fast with a clear configuration error when LEDGER_API_URL is empty, instead of the cryptic botocore crash.
Bug doc.
Spec change list. T0b writes docs/integration/dp_ledger_categories_spec_changes_considered.md. The content is in the Appendix below. You named this file explicitly, so writing it doesn't break the new spec rule.
Architecture Decisions
Internal routes. New Ledger routes go under /api/v1/ledger/categories/internal/... so InternalCallerFilter guards them. For users/{userId}, the path id must equal X-Internal-User-Id, otherwise 403. RLS keys off the header.

MerchantCategoryMap in DP DynamoDB.

Items: PK="MERCHANTMAP", SK=<pattern>, match_type, code, priority, active.
The JSON seed is converted from the SQL by a script, and a test keeps the two in sync.
Terraform aws_dynamodb_table_item loads it on deploy: idempotent, keyed by pattern.
The Normalizer runs one Query and caches the result for 5 minutes.
Matching uses the seed header's normalization (uppercase, collapse whitespace, keep punctuation), picks the lowest priority, and skips rows whose code isn't an active SYSTEM code.
Package IDs. Package ID = DP job_id; the per-row idempotency key = rowFingerprint (see answer 1). The user ID stays the X-Internal-User-Id header. If the body also carries it, it must match.

Category text. The Ledger derives transactions.category text from the resolved category's display name, so budgets and analytics keep working.

Merchant key. The DP computes a stable merchant_key (strips *XXXX order IDs, store numbers, and TST*/SQ * prefixes) and sends it with each row. The Ledger stores it and matches rules on it.

DP resolution order:

User merchant rule
Bank label vs the user's categories
Bank-label → code table (DP JSON)
Bank label vs SYSTEM codes
MerchantCategoryMap
uncategorized
Steps 2–4 are skipped when source_category is null (PDF).

Invalid category on ingest (spec 05, simplified). The Ledger stores the row as uncategorized with a per-row reason (NOT_FOUND / INACTIVE / NOT_ALLOWED) instead of rejecting it. The DP logs it and forces a cache refresh. No resend loop.

Commits. Each requirement gets a failing-tests commit before its implementation commit, per submodule.

Task List
Phase 0: Housekeeping
 T0a: CLAUDE.md. Add a "Spec Files" section:
AI agents must not create or edit any file whose name contains spec unless the user explicitly instructs it.
Agent output (summaries, runbooks, notes) goes in the appropriate existing docs/ folder.
Save a feedback memory.
XS.
 T0b: Write docs/integration/dp_ledger_categories_spec_changes_considered.md (Appendix). XS.
 T0c: In docs/sql/merchant_category_map_seed.sql:
Change health → healthcare (4 rows) and dining → food-and-drink (22 rows).
Correct the header comment: DO UPDATE does overwrite active/priority.
XS.
 T0d: Rename MappingConfirmation → CsvColMappingConfirmation. A pure rename; behavior is unchanged and existing tests are updated.
DP:
src/gatekeeper/mapping_confirmation_handler.py → csv_col_mapping_confirmation_handler.py, moved with git mv
PENDING_MAPPING_CONFIRMATION → PENDING_CSV_COL_MAPPING_CONFIRMATION
MappingConfirmationTimeoutError / MAPPING_CONFIRMATION_TIMEOUT → CsvColMappingConfirmation…
route /jobs/{jobId}/mapping-confirmation → /jobs/{jobId}/csv-col-mapping-confirmation
Terraform mapping_confirmation_lambda* → csv_col_mapping_confirmation_lambda*; the dev Lambda is recreated
tests
UI:
mapping-confirmation-dialog/ → csv-col-mapping-confirmation-dialog/
MappingConfirmationDialog(Data) → CsvColMappingConfirmationDialog(Data)
confirmMapping → confirmCsvColMapping
status union and WAITING_STATUSES
confirm_column_mapping and ColumnMappingProposal are already descriptive and keep their names.
Verification: poetry run pytest, ng test, terraform validate, and a grep shows no MappingConfirmation left outside spec files.
M.
 T0e: Fix TestReqDp03LedgerPushIdempotency (answer 7).
Commit the rewritten test plus a new failing test "empty LEDGER_API_URL raises a config error", then the implementation.
Bug doc docs/bugs/<date>_bug_ledger_push_idempotency_test_signing_crash.md.
S.
Phase 1: Ledger foundation
 T1: code, is_active, others→uncategorized (spec 01)
V21:
add code and is_active DEFAULT true
CHECK: SYSTEM requires code, USER requires null
partial unique index on code
trigger that rejects a changed code
backfill code using spec 03's normalization (lowercase, &→and, drop other punctuation, _/space → -)
rename others → uncategorized and dining → food_&_drink (code food-and-drink), both keeping their UUIDs
rename the text Others → Uncategorized and Dining → Food & Drink in transactions, budget lines, template lines and test-data/*.sql
enum labels follow until T6 removes the enum's use
R__system_categories.sql: insert-if-missing by code.
Model and DTOs get code and isActive.
Acceptance:
codes backfilled
updating code fails
re-running the seed creates no duplicates
uncategorized has the old others UUID
food-and-drink has the old dining UUID and displays as "Food & Drink"
M.
 T2: Deactivate instead of delete (spec 02)
delete sets is_active=false; reassignment becomes optional.
Lists exclude inactive categories.
Re-creating a deactivated name reactivates it.
uncategorized can't be deactivated.
M.
 T3: Internal read APIs (spec 02)
GET …/categories/internal/system with ETag and 304.
GET …/categories/internal/users/{userId}: user categories plus merchant rules (the rules come from T7).
Register the path in InternalCallerFilterConfig.
Acceptance:
304
403 when the path id ≠ header id
401 for a caller that isn't allow-listed
M.
Checkpoint A: mvn clean package green; migrations apply on a fresh DB and on the dev DB.

Phase 2: Ledger ingest and review
 T4: Transaction columns (spec 04)
V22 adds source_category TEXT NULL (null for PDF rows) and merchant_key TEXT NULL plus an index on (user_id, merchant_key).
The model gets categoryId, sourceCategory and merchantKey.
S.
 T5: Ingest v2 (spec 04/05)
The request adds packageId, and per row rowFingerprint (the idempotency key), categoryId, an optional sourceCategory and merchantKey. The text category is derived.
Rows are stored as PENDING.
Per-row result: ALREADY_STORED, or ACCEPTED with an optional reason when the category was downgraded to uncategorized.
A SECURITY DEFINER ledger.category_exists(uuid) tells NOT_FOUND apart from NOT_ALLOWED under RLS.
Acceptance: one IT test per case; a retried package creates no duplicates.
M.
 T6: Recategorize by categoryId + bug fix (spec 04)
PATCH takes categoryId, validates it is active and allowed, and sets both the ID and the text.
Drop the TransactionCategory enum from the update and split paths.
The category picker list comes from the DB.
Bug doc: "custom category saved as Others".
M.
 T7: Per-user merchant rules (spec-02 items 1–2)
V23 user_merchant_rules with RLS and a unique (user_id, merchant_key).
PATCH with remember=true upserts the rule and recategorizes the user's other PENDING rows with the same key.
Bulk categorize action.
Acceptance: rules stay isolated per user; remember=false creates no rule.
M.
Checkpoint B: Ledger suite green. Manual curl check: ingest → PATCH with remember → approve → POSTED.

Phase 3: Data Pipeline (branch req-dp-09-categorization)
 T8: MerchantCategoryMap (spec 06)
Converter script and JSON seed.
Terraform table, items, Normalizer env var and dynamodb:Query IAM.
Repository plus matcher (regex/contains/exact, priority).
Acceptance:
JSON equals the SQL
every code is known
lowest priority wins
inactive rows are skipped
Target → no match
terraform validate
M.
 T9: Categories client and cache (spec 02)
Module-level system copy, fetched on cold start, ETag refresh every 300 s.
A failed refresh keeps the stale copy and logs ERROR with a metric. No copy raises CategoriesUnavailableError.
force_refresh().
Per-job fetch of user categories and rules.
Reuse src/shared/sigv4.py::sign_headers.
M.
 T10: Resolver (spec 03/06 + rules)
Resolution order as above.
Remove _REGEX_MAP; the bank-label table maps to codes.
NormalizedTransaction gains category_id, source_category (optional) and merchant_key; category and sub_category are dropped.
M.
 T11: Dispatcher package v2
Send the new fields, all as PENDING.
Log downgrade reasons and call force_refresh() when any appear.
Job ends COMPLETED.
S.
 T12: Infrastructure
Normalizer LEDGER_API_URL.
Alarm on category-refresh failures.
Failure reason CATEGORIES_UNAVAILABLE.
The Normalizer and LedgerPush role ARNs must be added to the Ledger's ledger.internal.allowed-caller-arns.
S.
 T13: DP HTTP API identity + ownership (deploy blocker)
Replace the JWT authorizer with user-profile's REQUEST authorizer (Terraform var for its function ARN, plus an invoke permission).
Map X-Internal-User-Id from $context.authorizer.internal_user_id.
csv_col_mapping_confirmation_handler (renamed in T0d) checks that the job's user_id matches the header, else 404.
Fix the stale "Cognito sub" docstring.
Bug doc.
M.
Checkpoint C: DP suite green. Local end to end with the Chase CSV and a PDF against a local Ledger: every row has a valid category_id, PDF rows are matched through MerchantCategoryMap, and PDF rows have source_category = null.

Phase 4: UI
 T14: Pending review
Show "Bank: " (hidden when null).
Highlight uncategorized rows.
Picker by categoryId.
Remember checkbox, on by default.
Implement categorizeSelected().
Vitest.
M.
 T15: Manage categories: delete becomes deactivate; no reassignment required. S.
Phase 5: Deploy readiness
 T16: Deploy runbook in docs/instructions/deploy_dp_ledger_categories.md.
Order: Ledger migrations and deploy first, then DP terraform apply and deploy.
Allowed-caller ARNs and the authorizer ARN.
Smoke tests.
XS.
Risks and Mitigations
Risk	Impact	Mitigation
The ingest contract changes in both services	High	Ledger first; dev cut-over only, no mixed versions
The DP HTTP API depends on the user-profile authorizer being deployed	Med	The runbook orders it; terraform plan fails fast if the ARN is missing
Renaming Others text affects budget lines	Low	The same migration renames the budget text
An in-memory cache per Lambda container	Low	TTL check on each invocation
Verification
Ledger: mvn clean package.
DP: poetry run pytest and terraform validate.
UI: ng test.
Manual end to end:
CSV and PDF upload → PENDING rows.
Recategorize with remember → other pending rows from the same merchant follow.
Approve → POSTED → the budget moves.
Appendix: content for docs/integration/dp_ledger_categories_spec_changes_considered.md
A. spec-02 (data-pipeline-spec-02.md), REQ-DP-09: now out of date
Item 3 and item 6: the pipeline no longer emits Ledger category names/labels. It sends a Ledger category_id resolved through the spec 03 order. Replace "translated into FinTracker's category names" and "names the Ledger already recognizes" with "resolved to a valid Ledger category".
Item 3, second paragraph: the "built-in list of well-known merchants" is no longer hard-coded. It becomes the MerchantCategoryMap table (integration spec 06).
Item 5: a missing or blank bank label goes through the merchant table before ending up Uncategorized, not straight to Uncategorized.
Item 1: per-user rules live in the Ledger. The DP reads them per upload and applies them first. The rule key is a normalized merchant key computed by the DP.
Data Impacts:
"No Ledger schema change in this phase" no longer holds: code, is_active, source_category, merchant_key, the merchant rules table, and the others→uncategorized rename.
Add: new DP DynamoDB table MerchantCategoryMap.
Interface Details:
categorize_merchant(...) → category resolver returning category_id.
MerchantCategory.source / sub_category removed.
The "Category labels emitted" list and "Ledger push payload is unchanged (category, subCategory)" are both superseded by the package in integration spec 04.
Error Handling: "falls through to the built-in merchant list" → "falls through to MerchantCategoryMap".
B. Integration spec 05: DP "on receiving results"
Step 2 ("return the transaction to review") has no DP review to return to, because review lives in the Ledger (spec 04). Proposed replacement:
The Ledger does not reject a row for a bad category. It stores it under uncategorized with a reason (CATEGORY_NOT_FOUND / CATEGORY_INACTIVE / CATEGORY_NOT_ALLOWED), so it shows up highlighted in the Pending tab.
The DP logs the reason and forces a category refresh.
Ledger steps 3–5 and 7: result values become ACCEPTED (optionally with a reason when downgraded) and ALREADY_STORED. There is no REJECTED for category reasons.
Step 1 (DP): "Mark as delivered" is covered by the job reaching COMPLETED. No per-row delivery state is kept in the DP.
C. Other differences from the current spec files
data-pipeline-spec-01.md (REQ-DP-01): the "Mapping Confirmation handler", PENDING_MAPPING_CONFIRMATION and the mapping-confirmation route are renamed to CsvColMappingConfirmation / PENDING_CSV_COL_MAPPING_CONFIRMATION / /csv-col-mapping-confirmation.
SYSTEM categories: dining becomes "Food & Drink" (code food-and-drink) and others becomes uncategorized. Existing transaction and budget text is renamed to match.
01:
Instead of seeding a new uncategorized row, the existing others row is renamed to uncategorized, keeping its UUID, and existing "Others" transaction and budget text is renamed.
The seed "upsert by code" inserts missing rows only. It never overwrites an existing name, since names stay editable.
uncategorized cannot be deactivated.
02:
Endpoint paths are /api/v1/ledger/categories/internal/system and /api/v1/ledger/categories/internal/users/{userId}. They are internal-only, and the path user must match X-Internal-User-Id.
The user endpoint also returns the user's merchant rules.
"On startup" means a Lambda cold start.
"Raise an alert" means a CloudWatch alarm.
"Does not process uploads" means the job fails with CATEGORIES_UNAVAILABLE.
03:
The resolution order gains a first step (user merchant rule) and a step before uncategorized (MerchantCategoryMap, spec 06).
Steps 2–4 are skipped when there is no bank label.
source_category is null for PDF rows.
The bank-label → code table is a JSON file in the DP.
04:
The "unique transaction ID" is the DP's row fingerprint, an idempotency key. It is not the Ledger's transaction_id, which stays a Ledger-generated UUID.
The user ID travels in the X-Internal-User-Id header.
The Ledger fills the text category from the category's display name so budgets keep working.
06:
MerchantCategoryMap is a DP DynamoDB table (key: pattern) loaded from the SQL seed at deploy time.
exact match type is supported, but the seed uses only regex/contains.
Seed codes must be existing Ledger codes (health → healthcare).
