# FinTracker: DP–Ledger Categories Integration Spec

Version 1

## DP-LEDGER-CATEGORIES-01: Add an immutable `code` to SYSTEM categories

### Problem 
System category IDs are random UUIDs, so they differ between dev, staging and prod. DP needs a stable identifier for system categories that survives across environments, and `category_name` is a display value that may change.

### Requested Changes (Ledger):

- Add a `code` column to Categories: unique among SYSTEM rows, required for SYSTEM, empty for USER. Format matches the current naming rule (lowercase, dash for space), e.g. `personal-care`.
- Reject any update to `code` after creation. `category_name` stays editable.
- Backfill `code` for existing SYSTEM rows from their current `category_name`.
- Seed a SYSTEM category with code `uncategorized`. It is the fallback for unmapped transactions and the only code DP may hard-code.
- Make seed scripts upsert by `code`, so re-running them never creates duplicates or replaces an existing UUID.
- Keep `category_id` (UUID) as the primary key and as the key for grouping transactions and calculating budgets. It only needs to be stable within one environment, because each environment's Transactions reference that environment's own Categories table.

## DP-LEDGER-CATEGORIES-02: Categories read API (Ledger) and read-only cache (DP)

### Problem 
DP owns no category data but must map transactions to valid Ledger categories. It needs a supported way to read them instead of a manual copy. System categories are global and rarely change, so they can be cached. User categories can change between uploads, so they must be fetched fresh.

### Requested Changes:
**Ledger**

- Add `GET /categories/system`. It returns `category_id`, `code`, `category_name` and `is_active` for every SYSTEM category, with an `ETag` header and support for `If-None-Match` (returns 304 when nothing changed).
- Add `GET /users/{user_id}/categories`. It returns that user's USER categories with `category_id`, `category_name` and `is_active`.
- Deactivate categories (`is_active = false`) instead of deleting them, so IDs in existing transactions stay valid.

**Change (DP), refresh logic:**

1. On startup, DP calls `GET /categories/system` and keeps the result in memory as a read-only copy, together with its ETag.
2. Every 5 minutes, DP calls the same endpoint with `If-None-Match`. On 304 it keeps the copy. On 200 it replaces the whole copy.
3. If a refresh fails, DP keeps using the last copy and raises an alert. If DP has no copy at all, it does not process uploads.
4. At the start of each user upload session, DP calls `GET /users/{user_id}/categories` and holds the result for that session only.
5. If mapping (Request Change 3) references a code or ID missing from the copy, DP forces one refresh and checks again before falling back.
6. DP never creates, edits or stores categories itself.

## DP-LEDGER-CATEGORIES-03: Map bank categories to Ledger categories during normalization (DP)

### Problem 
Some Bank labels such as "Bills & Uitlities" do not match Ledger categories. DP must resolve every transaction to a valid Ledger `category_id` before the user sees it, so the user approves exactly what Ledger will store. The mapping table only pre-fills a suggestion so the user does not categorize each transaction by hand.

### Requested Changes
**Change (DP):**

- Keep a mapping table with two columns: normalized source label and SYSTEM category `code`. It references codes, never UUIDs, so the same table works in every environment. It holds no category data.
- Keep the bank's original label unchanged on each transaction as `source_category`.

**Resolution logic, run per transaction:**

1. Normalize the source label: lowercase, replace `&` with `and`, remove other punctuation, replace spaces with dashes ("Food & Drink" becomes `food-and-drink`).
2. Compare it with the user's own active categories from this session (Request Change 2, step 4). On a match, use that `category_id`. User categories are checked first because they are more specific than system ones.
3. Otherwise look it up in the mapping table. On a hit, resolve the `code` to a `category_id` using the cached SYSTEM categories. If the code is missing or inactive, treat it as no match and go to step 4.
4. Otherwise compare it with SYSTEM category codes. On a match, use that `category_id`.
5. Otherwise use the `category_id` of the `uncategorized` SYSTEM category.
6. Store the resolved `category_id` and the original `source_category` on the pending transaction.

