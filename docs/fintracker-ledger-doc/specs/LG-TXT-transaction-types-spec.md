# LG-TXT: Transaction Types

> **Formerly:** `docs/fintracker-ledger-doc/TXT-transaction-types-spec.md`, IDs TXT-NN → LG-TXT-NN (renamed 2026-10; see [SPECS.md](../../SPECS.md))

Last updated: 2026-10-06

---

## 1. Overview

### Problem
Users viewing imported banking data struggle with ambiguous transaction categories like "Credit" and "Purchase," which conflate balance directions (debit vs. credit) with transactional actions (refunds vs. purchases). This causes confusion in cash flow reports, miscalculates budget progress when returns or transfers occur, and leads to inaccurate spending totals.

### Goals
- Provide an explicit 5-type taxonomy (`expense`, `income`, `refund`, `transfer`, `adjustment`) to uniquely identify cash flow behavior.
- Ensure spending budgets accurately reflect net spending by applying refunds as budget offsets rather than new income.

### Design Principles
1. **Explicit Intent.** Every transaction must have exactly one primary core type that dictates its accounting behavior across all analytics and budgets.
2. **Net Budget Transparency.** Refunds must directly offset spending in their target category rather than inflating total income.

---

## 2. Workflow
[Ingest / Input Transaction Data] ──► LG-TXT-01
│
[Type Classification & Schema Validation] ──► LG-TXT-01, LG-TXT-02
│
[Budget & Analytics Aggregation Engine] ──► LG-TXT-02
│
[Store amount as positive + direction] ──► LG-TXT-03
│
[Failure handling] ──► LG-TXT-01

---

## 3. Requirements Index

| ID | Title | Area | Priority | Status |
|---|---|---|---|---|
| LG-TXT-01 | Transaction Type Definition and Ingestion | Data | MVP | Implemented |
| LG-TXT-02 | Type-Based Budgeting and Analytics Offset | Data | MVP | Implemented |
| LG-TXT-03 | One amount sign convention | Data | MVP | Implemented |

---

## 4. Requirements

### LG-TXT-01: Transaction Type Definition and Ingestion  `Priority: MVP` *(was TXT-01)*

**Problem:** Inconsistent or ambiguous bank labels fail to clearly express whether a transaction is a purchase, refund, salary, or transfer.
**Requirement:** 
- The system must validate and store incoming transactions using strictly one of 5 supported primary types: `expense`, `income`, `refund`, `transfer`, or `adjustment`.
- EXPENSE require money out, and INCOME and REFUND require money in.

**Acceptance Criteria:**
- [Happy] Incoming transactions with valid types (`expense`, `income`, `refund`, `transfer`, `adjustment`) are accepted and saved with matching `direction` (`debit` or `credit`).
- [Alt] An incoming credit transaction explicitly marked as a return/refund is stored as `type: "refund"` with `direction: "credit"`.
- [Alt] An incoming transaction moving money between two owned user accounts is stored as `type: "transfer"` and omitted from spending calculations.
- [Fail] An incoming transaction with missing type gets a 400 error.

**Open Questions:** Should `refund` transactions require a valid `linked_transaction_id` pointing to an original `expense` at ingestion time Database Schema: Include linked_transaction_id as an optional/nullable field. Ingestion Pipeline: Ignore it completely during initial ingestion (leave it null). Analytics Engine: Compute category spend simply by looking at type = 'refund' and matching on category and date, without caring whether linked_transaction_id is populated or not.
**Refs:** Appendix A

---

### LG-TXT-02: Type-Based Budgeting and Analytics Offset  `Priority: MVP` *(was TXT-02)*

**Problem:** Users returning purchases expect their category budgets to be credited back, rather than having the refund counted as earned income.
**Requirement:** The analytics engine must compute monthly budget totals by subtracting `refund` amounts from `expense` amounts per category, while excluding `transfer`, `income`, and `adjustment` types from spending totals.
**Acceptance Criteria:**
- [Happy] Viewing a category budget with $150 in `expense` items and $50 in `refund` items displays a net spend of $100.
- [Happy] The refund offset the month it lands in to reflect real cash flow. 
- [Alt] If `refund` amounts exceed `expense` amounts in a category for a period, the net spend is reported as negative spend and is excluded from total earned income. 
- [Alt] Transactions with `type: "transfer"` alter individual account balances but contribute $0 to spending or income totals.
**Refs:** LG-TXT-01, Appendix A

