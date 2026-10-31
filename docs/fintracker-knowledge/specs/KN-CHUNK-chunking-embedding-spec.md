# KN-CHUNK: Chunking and Embedding

| Field | Value |
|---|---|
| Product | FinTracker |
| Prefix | KN-CHUNK |
| File | fintracker-knowledge/specs/KN-CHUNK-chunking-embedding-spec.md |
| Owner | Van Vo |
| Status | Draft |
| Last updated | 2026-10-30 |

---

## 1. Overview

### Problem
Retrieval quality depends on how text is split and which model embeds it, and both will be tuned many times. Ingestion and retrieval must also use exactly the same model, because vectors from different models can't be compared. Keeping these rules in one spec means a tuning change touches one file, and the quality gate that approves it lives beside it.

### Goals
- Every chunk can be cited: it carries its source path and heading.
- recall@5 ≥ 0.90 on the golden question set before any chunking or model change ships.
- The owner can measure retrieval quality on demand against the real embedding model and the real help docs, and see how far each question is from failing (rank and score), not only whether it passed.
- A model change never leaves retrieval comparing vectors from two models.

### Non-Goals
- When ingestion runs and how it retries: see KN-SDOC.
- How a query is searched: see KN-RET (it reuses the embedding call defined here).
- Redaction of user documents: see KN-UDOC (later).
- Keyword or hybrid search (service decision S6, revisit later).

### Design Principles
1. **One active embedding model.** Ingestion and retrieval both read the same `active_embedding_model` setting; nothing hard-codes a model ID.
2. **Values are config, rules are spec.** Sizes and thresholds below are defaults in the service config; changing one is a config change that must pass KN-CHUNK-04.
3. **Deterministic.** The same input text and config always produce the same chunks, in the same order.

---

## 2. Workflow

```
[Markdown doc in] ──► KN-CHUNK-01
    │
[Split by headings, size limits, metadata] ──► KN-CHUNK-01
    │
[Embed each chunk with the active model] ──► KN-CHUNK-02
    │
[Chunks out to the ingestion workflow (KN-SDOC)]

[Change to chunking or model] ──► KN-CHUNK-04 (quality gate)
    │
[Every pull request: replay with recorded vectors, free. Owner-started live run: index help docs, run golden + negative sets, report, refresh recording] ──► KN-CHUNK-05
    │
[Model change: build new vectors, then switch] ──► KN-CHUNK-03
```

---

## 3. Requirements Index

| ID | Title | Area | Priority | Status |
|---|---|---|---|---|
| KN-CHUNK-01 | Heading-based chunking | Data | MVP | Implemented |
| KN-CHUNK-02 | Embedding model and call | AI | MVP | In progress |
| KN-CHUNK-03 | Embedding model switch | Reliability | MVP | In progress |
| KN-CHUNK-04 | Retrieval quality gate | Quality | MVP | In progress |
| KN-CHUNK-05 | Live retrieval evaluation and replay | Quality | MVP | Proposed |

---

## 4. Requirements

### KN-CHUNK-01: Heading-based chunking  `Priority: MVP`

**Requirement:** A Markdown doc is split at H1–H3 headings. Each chunk keeps the doc's source path and its heading path. Sections longer than the maximum are split at paragraph boundaries; sections shorter than the minimum are merged with the next section under the same parent heading. Limits are in Appendix A.
**Acceptance Criteria:**
- [Happy] A doc with three H2 sections of 200 tokens each produces 3 chunks, each with `heading_path` like `Statements > CSV mapping`.
- [Alt] A 1,500-token section produces chunks of ≤ 600 tokens each, split at paragraph boundaries, with 60 tokens of overlap between neighbours.
- [Alt] A 30-token section is merged into the next sibling section; a doc's last short section merges into the previous one.
- [Alt] Front matter and HTML comments are removed before splitting; code blocks are never split in the middle.
- [Alt] Running the chunker twice on the same input produces identical chunks (same text, order and `heading_path`).
- [Fail] A doc with no headings becomes chunks with `heading_path` set to the doc title (or the file name when there is no title), never an error.
**Refs:** Appendix A; service decision S3

