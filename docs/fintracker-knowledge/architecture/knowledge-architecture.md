# Knowledge Architecture

| Status | Owner | Last reviewed | Applies to | App architecture |
|---|---|---|---|---|
| Proposed. System help docs first (current focus); user documents later | Van Vo | 2026-10-18 | main | [FinTracker architecture](../../fintracker-architecture/fintracker-architectural-doc.md) |

This document describes how the Knowledge service works and the workflows it owns. Rules that apply to every service are in the app architecture doc. These include identity, events and invariants. Chunk sizes, model IDs and API payloads belong in the Knowledge spec once it exists.

---

## 1. Overview

**Purpose:** Knowledge makes text searchable for the AI assistant, while guaranteeing that a user can only ever retrieve system documents or their own. It owns the **retrieval half of RAG**; the AI assistant owns generation ([ADR-010](../../fintracker-architecture/architectural_decision_records/ADR-010-rag-retrieval-in-knowledge-service.md)).

**Responsibilities**
- **Index system help docs** *(current focus)*: re-index on every merge to main, through CI.
- **Retrieve:** `retrieve(query, scope, k)` returns the most relevant chunks with their source paths. It embeds the query, filters by scope and owner, and re-checks every result.
- **Delete:** remove the chunks of a replaced or removed help doc. Remove a user's documents and chunks when their account is deleted.
- **Measure retrieval quality:** recall@k on a golden question set whenever chunking or the embedding model changes.
- **Index user documents** *(later)*: extract text, redact identifiers, chunk and embed with `scope = mine`.

**Does not do**
- Generate answers, build prompts or call a generation model. The AI assistant does.
- Store original files. The Document service does; Knowledge asks it for a short-lived read link *(later)*.
- Answer questions about the user's numbers. Those go to Ledger and Analytics tools.
- Process bank statements. Statements become transactions, never search text (invariant 8).

**Owns**
- The `knowledge` database (pgvector), holding documents and their chunks with embeddings.
- The system-docs source prefix in S3, copies uploaded by CI. Git stays the source of truth.
- The embedding model configuration.

---

## 2. Architecture and workflows

![Knowledge components](images/knowledge-components.png)

**How to read the diagram**
- **Two inputs:**
  - CI writes help docs, and a storage event starts ingestion.
  - Later, the Document service announces user documents.
- **One output:** the retrieve API, called only by the AI assistant.
- **Only Knowledge's role can read or write the vector tables** (invariant 9), and only Knowledge's role may invoke the embedding model (invariant 10).
- The retrieve API never returns vectors. It returns text, source path, heading and score.

### Workflows

#### Index system help docs *(current focus)*

**Trigger:** CI uploads changed or deleted help docs after a merge to main · **Result:** the index matches the merged docs · **On failure:** the failing doc retries alone, and its previous version stays searchable

![Index system help docs](images/knowledge-index-system-docs.png)

1. CI assumes its deploy role through OIDC and uploads the changed and deleted files to the system-docs prefix.
2. The storage event starts the ingestion workflow, with one branch per doc.
3. Compare path and content hash with the indexed version. If they're unchanged, skip, so re-running a merge changes nothing.
4. Split by headings, keeping the doc path and heading on every chunk.
5. Embed each chunk with the embedding model.
6. In one transaction, write the new version's chunks with `scope = system` and drop the old version's.
7. For deleted files, remove their chunks and document row.
8. Record the indexed commit, chunk counts and any failed docs.

#### Retrieve for chat

**Trigger:** a signed internal request from the AI assistant's `execute_tool` · **Result:** up to *k* chunks with source paths · **On failure:** an error the AI assistant treats as "no docs available", so it answers without them and says so

![Retrieve for chat](images/knowledge-retrieve.png)

1. Check that the caller is on the allow-list. Today only the AI assistant is.
2. Validate the arguments:
   - `scope` must be `system`, or `mine` *(later)*;
   - `k` is capped;
   - the query length is capped.
