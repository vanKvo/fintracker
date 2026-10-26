# XS-DPCAT: Data Pipeline and Ledger Categories

> **Formerly:** `docs/fintracker-cross-services/dp-ledger-categories-spec.md`, IDs DP-LEDGER-CATEGORIES-NN → XS-DPCAT-NN (renamed 2026-10; see [SPECS.md](../../SPECS.md))

## Status

| ID | Status |
|---|---|
| XS-DPCAT-01 | Implemented |
| XS-DPCAT-02 | In progress (v3 built; dead code awaiting deletion, user-categories route retired after the pipeline deploys) |
| XS-DPCAT-03 | Implemented |
| XS-DPCAT-04 | In progress (package, fields and approval re-check built; the Pending tab highlight is UI) |
| XS-DPCAT-05 | Implemented |
| XS-DPCAT-06 | Implemented |
| XS-DPCAT-07 | In progress (Ledger built; "From your rule" in the Pending tab is UI) |


Version 3 (2026-10-21). The Data pipeline sends SYSTEM category codes only, and the Ledger resolves them and applies the user's own categories and rules: XS-DPCAT-02, -03, -05 and -06 revised, XS-DPCAT-07 added. Version 2 (2026-10-20) revised XS-DPCAT-04 and -05. See [Change Log](#change-log).

## XS-DPCAT-01: Add an immutable `code` to SYSTEM categories *(was DP-LEDGER-CATEGORIES-01)*

### Problem 
System category IDs are random UUIDs, so they differ between dev, staging and prod. DP needs a stable identifier for system categories that survives across environments, and `category_name` is a display value that may change.

### Requested Changes (Ledger):

- Add a `code` column to Categories: unique among SYSTEM rows, required for SYSTEM, empty for USER. Format matches the current naming rule (lowercase, dash for space), e.g. `personal-care`.
- Reject any update to `code` after creation. `category_name` stays editable.
- Backfill `code` for existing SYSTEM rows from their current `category_name`.
- Seed a SYSTEM category with code `uncategorized`. It is the fallback for unmapped transactions and the only code DP may hard-code.
- Make seed scripts upsert by `code`, so re-running them never creates duplicates or replaces an existing UUID.
- Keep `category_id` (UUID) as the primary key and as the key for grouping transactions and calculating budgets. It only needs to be stable within one environment, because each environment's Transactions reference that environment's own Categories table.

## XS-DPCAT-02: Categories read API (Ledger); no runtime category copy in DP *(was DP-LEDGER-CATEGORIES-02)*

> **Revised in v3 (2026-10-21):** DP no longer reads categories at runtime. It sends codes; the Ledger resolves them (XS-DPCAT-05) and applies the user's own categories and rules (XS-DPCAT-07). See [Change Log](#change-log).

### Problem 
DP must suggest valid categories without owning or copying category data. SYSTEM codes are stable in every environment, so DP can refer to SYSTEM categories by code without holding a copy. User categories and merchant rules belong to the Ledger and change often, so the Ledger applies them itself.

### Requested Changes:
**Ledger**

- Keep `GET /categories/internal/system` with its `ETag`. It is used only by DP's deploy-time check (below), not at runtime.
- Retire the internal user-categories endpoint once DP no longer calls it (after XS-DPCAT-07 ships).
- Deactivate categories (`is_active = false`) instead of deleting them, so IDs in existing transactions stay valid.
- A category is never deleted. Removing a custom category deactivates it: transactions and budget lines that reference it keep it, and it can't be chosen for new transactions or budget lines. This replaces LG-CAT-01 item 6 (reassign, then delete); LG-CAT is obsolete.
- No category route, public or internal, takes a `userId` in its path, query or body. The Ledger uses the `userId` from the verified user context (app invariant 2; XS-CTX).

**Change (DP):**

1. DP holds no copy of categories, in memory or in storage. These are removed:
   - the in-memory SYSTEM copy and its 5-minute refresh;
   - the forced refresh;
   - the per-upload fetch of the user's categories and rules;
   - the `CATEGORY_REFRESH_FAILED` alarm.
2. DP's code tables (the bank-label table and MerchantCategoryMap) refer to SYSTEM codes only.
3. At deploy, a check calls the Ledger's SYSTEM endpoint in that environment:
   - it fails the deploy if any code in DP's tables is missing or inactive;
   - it warns about any active SYSTEM code that has no entry in the bank-label table.
4. DP never creates, edits or stores categories itself.