### KN-CHUNK-02: Embedding model and call  `Priority: MVP`

**Requirement:** Chunks and queries are embedded with the model named in `active_embedding_model` (default in Appendix A), through Amazon Bedrock, using Knowledge's IAM role only (invariant 10). The text embedded is `heading_path` + a blank line + chunk text, so headings shape the vector.
**Acceptance Criteria:**
- [Happy] Each chunk gets a vector with the configured dimension count, normalized, and its `embedding_model` set to the active model ID.
- [Alt] Text over the model's input limit is rejected before the call; this can't happen for chunks within KN-CHUNK-01 limits, and query length is capped by KN-RET-02.
- [Fail] A throttled or failed Bedrock call is retried 3 times with backoff (1 s, 2 s, 4 s), then fails the caller's step with `embedding_unavailable`. No partial vector is written.
- [Fail] Any non-Knowledge role invoking the embedding model is denied by IAM.
- [Alt] No unit or CI test calls Bedrock. Tests give `Embedder` a fake client, or the recorded client of KN-CHUNK-05; only the owner's live run (KN-CHUNK-05) makes paid calls.
**Refs:** Appendix A; KN-VS-01 (`embedding`, `embedding_model`); invariant 10; service decision S5

### KN-CHUNK-03: Embedding model switch  `Priority: MVP`

**Problem:** Re-embedding doc by doc in place would leave the index holding two models' vectors, and queries embedded with one model would be compared to vectors from the other.
**Requirement:** Retrieval searches only chunks whose `embedding_model` equals `active_embedding_model`. To change models, a full rebuild (KN-SDOC-05) writes every doc under the new model alongside the old, KN-CHUNK-04 must pass on the new vectors, then the setting is switched, and the old model's rows are deleted.
**Acceptance Criteria:**
- [Happy] During a rebuild, retrieval keeps returning old-model results only; after the switch, new-model results only.
- [Alt] If the rebuild or the quality gate fails, the setting is not switched and the new model's rows are deleted.
- [Fail] If any doc has no chunks under the target model, the switch is refused and names the missing docs.
**Refs:** KN-SDOC-05; KN-RET-04; KN-VS-01 (unique key includes `embedding_model`)

### KN-CHUNK-04: Retrieval quality gate  `Priority: MVP`

**Requirement:** A golden set of at least 30 help-doc questions, each with its expected source paths, is run through `retrieve` (k = 5) whenever chunking config, the embedding model or the retrieval query changes. The change is blocked if recall@5 is below 0.90, or more than 0.05 below the last accepted run.
**Acceptance Criteria:**
- [Happy] A change with recall@5 ≥ 0.90 and no drop > 0.05 passes, and its score is stored as the new baseline. Only a passing live run (KN-CHUNK-05) stores a baseline; CI replays compare against it and never write it.
- [Alt] A question counts as a hit when any expected source path appears in the top 5.
- [Alt] The report lists each missed question and the paths that were returned instead.
- [Fail] recall@5 below threshold fails the CI job or the model switch (KN-CHUNK-03), with the score and the baseline in the message.
- [Alt] On every pull request CI runs the gate as a replay test (KN-CHUNK-05): no Bedrock call, recorded vectors.
- [Alt] The golden set is written and kept by the owner (45 questions today). Unanswered questions logged by the AI assistant do not feed it automatically; they are reviewed weekly and added as synthetic questions (AI-EVAL-07).
**Refs:** Appendix B; architecture doc "Evaluate retrieval quality"

### KN-CHUNK-05: Live retrieval evaluation and replay  `Priority: MVP`

**Problem:** KN-CHUNK-04 only says pass or fail at recall@5. With 12 help docs (a few dozen chunks), recall@5 will sit near 100% and hide weak retrieval, and the 0.35 help-doc score threshold in AI-CHAT is still a guess. Measuring this against the real embedding model costs money, so it must be rare, deliberate and owner-only, while everything that runs on every change must be free.
**Requirement:** Three layers, from free to paid:
1. **Unit tests** give `Embedder` a fake client (KN-CHUNK-02). No Bedrock.
2. **Replay tests** (every pull request) run the real chunker, a real pgvector database, the real retrieval service and the gate of KN-CHUNK-04 with a recorded Bedrock client (`RecordedBedrock`) that answers from a saved recording. No Bedrock.
3. **The live run** (owner only) indexes the help docs with the real embedding model, runs the golden and negative questions through the real retrieval service (k = 5), writes the report (Appendix C) and refreshes the recording.

