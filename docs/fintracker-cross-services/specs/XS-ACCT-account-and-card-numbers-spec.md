# XS-ACCT: Account and Card Numbers

| Field | Value |
|---|---|
| Product | FinTracker |
| Prefix | XS-ACCT |
| File | fintracker-cross-services/specs/XS-ACCT-account-and-card-numbers-spec.md |
| Owner | Van Vo |
| Status | Draft |
| Last updated | 2026-10-29 |

**Services:** Ledger (stores and serves accounts; masks text on every write path), Frontend (Accounts page), every service's logging, Data pipeline (bank sync, later), User profile (subscription payments, later). Decision: app doc D26. Compliance tracking: [XS-COMP](XS-COMP-compliance-controls-spec.md).

---

## 1. Overview

### Problem
LG-CORE-3.1 stores the full account number. The Ledger keeps it in plaintext (`ledger.accounts.account_number`, migration V5), and the Accounts API returns the full value to the browser. The browser masks it only for display ([bug record](../../bugs/bug_account_number_masked_before_reaching_edit_form.md)). The Ledger's `logback-spring.xml` logs jOOQ SQL with bound values at DEBUG, so a create or update writes the number into CloudWatch. A stored card number (PAN) brings the Ledger, Aurora, its backups, the gateway, the CDN, the browser and the logs into PCI DSS scope. A stored bank account number is the most sensitive field FinTracker would hold under the GLBA Safeguards Rule. Nothing in the app needs either number in full.

### Goals
- No FinTracker store, response, event, log, LLM payload or export holds more than the last four digits of an account or card number.
- PCI DSS stays out of scope while FinTracker shows accounts, and stays at the smallest self-assessment (SAQ A) once subscription payments ship.
- Existing full numbers in the dev database are gone, including from the table's on-disk pages.

### Non-Goals
- **Original statement files.** The Document service keeps each file exactly as uploaded, so the user can download it. A statement may show a full account number. The file is protected by the Document service's controls: encryption, ownership check, short-lived links, audit and deletion. Scanning stored files for numbers is tracked in XS-COMP-07.
- **Bank account numbers inside free text.** They have no checksum, so they can't be told apart from other digit runs. Only card-number-like runs are masked (XS-ACCT-05).
- **SSNs and identifiers in user documents.** Knowledge redacts them before chunking (app doc 4.5).
- **Payment processing itself:** pricing, plans and invoices belong to a future billing spec. XS-ACCT-08 only fixes where card data may go.

### Design Principles
1. **Don't hold what we can't afford to lose.** FinTracker stores at most the last four digits of any account or card number.
2. **The last four is all anyone sees.** No route, event, reporting view, log line, LLM payload or CSV/PDF export carries more.
3. **Never echo a rejected number.** An error names the field. It never contains the value, and neither does a log line.
4. **Card entry belongs to the payment provider.** No FinTracker page, API or service receives a card number or security code.

---

## 2. Workflow

```
[User enters or edits an account's last four on the Accounts page] ──► XS-ACCT-01
    │
[Ledger accepts only four digits; rejects a longer number without echoing it] ──► XS-ACCT-02
    │
[Ledger returns only the last four] ──► XS-ACCT-03
    │
[One-time: existing full numbers reduced to the last four and purged from disk] ──► XS-ACCT-04
    │
[Every Ledger write masks card-number-like runs in merchant and description text] ──► XS-ACCT-05
    │
[No service logs a card number or SQL bound values] ──► XS-ACCT-06
    │
[Later: bank sync stores the provider's last four, never full numbers] ──► XS-ACCT-07
[Later: subscription payments through the payment provider's hosted page] ──► XS-ACCT-08
```

---

## 3. Requirements Index