## DP-LEDGER-CATEGORIES-04: Send processed transactions to Ledger for user approval (DP and Ledger)

### Problem 
Ledger must receive only the categories the user approved, so budgets never shift because of unreviewed data. The user's choice must be exactly what Ledger stores, and the bank's original label must stay visible to explain any difference.

### Requested Changes 
**Ledger**

- Add a nullable text column `source_category` to Transactions to store the bank's original label.

**Change (DP), approval and delivery logic:**

1. DP builds one JSON package containing the package ID, the user ID, and the mapped transactions. Each transaction carries a unique transaction ID, its `category_id`, its `source_category` and its status as "PENDING". It sends the package to Ledger after normalization done.
2. The user sees each transaction with its mapped category and the bank's original label. Uncategorized transactions are highlighted.
3. The user may choose a different category from their active USER categories and the active SYSTEM categories. Ledger replaces that transaction's `category_id` in the pending transaction.
4. The user approves. Ledger changes the transaction status to "POSTED".
5. When a row's category is not found, inactive or not allowed, the Ledger stores the row anyway under uncategorized. It reports that per row (ACCEPTED with reason, e.g. CATEGORY_INACTIVE). The row lands highlighted in the Pending tab and the user picks a category there.

## DP-LEDGER-CATEGORIES-05: Validate categories and report results on ingest

### Problem 
DP's category copy can be out of date, and a category can be deactivated or removed between approval and delivery. Ledger is the owner of Categories, so it must never trust the package. The foreign key stays as the last line of defense, and Ledger returns a clear result per transaction so DP can recover.

### Requested Changes
**Change (Ledger), ingest logic:**

1. Receive the package from DP and check the package ID and user ID.
2. For each transaction, check whether its transaction ID already exists. If it does, report it as `ALREADY_STORED` and skip it, so a retried package never creates duplicates.
3. Check that `category_id` exists in Categories. If not, reject the transaction with `CATEGORY_NOT_FOUND`.
4. Check that the category is active. If not, reject with `CATEGORY_INACTIVE`.
5. Check that the category is a SYSTEM category, or a USER category owned by the package's user. Otherwise reject with `CATEGORY_NOT_ALLOWED`.
6. Insert every valid transaction, including `source_category`. Rejected transactions do not fail the rest of the package.
7. Return a per-transaction result: `ACCEPTED`, `ALREADY_STORED`, or `REJECTED` with its reason code.

**Change (DP), on receiving results:**

1. Mark `ACCEPTED` and `ALREADY_STORED` transactions as delivered.
2. For `CATEGORY_NOT_FOUND` or `CATEGORY_INACTIVE`, force a refresh of the category copy (Request Change 2, step 5) and return the transaction to review so the user picks a current category.

## DP-LEDGER-CATEGORIES-06: PDF-sourced transactions with no bank category 

### Problem
PDF rows have no bank label, so every PDF transaction would become Uncategorized, which is not true.

### Requested Changes
**DP, mapping logic for PDF transactions**

1. Replace hard-coded regex with a table
Remove hard-coded regex from the business logic and store it in a table named MerchantCategoryMap table. In the new logic, we will normalize merchant string, then check patterns can match with the string. If there're multiple matches, we choose the one with lowest priority number. Use merchant_category_map_seed.sql to seed data for the table,

MerchantCategoryMap table
  pattern          text   -- regex or substring, e.g. "TRADER JOE'?S"
  match_type       enum   -- 'regex' | 'contains' | 'exact'
  code             text   -- FK-ish reference to SYSTEM category code
  priority         int    -- for ordering when multiple patterns could match
  active           bool

2. Starter list — common, low-ambiguity merchants
Keep the first pass to merchants where the category is obvious and stable. Skip anything ambiguous (e.g., "Target" could be groceries, home goods, or clothing; don't guess, let it fall to uncategorized and let the user decide).

3. If no categories is found in the table, classify the transaction as 'uncategorized'.