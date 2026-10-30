# KN-DEL: Account Deletion

| Field | Value |
|---|---|
| Product | FinTracker |
| Prefix | KN-DEL |
| File | fintracker-knowledge/specs/KN-DEL-account-deletion-spec.md |
| Owner | Van Vo |
| Status | Draft |
| Last updated | 2026-10-20 |

---

## 1. Overview

### Problem
When an account is deleted, every service must delete its own share of the user's data and report back, or FinTracker breaks its data-deletion obligations (invariant 11). Embeddings count as user data, because they can leak what they encode. Today a user owns nothing in Knowledge, but the handler must exist and report completion now, so the deletion tracker in User profile is complete and the path is tested before user documents arrive.

### Goals
- Knowledge reports `UserDataDeleted` within 1 hour of receiving `UserAccountDeleted` (the app-wide limit is 7 days).
- System help docs are never touched by a user's deletion.
- Replaying the event is harmless.

### Non-Goals
- Deleting one document on `DocumentDeleted`: see KN-UDOC (later).
- The grace period and the 7-day completion alarm: User profile owns them.
- Removing a help doc from the index: see KN-SDOC-03.

### Design Principles
1. **Delete only Knowledge's share.** Never another service's data, and never `scope = system` rows.
2. **Idempotent.** The same event processed twice gives the same result and publishes the same completion.
3. **No user data in logs or events.** Only the `userId`, counts and IDs.

---

## 2. Workflow

```
[UserAccountDeleted on Knowledge's SQS queue] ──► KN-DEL-01
    │
[One transaction as kn_delete: set user context, delete own documents (chunks cascade)] ──► KN-DEL-02
    │
[Publish UserDataDeleted(userId, knowledge)] ──► KN-DEL-03
    │
[Failure → retry, then DLQ + alarm] ──► KN-DEL-04
```

---

## 3. Requirements Index

| ID | Title | Area | Priority | Status |
|---|---|---|---|---|
| KN-DEL-01 | Consume UserAccountDeleted | Data | MVP | Proposed (no Knowledge service yet) |
| KN-DEL-02 | Delete the user's documents and chunks | Security | MVP | Proposed (no Knowledge service yet) |
| KN-DEL-03 | Publish UserDataDeleted | Data | MVP | Proposed (no Knowledge service yet) |
| KN-DEL-04 | Retry, dead-letter and alarm | Reliability | MVP | Proposed (no Knowledge service yet) |

---

## 4. Requirements

### KN-DEL-01: Consume UserAccountDeleted  `Priority: MVP`

**Requirement:** Knowledge subscribes to `UserAccountDeleted(userId)` through an EventBridge rule to its own SQS queue, consumed by the deletion Lambda with batch size 1.
**Acceptance Criteria:**
- [Happy] An event published by User profile is processed within 5 minutes.
- [Alt] An event whose `source` is not User profile is rejected by the EventBridge rule and never reaches the queue.
- [Fail] An event without a valid `userId` is sent straight to the DLQ (no retries) and counted as `invalid_event`.
**Refs:** architecture doc "Events" and "Delete an account"

### KN-DEL-02: Delete the user's documents and chunks  `Priority: MVP`

**Requirement:** In one Data API transaction as role `kn_delete`, set `app.current_user_id` to the event's `userId` and delete every `kn_documents` row with `scope = 'user'` and that `user_id`; chunks are deleted by cascade. Until user documents ship, this deletes 0 rows and still succeeds.
**Acceptance Criteria:**
- [Happy] With 2 seeded documents and 12 chunks for user A, all are gone afterwards, and counts of 2 and 12 are recorded.
- [Alt] User B's rows and all `system` rows are unchanged (row counts and hashes match before and after).
- [Alt] A user who owns nothing gives counts of 0 and 0, and the handler succeeds.
- [Alt] Processing the same event again deletes 0 rows and succeeds.
- [Fail] If the transaction fails, nothing is deleted and the message returns to the queue (KN-DEL-04).
**Refs:** KN-VS-02 (`kn_delete`); KN-VS-03; invariant 11

### KN-DEL-03: Publish UserDataDeleted  `Priority: MVP`

**Requirement:** After the delete commits, Knowledge publishes `UserDataDeleted` (Appendix A). The SQS message is deleted only after the publish succeeds.
**Acceptance Criteria:**
- [Happy] User profile receives `UserDataDeleted` with `service = "knowledge"` and the deletion counts.
- [Alt] If the publish fails after the delete committed, the retry re-runs the delete (0 rows) and publishes again; a duplicate `UserDataDeleted` is acceptable.
- [Fail] A publish failure after all retries sends the message to the DLQ (KN-DEL-04).
**Refs:** Appendix A

### KN-DEL-04: Retry, dead-letter and alarm  `Priority: MVP`

**Requirement:** A failed message is retried by SQS up to 5 times (visibility timeout 60 s), then moved to the Knowledge deletion DLQ, kept for 14 days. Logs carry `userId`, the request ID, counts and the error code only.
**Acceptance Criteria:**
- [Happy] A transient Aurora error is retried and the message completes, with no DLQ entry.
- [Alt] Moving a DLQ message back to the queue (redrive) completes the deletion and publishes `UserDataDeleted`.
- [Fail] An alarm fires when the DLQ holds 1 or more messages, or when the oldest queue message is older than 1 hour.
**Refs:** architecture doc 3.6 Recover and 3.7 Observe

---

## 5. Open Questions (consolidated)

| # | Question | Blocks |
|---|---|---|
| 1 | Does User profile need deletion counts in `UserDataDeleted`, or only completion? | KN-DEL-03 |

---

## Appendix A: `UserDataDeleted` event

Produced by: Knowledge (code). Consumed by: User profile.

```json
{
  "source": "fintracker.knowledge",
  "detail-type": "UserDataDeleted",
  "detail": {
    "userId": "u_123",
    "service": "knowledge",
    "deletedDocuments": 0,
    "deletedChunks": 0,
    "completedAt": "2026-10-20T19:40:00Z"
  }
}
```