| ID | Title | Area | Priority | Status |
|---|---|---|---|---|
| XS-ACCT-01 | Accounts page shows and edits only the last four | UI | MVP | Implemented |
| XS-ACCT-02 | The Ledger accepts only the last four | Security | MVP | In progress |
| XS-ACCT-03 | The Ledger returns only the last four | Security | MVP | In progress |
| XS-ACCT-04 | Remove stored full numbers | Data | MVP | In progress |
| XS-ACCT-05 | Mask card-number-like text on every Ledger write | Security | MVP | In progress |
| XS-ACCT-06 | No card numbers or SQL bound values in logs | Security | MVP | In progress |
| XS-ACCT-07 | Bank sync stores only the last four | Security | Later | Proposed |
| XS-ACCT-08 | Subscription payments through a tokenization vault | Security | Later | Proposed |

---

## 4. Requirements

### XS-ACCT-01: Accounts page shows and edits only the last four  `Priority: MVP`

**Problem:** The Accounts table masks the full number in the browser, and inline edit pre-fills the full number. The UI is the reason the full number was ever returned (bug record).
**Requirement:** The Accounts table shows `•••• 1234`. The create dialog and inline edit have one field, labeled "Last 4 digits", that accepts exactly four digits. Inline edit pre-fills it with the stored last four.
**Acceptance Criteria:**
- [Happy] An account with last four `6789` shows `•••• 6789`; inline edit opens with `6789` in the field.
- [Alt] An account with no last four shows `—`, and the field starts empty. Saving it empty leaves the value unset.
- [Fail] Typing a fifth character is blocked. Pasting `4111 1111 1111 1111` keeps only the last four digits (`1111`), and the full value is never sent to the API.
- [Fail] A 400 `invalid_argument` naming `accountLastFour` shows "Enter only the last 4 digits." under the field.
**Refs:** `fintracker-ui` `account.service.ts`, `accounts.ts`, `accounts.html` (bug record); [help/accounts.md](../../help/accounts.md) (state that only the last four is kept).

### XS-ACCT-02: The Ledger accepts only the last four  `Priority: MVP`

**Problem:** `CreateAccountRequest` and `UpdateAccountRequest` take `accountNumber` of any length, and Jackson ignores unknown fields. An old client could keep sending full numbers without anyone noticing.
**Requirement:** `POST /api/v1/ledger/accounts` and `PATCH /api/v1/ledger/accounts/{id}` accept `accountLastFour`: optional, exactly four ASCII digits (`^[0-9]{4}$`). A body that has an `accountNumber` field, or any field the contract doesn't list, is rejected (Appendix A).
**Acceptance Criteria:**
- [Happy] A create with `"accountLastFour": "1234"` returns 201 with `accountLastFour` = `1234`.
- [Alt] A PATCH without `accountLastFour` leaves the stored value unchanged. A PATCH with `null` clears it.
- [Fail] `"accountLastFour": "12345"`, `"12a4"` or `"4111111111111111"` returns 400 `invalid_argument` with `detail` naming `accountLastFour`. Nothing is stored.
- [Fail] A body with `accountNumber`, with any value, returns 400 `invalid_argument` naming `accountNumber`. Nothing is stored.
- [Fail] In both failures the submitted value appears neither in the response body nor in any log line, checked by capturing the logs during the test.
**Refs:** Appendix A; error catalog `invalid_argument`; supersedes the account-number rule in LG-CORE-3.1.

### XS-ACCT-03: The Ledger returns only the last four  `Priority: MVP`

**Requirement:** Every Ledger response that describes an account carries `accountLastFour` and no other form of the number. The same holds for internal routes, reporting views, outbox events and CSV/PDF exports.
**Acceptance Criteria:**
- [Happy] `GET /api/v1/ledger/accounts` returns the fields in Appendix A, with `accountLastFour` and no `accountNumber`.
- [Alt] An account created before XS-ACCT-04 returns the last four derived by the migration.
- [Fail] A contract test serializes every account DTO, event payload and export row and fails if any of them has a field whose name contains `accountNumber` or `account_number`.
**Refs:** `AccountDto`, `JooqAccountRepository.mapToAccountDto`; D22 (reporting views already carry no account numbers).

