# SDR-001: Statement Imports Are Idempotent by Statement and Row Fingerprint

## Service Name: fintracker-ledger

## Status
Proposed (Ledger architecture doc S2). Follows REQ-STMT-02 and the app architecture doc; conflicts with DP-LEDGER-CATEGORIES-05, which keys on a transaction ID.

## Date
2026-10-20

## Context
The Data pipeline sends each statement's transactions to the Ledger in one internal call. Step Functions retries a failed call, and a user may re-run an import, so the same rows can arrive more than once. A duplicate row inflates balances, budgets and reports. Two specs disagree on the key that makes a retry safe.

Key requirements:
- A retried or repeated import never creates a duplicate transaction.
- One bad row never fails the rest of the statement.
- Two genuinely identical purchases on one statement (two $4.50 coffees at the same shop on the same day) are both kept.
- The key is the same however many times the file is processed.

## Options

- **Row fingerprint** *(chosen)*: the Ledger enforces a unique `(statement_id, row_fingerprint)`, where the fingerprint is a hash of the row's date, merchant, amount and its occurrence number among identical rows in that statement.
- **Transaction ID from the Data pipeline**: the pipeline assigns each row an ID, and the Ledger skips IDs it already stored.

## Trade-offs

| Dimension | Row fingerprint | Transaction ID from the pipeline | Edge |
|---|---|---|---|
| **Same key when the file is processed again** | Yes: derived from the row's content | Only if the pipeline derives IDs deterministically; a fresh UUID per run creates duplicates | Fingerprint |
| **Who guarantees uniqueness** | The Ledger's unique index | The Ledger trusts a value the caller generated | Fingerprint |
| **Reuse** | The same row hashes build the statement-level fingerprint for duplicate-statement detection (REQ-STMT-04) | A separate mechanism is still needed there | Fingerprint |
| **Identical rows on one statement** | Kept, because the occurrence number differs | Kept | Tie |

## Decision
**The Ledger deduplicates imports on `(statement_id, row_fingerprint)`, in both profiles.**

1. The Data pipeline computes `row_fingerprint` = hash(date, normalized merchant, amount, occurrence number). The occurrence number is 1 for the first row with that date, merchant and amount in the statement, 2 for the next, and so on.
2. The Ledger validates rows in code first. Invalid rows are reported and left out, so they never abort the insert.
3. Valid rows go in one `INSERT … ON CONFLICT (statement_id, row_fingerprint) DO NOTHING`, all as `PENDING`.
4. The response reports each row as `ACCEPTED`, `ALREADY_STORED` or `REJECTED` with a reason code.

## Consequences
- **Retries are free:** a repeated call stores nothing new and reports every row as `ALREADY_STORED`.
- **Fingerprint rules are a contract between two services.** Changing the hash inputs re-imports every row of a re-processed statement, so the rules are versioned in the spec.
- **Follow-up:** REQ-STMT-02 hashes only date, merchant and amount, which would silently drop the second of two identical purchases. Add the occurrence number to REQ-STMT-02, and align DP-LEDGER-CATEGORIES-05 with this key.

## Revisit when
- Bank sync arrives (Teller.io), where the bank's own transaction ID (`external_tx_id`) is the natural key for synced rows.

## Related
- [Ledger architecture](../ledger-architecture.md): workflow "Import a statement's transactions".
- Specs: [ledger-statement-spec-02.md](../../ledger-statement-spec-02.md) (REQ-STMT-02, REQ-STMT-04), [dp-ledger-categories-spec.md](../../../fintracker-cross-services/dp-ledger-categories-spec.md) (DP-LEDGER-CATEGORIES-05).
