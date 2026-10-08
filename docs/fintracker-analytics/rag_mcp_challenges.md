## MCP tools

Identity propagation. The biggest risk is a tool accepting user_id as an argument the LLM fills in. We found the analytics endpoints trust a query parameter, and the user-profile service had no service-to-service auth path at all, so we had to add one.

Silent data errors. We found the analytics SQL filtering on SALE/RETURN while the Ledger defines PURCHASE/CREDIT. A mismatch like that doesn't throw an error. It returns zeros, and the LLM then confidently explains wrong numbers. Tools need contract tests against the real schema.

Deployment fit. MCP's HTTP transport needs a long-lived session manager. Our Lambda setup (Mangum, lifespan off) doesn't provide one, so we couldn't simply mount it into the existing app.

Tool granularity and cost. Too many narrow tools confuse the model; too few make every call expensive. Our two Bedrock-backed insight tools share one call so an agent doesn't pay twice.

Error leakage. Raw exception text returned to the LLM exposes internal details and becomes a prompt-injection surface. Return generic messages and log the details.
Source of truth. The read replica can lag. Decide per tool whether the replica or the Ledger is authoritative.

## RAG pipelines

Multi-tenant isolation. Every vector query must filter by user. Filtered approximate search (HNSW) can also silently return fewer results than requested, so test recall with the filter applied.

PII in embeddings. Embeddings can leak what they encode, so redact before embedding. Account deletion must also delete vectors, or you break data-deletion obligations.

Freshness. When a user corrects a category, the stored embeddings go stale. You need a re-embedding trigger.
Numbers. Embeddings retrieve poorly on numbers and LLMs calculate poorly. Keep arithmetic in SQL.

Made-up causes. A variance explanation can sound right and be wrong. Require the answer to cite the retrieved record it's based on.

Evaluation. Answer quality is hard to measure. Build a fixed set of real questions with expected answers and run it on every prompt or model change.