### XS-ACCT-04: Remove stored full numbers  `Priority: MVP`

**Problem:** Dev already holds full numbers. A dropped PostgreSQL column stays in the table's pages until the table is rewritten.
**Requirement:** One forward-only migration adds `account_last_four` and fills it from the existing value (the last four digits once non-digits are stripped; left null if fewer than four digits remain). It then drops `account_number`, and the table is rewritten so the old values are gone from its pages. The backfill reaches every user's rows even though Row-Level Security is forced on the table.
**Acceptance Criteria:**
- [Happy] Two users' accounts with `000123456789` and `9876-5432` end with `6789` and `5432`, and `information_schema.columns` has no `account_number` for `ledger.accounts`.
- [Happy] The table's `pg_class.relfilenode` changes across the migration, which shows the table was rewritten.
- [Alt] A value with fewer than four digits (`AB1`), or a null, ends with a null last four.
- [Alt] RLS is forced again when the migration finishes, and a session with no user set still sees zero rows (ADR-002).
- [Fail] If any step fails, Flyway stops and the deploy fails. The column isn't dropped while the backfill is incomplete.
- [Fail] After the deploy, manual Aurora snapshots taken before it are deleted, and the release notes record that automated backups age out on their own (1 day in dev).
**Refs:** next free migrations `V32__Account_Last_Four.sql` (backfill and drop; turns forced RLS off and on again inside the same transaction so the owner role reaches every row) and `V33__Rewrite_Accounts_Table.sql` (`VACUUM FULL ledger.accounts`, run outside a transaction with Flyway's `executeInTransaction=false`). The table is small, so the brief exclusive lock is acceptable.

### XS-ACCT-05: Mask card-number-like text on every Ledger write  `Priority: MVP`

**Problem:** Merchant or description text from a statement row or a manual entry can carry a full card number, for example a payment-to-card line.
**Requirement:** Before storing a transaction's merchant, description or tags, and an account's name or owner, the Ledger replaces every card-number-like run (Appendix B) with `****` plus its last four digits. This applies on manual create and update, splits, and the internal import route. Other text is stored unchanged.
**Acceptance Criteria:**
- [Happy] An imported merchant `PAYMENT TO CARD 4111 1111 1111 1111` is stored as `PAYMENT TO CARD ****1111`.
- [Alt] A 16-digit run that fails the Luhn check (`1234567812345678`), a 10-digit phone number and a 13-digit order number that fails Luhn are stored unchanged.
- [Alt] Masking happens before the import's row fingerprint is computed, so re-importing the same file stays idempotent (SDR-001).
- [Fail] Masking never fails a write. A field that becomes empty after masking is rejected by the existing validation for that field.
**Refs:** Appendix B; LG-STMT internal import; XS-IMP-01.

### XS-ACCT-06: No card numbers or SQL bound values in logs  `Priority: MVP`

**Problem:** `logback-spring.xml` sets `org.jooq.tools.LoggerListener` and `com.fintracker.ledger` to DEBUG in every profile. jOOQ's listener logs each statement with its bound values.
**Requirement:** Outside the `dev` and `test` profiles, the Ledger logs at INFO and never logs SQL text or bound values. Every service's JSON log output passes through a mask that replaces card-number-like runs (Appendix B) with `****` plus the last four, as a last line of defense behind the rule that logs carry no financial values (app doc 4.7).
**Acceptance Criteria:**
- [Happy] With the default profile, creating an account and importing a statement writes no line from `org.jooq` and no line containing a bound value.
- [Happy] A log call in each service whose message includes `4111111111111111` writes `****1111`.
- [Alt] The `dev` profile may enable jOOQ DEBUG for local work. The deployed dev environment does not use the `dev` profile.
- [Fail] A CI check fails the Ledger build if `logback-spring.xml` sets `org.jooq` below INFO outside a `dev`/`test` `springProfile` block.
**Refs:** Ledger: `logback-spring.xml` with a `MaskingJsonGeneratorDecorator` (logstash-logback-encoder) value mask. Python services: a Powertools Logger formatter that applies the same pattern. AI assistant `scripts/check_log_redaction.py`.

### XS-ACCT-07: Bank sync stores only the last four  `Priority: Later`

**Requirement:** When bank sync ships, the Data pipeline stores the account's last four as reported by the bank-data provider (Teller's `last_four`), plus the provider's account and enrollment IDs. It never calls the provider's account-details endpoint, which returns full account and routing numbers. The provider access token is stored encrypted with the Data pipeline's customer-managed KMS key, or in Secrets Manager, and is never logged.
**Acceptance Criteria:**
- [Happy] A synced account shows the provider's last four on the Accounts page.
- [Fail] A CI check fails if the code references the provider's account-details path.
- [Fail] A test that captures logs during enrollment and sync finds no access token and no digit run longer than four.
**Refs:** ledger-schema `bank_connections`; roadmap *Later*; XS-COMP-17.