3. Embed the query text.
4. In one Data API transaction, set the user context and run the vector search with the scope filter. Row-Level Security allows only `scope = system`, or this user's own rows.
5. Re-check every returned chunk's scope and owner, and drop any mismatch.
6. Return text, source path, heading and score. An empty result is a valid answer.

#### Handle account deletion

**Trigger:** `UserAccountDeleted` · **Result:** the user's documents and chunks are gone, and `UserDataDeleted` is published · **On failure:** retry from the queue, then the dead-letter queue

1. Delete every document row and chunk owned by the user. System docs are untouched.
2. Publish `UserDataDeleted(userId, knowledge)`.

Until user documents ship, a user owns nothing here, so this is a no-op that still reports completion.

#### Index a user document *(later)*

**Trigger:** `UploadAccepted(type ≠ statement)` from the Document service · **Result:** the document is searchable only by its owner

1. Ask the Document service for a short-lived read link by `documentId`. Knowledge never stores the file's location.
2. Extract the text.
3. Redact account numbers, SSNs and similar identifiers.
4. Chunk and embed, as for system docs.
5. Write with `scope = mine` and the owner's `user_id`.
6. On `DocumentDeleted`, remove that document's chunks.

#### Evaluate retrieval quality

**Trigger:** a change to chunking, the embedding model or the retrieval query · **Result:** recall@k on a golden question set, compared with the last run

1. Run each golden question, for example "How do I confirm a CSV column mapping?", through `retrieve`.
2. Check that the expected source docs appear in the top *k*.
3. Block the change if recall drops below the agreed threshold.

---

## 3. Concepts of Operation

### 3.1 Enter: what does this service expose and consume?

| Interface | Type | Caller / producer | Purpose |
|---|---|---|---|
| `retrieve(query, scope, k)` | Internal API (IAM) | AI assistant | Relevant chunks with sources |
| System-docs prefix storage event | System trigger | CI uploads | Start ingestion |
| `UserAccountDeleted` | Event consumed | User profile | Delete the user's documents and chunks |
| `UserDataDeleted` | Event published | → User profile | Report deletion complete |
| `UploadAccepted`, `DocumentDeleted` *(later)* | Events consumed | Document service | Index or remove user documents |

### 3.2 Trust: who may call it, and how is each request scoped to a user?

- **Retrieve:** only allow-listed IAM roles (today the AI assistant). The user comes from the signed user context, never from the query or the model.
- **System docs:** only CI's deploy role may write the system-docs prefix. Nothing else can change what every user reads.
- **Database:**
  - Row-Level Security allows `scope = system` or `user_id = current user`.
  - The user context is set in the same Data API transaction as the search.
  - Only Knowledge's role has grants on the `knowledge` database.
- **Embedding model:** only Knowledge's IAM role may invoke it.

### 3.3 Flow: how does it depend on other services?

| Depends on | How | Why | If unavailable |
|---|---|---|---|
| Amazon Bedrock (embedding model) | AWS SDK (IAM) | Embed chunks and queries | Ingestion retries the doc; retrieval returns an error the AI assistant handles |
| Aurora `knowledge` database | RDS Data API | Store and search chunks | Retry while Aurora resumes (dev); otherwise an error |
| S3 system-docs prefix | Storage events | Source copies of help docs | Ingestion waits; the index keeps the last good version |
| Document service *(later)* | Signed internal request | Short-lived read link for a user document | Ingestion retries from the queue |
| EventBridge / SQS | Events | Account deletion; later user documents | Retries from its own queue |

### 3.4 Store: what data does it keep, and for how long?

| Data | Store | Retention | On account deletion |
|---|---|---|---|
| System help-doc chunks + embeddings | `knowledge` database | While the doc exists in Git | Not user data; kept |
| User document chunks + embeddings *(later)* | `knowledge` database | Until the document or account is deleted | Deleted |
| System-docs source copies | S3 prefix | Replaced on each merge; Git is the record | Not user data |

Embeddings are derived data: the source docs are the backup, and any version can be rebuilt by re-indexing.

### 3.5 Protect: what does this service guard beyond the app-level rules?

