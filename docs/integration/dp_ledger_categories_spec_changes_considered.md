# DP–Ledger Categories: Spec Changes Considered

These are changes to the spec files that the implementation plan (2026-09-28) depends on. Spec files are user-owned, so they are listed here for you to apply rather than edited directly.

Specs covered: `docs/fintracker-data-pipelines/data-pipeline-spec-02.md` (REQ-DP-09), `docs/integration/dp-ledger-categories-spec.md` (01–06), and `docs/fintracker-data-pipelines/data-pipeline-spec-01.md` (REQ-DP-01).

## A. data-pipeline-spec-02.md — REQ-DP-09 (now out of date)
- **Items 3 and 6.** The pipeline no longer sends category *names*. It sends a Ledger `category_id`, resolved using the order in integration spec 03. Replace "translated into FinTracker's category names" and "names the Ledger already recognizes" with "resolved to a valid Ledger category".
- **Item 3, second paragraph.** The "built-in list of well-known merchants" is no longer hard-coded in the pipeline's code. It becomes the MerchantCategoryMap table (integration spec 06).
- **Item 5.** A missing or blank bank label goes through the MerchantCategoryMap table first. It ends up Uncategorized only if nothing matches there.
- **Item 1.** Per-user merchant rules live in the Ledger. The pipeline reads the user's rules at the start of each upload and applies them before anything else. Rules match on a normalized merchant key that the pipeline computes.
- **Data Impacts.** "No Ledger schema change in this phase" no longer holds. The Ledger gains:
  - a category `code` and `is_active`
  - transaction `source_category` and `merchant_key`
  - a per-user merchant rules table
  - the `others`→`uncategorized` and `dining`→"Food & Drink" renames

  Also add the new pipeline DynamoDB table, MerchantCategoryMap.
- **Interface Details.**
  - `categorize_merchant(...)` becomes a category resolver that returns a `category_id`.
  - `MerchantCategory.source` and `sub_category` are removed.
  - The "Category labels emitted" list and "Ledger push payload is unchanged (`category`, `subCategory`)" are both replaced by the package in integration spec 04.
- **Error Handling.** "Falls through to the built-in merchant list" becomes "falls through to MerchantCategoryMap".

## B. dp-ledger-categories-spec.md — 05, DP "on receiving results"
- **Step 2 ("return the transaction to review").** The pipeline no longer has a review step to return a row to, because review happens in the Ledger (spec 04). Proposed replacement:
  - The Ledger does not reject a row because of a bad category.
  - It stores the row under `uncategorized` with a reason: `CATEGORY_NOT_FOUND`, `CATEGORY_INACTIVE` or `CATEGORY_NOT_ALLOWED`. The row then shows up highlighted in the Pending tab.
  - The pipeline logs the reason and refreshes its category copy.
- **Ledger steps 3–5 and 7.** Each row's result is either `ACCEPTED` (with a reason when its category was downgraded) or `ALREADY_STORED`. No row is `REJECTED` for a category reason.
- **DP step 1.** "Mark as delivered" is covered by the upload job reaching COMPLETED. The pipeline keeps no per-row delivery state.

## C. Other differences from the current spec files
- **data-pipeline-spec-01.md (REQ-DP-01).** Three names are renamed:

  | Old | New |
  |---|---|
  | "Mapping Confirmation handler" | CsvColMappingConfirmation handler |
  | `PENDING_MAPPING_CONFIRMATION` | `PENDING_CSV_COL_MAPPING_CONFIRMATION` |
  | `/jobs/{jobId}/mapping-confirmation` | `/jobs/{jobId}/csv-col-mapping-confirmation` |

  The old names were easy to confuse with category mapping.
- **SYSTEM categories.** `dining` becomes "Food & Drink" (code `food-and-drink`) and `others` becomes `uncategorized`. Both keep their existing IDs. Transaction and budget text that says "Dining" or "Others" is renamed to match.
- **01.**
  - The existing `others` row is renamed to `uncategorized` instead of seeding a new row.
  - "Upsert by code" in the seed script only inserts rows that are missing. It never overwrites an existing name, because names stay editable.
  - `uncategorized` cannot be deactivated.
  - Codes are generated with the same normalization as spec 03 step 1 (`&` becomes `and`). That makes "Food & Drink" `food-and-drink`, not `food-&-drink`.
- **02.**
  - The endpoints are `/api/v1/ledger/categories/internal/system` and `/api/v1/ledger/categories/internal/users/{userId}`. Both are internal-only. For the user endpoint, the user in the path must match the caller's `X-Internal-User-Id`.
  - The user endpoint also returns the user's merchant rules.
  - "On startup" means when a Lambda container starts (cold start).
  - "Raise an alert" means a CloudWatch alarm.
  - "Does not process uploads" means the job fails with `CATEGORIES_UNAVAILABLE`.
- **03.**
  - The resolution order gets two new steps: the user's merchant rule comes first, and MerchantCategoryMap (spec 06) comes just before `uncategorized`.
  - Steps 2–4 are skipped when there is no bank label.
  - `source_category` is empty for PDF rows.
  - The bank-label → code table is a JSON file in the pipeline.
- **04.**
  - The "unique transaction ID" is the pipeline's row fingerprint, an idempotency key. The Ledger's own `transaction_id` stays a Ledger-generated UUID.
  - The user ID travels in the `X-Internal-User-Id` header.
  - The Ledger fills its text `category` column from the category's display name, so budgets keep working.
- **06.**
  - MerchantCategoryMap is a DynamoDB table in the pipeline, keyed by pattern. It is loaded from `docs/data/merchant_category_map_seed.md` at deploy time.
  - The `exact` match type is supported, but the seed only uses `regex` and `contains`.
  - Seed codes must be existing Ledger codes: `health` became `healthcare` and `dining` became `food-and-drink`.
