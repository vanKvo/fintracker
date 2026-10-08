TXT: Transaction Types

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
[Ingest / Input Transaction Data] ──► TXT-01
│
[Type Classification & Schema Validation] ──► TXT-01, TXT-02
│
[Budget & Analytics Aggregation Engine] ──► TXT-02
│
[Failure handling] ──► TXT-01

---

## 3. Requirements Index

| ID | Title | Area | Priority |
|---|---|---|---|
| TXT-01 | Transaction Type Definition and Ingestion | Data | MVP |
| TXT-02 | Type-Based Budgeting and Analytics Offset | Data | MVP |

---

## 4. Requirements

### TXT-01: Transaction Type Definition and Ingestion  `Priority: MVP`

**Problem:** Inconsistent or ambiguous bank labels fail to clearly express whether a transaction is a purchase, refund, salary, or transfer.
**Requirement:** The system must validate and store incoming transactions using strictly one of 5 supported primary types: `expense`, `income`, `refund`, `transfer`, or `adjustment`.
**Acceptance Criteria:**
- [Happy] Incoming transactions with valid types (`expense`, `income`, `refund`, `transfer`, `adjustment`) are accepted and saved with matching `direction` (`debit` or `credit`).
- [Alt] An incoming credit transaction explicitly marked as a return/refund is stored as `type: "refund"` with `direction: "credit"`.
- [Alt] An incoming transaction moving money between two owned user accounts is stored as `type: "transfer"` and omitted from spending calculations.
- [Fail] An incoming transaction with missing type defaults to `type: "income"` if it is a credit, or `type: "expense"` if it is a debit, and logs a warning with the payload ID.
**Open Questions:** Should `refund` transactions require a valid `linked_transaction_id` pointing to an original `expense` at ingestion time Database Schema: Include linked_transaction_id as an optional/nullable field. Ingestion Pipeline: Ignore it completely during initial ingestion (leave it null). Analytics Engine: Compute category spend simply by looking at type = 'refund' and matching on category and date, without caring whether linked_transaction_id is populated or not.
**Refs:** Appendix A

---

### TXT-02: Type-Based Budgeting and Analytics Offset  `Priority: MVP`

**Problem:** Users returning purchases expect their category budgets to be credited back, rather than having the refund counted as earned income.
**Requirement:** The analytics engine must compute monthly budget totals by subtracting `refund` amounts from `expense` amounts per category, while excluding `transfer`, `income`, and `adjustment` types from spending totals.
**Acceptance Criteria:**
- [Happy] Viewing a category budget with $150 in `expense` items and $50 in `refund` items displays a net spend of $100.
- [Happy] The refund offset the month it lands in to reflect real cash flow. 
- [Alt] If `refund` amounts exceed `expense` amounts in a category for a period, the net spend is reported as negative spend and is excluded from total earned income. 
- [Alt] Transactions with `type: "transfer"` alter individual account balances but contribute $0 to spending or income totals.
**Refs:** TXT-01, Appendix A

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
| `amount` | DECIMAL(15,2) | NOT NULL | `amount != 0` | |
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
