# FinTracker Roadmap

Phasing for the services and features in the [architecture document](fintracker-architectural-doc.md). Status labels there (*Existing*, *Proposed*) show what is built today.

**Current focus:** the Refactor phase, plus LLM features in the AI assistant and a RAG pipeline over system help docs (retrieval in Knowledge, generation in the AI assistant; ADR-010). Everything about user documents is deferred to *Next* and *Later*.

| Phase | Scope |
|---|---|
| **Refactor** | Move the Financial Summary's LLM flow and the agent tool catalog from Analytics to the AI assistant. Analytics exposes facts and detectors as internal APIs; its local MCP tool server is retired. |
| **Launch** | Chat with system help docs, plus tool calls to the Ledger and Analytics. Transaction source pointers (page/row) for the Statements tab. Log questions the assistant couldn't answer. |
| **Next** | One user document type, likely loan or credit card agreements, using *extract, then user confirms*: key fields become structured data, with document search as a fallback. |
| **Later** | Expand allowed document types based on logged questions, adding only types the app can act on. Bank sync (Teller.io) in the Data pipeline. |

**Out of scope for user uploads until the app supports them:** tax documents, investment and brokerage statements, insurance policies, and identity documents. They carry the most sensitive data and invite tax or investment advice the app isn't designed to give.
