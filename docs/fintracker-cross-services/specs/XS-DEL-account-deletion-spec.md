# XS-DEL: Account Deletion

| Field | Value |
|---|---|
| Product | FinTracker |
| Prefix | XS-DEL |
| File | fintracker-cross-services/specs/XS-DEL-account-deletion-spec.md |
| Owner | Van Vo |
| Status | Draft |
| Last updated | 2026-10-26 |

**Services:** User profile (starts deletion, publishes the event, tracks completion), Ledger, Data pipeline, Knowledge, AI assistant (each deletes its own share). Decision: app doc D15 (retention and deletion); invariant 11 (deletion cascades). Knowledge's share is specified in [KN-DEL](../../fintracker-knowledge/specs/KN-DEL-account-deletion-spec.md), the AI assistant's chat data in AI-CHAT-14.

---

## 1. Overview

### Problem
D15 and the app doc describe account deletion, but no spec defines it, and the code doesn't match the design:
- `DELETE /profile` deletes at once, with no grace period.
- It deletes the identity mapping before publishing `UserAccountDeleted`. If the publish fails, a retry can't find the user, so the event is never sent and no other service deletes anything.
- The Ledger and the statement files have no deletion handler, and the Cognito user is never removed.

A user who closes their account keeps every transaction and every bank statement file.

### Goals
- Every service holding the user's data deletes it within 7 days after the 30-day grace period, inside the 45-day window of state privacy laws (D15).
- A failure at any step is retried and alarmed. It never silently ends the deletion.
- Replaying any event is harmless.

### Non-Goals
- Deleting one statement or document: ADR-005 (`StatementDeleted`) and the Document service spec.
- Data download (access requests).
- Billing records, which don't exist yet (D15).

### Design Principles
1. **Each service deletes only its own share,** on `UserAccountDeleted`, and reports `UserDataDeleted`.
2. **The event is never lost.** Nothing a retry needs is removed before the event has been published.
3. **Idempotent everywhere.** Deleting what's already gone succeeds and reports the same completion.
4. **No user data in logs or events.** Only the user ID, counts and request IDs.

---

## 2. Workflow

```
[User closes the account → disabled, 30-day grace period] ──► XS-DEL-01
    │
[Grace period ends → User profile publishes UserAccountDeleted, then deletes its own records and the Cognito user] ──► XS-DEL-02
    │
[EventBridge delivers to each service's queue] ──► XS-DEL-03
    │
[Ledger deletes its rows] ──► XS-DEL-04
[Data pipeline deletes statement files, job records and mappings] ──► XS-DEL-05
[Knowledge (KN-DEL), AI assistant (AI-CHAT-14 and summary data)] ──► XS-DEL-03
    │
[Each service publishes UserDataDeleted → User profile records completion; alarm after 7 days] ──► XS-DEL-06
    │
[Old file versions and backups expire on their own schedule] ──► XS-DEL-07
```

---

## 3. Requirements Index

| ID | Title | Area | Priority | Status |
|---|---|---|---|---|
| XS-DEL-01 | Close the account with a 30-day grace period | Data | MVP | Proposed |
| XS-DEL-02 | Publish the event before removing what a retry needs | Reliability | MVP | In progress (records are deleted and the event published, in the wrong order and without the grace period; the Cognito user is not deleted) |
| XS-DEL-03 | Event contract and delivery to every service | Reliability | MVP | Proposed |
| XS-DEL-04 | The Ledger deletes the user's rows | Security | MVP | Proposed |
| XS-DEL-05 | The Data pipeline deletes statement files, job records and mappings | Security | MVP | In progress (mappings and votes deleted, DP-MAP-06; files and job records not) |
| XS-DEL-06 | Completion tracking and alarm | Observability | MVP | Proposed |
| XS-DEL-07 | Old file versions expire | Security | MVP | Proposed |

---

## 4. Requirements

### XS-DEL-01: Close the account with a 30-day grace period  `Priority: MVP`

