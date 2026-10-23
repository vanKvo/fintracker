# KN-VS: Vector Store

| Field | Value |
|---|---|
| Product | FinTracker |
| Prefix | KN-VS |
| File | fintracker-knowledge/specs/KN-VS-vector-store-spec.md |
| Owner | Van Vo |
| Status | Draft |
| Last updated | 2026-10-20 |

---

## 1. Overview

### Problem
Every Knowledge workflow (indexing, retrieval, deletion) reads or writes the same document and chunk tables. If the isolation rules live inside each workflow, they get copied and drift, and one missed filter leaks another user's text. This spec defines the tables, scopes and Row-Level Security once, so the other Knowledge specs can depend on them instead of restating them.

### Goals
- One schema and one isolation model for all Knowledge data, enforced by the database rather than by each query.
- An isolation test suite in CI that proves user A can never read user B's rows, and that `scope = system` never returns a user row.
- A schema that holds user documents later (`scope = mine`) without a migration of existing rows.

### Non-Goals
- Chunk sizes, embedding model and dimensions: see KN-CHUNK.
- How rows are written or searched: see KN-SDOC, KN-RET and KN-DEL.
- Storing original files. The Document service owns them (invariant 7).

### Design Principles
1. **The database enforces isolation.** Row-Level Security is forced on every Knowledge table; application filters are a second layer, never the only one.
2. **Two scopes only.** A row is `system` (visible to every user, no owner) or `mine` (one owner). Nothing else.
3. **Least privilege per workflow.** Each workflow connects as its own database role, with only the grants it needs.
4. **Derived data, rebuildable.** Every row can be rebuilt from its source, so there are no backups of the vector tables beyond Aurora's standard ones.

---

## 2. Workflow

```
[Schema migration, deploy step before the new service version] ──► KN-VS-01
    │
[Roles and grants applied] ──► KN-VS-02
    │
[Every session sets user context in the same transaction] ──► KN-VS-03
    │
[RLS decides visible rows: system, or own] ──► KN-VS-03
    │
[Vector index serves filtered search] ──► KN-VS-04
    │
[CI isolation suite runs on every change] ──► KN-VS-05
```

---

## 3. Requirements Index

| ID | Title | Area | Priority | Status |
|---|---|---|---|---|
| KN-VS-01 | Document and chunk schema | Data | MVP | Implemented |
| KN-VS-02 | Database roles and grants | Security | MVP | Implemented |
| KN-VS-03 | Row-Level Security by scope and owner | Security | MVP | Implemented |
| KN-VS-04 | Vector index and filtered-search recall | Data | MVP | Implemented |
| KN-VS-05 | Isolation test suite | Security | MVP | Implemented |

---

## 4. Requirements

### KN-VS-01: Document and chunk schema  `Priority: MVP`

**Problem:** Indexing, retrieval and deletion need one shared definition of a document version and its chunks.
**Requirement:** The `knowledge` database holds `kn_documents` and `kn_chunks` as defined in Appendix A. A document is identified by scope, owner and source path; a version by its content hash. The migration runs as a deploy step before the new service version, never at service startup.
**Acceptance Criteria:**
- [Happy] After migration, both tables, their constraints and the pgvector extension exist in the `knowledge` database.
- [Alt] Inserting a row with `scope = system` and a non-null `user_id`, or `scope = mine` and a null `user_id`, is rejected by a check constraint.
- [Alt] Inserting a second active document with the same `(scope, user_id, source_path)` is rejected by a unique constraint.
- [Alt] Deleting a document row deletes its chunks (`ON DELETE CASCADE`).
- [Fail] A failed migration stops the deploy; the previous service version keeps running on the previous schema.
**Refs:** Appendix A; ADR-006; architecture doc "Migrations"

### KN-VS-02: Database roles and grants  `Priority: MVP`

**Requirement:** Knowledge connects through three database roles, each with only the grants in Appendix B. No other service's role has any grant on the `knowledge` database (invariant 9).
**Acceptance Criteria:**
- [Happy] The ingestion workflow, the retrieve API and the deletion consumer each connect with their own role from Appendix B.
- [Alt] `kn_retrieve` can `SELECT` but an `INSERT`, `UPDATE` or `DELETE` fails with a permission error.
- [Alt] `kn_delete` can delete only `scope = mine` rows; a delete aimed at a `system` row affects 0 rows.
- [Fail] A connection as any non-Knowledge role (e.g., Ledger, Analytics) to the `knowledge` database fails with a permission error.
**Refs:** Appendix B; invariant 9; ADR-003

### KN-VS-03: Row-Level Security by scope and owner  `Priority: MVP`

