# DPTXT: Data Pipeline Transaction Type & Category

Last updated: 2026-10-06

Status: Problem list only. Requirements to be refined from these items.

Related: [TXT: Transaction Types](../fintracker-ledger-doc/TXT-transaction-types-spec.md). The Ledger accepts only `EXPENSE`, `INCOME`, `REFUND`, `TRANSFER`, `ADJUSTMENT`, and every row must also carry a direction (`DEBIT` / `CREDIT`).

**Interim behavior (TXT change, 2026-10-06):** the pipeline now uses the Ledger's types end to end. Until these problems are resolved, it assigns direction from the amount's sign and an interim type from the direction (credit → INCOME, debit → EXPENSE). That means refunds and transfers are not yet recognized, and P-03 still inverts Chase rows. The Ledger no longer fills in a missing type (TXT-01 rejects it), so the pipeline must always send one.

---

## 1. Problems and Gaps

### P-01: No rules for assigning a transaction type
**Problem:** The pipeline decides type only from whether the amount is positive or negative (credit → INCOME, debit → EXPENSE). Nothing says how a bank's own label (e.g. Chase "Sale", "Return", "Payment", "Fee", "Adjustment") becomes one of the Ledger's types, or how the amount's sign is read for each bank.
**Needs:** A per-bank mapping from bank label to type, and a per-bank rule for which sign means money out.
**Technical notes:** `normalizer/service.py` — `direction = "CREDIT" if amount < 0 else "DEBIT"`, then the type follows the direction. `bank_mappings.json` declares `amount_sign_convention` per bank, but no code reads it.

### P-02: The bank's type column is thrown away
**Problem:** Bank CSVs often include a type column, but the pipeline never reads it, so the most reliable signal for classifying a row is lost.
**Technical notes:** `RawTransaction.raw_type` exists (`extractor/schemas.py:39`) but is never populated. The extractor only maps `date`, `merchant` and `amount` (`extractor/service.py:49`). `bank_mappings.json` maps `"Transaction Type": "type"` for some banks, but nothing uses it.

### P-03: Chase purchases are imported as money in (live bug)
**Problem:** Chase shows purchases as negative amounts and card payments as positive. The pipeline treats every negative amount as money in, so Chase purchases are recorded as income and card payments as spending. In the sample files under `2026_Chase8760_KVV/`, that affects 89 "Sale" rows and 8 "Payment" rows.
**Technical notes:** `_parse_amount` (`normalizer/service.py:35-50`) treats a leading `-` as a credit. Chase is configured `"amount_sign_convention": "standard"`, but that setting is unused (see P-01).

### P-04: Statement rows and manual rows store amounts with different signs
**Problem:** Direction is now stored in its own field and sent by the pipeline, so it is no longer lost. Amounts still differ by source, though: the pipeline sends every amount as a positive number, while manual entries are signed (negative for money out). Ledger and Analytics totals work around this by ignoring the sign, but anything that shows or sums raw amounts will see the two sources disagree.
**Needs:** A decision on whether statement rows should be signed the same way as manual entries.
**Technical notes:** `NormalizedTransaction(amount=abs(amount))` in `normalizer/service.py`. `ManualTransactionRequest` documents negative = money out, positive = money in.

### P-05: Detecting transfers between the user's own accounts
**Problem:** The pipeline processes one statement at a time, so it can't see both sides of a transfer. Credit-card bill payments are the most common case: if they aren't treated as transfers, the spending is counted twice, once on the card and again as the payment from checking.
**Needs:** A decision on whether transfers are identified from bank labels (e.g. "Payment"), the "Transfer" category, matching across statements, or user confirmation.

### P-06: Rows with an unknown type
**Problem:** When the pipeline can't determine a row's type, it must flag the row, try to resolve it, and then ask the user to choose. The Ledger accepts only the five types, so the row must be resolved before it is sent. Where an unresolved row waits, how the flag is shown, and what happens if the user never answers are all undefined.
**Technical notes:** This overlaps with the existing low-confidence flag (`needs_review`, REQ-DP-01) and with the paused state used for unrecognized CSV column mappings. Decide whether to reuse either one.

### P-07: Users can't correct a wrong type
**Problem:** During review, users can correct a row's category and save a "remember this merchant" rule, but they can't change its type. A misclassified row stays wrong, and the same mistake repeats on every future statement.
**Needs:** A decision on whether type is editable in review, and whether a merchant rule also remembers type. This involves the UI and the Ledger as well as the pipeline.

### P-08: Overlap between type and category
**Problem:** "Income" and "Transfer" exist both as categories and as types. Nothing says how they relate: whether one determines the other, whether they must agree, and what happens when the user changes one.

### P-09: Statements with no type column (PDF and scanned images)
**Problem:** PDF and OCR extraction produce no bank type label, so only the amount's sign and the merchant are available. No classification rule exists for these sources.

### ~~P-10~~ Resolved: The pipeline's internal vocabulary and the Ledger contract were out of date
Resolved by the TXT change (2026-10-06). The pipeline now uses the Ledger's five types and sends `direction` with every row. The `SALE`/`RETURN` labels and the `_TYPE_TO_LEDGER` translation have been removed.