## XS-DPCAT-03: Map bank categories to SYSTEM category codes during normalization (DP) *(was DP-LEDGER-CATEGORIES-03)*

> **Revised in v3 (2026-10-21):** DP suggests a SYSTEM `code`, not a `category_id`, and no longer looks at the user's categories. See [Change Log](#change-log).

### Problem 
Some bank labels, such as "Bills & Utilities", don't match Ledger categories. DP pre-fills a suggestion so the user doesn't categorize each transaction by hand. The Ledger turns the suggestion into a category, so the user approves exactly what the Ledger will store (XS-DPCAT-07).

### Requested Changes
**Change (DP):**

- Keep a bank-label table with two columns: normalized source label and SYSTEM category `code`. It refers to codes, never UUIDs, so the same table works in every environment.
- The table has an entry for every active SYSTEM code's own label (for example `groceries` → `groceries`), so DP can match a label to a code without a list of categories. The deploy check in XS-DPCAT-02 warns when an entry is missing.
- Keep the bank's original label unchanged on each transaction as `source_category`.

**Resolution logic, run per transaction:**

1. Normalize the source label using the rule in Appendix A ("Food & Drink" becomes `food-and-drink`).
2. Look it up in the bank-label table. On a hit, suggest that `code`.
3. Otherwise, match the merchant against MerchantCategoryMap (XS-DPCAT-06). On a hit, suggest that `code`.
4. Otherwise, suggest no code. The Ledger stores the transaction as `uncategorized`.
5. Send the suggested `categoryCode` (or none), the original `source_category` and the `merchant_key` with the transaction.

Step 2 is skipped when the row has no bank label (PDF rows). DP never sends a `category_id`.

## XS-DPCAT-04: Send processed transactions to Ledger for user approval (DP and Ledger) *(was DP-LEDGER-CATEGORIES-04)*

