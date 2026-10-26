# DP-MAP: CSV Column Mapping

| Field | Value |
|---|---|
| Product | FinTracker |
| Prefix | DP-MAP |
| File | fintracker-data-pipelines/specs/DP-MAP-csv-column-mapping-spec.md |
| Owner | Van Vo |
| Status | Draft |
| Last updated | 2026-10-21 |

Extends DP-ING-01 ("CSV Bank-Specific Column Mapping", "User Mapping Confirmation Gate"), which stay in force: every CSV still pauses for the user to confirm its columns.

---

## 1. Overview

### Problem
Today one column mapping is kept per bank, and every user's confirmation writes straight into it. That causes three problems:
- One user's mistake, or a deliberate bad mapping, changes the proposal every other user of that bank sees.
- When a bank changes its export format, nothing notices. Users just start correcting the proposal.
- A bank with two export formats (checking and credit card, say) fights over one mapping.

### Goals
- No single user can change another user's proposal.
- A bank's format change is detected and alarmed the first time it's seen.
- When enough different users agree on a new mapping, the system adopts it, without a code deploy.

### Non-Goals
- Skipping the column check for known formats. Every CSV still pauses (DP-ING-01).
- Machine learning for column detection.
- An admin UI. Promotion starts as a notification plus a script.

### Design Principles
1. **The baseline is curated, not crowd-written.** It changes only by promotion (DP-MAP-05), never by a single confirmation.
2. **Mappings are keyed by format, not just by bank.** The key is the bank plus the file's header signature, so formats live side by side.
3. **One user, one vote.** Agreement counts distinct users, never repeated confirmations.

---

## 2. Workflow

```
[CSV arrives → compute header signature] ──► DP-MAP-01
    │
[Propose: user's own → baseline for signature → nearest baseline → defaults] ──► DP-MAP-02
    │
[New signature for a known bank → BANK_FORMAT_CHANGED alarm] ──► DP-MAP-04
    │
[User confirms → saves their own mapping + one vote] ──► DP-MAP-03
    │
[Enough distinct users agree → promote to baseline] ──► DP-MAP-05
    │
[Account deleted → user's mappings and votes removed] ──► DP-MAP-06
```

---

## 3. Requirements Index

| ID | Title | Area | Priority | Status |
|---|---|---|---|---|
| DP-MAP-01 | Header signature | Data | MVP | Implemented |
| DP-MAP-02 | Proposal order | Data | MVP | Implemented |
| DP-MAP-03 | Confirmation saves a personal mapping and a vote | Data | MVP | Implemented |
| DP-MAP-04 | Detect a bank's format change | Observability | MVP | Implemented |
| DP-MAP-05 | Promote an agreed mapping to the baseline | Data | MVP (notify), Later (automatic) | Implemented |
| DP-MAP-06 | Delete a user's mappings and votes | Security | MVP | Implemented |

---

## 4. Requirements

### DP-MAP-01: Header signature  `Priority: MVP`

**Requirement:** For every CSV, the Gatekeeper computes a header signature:
1. normalize each header: trim, lowercase, collapse whitespace;
2. sort the headers;
3. join them with `|`;
4. take the first 16 hex characters of the SHA-256 hash.

Column order and letter case don't change the signature. Adding, removing or renaming a column does.
**Acceptance Criteria:**
- [Happy] `Transaction Date, Description, Amount` and `amount,transaction date,DESCRIPTION` give the same signature.
- [Alt] Adding a `Memo` column gives a new signature.
- [Fail] A CSV with duplicate header names is rejected with `INVALID_CSV_FORMAT`, as today.

### DP-MAP-02: Proposal order  `Priority: MVP`

**Requirement:** The Gatekeeper proposes the first mapping found, in this order:
1. the user's own mapping for this bank and signature;
2. the baseline for this bank and signature;
3. the baseline for the same bank whose headers overlap most with this file (at least 2 of the 3 required fields);
4. the default names `date`, `merchant`, `amount`.

It stores where the proposal came from (`USER`, `BASELINE`, `NEAREST_BASELINE` or `DEFAULT`) on the job.
**Acceptance Criteria:**
- [Happy] A user who corrected Chase's mapping last month gets their own mapping proposed, even though the baseline differs.
- [Alt] A user with no mapping of their own gets the baseline.
- [Alt] The dialog shows "Most users map *Posting Date* to Date" when the user's own mapping differs from the baseline for the same signature.
- [Fail] If the mapping table can't be read, the proposal falls back to the defaults and the dialog still opens. The column check never fails because of the proposal.

### DP-MAP-03: Confirmation saves a personal mapping and a vote  `Priority: MVP`

**Requirement:** Confirming the columns:
- saves the mapping as the user's own for this bank and signature;
- records one vote: the user, the signature and a hash of the confirmed mapping. A later vote from the same user replaces their earlier one.

