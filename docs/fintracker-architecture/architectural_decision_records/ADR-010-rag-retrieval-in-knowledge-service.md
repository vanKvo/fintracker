# ADR-010: RAG Retrieval Lives in the Knowledge Service; Generation in the AI Assistant

## Service Name: app-wide (Knowledge, AI assistant)

## Status
Accepted (architecture doc D17)

## Date
2026-10-18

## Context
The current focus includes a retrieval-augmented generation (RAG) pipeline, so chat can answer how-to and troubleshooting questions from FinTracker's own help docs. A RAG pipeline has two halves:

- **Retrieval:** ingest documents, split them into chunks, embed and index them, then find the chunks relevant to a question.
- **Generation:** put the retrieved chunks into a prompt, call the LLM, cite sources and check the answer.

It is tempting to build both halves inside the AI assistant, since only system help docs are in scope now. But the same pipeline will later index **users' own documents**, where one missed filter leaks another user's text. Where the vector store lives now decides how hard that isolation will be later.

Key requirements:
- Per-user isolation of document text, enforced in one place and testable (CONOPS 4.2, invariant 9).
- Embeddings get the same protection and deletion as their source text.
- Only the AI assistant calls a generation model (invariant 10).
- Help-doc changes in Git reach the index without a manual step.

## Decision
- **Knowledge owns retrieval:**
  - the ingestion workflow (load, hash, chunk, embed, replace);
  - the vector store (pgvector in the `knowledge` database, ADR-006);
  - the embedding model;
  - the `retrieve(query, scope, k)` internal API.
- **The AI assistant owns generation:**
  - deciding when to retrieve, as a tool call through `execute_tool`;
  - building the prompt with retrieved chunks as data;
  - calling the LLM, citing sources, post-checking the answer and logging unanswered questions.
- **The contract between them is text in, chunks out.** The AI assistant sends a query string; Knowledge embeds it, searches, re-checks ownership and returns chunks with source paths. The AI assistant never sees vectors or the database.
- **System help docs come first.** User documents reuse the same service later, with a redaction step and `scope = mine`.

## Alternatives Considered

### Whole pipeline inside the AI assistant
- Pros: One service and one deployment; no extra network hop; fastest way to ship system-doc RAG.
- Cons:
  - The AI assistant would hold both LLM orchestration and a user-data store. That is two kinds of risk in one place: prompt injection and data isolation.
  - When user documents arrive, the vector store either moves out (a migration) or the AI assistant becomes the owner of sensitive per-user text.
  - It breaks "only Knowledge touches the vector tables", which the deletion and isolation rules are built on.
- Rejected: It saves a small service now and costs a migration and a weaker isolation story later.

### Managed RAG: Amazon Bedrock Knowledge Bases (retrieve-and-generate)
- Pros: Managed ingestion, chunking, embedding, retrieval and generation with little code.
- Cons:
  - It combines retrieval and generation in one call, which bypasses the AI assistant's prompts, validation and cost guard.
  - Less control over redaction before embedding and over the post-retrieval ownership check (ADR-006).
- Rejected for now. Its retrieve-only mode could still back Knowledge later without changing the contract.

### Retrieval inside Analytics (the earlier design)
- Pros: Analytics already served data to the AI.
- Cons: Analytics is deterministic and stores nothing (app doc D4). Adding a vector store and an embedding model contradicts both.
- Rejected.

## Consequences
- **One more small service now:** an ingestion workflow, a retrieve Lambda and the `knowledge` database on the existing Aurora cluster. It scales to zero in dev.
- **One extra internal hop per retrieval:** a signed request, typically tens of milliseconds, small next to an LLM call.
- **Clear quality ownership:**
  - Knowledge owns retrieval quality, measured as recall@k on a golden question set, re-run when chunking or the embedding model changes.
  - The AI assistant owns answer quality.
- **Embedding-model access belongs only to Knowledge's role.** Generation-model access belongs only to the AI assistant's role. Both are enforced in IAM.
- **User documents are additive later:** a new ingestion trigger (`UploadAccepted`), a redaction step and `scope = mine`. No change to the AI assistant's contract.
- **Revisit when** retrieval latency or cost becomes material, for example by moving to Bedrock Knowledge Bases in retrieve-only mode behind the same API.