**Requirement:** `DELETE /profile` closes the account: User profile marks it `CLOSED` with the closing time, disables the Cognito user (sign-in fails) and deletes nothing yet. Within 30 days the user can reactivate through support, which re-enables the Cognito user and clears `CLOSED`. A scheduled job starts hard deletion (XS-DEL-02) for accounts closed more than 30 days ago.
**Acceptance Criteria:**
- [Happy] After closing, the user can't sign in, and every API call with an old token is denied once the authorizer cache expires (60 s, UP-AUTH-03), because the authorizer denies a `CLOSED` account.
- [Alt] Reactivating on day 29 restores sign-in and every piece of data.
- [Alt] Closing an account that is already closed returns 204 and keeps the original closing time.
- [Fail] If disabling the Cognito user fails, the account is not marked `CLOSED` and the user sees a retryable error.
**Open Questions:** 1 (deleting at once on request).
**Refs:** app doc D15 and "Delete an account"; UP-AUTH-03

### XS-DEL-02: Publish the event before removing what a retry needs  `Priority: MVP`

**Requirement:** Hard deletion in User profile runs in this order, each step safe to repeat: (1) publish `UserAccountDeleted` (Appendix A) and record that it was published; (2) delete every `USER#<id>` item, reading every page of the partition; (3) delete the Cognito user; (4) delete the `IDENTITY#<sub>` mapping, last. A failure at any step leaves the account `CLOSED` and the run is retried until it finishes.
**Acceptance Criteria:**
- [Happy] One run publishes the event once, removes every `USER#` item, the Cognito user and the mapping.
- [Alt] A run that failed after step 1 is retried, publishes the event again with the same `eventId`, and finishes; consumers treat the repeat as a no-op.
- [Fail] If the publish fails after 3 attempts, nothing is deleted, the run is retried on the next schedule, and `account_deletion_failed` raises an alarm.
- [Fail] A test fails the build if any code path deletes the mapping before the publish has succeeded.
**Refs:** User profile architecture "Delete an account"; Appendix A

### XS-DEL-03: Event contract and delivery to every service  `Priority: MVP`

**Requirement:** Every service that stores user data (Appendix B) receives `UserAccountDeleted` through an EventBridge rule that matches `source = fintracker.user-profile-service`, into its own SQS queue with a dead-letter queue. A message is retried 5 times (visibility timeout 60 s), then moves to the DLQ, kept 14 days. Each service deletes only its share and then publishes `UserDataDeleted` (Appendix A); the queue message is deleted only after that publish succeeds.
**Acceptance Criteria:**
- [Happy] One event reaches every queue in Appendix B within 5 minutes.
- [Alt] An event from another source never reaches the queues.
- [Alt] An event without a valid `userId` goes straight to the DLQ and is counted as `invalid_event`.
- [Fail] An alarm fires when any deletion DLQ holds 1 or more messages, or when a queue's oldest message is older than 1 hour.
**Refs:** KN-DEL-01, KN-DEL-03, KN-DEL-04 (the same pattern); Appendix A, B

### XS-DEL-04: The Ledger deletes the user's rows  `Priority: MVP`

**Requirement:** On `UserAccountDeleted`, the Ledger sets the user context and deletes every row with that `user_id`, in every Ledger table, in one transaction (D1: one `DELETE … WHERE user_id = ?` per table), children before parents. It then publishes `UserDataDeleted` with `service = "ledger"` and the row counts per table.
**Acceptance Criteria:**
- [Happy] With accounts, statements, transactions, budgets, rules and bills seeded for user A, a query as user A afterwards returns no rows in any table.
- [Alt] User B's rows and SYSTEM categories and templates are unchanged.
- [Alt] A second delivery deletes 0 rows and publishes again.
- [Fail] A failed transaction deletes nothing and the message returns to the queue (XS-DEL-03).
**Refs:** ADR-001; ADR-002; ADR-009 (the outbox publishes `UserDataDeleted`)

### XS-DEL-05: The Data pipeline deletes statement files, job records and mappings  `Priority: MVP`