The recording holds one vector per embedded text, keyed by the model and the SHA-256 of the exact text sent, for every chunk of the snapshot corpus and every golden and negative question. The snapshot corpus is a copy of `docs/help/**` stored beside the recording, so editing a help doc never breaks CI; the live run refreshes both.
**Acceptance Criteria:**
- [Happy] **Live run report:** for each golden question, the rank and score of the first expected path (or `miss`) and the returned paths with scores; the summary has recall@5, hit@1, hit@3 and MRR. For each negative question, the top score. A threshold sweep from 0.20 to 0.60 in steps of 0.05 shows recall@5 after dropping chunks below each value and how many negatives still return a chunk at or above it.
- [Happy] **Replay:** a pull request runs the full pipeline against the recording and reports the same figures as the last live run, within 0.001 on every score.
- [Alt] **Stamp:** the report and the recording carry the embedding model, dimensions, chunk-config hash, embedding input format version, retrieval query version, golden-set hash, snapshot-corpus hash, chunk count per document and the git commit (with a `dirty` flag).
- [Alt] **Owner-only runs:** a live run starts in one of two ways. In CI, the manual `rag-eval` workflow runs in a protected GitHub environment (required reviewer = owner, Van) and assumes a role through OIDC from that environment only; the role may invoke only the Titan model. Locally, the owner runs the command from their own terminal with their own named AWS profile (`--aws-profile` or `RAG_EVAL_AWS_PROFILE`); the OIDC role and the read-only pull-request role are for CI and are not needed locally. The command refuses to start under pytest, when an AI-agent environment marker is set, without an interactive terminal (local), with static AWS credential variables in the environment (local), or in CI outside a manual run in the `rag-eval` environment. Before any call the owner types the number of calls to approve. These checks are speed bumps: the real control is that no other CI job, local setup or AI agent holds Bedrock credentials. An AI model or agent never starts a live run.
- [Alt] **Cost guard:** the live run has a dry run that prints the number of embedding calls and the estimated cost without calling Bedrock; it aborts before any call if the worst-case estimate is above the cap (default $0.50) unless the owner confirms, and stops mid-way if actual spend passes it. A call that timed out is counted at its worst-case cost. There are no tiers: the whole set costs cents.
- [Alt] **Results:** every live report is kept, pass or fail, in the private evaluation results bucket (Knowledge's own Terraform: roles and one S3 bucket, modelled on the AI assistant's `eval_results` module) under `results/`; a passing run also leaves a pass record under `passes-by-version/<version_key>/` carrying the stamp and the recording hash. Records are never overwritten and never expire. Reports hold ids, document paths, ranks and scores, never chunk or question text. Pull requests read the bucket through a read-only role that has no Bedrock permission.
- [Alt] **Eval-required check:** on a pull request that changes any stamp component (chunk config, embedding model or input format, retrieval query, golden set), CI blocks the merge until a passing live run record exists for exactly those versions. A change to a help document alone does not need one.
- [Alt] **Throwaway database:** the live run indexes the snapshot corpus into a temporary pgvector database started for that run (Testcontainers) and discards it, so the owner's local `knowledge` database is never read or changed. Only a passing run replaces the committed fixture and the baseline; a failing or aborted run leaves both as they were.
- [Alt] **Replay mode for the running service:** with `KNOWLEDGE_EMBEDDER=replay` and `KNOWLEDGE_REPLAY_DIR`, the service and the index command embed from the recording with no AWS credentials. Only the recorded texts (the golden and negative questions and the snapshot chunks) can be embedded; any other text fails at once as `embedding_unavailable` (503) with a `replay_miss` log, with no retries. Replay mode is refused when an AWS runtime variable is set. The local Docker stack uses it and holds no AWS credentials.
- [Fail] A replay that needs a text that is not in the recording (a changed chunk or a new question) fails with `replay_miss` naming the document path or question id, and never calls Bedrock.
- [Fail] A live run with missing AWS credentials, or an embedding failure after KN-CHUNK-02's retries, exits non-zero and writes no report that looks like a pass.
- [Fail] A golden `expected_paths` entry that is not an indexed document, or a document that produced no chunks, stops the run before any query and names the path.
- [Fail] A test fails if any code path other than the live-run command can reach the real Bedrock client from the test suite. The test configuration clears AWS credentials and makes creating a Bedrock client raise, and a source check allows only the production container's builder and the live command to name a Bedrock service.
**Refs:** KN-CHUNK-02; KN-CHUNK-04; KN-RET-04; KN-FAPI-05, -06, -07; AN-FS-20, AN-FS-22 (the rules this copies); AI-EVAL-09. Tuning problems and the fixes chosen are logged (problem → choice) in `eval/retrieval-eval-log.md`, not in the architecture doc.

