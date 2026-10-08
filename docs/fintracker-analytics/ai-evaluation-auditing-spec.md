# Fintracker Analytics - Evaluations & Auditing

Part 2: Centralizing evals and auditing across all three
Best practices
One trace schema for all three integrations. Every AI event includes:

trace ID, integration (summary, chat or external), use case
pseudonymous user key
model, prompt version, tool allowlist version
tool calls, outcome, guardrail hits, tokens and cost
Build it on OpenTelemetry's GenAI conventions, since you already standardize on OpenTelemetry. External traces simply carry fewer fields (tool level only).

Instrument the choke points, not every feature:

execute_tool in the tool registry is the one place all three integrations pass through.
The two orchestrators capture prompts and outputs.
The MCP Gateway captures external identity and access.
A version registry for prompts, models, tool allowlists and eval sets, kept as config in code. Every trace is stamped with these versions, so any result can be reproduced and compared.

Two storage tiers:

Audit: metadata for all users, immutable, long retention.
Content and training: redacted, opted-in users only, KMS-encrypted, with a TTL.
Redaction and the consent check run once, centrally, before anything is stored.

Offline evals as a deploy gate. Each use case has a golden question set. It runs in CI on every prompt, model or tool change, and a failing run blocks the deploy.

Online evals on sampled production traces.

Rule checks: numbers match the facts, evidence references exist, no banned terms, within scope.
An LLM judge for tone and helpfulness.
Low scores go to a human review queue.
Tool contract tests against the real schema, so a mismatch like SALE/RETURN vs PURCHASE/CREDIT is caught. For integration ③ this is the only quality lever you have, so it matters most there.

Close the loop. Production failures and negative feedback become new golden cases.

Dashboards and alerts by integration:

fallback rate and validation failures
guardrail hits
cost per user and per tier
latency and tool error rate
unusual external access, such as one token calling many tools
Deletion that works with immutable storage.

Audit store: keep only pseudonymous keys there. On account deletion, delete the key mapping (crypto-shredding), which makes the immutable records unlinkable to the person.
Content store: purge the user's records outright.
Least-privilege access to traces, with an emergency ("break-glass") access path, and Bedrock model invocation logging as a backstop for ① and ②.