**Requirement:** On `UserAccountDeleted`, the Data pipeline deletes every object version and delete marker under `statements/{userId}/` in the statement bucket, the user's job records, and the user's column mappings and votes (DP-MAP-06). It then publishes `UserDataDeleted` with `service = "data-pipeline"` and the counts.
**Acceptance Criteria:**
- [Happy] Afterwards, `ListObjectVersions` under `statements/{userId}/` returns nothing, and no job record or mapping item for the user remains.
- [Alt] More than 1,000 versions are deleted in batches; a second delivery deletes nothing and publishes again.
- [Alt] Shared bank baselines and other users' votes are unchanged.
- [Fail] A failed batch returns the message to the queue; already-deleted versions are not an error on retry.
**Refs:** DP-MAP-06; DP-ING-11; app doc "Delete an account" (Document service owns this once it exists)

### XS-DEL-06: Completion tracking and alarm  `Priority: MVP`

**Requirement:** User profile records each `UserDataDeleted` against the deletion record (`userId`, closing time, publish time, services done). When every service in Appendix B other than User profile has reported, the record is marked complete and kept 24 months (D15). If any service hasn't reported 7 days after the publish, `account_deletion_incomplete` raises an alarm naming the missing services.
**Acceptance Criteria:**
- [Happy] After all four reports (Ledger, Data pipeline, Knowledge, AI assistant), the record is complete, with each service's completion time.
- [Alt] A duplicate report changes nothing.
- [Fail] With the Ledger's report missing on day 7, the alarm fires and names `ledger`.
**Refs:** app doc 3.7 Observe ("Deletion tracking"); KN-DEL open question 1

### XS-DEL-07: Old file versions expire  `Priority: MVP`

**Requirement:** The statement bucket expires noncurrent object versions after 7 days and removes expired delete markers, so a deleted statement file (account deletion, statement deletion, overwrite, or a failed import cleared by XS-IMP-03) is gone from S3 within 7 days. This is the schedule the privacy policy discloses (D15).
**Acceptance Criteria:**
- [Happy] The bucket's lifecycle configuration has a noncurrent-version expiration of 7 days and expired-delete-marker removal.
- [Alt] A current object is never expired by this rule.
- [Fail] A Terraform test fails if the rule is missing or longer than 7 days.
**Refs:** app doc D15 ("S3 noncurrent versions: 7 days"); DP-ING-11

---

## 5. Open Questions (consolidated)

| # | Question | Blocks |
|---|---|---|
| 1 | Should a user be able to ask for deletion at once, skipping the 30-day grace period? D15 allows a shorter path only if counsel agrees. | XS-DEL-01 |

---

## Appendix A: Events

Produced by: User profile (`UserAccountDeleted`), each service in Appendix B (`UserDataDeleted`). Code, not AI.

```json
{
  "source": "fintracker.user-profile-service",
  "detail-type": "UserAccountDeleted",
  "detail": {
    "schemaVersion": 1,
    "eventId": "7f1c…",
    "userId": "d781b133-…",
    "closedAt": "2026-09-26T14:02:11Z",
    "publishedAt": "2026-10-26T14:05:00Z"
  }
}
```

```json
{
  "source": "fintracker.<service>",
  "detail-type": "UserDataDeleted",
  "detail": {
    "schemaVersion": 1,
    "eventId": "7f1c…",
    "userId": "d781b133-…",
    "service": "ledger",
    "counts": { "transactions": 412, "statements": 6 },
    "completedAt": "2026-10-26T14:06:30Z"
  }
}
```

`eventId` is the `UserAccountDeleted` event's ID, repeated in each `UserDataDeleted`, so User profile matches reports to the deletion.

---

## Appendix B: Who deletes what

| Service | Its share | Spec |
|---|---|---|
| User profile | `USER#` items, Cognito user, identity mapping | XS-DEL-02 |
| Ledger | Every Ledger table's rows for the user | XS-DEL-04 |
| Data pipeline | Statement files (all versions), job records, mappings and votes | XS-DEL-05 |
| Knowledge | The user's documents and chunks | KN-DEL |
| AI assistant | Conversations, usage counters, summary cache and snapshots; audit records keep a hashed user ID | AI-CHAT-14; AN-FS deletion |