### XS-ACCT-08: Subscription payments through a tokenization vault  `Priority: Later`

**Requirement:** When paid plans ship, card entry happens only on the payment provider's hosted checkout page, which the user is redirected to. Embedded provider fields are acceptable only if the billing spec records why. FinTracker stores only the provider's customer, subscription and payment-method IDs, card brand, last four and expiry month and year. It learns of payment changes through the provider's signed webhooks.
**Acceptance Criteria:**
- [Happy] A user upgrades through the hosted checkout. User profile records the tier from the verified webhook, and Settings shows `Visa •••• 4242`.
- [Fail] No FinTracker API schema has a field for a card number or security code. A contract test fails if a request or response model gains a field whose name contains `card_number`, `cardNumber`, `pan`, `cvv` or `cvc`.
- [Fail] A webhook with an invalid signature returns 400. No tier change is made, and the attempt is logged without its body.
**Refs:** XS-COMP-18 (provider choice and PCI SAQ A); the future billing spec.

---

## 5. Open Questions (consolidated)

| # | Question | Blocks |
|---|---|---|
| — | None open. Resolved 2026-10-29: last four only, digits only; payments later through a tokenization vault. | — |

---

## Appendix A: Accounts API contract (Ledger)

Request, create (`POST /api/v1/ledger/accounts`). Unknown fields are rejected with 400 `invalid_argument`:

```json
{ "accountName": "Everyday Checking", "accountType": "CHECKING",
  "accountLastFour": "1234", "owner": "Van Vo", "syncMode": "MANUAL" }
```

Request, update (`PATCH /api/v1/ledger/accounts/{id}`): the same fields, all optional. An absent field is unchanged; `"accountLastFour": null` clears the value.

Response (both, and each item of `GET`):

```json
{ "accountId": "uuid", "userId": "uuid", "accountName": "Everyday Checking", "accountType": "CHECKING",
  "accountLastFour": "1234", "owner": "Van Vo", "currentBalance": 1520.40,
  "syncMode": "MANUAL", "createdAt": "2026-10-29T14:00:00Z" }
```

Only `accountNumber` → `accountLastFour` changes; every other field keeps its current name and type.

Column: `ledger.accounts.account_last_four CHAR(4) NULL CHECK (account_last_four ~ '^[0-9]{4}$')`.

---

## Appendix B: Card-number-like run

A run of 13 to 19 digits, where single spaces or hyphens may separate the digits, that passes the Luhn check once the separators are removed. Matching uses word boundaries, so a run inside a longer digit string isn't matched. The replacement is `****` followed by the run's last four digits.

Produced by code (Ledger write paths and log masks). Test vectors: `4111111111111111`, `4111-1111-1111-1111` and `5500 0000 0000 0004` are masked; `1234567812345678` (fails Luhn) and `202610291430` (12 digits) are not.

---

## Change Log

| Change | Reason |
|---|---|
| New spec, 2026-10-29 | Decision to store only the last four (D26); supersedes LG-CORE-3.1's "record the full account number" and resolves the Ledger architecture's account-number open question |