---

### LG-TXT-03: One amount sign convention  `Priority: MVP`

**Problem:** Statement rows are stored unsigned and manual rows signed (negative = money out), while `direction` already says which way money moved. Two fields that can disagree, and every sum must know which source a row came from.
**Requirement:** Every transaction stores `amount` as a positive number; `direction` alone says whether money went out (`DEBIT`) or came in (`CREDIT`). Manual entry converts a signed input to this form once, at the API boundary. A migration converts existing manual rows (negative amount → its absolute value, direction unchanged) and adds a database check `amount > 0`.
**Acceptance Criteria:**
- [Happy] A manual entry of −40.00 with type `EXPENSE` is stored as `amount 40.00`, `direction DEBIT`.
- [Happy] A statement row arrives positive and is stored unchanged.
- [Alt] After the migration, no row has `amount <= 0`, and every existing total (Dashboard, budgets, Analytics) is unchanged on the migration fixture.
- [Fail] An insert or update with `amount <= 0` is rejected by the database check, whatever the code path.
- [Fail] A manual entry whose sign contradicts its type (positive `EXPENSE` input with `direction CREDIT`) returns 400 under LG-TXT-01's type/direction rule.
**Refs:** LG-TXT-01; DP-TXT P-04; XS-RPTV-01

---

## Appendix A: Transaction Data Model Schema

*Table `ledger.transactions` (Ledger Service, PostgreSQL). The existing schema is the source of truth. Changes: the allowed `type` values, plus four new columns (`direction`, `currency`, `is_recurring`, `linked_transaction_id`).*

| Column | Type | Null | Default / Constraint | Notes |
|---|---|---|---|---|
| `transaction_id` | UUID | NOT NULL | PK, `gen_random_uuid()` | |
| `account_id` | UUID | NOT NULL | FK → `ledger.accounts`, ON DELETE CASCADE | |
| `user_id` | UUID | NOT NULL | Derived from the account by trigger | Row-Level Security key |
| `statement_id` | UUID | NULL | FK → `ledger.statements`, ON DELETE CASCADE | Null for manual / bank-sync rows |
| `parent_transaction_id` | UUID | NULL | FK → `ledger.transactions`, ON DELETE CASCADE | Set on split children |
| `external_tx_id` | VARCHAR(255) | NULL | Unique per `account_id` when not null | |
| `amount` | DECIMAL(15,2) | NOT NULL | `amount > 0` (LG-TXT-03) | Always positive; `direction` gives the sign |
| `merchant` | VARCHAR(255) | NOT NULL | | |
| `category` | VARCHAR(100) | NOT NULL | | Category label |
| `category_id` | UUID | NULL | FK → `ledger.categories`, ON DELETE RESTRICT | |
| `description` | VARCHAR(500) | NULL | | |
| `tags` | TEXT[] | NULL | | |
| `tx_date` | DATE | NOT NULL | | |
| `source` | VARCHAR(50) | NOT NULL | `STATEMENT_UPLOAD`, `BANK_SYNC`, `MANUAL_ENTRY` | |
| **`type`** | VARCHAR(50) | NOT NULL | **`EXPENSE`, `INCOME`, `REFUND`, `TRANSFER`, `ADJUSTMENT`** | **Changed** — replaces `PURCHASE`, `CREDIT` |
| **`direction`** | VARCHAR(10) | NOT NULL | **`DEBIT`, `CREDIT`** | **New** — money out (`DEBIT`) or in (`CREDIT`) |
| **`currency`** | CHAR(3) | NOT NULL | **`USD`** | **New** — ISO 4217 code |
| **`is_recurring`** | BOOLEAN | NULL | | **New** |
| **`linked_transaction_id`** | UUID | NULL | **FK → `ledger.transactions`, ON DELETE SET NULL** | **New** — e.g. a refund's original expense; left null at ingestion |
| `status` | VARCHAR(50) | NOT NULL | `PENDING`, `POSTED`, `DELETED` | |
| `is_excluded` | BOOLEAN | NOT NULL | `FALSE` | |
| `is_manual` | BOOLEAN | NOT NULL | `FALSE` | |
| `row_fingerprint` | CHAR(64) | NULL | Unique per `statement_id` when not null | Statement-upload idempotency key |
| `created_at` | TIMESTAMPTZ | NULL | `CURRENT_TIMESTAMP` | |