---

## 5. Open Questions (consolidated)

| # | Question | Blocks |
|---|---|---|
| 1 | Is 1,024 dimensions needed, or would 512 keep recall@5 ≥ 0.90 at lower storage cost? | KN-CHUNK-02 |

---

## Appendix A: Config defaults

Produced by: service config (code). Changing any value requires KN-CHUNK-04 to pass.

| Setting | Default |
|---|---|
| `split_headings` | H1, H2, H3 |
| `max_chunk_tokens` | 600 |
| `min_chunk_tokens` | 50 |
| `overlap_tokens` (paragraph splits only) | 60 |
| `active_embedding_model` | `amazon.titan-embed-text-v2:0` |
| `embedding_dimensions` | 1024 |
| `embedding_normalize` | true |

---

## Appendix B: Golden question set

Produced by: developer (user). Stored in the Knowledge repo as `eval/golden-questions.yaml`.

```yaml
- id: GQ-001
  question: "How do I confirm a CSV column mapping?"
  expected_paths:
    - help/statements/csv-mapping.md
```

Optional fields used only by the AI assistant's live chat evaluation (AI-EVAL-09) are ignored by this gate: `must_mention` on golden questions and `expected_outcome` on negatives. The negative set (`eval/golden-negative-questions.yaml`, ids `NQ-nnn`) holds questions the docs must not answer: features that don't exist, out-of-scope advice and unrelated questions. It is not part of recall@5.

---

## Appendix C: Live retrieval evaluation report

Produced by: the live evaluation command (code). One JSON file per run in the evaluation results store, synced to `eval/rag_eval_results/`. Holds paths, ranks, scores and counts; never chunk text. The recording is a separate fixture (`tests/fixtures/rag/`) holding vectors, not text.

| Field | Example |
|---|---|
| `run_id`, `started_at`, `github_run_id` | `rag-2026-10-30T15-40Z`; the last is null outside GitHub Actions |
| `stamp` | `{ "embedding_model": "amazon.titan-embed-text-v2:0", "dimensions": 1024, "chunk_config": {…}, "docs": 12, "chunks_per_doc": {"help/budgets.md": 4, …}, "docs_commit": "9f2c1ab", "docs_dirty": false, "golden_hash": "…" }` |
| `summary` | `{ "recall_at_5": 0.98, "hit_at_1": 0.84, "hit_at_3": 0.96, "mrr": 0.90 }` |
| `questions[]` | `{ "id": "GQ-022", "first_expected_rank": 1, "first_expected_score": 0.74, "returned": [ {"path": "…", "heading_path": "…", "score": 0.74} ] }` |
| `negatives[]` | `{ "id": "NQ-001", "top_score": 0.41, "top_path": "…" }` |
| `threshold_sweep[]` | `{ "threshold": 0.35, "recall_at_5": 0.96, "negatives_leaking": 2 }` |
| `baseline` | `{ "recall_at_5": 0.98, "change": 0.00, "gate": "pass" }` |
