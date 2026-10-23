# KN-SDOC: System Docs Indexing

| Field | Value |
|---|---|
| Product | FinTracker |
| Prefix | KN-SDOC |
| File | fintracker-knowledge/specs/KN-SDOC-system-docs-indexing-spec.md |
| Owner | Van Vo |
| Status | Draft |
| Last updated | 2026-10-20 |

---

## 1. Overview

### Problem
Chat can only answer how-to questions from help docs if the index matches what's merged in Git. A manual re-index step gets forgotten, and a failed run must never leave a doc half-indexed or remove a good version that users can still search.

### Goals
- The index matches main within 10 minutes of a merge that changes help docs.
- Re-running a merge, or replaying an event, changes nothing.
- One bad doc never blocks the rest, and its previous version stays searchable.

### Non-Goals
- How docs are split and embedded: see KN-CHUNK.
- Table definitions and isolation: see KN-VS.
- User-uploaded documents: see KN-UDOC (later).

### Design Principles
1. **Git is the source of truth.** The S3 system-docs prefix holds copies only; the index can be rebuilt from any commit.
2. **Only CI writes system docs.** No other role can change what every user reads.
3. **Per-doc atomic replace.** A doc's new version and the removal of its old version happen in one transaction.

---

## 2. Workflow

```
[Merge to main changes help/**] ──► KN-SDOC-01
    │
[CI uploads changed docs + manifest to S3] ──► KN-SDOC-01
    │
[Manifest event starts the workflow, one branch per doc] ──► KN-SDOC-02
    │
[Path + hash unchanged → skip] ──► KN-SDOC-02
    │
[Chunk + embed (KN-CHUNK-01, KN-CHUNK-02)]
    │
[Replace in one transaction] ──► KN-SDOC-03
    │
[Deleted paths → remove document and chunks] ──► KN-SDOC-03
    │
[Record run] ──► KN-SDOC-06
    │
[Failure in a branch → retry, keep old version] ──► KN-SDOC-04

[Manual full rebuild] ──► KN-SDOC-05
```

---

## 3. Requirements Index

| ID | Title | Area | Priority | Status |
|---|---|---|---|---|
| KN-SDOC-01 | CI upload of changed and deleted docs | Security | MVP | In progress |
| KN-SDOC-02 | Ingestion trigger and change detection | Data | MVP | In progress |
| KN-SDOC-03 | Atomic replace and delete | Data | MVP | Implemented |
| KN-SDOC-04 | Per-doc failure isolation and retry | Reliability | MVP | Implemented |
| KN-SDOC-05 | Full rebuild | Reliability | MVP | Implemented |
| KN-SDOC-06 | Run record and freshness | Observability | MVP | In progress |

---

## 4. Requirements

### KN-SDOC-01: CI upload of changed and deleted docs  `Priority: MVP`

**Requirement:** After a merge to main that changes files under `help/`, CI assumes its deploy role through OIDC, uploads each changed `.md` file to `s3://<knowledge-bucket>/system-docs/<path>`, and then uploads a manifest (Appendix A) to `system-docs/_manifests/<commit>.json` listing changed and deleted paths. Only CI's deploy role may write the `system-docs/` prefix.
**Acceptance Criteria:**
- [Happy] A merge changing 2 docs and deleting 1 uploads 2 files and one manifest listing all 3 paths.
- [Alt] A merge that changes no file under `help/` uploads nothing and starts no workflow.
- [Alt] Non-`.md` files and files over 200 KB are left out of the upload; the CI job lists them as skipped and still succeeds.
- [Fail] A write to `system-docs/` by any role other than CI's deploy role is denied by the bucket policy.
- [Fail] If an upload fails, CI does not write the manifest and the job fails, so no partial run starts.
**Open Questions:** Is a manifest file acceptable, or should each S3 object event start its own execution?
**Refs:** Appendix A; architecture doc "Update a help doc"

### KN-SDOC-02: Ingestion trigger and change detection  `Priority: MVP`

**Requirement:** A manifest's S3 event starts one Step Functions execution, named after the commit, that processes each listed path as its own branch (max concurrency 4). For a changed path, the branch computes the SHA-256 of the uploaded file and skips the doc if `kn_documents` already holds that path and hash under the active model.
**Acceptance Criteria:**
- [Happy] A manifest with 3 changed paths produces 3 branches, each ending as `indexed` or `skipped`.
- [Alt] Replaying the same manifest event starts no second execution (the execution name is already used), and the index is unchanged.
- [Alt] A path whose hash matches the indexed version ends as `skipped`, with no embedding calls.
- [Fail] A listed changed path missing from S3 ends its branch as `failed: source_missing`; other branches continue.
**Refs:** KN-VS-01 (`content_hash`); KN-CHUNK-03 (active model)

