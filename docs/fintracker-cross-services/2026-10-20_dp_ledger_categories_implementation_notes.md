# DP–Ledger categories: implementation notes (Phases 2–5)

These notes cover where the implementation differs from `dp-ledger-categories-spec.md`, `data-pipeline-spec-02.md` (REQ-DP-09) and the plan (`implementation_plans/2026-09-28_dp_ledger_categories.md`), and what is left open. Spec files are not edited; the proposed spec wording is at the end.

## Conflicts with the architecture doc (resolved 2026-10-20: the architecture doc wins)
1. **CATEGORY_NOT_ALLOWED is never sent.** Spec 05 step 5 says another user's category is rejected with CATEGORY_NOT_ALLOWED. Invariant 5 says cross-tenant requests answer like "not found", so the Ledger reports CATEGORY_NOT_FOUND.
2. **The internal user endpoint** (`GET …/categories/internal/users/{userId}`) now answers 404 instead of 403 when the path user isn't the caller's user.

## Differences from the spec and plan
3. **New reason CATEGORY_MISSING.** A row with no `categoryId` is stored as uncategorized with this reason, instead of the whole package failing validation.
4. **`packageId` is required.** A package without one is a 400. This makes an out-of-date pipeline fail loudly rather than import rows silently uncategorized.
5. **Spec 05 "DP forces a refresh" on a downgraded row is not implemented as written.**
   - The category copy lives in the Normalizer Lambda's memory. The LedgerPush Lambda, which receives the results, can't refresh it.
   - Instead, LedgerPush logs `LEDGER_CATEGORY_DOWNGRADE` with counts per reason, and the Normalizer re-checks within 5 minutes on its own.
   - A missing code during normalization does force one refresh (spec 02 step 5).
6. **The bank-label → code table is a Python dict** (`src/categorizer/bank_categories.py`), not a JSON file as the plan said. Keys are normalized labels. A test checks that every value is a Ledger SYSTEM code.
7. **Bank-label matching follows spec 03 normalization** ("Bills & Utilities" → `bills-and-utilities`). Labels that already equal a code ("Food & Drink", "Groceries", "Travel") need no table entry.
8. **Merchant key.** The pipeline computes it from the raw merchant: uppercase, then strip POS prefixes (TST\*, SQ \*), order ids after `*` that contain a digit, and store or reference numbers. So "UBER \*TRIP" and "UBER \*EATS" stay different merchants.
9. **"Fills in the user's other pending uncategorized transactions"** (REQ-DP-09 #2) only changes rows that are PENDING and still in SYSTEM `uncategorized`. Posted rows, and rows the user already categorized, are left alone.
10. **The category text on a recategorize is resolved against the database.** An unknown name is now a 400 instead of being saved silently as Uncategorized. This is the bug fixed in `docs/bugs/2026-10-20_bug_custom_category_saved_as_uncategorized.md`.
11. **The Data Pipeline HTTP API** reads the user from `requestContext.authorizer.lambda.internal_user_id` (architecture invariant 2), not from an `X-Internal-User-Id` header as the plan said.

## Found and fixed along the way
- `docs/bugs/2026-10-20_bug_rls_policies_fail_after_user_context_reset.md`: V25. This also fixes the month-end budget job on reused connections.
- `docs/bugs/2026-10-20_bug_data_pipeline_api_uses_cognito_sub_and_skips_job_ownership.md`

## Not done (follow-ups)
- **The Ledger's internal edge isn't provisioned.** Nothing checks the pipeline's signed requests yet: there is no `ledger-internal` API with IAM authorization in front of `/internal/**`, and the pipeline's Lambda roles have no `execute-api:Invoke` grants. This is the `internal_api` module in ADR-011.
- **User-facing list and delete for merchant rules:** out of scope for now, by your decision on 2026-10-20.
- **The one-time backfill script** (`scripts/one-time/2026-10-20_DP-LEDGER-CATEGORIES-04_backfill_transaction_category_id.sql`) has not been run against a real database.

Done 2026-10-20:
- Manual transactions now store the category id. The name must be one of the user's active categories; an unknown name is a 400.
- `TransactionCategory.java`, its test and `CategoryInUseException.java` (with its handler) are deleted.

## Proposed spec updates (for you to apply)
- **dp-ledger-categories-spec 04 Ledger:** also add `merchant_key` to Transactions (REQ-DP-09), and say the package ID is the pipeline's job id.
- **dp-ledger-categories-spec 02 Ledger:** the user endpoint answers 404 when the path user isn't the caller's user.
- **dp-ledger-categories-spec 05:**
  - Ledger steps 3–5 and 7: "store as uncategorized with a reason" instead of "reject".
  - The reasons are CATEGORY_MISSING, CATEGORY_NOT_FOUND (also for another user's category) and CATEGORY_INACTIVE.
  - DP step 2: replace "force a refresh and return to review" with "log the reason; the user picks a category in the Pending tab".
- **data-pipeline-spec-02 REQ-DP-09:**
  - Items 3 and 6: "resolved to a Ledger category id".
  - "No Ledger schema change in this phase" no longer holds: there are now the merchant rules table and the `source_category` and `merchant_key` columns.
  - Interface Details: `categorize_merchant` and `translate_bank_category` are replaced by `CategoryResolver.resolve` and `BANK_LABEL_TO_CODE`.
