# FinTracker Roadmap

Phasing for the services and features in the [architecture document](fintracker-architectural-doc.md). Status labels there (*Existing*, *Proposed*) show what is built today.

**Current focus:** the Refactor phase, plus LLM features in the AI assistant and a RAG pipeline over system help docs (retrieval in Knowledge, generation in the AI assistant; ADR-010). Everything about user documents is deferred to *Next* and *Later*.

## Build order (current focus)

One requirement at a time, tests first; commit as `<ID>: <summary>`. Index: [SPECS.md](../SPECS.md).

1. **Context:** `XS-CTX-01` … `XS-CTX-07`. Every later step reads the verified context.
2. **Vector store:** `KN-VS-01` … `KN-VS-05`.
3. **Chunking and embedding:** `KN-CHUNK-01` … `KN-CHUNK-03`.
4. **Indexing:** `KN-SDOC-01` … `KN-SDOC-06`.
5. **Retrieval:** `KN-RET-01` … `KN-RET-08`.
6. **Help-doc content**, then `KN-CHUNK-04` (quality gate) and `AI-EVAL-01`, `-02`, `-04`, `-05`, `-06`.
7. **Chat on help docs:** `AI-CHAT-01`, `-02`, `-03`, `-04`, `-06`, `-07`, `-09`, `-10`, `-11`, `-13`, `-15`, `-12`; `AI-EVAL-03` once the owner has scored 20 cases.
8. **Reporting:** `XS-RPTV-01` … `XS-RPTV-09`, then `AN-RPT`.
9. **Chat on the user's numbers:** `AI-CHAT-05`, `AI-CHAT-08`, `AI-EVAL-08`, then `AI-CHAT-14`, `AI-EVAL-07`.
10. **Deferred:** `KN-DEL` (when user documents arrive; Knowledge holds no user data before then), `DS-DL` (statement downloads move to the Document service).

| Phase | Scope |
|---|---|
| **Refactor** | Move the Financial Summary's LLM flow and the agent tool catalog from Analytics to the AI assistant. Analytics exposes facts and detectors as internal APIs; its local MCP tool server is retired. |
| **Launch** | Chat with system help docs, plus tool calls to the Ledger and Analytics. Transaction source pointers (page/row) for the Statements tab. Log questions the assistant couldn't answer. |
| **Next** | One user document type, likely loan or credit card agreements, using *extract, then user confirms*: key fields become structured data, with document search as a fallback. |
| **Later** | Expand allowed document types based on logged questions, adding only types the app can act on. Bank sync (Teller.io) in the Data pipeline. |

**Out of scope for user uploads until the app supports them:** tax documents, investment and brokerage statements, insurance policies, and identity documents. They carry the most sensitive data and invite tax or investment advice the app isn't designed to give.
