# KN-CHUNK: Chunking and Embedding

| Field | Value |
|---|---|
| Product | FinTracker |
| Prefix | KN-CHUNK |
| File | fintracker-knowledge/specs/KN-CHUNK-chunking-embedding-spec.md |
| Owner | Van Vo |
| Status | Draft |
| Last updated | 2026-10-20 |

---

## 1. Overview

### Problem
Retrieval quality depends on how text is split and which model embeds it, and both will be tuned many times. Ingestion and retrieval must also use exactly the same model, because vectors from different models can't be compared. Keeping these rules in one spec means a tuning change touches one file, and the quality gate that approves it lives beside it.

### Goals
- Every chunk can be cited: it carries its source path and heading.
- recall@5 ≥ 0.90 on the golden question set before any chunking or model change ships.
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
- [Happy] A change with recall@5 ≥ 0.90 and no drop > 0.05 passes, and its score is stored as the new baseline.
- [Alt] A question counts as a hit when any expected source path appears in the top 5.
- [Alt] The report lists each missed question and the paths that were returned instead.
- [Fail] recall@5 below threshold fails the CI job or the model switch (KN-CHUNK-03), with the score and the baseline in the message.
**Open Questions:** Who writes the first 30 questions, and should unanswered questions logged by the AI assistant feed the set automatically?
**Refs:** Appendix B; architecture doc "Evaluate retrieval quality"

---

## 5. Open Questions (consolidated)

| # | Question | Blocks |
|---|---|---|
| 1 | Who writes the first 30 golden questions, and should unanswered questions logged by the AI assistant feed the set? | KN-CHUNK-04 |
| 2 | Is 1,024 dimensions needed, or would 512 keep recall@5 ≥ 0.90 at lower storage cost? | KN-CHUNK-02 |

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