> **Revised in v2 (2026-10-20):** steps 2–4 are now labeled as Ledger and UI work, and step 4 re-checks the category on approval. See [Change Log](#change-log).

### Problem 
Ledger must receive only the categories the user approved, so budgets never shift because of unreviewed data. The user's choice must be exactly what Ledger stores, and the bank's original label must stay visible to explain any difference.

### Requested Changes 
**Ledger**

- Add a nullable text column `source_category` to Transactions to store the bank's original label.

**Change (DP), delivery logic:**

1. DP builds one JSON package containing the package ID, the user ID, and the mapped transactions. Each transaction carries a unique transaction ID, its suggested `categoryCode` (or none), its `source_category`, its `merchant_key` and its status as "PENDING". It sends the package to Ledger after normalization done.

**Change (Ledger and UI), review and approval logic** (DP takes no part in review or approval):

2. The user sees each transaction in the Ledger's Pending tab with its mapped category and the bank's original label. Uncategorized transactions are highlighted.
3. The user may choose a different category from their active USER categories and the active SYSTEM categories. Ledger replaces that transaction's `category_id` in the pending transaction.
4. The user approves. Ledger checks again that each transaction's category exists, is active, and is a SYSTEM category or one of the user's own, because a category can be deactivated while the transaction is pending.
   - If the category is still valid, Ledger changes the transaction status to "POSTED".
   - If not, the transaction stays "PENDING" and is highlighted with "This category is no longer available", so the user picks another one. The other approved transactions are still posted.

## XS-DPCAT-05: Validate categories and report results on ingest *(was DP-LEDGER-CATEGORIES-05)*

> **Revised in v2 (2026-10-20):** a bad category no longer rejects the transaction. Ledger stores it as `uncategorized` with a reason, and DP only logs it, because review happens in Ledger (XS-DPCAT-04), not in DP.
>
> **Revised in v3 (2026-10-21):** the package carries a SYSTEM `code`. The Ledger resolves it, and `CATEGORY_MISSING` is removed because no code means no suggestion, not an error. See [Change Log](#change-log).

### Problem 
A code in DP's tables can be wrong, or its category can be deactivated. Ledger is the owner of Categories, so it must never trust the package. DP's code is only a suggestion: the user reviews and approves every transaction in Ledger (XS-DPCAT-04), so a bad suggestion is downgraded to `uncategorized` for the user to fix, never rejected. The foreign key stays as the last line of defense, and Ledger returns a clear result per transaction so DP can log what happened.

### Requested Changes
**Change (Ledger), ingest logic:**

1. Receive the package from DP and check the package ID and user ID. The package ID is the DP job ID and is required: a package without one is rejected with 400.
2. For each transaction, check whether its transaction ID already exists. If it does, report it as `ALREADY_STORED` and skip it, so a retried package never creates duplicates.
3. Choose the category with the order in XS-DPCAT-07. When DP's suggested code decides it (XS-DPCAT-07, step 3) and the code can't be used, store the transaction under `uncategorized` with this reason:
   - `CATEGORY_NOT_FOUND`: no SYSTEM category has that code.
   - `CATEGORY_INACTIVE`: the SYSTEM category with that code is inactive.

   A transaction with no suggested code is stored as `uncategorized` with no reason.
4. Store every transaction as "PENDING", including `source_category` and `merchant_key`. A downgraded transaction keeps its reason and is highlighted in the Pending tab. A category problem never rejects a transaction or fails the package.
5. Return a per-transaction result: `ACCEPTED` (with the reason code when the category was downgraded), `ALREADY_STORED`, or `REJECTED` with reason `INVALID_ROW` (step 6).
6. A transaction that fails row validation (a missing or unreadable date, an amount that is not positive or has more than 2 decimal places, a missing merchant, or an invalid type, direction or row fingerprint) is not stored and is reported as `REJECTED` with `INVALID_ROW`. The detail goes in the response's `failedRows`. The rest of the package is still stored. A category problem is never a reason to reject (step 4).

**Rollout:** until DP sends codes, the Ledger also accepts `categoryId` with the v2 checks. That path is removed once every DP deploy sends codes.

**Change (DP), on receiving results:**

1. The upload job is marked COMPLETED once Ledger returns the results. DP keeps no per-transaction delivery state.
2. For downgraded transactions, DP logs `LEDGER_CATEGORY_DOWNGRADE` with a count per reason, and an alarm fires on any. A downgrade now means DP's tables refer to a code the Ledger doesn't have, so the fix is a table change. The deploy check in XS-DPCAT-02 should catch it first.

## XS-DPCAT-06: PDF-sourced transactions with no bank category *(was DP-LEDGER-CATEGORIES-06)*

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

3. If no pattern matches, DP suggests no code, and the Ledger stores the transaction as `uncategorized` (XS-DPCAT-03, step 4).

## XS-DPCAT-07: Ledger applies the user's own categories and rules on import

> **Added in v3 (2026-10-21).** This moves steps that DP ran in v2 into the Ledger, which owns the user's categories and merchant rules.

### Problem
The user's merchant rules ("Always use this for <merchant>") and custom categories change often and belong to the Ledger. When DP applied them, it had to fetch them on every upload, and an upload failed whenever the Ledger couldn't answer. The Ledger already has code that applies a newly saved rule to pending transactions, so applying rules on import reuses it.

### Requested Changes
**Change (Ledger), category choice on import, run per transaction (first match wins):**

1. The user's merchant rule for the transaction's `merchant_key`, if the rule's category is active.
2. The normalized `source_category` (Appendix A) equals the normalized name of one of the user's active USER categories.
3. DP's suggested `categoryCode`, if it names an active SYSTEM category (XS-DPCAT-05, step 3).
4. The `uncategorized` SYSTEM category.

- The Ledger records which step chose the category: `USER_RULE`, `USER_CATEGORY`, `SUGGESTED` or `NONE`. The Pending tab shows "From your rule" for `USER_RULE`.
- The user's rules and categories are read once per package, not once per transaction.
- The normalization in step 2 must give the same result as DP's (XS-DPCAT-03, step 1). Both services' test suites include the test cases in Appendix A.

**Acceptance examples:**
- A user has a rule "Target → Gifts" (a USER category). A Target row with the bank label "Shopping" and suggested code `shopping` is stored as Gifts, from `USER_RULE`.
- A user has a category "Food & Drink" of their own. A Chase row labeled "Food & Drink" is stored under the user's category, not the SYSTEM one.
- A rule that points to a deactivated category is skipped, and the next step decides.

## Appendix A: Label normalization (shared by DP and Ledger)

Rule:
1. Trim and lowercase.
2. Replace `&` with ` and `.
3. Replace every character other than `a–z`, `0–9`, space and `-` with a space.
4. Collapse runs of spaces and dashes into one `-`.
5. Strip leading and trailing `-`.

An empty result means no label.

| Input | Output |
|---|---|
| `Food & Drink` | `food-and-drink` |
| `Bills & Utilities` | `bills-and-utilities` |
| `  Personal Care ` | `personal-care` |
| `Gas/Automotive` | `gas-automotive` |
| `--Travel--` | `travel` |
| `Café` | `caf` (non-ASCII letters are dropped; both services must agree) |
| *(blank)* | *(no label)* |

## Change Log

| Version | Change | Reason |
|---|---|---|
| 2 (2026-10-20) | XS-DPCAT-05: a bad category no longer rejects the transaction (`REJECTED` removed). Ledger stores it as `uncategorized` with a reason, and the result is `ACCEPTED` with that reason. | v1 had DP "return the transaction to review", but review happens in Ledger (XS-DPCAT-04), so DP had nowhere to return it. DP's category is only a suggestion; Ledger has the final say. |
| 2 (2026-10-20) | XS-DPCAT-05: reasons are now `CATEGORY_MISSING` (new), `CATEGORY_NOT_FOUND` and `CATEGORY_INACTIVE`. `CATEGORY_NOT_ALLOWED` is removed; another user's category is reported as `CATEGORY_NOT_FOUND`. | Cross-tenant requests must answer like "not found" (architecture doc, invariant 5). A transaction without a category is downgraded rather than failing the whole package. |
| 2 (2026-10-20) | XS-DPCAT-05: the package ID is the DP job ID and is required (400 without it). | An out-of-date pipeline fails loudly instead of silently importing transactions as uncategorized. |
| 2 (2026-10-20) | XS-DPCAT-05, DP: "force a refresh and return to review" replaced by "log `LEDGER_CATEGORY_DOWNGRADE`". "Mark as delivered" replaced by the job reaching COMPLETED. | The category copy lives in the Normalizer Lambda, which the LedgerPush Lambda can't refresh; the 5-minute refresh (XS-DPCAT-02) covers it. |
| 2 (2026-10-20) | XS-DPCAT-04: steps 2–4 (review, recategorize, approve) moved out of "Change (DP)" into "Change (Ledger and UI)". | v1 listed them under DP, which read as if the user approves categories in the pipeline. The pipeline only suggests a category; review and approval happen in the Ledger's Pending tab. |
| 2 (2026-10-20) | XS-DPCAT-04, step 4: Ledger checks the category again when the user approves. | A category can be deactivated while a transaction is pending; v1 only checked on ingest. |
| 3 (2026-10-21) | XS-DPCAT-02: DP holds no copy of categories; the runtime cache, refresh, user fetch and refresh alarm are removed. A deploy-time check validates DP's codes against the Ledger. | SYSTEM codes are stable in every environment, so DP can refer to them without a copy; user data is applied by its owner (XS-DPCAT-07). |
| 3 (2026-10-21) | XS-DPCAT-03: DP suggests a SYSTEM `code` (or none) and never a `category_id`. Matching against the user's categories and against SYSTEM codes directly is removed from DP; the bank-label table holds an entry per SYSTEM code instead. | Turning codes into IDs is the Ledger's job. Without a category list, DP can't compare labels to codes, so the table covers them. |
| 3 (2026-10-21) | XS-DPCAT-05: the Ledger resolves the code. `CATEGORY_MISSING` is removed (no code = no suggestion, stored as `uncategorized` without a reason). `CATEGORY_NOT_FOUND` no longer covers another user's category, because codes are SYSTEM only. The Ledger accepts `categoryId` during rollout. | Follows from codes over the boundary; rollout lets the Ledger deploy before DP. |
| 3.1 (2026-10-26) | XS-DPCAT-05: step 5 lists `REJECTED` again, and step 6 says when: only for a row that fails validation (`INVALID_ROW`), never for its category. | Version 2 removed `REJECTED` for category problems, but the text read as if it no longer existed at all. The Ledger still rejects an invalid row (LG-STMT-02 row rules) while storing the rest of the package, and the Ledger architecture doc describes that correctly. |
| 3 (2026-10-21) | XS-DPCAT-06: no pattern match → no code, instead of DP sending `uncategorized`. | Same rule as XS-DPCAT-03. |
| 3 (2026-10-21) | XS-DPCAT-07 added: the Ledger applies merchant rules and the user's own categories on import, and records which step chose the category. Appendix A added. | The Ledger owns that data; the normalization rule now runs in two services, so shared test cases keep them in step. |
| 4 (2026-10-21) | XS-DPCAT-02: categories are never deleted; removing a custom category deactivates it. No category route takes `userId` from the request. | Resolves the conflict with LG-CAT-01 item 6, now obsolete; identity comes only from the verified context. |