### KN-SDOC-03: Atomic replace and delete  `Priority: MVP`

**Requirement:** For a changed doc, one transaction (as role `kn_ingest`) writes the new `kn_documents` row and its chunks with `scope = system`, `user_id` null and `source_commit`, then deletes the previous version. For a deleted path, one transaction deletes its document row; its chunks follow by cascade.
**Acceptance Criteria:**
- [Happy] After the transaction, a search returns only the new version's chunks for that path.
- [Alt] During the transaction, concurrent searches see the old version only, never a mix or nothing.
- [Alt] A deleted path that isn't indexed is a no-op, ending as `deleted: 0`.
- [Fail] If the transaction fails, nothing is committed and the old version stays searchable.
**Refs:** KN-VS-01; KN-VS-02 (`kn_ingest`); service decision S4

### KN-SDOC-04: Per-doc failure isolation and retry  `Priority: MVP`

**Requirement:** Each branch retries a failed step 3 times with backoff (2 s, 4 s, 8 s). A branch that still fails is marked `failed` with an error code (Appendix B), and the execution continues with the other branches.
**Acceptance Criteria:**
- [Happy] A transient Bedrock throttle on one doc is retried and the doc ends as `indexed`.
- [Alt] With 1 of 5 docs failing permanently, 4 docs are indexed and the run ends as `partial`.
- [Fail] A permanently failed doc keeps its previous version searchable, and raises the alarm in KN-SDOC-06.
- [Fail] Aurora resuming from pause (dev) is retried like any transient error; the first retry waits at least 2 s.
**Refs:** Appendix B; KN-CHUNK-02 (embedding retries)

### KN-SDOC-05: Full rebuild  `Priority: MVP`

**Requirement:** A manual workflow input `{ "mode": "rebuild", "commit": "<sha>", "embedding_model": "<id>" }` re-indexes every doc under `help/` at that commit, ignoring the hash skip. With a new model ID, the new chunks are written alongside the old ones for KN-CHUNK-03.
**Acceptance Criteria:**
- [Happy] A rebuild of 40 docs ends with 40 docs `indexed` under the requested model, and a run record.
- [Alt] A rebuild with the active model replaces each doc in place, as in KN-SDOC-03.
- [Alt] Only CI's deploy role or the developer's admin role can start a rebuild.
- [Fail] A rebuild with any failed doc ends as `partial`, and KN-CHUNK-03 refuses the model switch.
**Refs:** KN-CHUNK-03; architecture doc 3.6 Recover

### KN-SDOC-06: Run record and freshness  `Priority: MVP`

**Requirement:** Each execution writes one run record (Appendix C) with the commit and per-status counts, and emits metrics. Logs carry paths, counts and error codes, never doc or chunk text.
**Acceptance Criteria:**
- [Happy] A finished run records `status`, `commit`, and counts of indexed, skipped, deleted and failed docs, and total chunks written.
- [Alt] A `GET /internal/index-status` call (Knowledge-internal role only) returns the last indexed commit and its finish time.
- [Fail] An alarm fires when any run ends `partial` or `failed`, or when no successful run has followed a manifest within 30 minutes.
**Refs:** Appendix C; architecture doc 3.7 Observe

---

## 5. Open Questions (consolidated)

| # | Question | Blocks |
|---|---|---|
| 1 | Is a manifest file acceptable, or should each S3 object event start its own execution? | KN-SDOC-01 |

---

## Appendix A: Manifest

Produced by: CI (code).

```json
{
  "commit": "9f2c1ab",
  "merged_at": "2026-10-20T18:04:00Z",
  "changed": ["help/statements/csv-mapping.md"],
  "deleted": ["help/legacy/old-import.md"]
}
```

---

## Appendix B: Branch outcomes

| Outcome | Meaning |
|---|---|
| `indexed` | New version written |
| `skipped` | Same path and hash already indexed |
| `deleted: <n>` | Document removed (n = 0 or 1) |
| `failed: source_missing` | Listed in the manifest but not in S3 |
| `failed: embedding_unavailable` | Bedrock failed after retries |
| `failed: database_unavailable` | Aurora failed after retries |
| `failed: invalid_source` | File not UTF-8 or over size limit |

---

## Appendix C: `kn_index_runs`

Produced by: ingestion workflow (code). Written as `kn_ingest`.

| Column | Type |
|---|---|
| `run_id` | `uuid` PK |
| `mode` | `text` (`incremental` / `rebuild`) |
| `commit` | `text` |
| `embedding_model` | `text` |
| `status` | `text` (`succeeded` / `partial` / `failed`) |
| `docs_indexed`, `docs_skipped`, `docs_deleted`, `docs_failed`, `chunks_written` | `int` |
| `started_at`, `finished_at` | `timestamptz` |
