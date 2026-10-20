# ADR-006: Vector Store: pgvector in the Aurora `knowledge` Database

## Service Name: fintracker-knowledge (app-wide impact: data isolation and cost)

## Status
Proposed (architecture doc D10, "Recommended"). Becomes Accepted when Knowledge is built.

## Date
2026-10-17

## Context
The Knowledge service needs a vector store for chat retrieval, holding two collections:
- **System:** help docs, visible to every user.
- **User:** each user's own documents, visible only to that user.

Key requirements:
- **Per-user isolation is the top risk.** One missed filter leaks another user's document text. Isolation must be enforced in one place and testable.
- **Text is redacted before embedding**, and embeddings get the same protection and deletion as their source text.
- **Low fixed cost**, so the dev environment can scale to near zero.
- **Modest scale at launch:** help docs plus, later, a few document types per user. That is thousands to low millions of chunks, not billions.

## Decision
Store chunks and embeddings in a **`knowledge` database with the pgvector extension, on the existing Aurora PostgreSQL cluster**.

- Knowledge owns the database and is the only service whose database role can read or write it (invariant 9).
- Every user-owned row carries `user_id`, and Row-Level Security applies, the same as in the Ledger (ADR-002).
- Knowledge reaches it through the RDS Data API (ADR-003), setting the user context inside each transaction.
- Retrieval filters by owner or `scope = system`, and Knowledge re-checks ownership of every returned chunk.

## Alternatives Considered

### Amazon OpenSearch Serverless
- Pros: Purpose-built vector and hybrid (keyword plus vector) search; scales to very large indexes.
- Cons: A minimum always-on capacity costing hundreds of dollars a month, in every environment. Isolation becomes index or document-level filtering in a second system, outside the database's Row-Level Security.
- Rejected: Its fixed cost is far above FinTracker's dev budget, and its scale isn't needed yet.

### Amazon Bedrock Knowledge Bases
- Pros: Managed ingestion, chunking, embedding and retrieval with little code.
- Cons:
  - Less control over the pipeline steps that matter most here: redaction before embedding, and the post-retrieval ownership check.
  - The per-user filter becomes metadata filtering configured in another service.
  - It still needs a vector store underneath.
- Rejected for now: Control over redaction and isolation outweighs the saved code. It could be revisited with Aurora pgvector as its backing store.

### A separate managed vector database (third-party)
- Pros: Strong vector features and performance.
- Cons: Sends redacted but still sensitive financial document text to another vendor. Adds a contract, a security review and a separate deletion path.
- Rejected: An unnecessary data processor for a GLBA-scoped app at this scale.

## Consequences
- **No new fixed cost:** the vector store shares the Aurora cluster and pauses with it in dev.
- **One isolation model for all relational data:** Row-Level Security plus owner-scoped queries, tested the same way as the Ledger.
- **Shared-cluster load:** large re-indexing jobs compete with Ledger traffic for capacity. Ingestion runs as a throttled Step Functions workflow, and Aurora's maximum ACU is sized for both.
- **Scale ceiling:** if chunk count or query latency outgrows Postgres (for example, tens of millions of vectors or strict latency targets), move to a dedicated store. Knowledge is the only service touching vectors, so that change is contained to it.
- **Index choice** (HNSW vs. IVFFlat) and embedding dimensions are Knowledge-level details, recorded in its service doc.
