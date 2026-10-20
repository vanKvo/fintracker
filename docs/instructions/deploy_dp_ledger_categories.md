# Deploying the DP–Ledger categories change (dev)

This change spans four services, and the Ledger's statement import contract changes with it. Deploy in this order. A pipeline that runs before the Ledger is updated sends packages the Ledger rejects (400, missing `packageId`), and the job fails visibly.

## 1. Ledger

1. **Back up the dev database** (`pg_dump -Fc -d fintracker > before_categories.dump`).
2. **Migrate.** Start a Ledger build that includes V21–V27 (`mvn spring-boot:run`, or the deploy's Flyway step). V21–V27 are schema-only:
   - V21: category `code` and `is_active`; `others` → `uncategorized`, `dining` → `food_&_drink`.
   - V25: RLS policies treat a reset user context as "no user".
   - V26: `source_category` and `merchant_key` on transactions.
   - V27: `user_merchant_rules`.
   The repeatable `R__System_Categories.sql` adds any missing SYSTEM category by code.
3. **Backfill category ids** on existing transactions, once, as the Postgres superuser:
   ```bash
   psql -h localhost -U postgres -d fintracker \
        -f services/fintracker-ledger/scripts/one-time/2026-10-20_DP-LEDGER-CATEGORIES-04_backfill_transaction_category_id.sql
   ```
4. **Allow the pipeline's Lambdas** to call the internal API. Set `LEDGER_INTERNAL_ALLOWED_CALLER_ARNS` to the comma-separated list from the pipeline's `ledger_allowed_caller_arns` Terraform output (step 3): the S3 processor, Normalizer and LedgerPush roles. The Normalizer role is new; it reads `/api/v1/ledger/categories/internal/**`.
5. **Smoke test:**
   - `GET /api/v1/ledger/categories/internal/system` (allow-listed caller) returns 17 categories, with `uncategorized` and `food-and-drink` among them.
   - Repeating the call with `If-None-Match: <ETag>` returns 304.

## 2. User Profile

The pipeline's HTTP API now uses User Profile's identity authorizer. Deploy User Profile (SAM) if it isn't already deployed. Note the authorizer Lambda's ARN from its stack outputs.

## 3. Data Pipeline

1. In `infrastructure/terraform/environments/dev/terraform.tfvars` (gitignored):
   - Add `identity_authorizer_function_arn = "<User Profile authorizer ARN>"`.
   - Remove `cognito_user_pool_id` and `cognito_user_pool_client_id`. They are no longer variables, and Terraform warns about undeclared ones.
   - Optional: set `alarm_sns_topic_arn` to receive the category-refresh alarm.
2. If the merchant seed changed, regenerate it with `python -m scripts.build_merchant_category_map`. The test suite fails if the JSON and the SQL differ.
3. Run `terraform plan` and check it shows these changes:
   - The new `MerchantCategoryMap` table and its 85 items.
   - `LEDGER_API_URL` and `MERCHANT_CATEGORY_MAP_TABLE` on the Normalizer.
   - The REQUEST authorizer replacing the JWT authorizer.
   - The metric filter and alarm.
4. `terraform apply`, then copy the `ledger_allowed_caller_arns` output into the Ledger (step 1.4) and restart the Ledger.

## 4. UI

Deploy the UI build. These features depend on the new Ledger fields:
- the Pending tab's bank label;
- the uncategorized highlight;
- "Always use this for <merchant>";
- bulk Categorize.

## 5. End-to-end check

1. **CSV with bank categories.** Upload a Chase CSV.
   - The job ends `COMPLETED` and every row is `PENDING`.
   - A row with "Food & Drink" from the bank shows Food & Drink with "Bank: Food & Drink".
2. **PDF.** Upload a PDF statement.
   - Known merchants (e.g. Starbucks) are categorized.
   - Unknown ones are highlighted as Uncategorized and show no bank label.
3. **Merchant rule.** On one uncategorized Target row, pick a category with "Always use this for …" checked. The user's other pending uncategorized Target rows follow.
4. **Rule on the next upload.** Upload another statement with Target. It arrives already categorized: the pipeline applied the user's rule.
5. **Approve.** The row becomes POSTED and the budget for its category moves.
6. **Ownership.** `GET /jobs/{jobId}` with another user's token answers 404.

## Rollback

- **Ledger:** restore the dump from step 1.1. The migrations only add things and Flyway has no down migrations, so restoring is the rollback.
- **Pipeline:** `terraform apply` the previous commit.
- **Order:** roll back the pipeline first, then the Ledger.
