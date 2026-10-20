# ADR-005: Statement Deletion Starts in the Ledger

## Service Name: app-wide (Ledger, Document service)

## Status
Accepted (architecture doc D9)

## Date
2026-10-17

## Context
A bank statement has two owners (architecture doc, CONOPS 4.4):

- The **Document service** owns the file: bytes, name, type, hash, scan status, identified by `documentId`.
- The **Ledger** owns what it means: account, period, import status, and the transactions it produced.

When a user deletes a statement, both must go. Deleting transactions is the consequential part, because it changes balances, budgets and reports. Deleting the file is housekeeping.

Key requirements:
- A user must never see transactions whose statement is gone, or budgets that still count deleted transactions.
- Neither service may delete the other's data directly (one owner per data store).
- A failure in either service must not leave the deletion silently half-done.

## Decision
Deletion of a statement **starts in the Ledger**:

1. The client asks the Ledger to delete the statement.
2. The Ledger deletes the statement's transactions and its statement record in one database transaction. Budgets and reports reflect the change immediately.
3. The Ledger publishes `StatementDeleted(documentId)`.
4. The Document service consumes the event and deletes the file and all its stored versions. On failure, the event retries from its queue and lands in the dead-letter queue if it keeps failing.

The Document service rejects direct deletion requests for documents of type `statement`, and points the caller to the Ledger.

## Alternatives Considered

### Start in the Document service
- Pros: The service that owns files handles every file deletion the same way.
- Cons: The file disappears first. If the Ledger's event consumer is slow or failing, the user still sees transactions from a statement that no longer exists. That is the inconsistency users notice most.
- Rejected: The financial records must change first, because they are what the user sees.

### Synchronous call: Ledger calls the Document service during the deletion
- Pros: Both deletions finish before the user gets a response.
- Cons: Couples the Ledger's availability to the Document service's. If the Document service is down, users cannot delete statements at all.
- Rejected: A file left behind for a short time is acceptable. Blocking the user's action is not.

### Orchestrated workflow (saga) in Step Functions
- Pros: Explicit state, compensation steps and visibility for each deletion.
- Cons: More moving parts for a two-step deletion whose second step needs no compensation.
- Rejected: Overkill. Reconsider if statement deletion gains more steps across more services.

## Consequences
- **The file can briefly outlive its transactions**, until the Document service processes the event. The file stays private to its owner during that window.
- **A stuck deletion is visible.** It sits in the Document service's dead-letter queue with an alarm, not lost.
- **The Document service's consumer must be idempotent:** deleting a file that is already gone succeeds.
- **Account deletion is unaffected.** On `UserAccountDeleted`, each service deletes all of its own data for the user independently (invariant 11).
