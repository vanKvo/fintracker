# AI Integration Architecture: Analytics

FinTracker integrates AI in three ways:
1. **Financial summary**: FinTracker generates it on the backend and validates it.
2. **In-app open chat**: FinTracker runs the AI agent.
3. **User's own AI assistant**: an external assistant reaches FinTracker through an MCP Gateway.

All three share one tool layer. The user's identity always comes from the authenticated session or token, never from the model.

## Overview: three entry points, one shared tool layer

```mermaid
flowchart LR
  subgraph Clients
    UI[FinTracker UI]
    EXT["User's AI assistant<br/>Claude / ChatGPT"]
  end

  subgraph Edge
    APIGW["API Gateway<br/>Cognito JWT → X-Internal-User-Id"]
    MCPGW["MCP Gateway<br/>OAuth 2.1 via Cognito · rate limit · tool allowlist"]
  end

  subgraph AN["Analytics service — FinTracker AWS account"]
    SUM["① Summary orchestrator<br/>fixed flow · small model"]
    CHAT["② Chat orchestrator<br/>agent loop · large model"]
    MCPS["③ MCP server<br/>Lambda or Fargate"]
    VAL["Output validator<br/>schema · evidence refs · banned terms · fallback"]
    REG["Shared tool registry<br/>ToolContext with user_id · allowlist per use case"]
  end

  BR["Amazon Bedrock"]

  subgraph Data
    RR[("Postgres read replica")]
    LED["Ledger API"]
    UP["User Profile API"]
  end

  UI --> APIGW
  APIGW --> SUM
  APIGW --> CHAT
  EXT --> MCPGW --> MCPS
  SUM <--> BR
  CHAT <--> BR
  SUM --> VAL
  CHAT --> VAL
  SUM --> REG
  CHAT --> REG
  MCPS --> REG
  REG --> RR
  REG --> LED
  REG --> UP
```

| | ① Financial summary | ② In-app open chat | ③ User's own assistant |
|---|---|---|---|
| Who runs the AI loop | FinTracker | FinTracker | User's assistant |
| Where the model runs | Bedrock, in our account | Bedrock, in our account | Third-party provider |
| Who pays for the model | FinTracker (small model, cached, batch) | FinTracker (rate-limited by tier) | The user |
| What FinTracker sees | Everything | Everything | Tool calls only |
| Output control | Full: schema, validator, fallback | Strong: post-checks, safe fallback | None beyond the facts returned |
| Identity source | Session (API Gateway) | Session (API Gateway) | OAuth token (MCP Gateway) |

## ① Financial summary workflow

```mermaid
sequenceDiagram
  participant UI
  participant S as Summary orchestrator
  participant C as Summary cache
  participant B as Bedrock small model
  participant T as Tool registry
  participant V as Validator

  UI->>S: Get summary for period
  S->>C: Look up user, period, data_version
  alt Cache hit
    C-->>S: Stored summary
  else Cache miss
    S->>B: Prompt vN + 3 allowed tools
    loop Up to 4 tool calls
      B->>T: Tool call, no user_id
      T-->>B: Precomputed facts
    end
    B-->>S: Structured JSON
    S->>V: Validate schema, evidence, banned terms
    alt Fails twice or limit hit
      V-->>S: Template summary
    end
    S->>C: Store with prompt version
  end
  S-->>UI: Facts rendered as numbers + AI narrative as text
```

A nightly EventBridge job on the 1st of each month precomputes "Last month" summaries with Bedrock batch inference.

## ② In-app open chat workflow

```mermaid
sequenceDiagram
  participant UI
  participant G as API Gateway
  participant O as Chat orchestrator
  participant M as Conversation store
  participant B as Bedrock large model
  participant T as Tool registry
  participant P as Post-checks

  UI->>G: User message
  G->>O: Message + X-Internal-User-Id
  O->>O: Tier check and rate limit
  O->>M: Load history
  O->>B: History + message as data + chat tool allowlist
  loop Up to 8 tool calls
    B->>T: Tool call
    T-->>B: Facts
  end
  B-->>O: Answer
  O->>P: Scope, banned terms, evidence
  P-->>O: Pass or safe fallback
  O->>M: Save turn + trace
  O-->>UI: Streamed answer
```

## ③ User's own assistant workflow

```mermaid
sequenceDiagram
  actor U as User
  participant FT as FinTracker UI
  participant A as User's AI assistant
  participant GW as MCP Gateway
  participant S as MCP server
  participant T as Tool registry

  U->>FT: Connect assistant, approve scopes via OAuth
  U->>A: Can I afford $400 tickets?
  A->>GW: MCP tool call + OAuth token
  GW->>GW: Token → user, check scope, rate limit, log
  GW->>S: Tool call + verified identity
  S->>T: execute_tool with ctx, name, args
  T-->>S: Aggregated facts, no PII
  S-->>GW: Result
  GW-->>A: Result
  A-->>U: Answer, which FinTracker never sees
```