**Problem:** The RDS Data API runs each call as its own session, so a user context set in one call does not apply to the next.
**Requirement:** RLS is enabled and forced on both tables. A row is visible when `scope = 'system'`, or when `scope = 'mine'` and `user_id = current_setting('app.current_user_id', true)`. Callers set the user context with `set_config('app.current_user_id', :uid, true)` inside the same transaction as their query.
**Acceptance Criteria:**
- [Happy] With the context set to user A, a query returns system rows and user A's rows only.
- [Alt] With no user context set, a query returns system rows only and zero `mine` rows.
- [Alt] With the context set in one Data API call and the query in another call (no transaction), zero `mine` rows are returned.
- [Fail] An attempt to insert or update a `mine` row whose `user_id` differs from the current context is rejected by the RLS `WITH CHECK` policy.
**Refs:** ADR-002; ADR-003; invariant 4

### KN-VS-04: Vector index and filtered-search recall  `Priority: MVP`

**Problem:** Approximate vector search with a filter can silently return fewer than *k* rows, because the index finds the nearest rows first and the filter removes some afterwards.
**Requirement:** `kn_chunks.embedding` has an HNSW index using cosine distance (`m = 16`, `ef_construction = 64`). Search sessions set `hnsw.ef_search = 100` and enable iterative scans (`hnsw.iterative_scan = relaxed_order`) so filtered searches keep scanning until *k* rows pass the filter or the index is exhausted.
**Acceptance Criteria:**
- [Happy] A search for *k* = 5 on a corpus where at least 5 rows pass the filter returns exactly 5 rows.
- [Alt] On a test corpus where 95% of rows belong to other users, a filtered search for *k* = 5 still returns 5 of the caller's rows when they exist.
- [Alt] When fewer than *k* rows pass the filter, the search returns all of them and no error.
- [Fail] If the index is missing or invalid, the CI isolation and recall suite (KN-VS-05) fails the build.
**Open Questions:** Are `ef_search = 100` and iterative scans enough at user-document scale, or will a partial index per scope be needed? (Revisit with KN-UDOC.)
**Refs:** ADR-006 "Index choice"; KN-CHUNK-02 (dimensions)

### KN-VS-05: Isolation test suite  `Priority: MVP`

**Requirement:** An automated suite, run in CI on every change to the Knowledge service or its schema, seeds two users and system rows and proves the isolation rules hold.
**Acceptance Criteria:**
- [Happy] With context user A, no query against either table (select, vector search) returns any of user B's rows.
- [Alt] A search with the scope filter `system` returns zero `mine` rows, even when user rows are nearer to the query vector.
- [Alt] The suite covers both paths: a single Data API transaction, and the no-transaction case from KN-VS-03.
- [Fail] Any leaked row fails the build, and the failure names the test and the table, never the row text.
**Refs:** KN-VS-03; KN-RET-05; architecture doc 3.5 Protect

---

## 5. Open Questions (consolidated)

| # | Question | Blocks |
|---|---|---|
| 1 | Are `ef_search = 100` and iterative scans enough at user-document scale, or is a partial index per scope needed? | KN-VS-04 (Later) |

---

## Appendix A: Tables

Produced by: the schema migration (code).

**`kn_documents`**

| Column | Type | Notes |
|---|---|---|
| `document_id` | `uuid` PK | |
| `scope` | `text` | `system` or `mine` (check constraint) |
| `user_id` | `text` null | Null when `scope = system`; required when `mine` (check constraint) |
| `source_path` | `text` | Repo-relative path for system docs, e.g. `help/statements/csv-mapping.md`; `documentId` for user docs (later) |
| `content_hash` | `char(64)` | SHA-256 of the source bytes |
| `source_commit` | `text` null | Git commit that produced this version (system docs) |
| `embedding_model` | `text` | Model ID used for this version's chunks |
| `chunk_count` | `int` | |
| `indexed_at` | `timestamptz` | |

Unique: `(scope, coalesce(user_id, ''), source_path, embedding_model)`.

**`kn_chunks`**

| Column | Type | Notes |
|---|---|---|
| `chunk_id` | `uuid` PK | |
| `document_id` | `uuid` FK → `kn_documents` | `ON DELETE CASCADE` |
| `scope` | `text` | Copied from the document, so RLS needs no join |
| `user_id` | `text` null | Copied from the document |
| `ordinal` | `int` | Position in the document, from 0 |
| `heading_path` | `text` | e.g. `Statements > CSV mapping > Confirm columns` |
| `text` | `text` | Chunk text (redacted, for user docs) |
| `token_count` | `int` | |
| `embedding` | `vector(<dims from KN-CHUNK-02>)` | |
| `embedding_model` | `text` | Must equal the document's |

---

## Appendix B: Database roles

| Role | Used by | Grants |
|---|---|---|
| `kn_ingest` | Ingestion workflows (KN-SDOC; KN-UDOC later) | `SELECT, INSERT, UPDATE, DELETE` on both tables |
| `kn_retrieve` | Retrieve API (KN-RET) | `SELECT` on both tables |
| `kn_delete` | Account deletion consumer (KN-DEL) | `SELECT, DELETE` on both tables; RLS limits deletes to `scope = mine` rows of the current user |