- **Isolation tested in CI:** user A can never retrieve user B's chunks, and `scope = system` never returns a user chunk.
- **Redact before embedding** *(user documents)*: embeddings can leak what they encode, so identifiers are masked first, and embeddings get the same encryption, access control and deletion as their text.
- **Retrieved text is data:** chunks are returned as data fields. The AI assistant passes them to the model as data, never as instructions. A help doc containing instructions can't take over the chat.
- **Logging:** query text and chunk text are never logged; only IDs, counts and scores.
- **Filtered-search recall:** approximate vector search with a filter can silently return fewer results than requested, so recall is tested with the filter applied.

### 3.6 Recover: how does it fail, and how does it recover?

- **Atomic replace:** a doc's new version replaces the old in one transaction, so a failed ingestion never leaves a doc half-indexed.
- **Per-doc isolation:** each doc is its own workflow branch with retries, and one bad doc doesn't block the rest.
- **Idempotent:** path plus content hash means re-running a merge, or replaying an event, changes nothing.
- **Full rebuild:** re-index everything from Git. This is needed after changing the embedding model or chunking, because vectors from different models can't be mixed.

### 3.7 Observe: how do we know it is healthy?

- Index freshness: the last indexed commit compared with main.
- Ingestion success and failure per doc.
- Retrieval latency and the empty-result rate.
- recall@k from the evaluation set.
- Unanswered questions, logged by the AI assistant, show which help docs are missing.

---

## 4. Service decisions

| # | Decision | Choice | Why | Revisit when | Status |
|---|---|---|---|---|---|
| S1 | Vector store | pgvector in the Aurora `knowledge` database ([ADR-006](../../fintracker-architecture/architectural_decision_records/ADR-006-vector-store-pgvector.md)) | No new fixed cost; Row-Level Security like the Ledger | Corpus or latency outgrows Postgres | Proposed |
| S2 | Ownership of RAG | Retrieval here, generation in the AI assistant ([ADR-010](../../fintracker-architecture/architectural_decision_records/ADR-010-rag-retrieval-in-knowledge-service.md)) | One owner for vectors and isolation; one owner for LLM risk | Never, without a new record | Accepted |
| S3 | Chunking | Split by headings, keeping doc path and heading as metadata; sizes are config | Help docs are structured by heading, and citations need the path | Recall@k shows chunks are too coarse or too fine | Proposed |
| S4 | Versioning | A doc version is identified by path + content hash; replace in one transaction | Idempotent re-runs, no half-indexed docs | Never | Accepted |
| S5 | Embedding model | One Bedrock embedding model, pinned (candidate: Amazon Titan Text Embeddings V2) | Low cost, stays in AWS; switching models means a full re-index | Evaluation shows better recall elsewhere | Proposed |
| S6 | Search type | Vector search only at first | Help docs are a small corpus | Keyword-heavy questions (error codes, exact field names) miss; add keyword search alongside | Proposed |

---

## 5. Related documents

- **App architecture:** [FinTracker architecture](../../fintracker-architecture/fintracker-architectural-doc.md). See the Store and Protect concepts, invariants 8–10, and D10 and D17.
- **ADRs:** [ADR-006 vector store](../../fintracker-architecture/architectural_decision_records/ADR-006-vector-store-pgvector.md), [ADR-010 RAG ownership](../../fintracker-architecture/architectural_decision_records/ADR-010-rag-retrieval-in-knowledge-service.md).
- **AI assistant** (the only caller of `retrieve`): [ai-assistant-architecture.md](../../fintracker-ai-assistant/architecture/ai-assistant-architecture.md).
- **Earlier notes:** [rag_mcp_challenges.md](../../fintracker-analytics/rag_mcp_challenges.md) (isolation, PII in embeddings, freshness, evaluation). [ai-rag-pipelines-spec.md](../../fintracker-analytics/ai-rag-pipelines-spec.md) describes user-data retrieval, which is deferred with user documents.
- **Diagram sources:** `images/` (an editable SVG for every PNG).