A confirmation never writes the baseline. This replaces today's write-back to the bank mapping.
**Acceptance Criteria:**
- [Happy] User A changes *Posting Date* to *Transaction Date*. User A's next upload proposes *Transaction Date*. User B's proposal is unchanged.
- [Alt] Confirming the proposal unchanged still records a vote. Agreement counts too.
- [Fail] If saving the mapping or the vote fails, the error is logged and the import still resumes. Losing a vote must never block an import.

### DP-MAP-04: Detect a bank's format change  `Priority: MVP`

**Requirement:**
- When a CSV's signature has no baseline for a bank that has at least one baseline, the Gatekeeper logs `BANK_FORMAT_CHANGED` with the bank id and the new signature, never the headers. A CloudWatch metric filter alarms on it.
- The service also publishes the share of confirmations per bank in which the user changed the proposal. An alarm fires when it rises above 30% over 7 days with at least 5 confirmations.

**Acceptance Criteria:**
- [Happy] Chase adds a `Memo` column. The first upload in the new format raises `BANK_FORMAT_CHANGED` for Chase.
- [Alt] A bank with no baseline at all raises nothing. It's an unknown bank, not a changed format.
- [Alt] The same new signature alarms once per day at most.

### DP-MAP-05: Promote an agreed mapping to the baseline  `Priority: MVP (notify), Later (automatic)`

**Requirement:**
- **When it's checked:** after each confirmation, against that signature's votes.
- **When a mapping qualifies:** at least 3 distinct users voted for it for the same bank and signature within 30 days, and at least 80% of that signature's votes in the window agree with it.
- **Phase 1 (MVP):** the pipeline notifies the owner (SNS) with the bank, the signature, the mapping and the vote counts. The owner promotes it with a script.
- **Phase 2 (Later):** the pipeline promotes a qualifying mapping on its own.
- **Old baselines stay,** because banks may serve old and new formats at the same time.
- **Every promotion records** who or what promoted it, and when.

**Acceptance Criteria:**
- [Happy] 3 different users confirm the same new mapping for Chase's new signature. The owner gets one notification, runs the script, and the 4th user is proposed the new baseline.
- [Alt] One user confirming the same mapping 10 times counts as 1 vote and never qualifies.
- [Alt] 3 votes for mapping X and 2 for mapping Y (60%) don't qualify.
- [Fail] A promotion that would remove a required field (`date`, `merchant`, `amount`) is refused by the script.

**Open Questions:** Are 3 users, 80% and 30 days right for launch volumes? These are proposed defaults, kept as configuration values.

### DP-MAP-06: Delete a user's mappings and votes  `Priority: MVP`

**Requirement:** Personal mappings and votes are keyed by user. They are deleted when the user's account is deleted (the `UserAccountDeleted` handler, proposed app-wide). Baselines keep no user ids, only the vote counts at the time of promotion.
**Acceptance Criteria:**
- [Happy] After account deletion, no item with that user's id remains in the mapping table.
- [Alt] A baseline promoted from that user's vote stays. It holds no personal data.

---

## 5. Open Questions (consolidated)

| # | Question | Blocks |
|---|---|---|
| 1 | Promotion thresholds for launch: 3 users, 80%, 30 days? | DP-MAP-05 |

---

## Appendix A: Bank mapping table (DynamoDB, one table)

Written by the pipeline. The baseline seed comes from today's per-bank baselines, with signatures computed at deploy.

| PK | SK | Attributes | Purpose |
|---|---|---|---|
| `BANK#{bankId}` | `BASELINE#{signature}` | `mapping`, `headers`, `source` (`SEED` / `PROMOTED`), `promotedAt`, `promotedBy`, `voteCount` | Curated mapping per format |
| `USER#{userId}` | `MAP#{bankId}#{signature}` | `mapping`, `confirmedAt` | The user's own mapping |
| `VOTE#{bankId}#{signature}` | `USER#{userId}` | `mappingHash`, `confirmedAt` | One vote per user per format |
| `BANK#{bankId}` | `PROMOTION_NOTICE#{signature}#{mappingHash}` | `notifiedAt` | The owner is told once that a mapping qualifies for promotion (DP-MAP-05); written with a condition so a second confirmation doesn't notify again |
| `STATS#{bankId}` | `DAY#{yyyy-mm-dd}` | `confirmations`, `changed`, `ttl` (10 days) | Daily confirmation counters for the 7-day change share (DP-MAP-04); hold no user ids |

Reads per CSV: one query for the user's mapping, one for the bank's baselines. Votes are read only by the promotion check.

---

## Change Log

| Change | Reason |
|---|---|
| 2026-10-26: Appendix A adds the `PROMOTION_NOTICE#` and `STATS#` item kinds. The proposal function takes the user id (`propose_column_mapping(bucket, csv_s3_key, bank_id, user_id)`) so it can read the user's own mapping first (DP-MAP-02). | Both item kinds were built and are needed: the change share needs daily counters, and the promotion notice must go out once. |
