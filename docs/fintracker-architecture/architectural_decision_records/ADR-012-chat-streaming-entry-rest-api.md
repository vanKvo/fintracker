# ADR-012: Chat Streams Through a REST API with the Identity Authorizer

## Service Name: app-wide (AI assistant, User profile identity authorizer)

## Status
Accepted (architecture doc D19)

## Date
2026-10-19

## Context
Chat needs **response streaming**: the answer is sent token by token over one HTTP response, and it can take longer than 30 seconds once tool calls are involved. The public gateway is an HTTP API, which can't stream and stops waiting after 30 seconds. So chat had its own entry point:
- **dev:** a Lambda Function URL with auth type `NONE`, checking the JWT in code;
- **prod:** a public ALB with WAF, also checking the JWT in code.

The dev Function URL is open. Any request from anywhere runs and bills the AI assistant Lambda, even when the code then rejects it, and nothing limits the request rate except reserved concurrency, which also takes chat down. Chat was also the one user entry point that bypassed the identity authorizer.

In November 2025, API Gateway **REST APIs** gained response streaming, with integration timeouts up to 15 minutes.

Key requirements:
- Unauthenticated requests are rejected before any FinTracker code runs.
- A request-rate limit that also caps the bill.
- The same entry mechanism in dev and prod (app doc 6.1, invariant 12).
- Lowest cost that meets the above; dev idle cost stays near zero.

## Decision
**Chat streams through its own Regional REST API with response streaming, behind the same identity authorizer, in both profiles.** Only the integration target differs by profile, as for the Ledger (D11).

**Why:** It is the only option that rejects junk before any FinTracker code runs, limits the request rate without extra services (the throttle also caps the bill), and gives one chat entry in both profiles. The maturity risk, that streaming on REST APIs is new (Nov 2025), is bounded by the spike in item 6 and a known fallback (see Revisit when).

1. **One REST API (`chat-api`), Regional endpoint.**
   - An edge-optimized endpoint drops streams idle for 30 seconds; a Regional one allows 5 minutes.
   - The chat route uses streaming mode (`responseTransferMode: STREAM`), with an integration timeout of 5 minutes, raised only if real chats need it.
2. **Authorizer:** the User profile identity authorizer, as a REST `REQUEST` authorizer.
   - Its identity source is the `Authorization` header, so requests without one are rejected before the authorizer runs.
   - It shares code with the gateway authorizer. Only the response format differs, because HTTP and REST authorizers expect different formats.
3. **Throttling:** a stage-level limit (dev about 2 requests/second, burst 5), plus the per-user daily token cap in the AI assistant. The REST API carries no per-user throttle.
4. **dev:** the API integrates with the AI assistant Lambda in streaming mode. The Function URL is deleted.
5. **prod:**
   - The API integrates through a VPC link with an internal ALB in front of the AI assistant tasks, and WAF is attached to the API stage.
   - The public ALB is removed, and so is the in-code JWT check.
6. **Spike first:** streaming end to end with the Python AI assistant before building the chat feature. Lambda streams natively only on Node.js and custom runtimes, so Python streams through Lambda Web Adapter. That's true for either option.

## Alternatives Considered

### CloudFront + origin access control → Function URL
The Function URL switches to IAM auth, so only CloudFront can invoke it. The JWT is still checked in code.
- Pros: CloudFront requests cost about $0; no new API Gateway resource.
- Cons:
  - CloudFront signs and forwards every request, so the Lambda still runs and rejects junk in code.
  - It has no throttle. A rate limit needs WAF (web ACL + rate rule), about $6–7/month in dev.
  - It doesn't apply to Fargate, so prod keeps a public ALB with the JWT checked in code: two different chat entries.
  - The browser must send the SHA-256 of every POST body in `x-amz-content-sha256`.
- Rejected: At equal protection it costs more in dev and leaves two chat entries and an in-code JWT check in prod.

**Also considered**
- **Keep the open Function URL:** Rejected. Junk requests bill the Lambda, and the only rate limit is reserved concurrency.
- **API Gateway WebSocket API:** Rejected. Chat streams one way, so a two-way connection adds connection tracking and cost for nothing.
- **Lambda@Edge JWT check in front of the Function URL:** Rejected. It blocks junk at the edge, but it is a second authentication code path, costs $0.60 per million requests plus duration, and does nothing for prod.

## Consequences

**Pros**
- Junk requests never run the AI assistant: a missing token is rejected without even invoking the authorizer. Stage and route throttles are built in, and WAF can be attached.
- Every user entry point now goes through the identity authorizer. The "verified in code" exception is gone from invariant 2 and the Trust concept.
- Cost: dev is a few cents a month (about $3.50 per million requests), with no WAF; the throttle caps the bill instead. Prod's public ALB becomes an internal one, so the cost is about the same, and it drops by about $16–20/month if the AI assistant shares the Ledger's internal ALB, using separate listener rules and target groups.
- Prod drops the public ALB and the in-code JWT check. The client uses plain `fetch` with a bearer token.

**Cons**
- Streaming on REST APIs is new (Nov 2025), so it needs a spike first.
- One more API Gateway resource to deploy and monitor.
- Two authorizer response formats to keep in sync, handled in the shared identity library.
- Streaming mode has no response caching, mapping templates or content encoding on the chat route. Chat needs none of them.

**Follow-up**
- The AI assistant reads the user from the REST authorizer context instead of a JWT library. The client calls the chat API's URL with its bearer token.

## Revisit when
- The spike shows streaming doesn't work with Lambda Web Adapter. Fall back to CloudFront + OAC with a WAF rate rule.
- HTTP APIs gain response streaming. Chat could then move onto the main gateway.

## Related
- App architecture doc: 4.1 Enter, 4.2 Trust, 6.1–6.3 Deployment, D11, D19, invariant 2.
- [ADR-007](ADR-007-compute-per-profile.md) (Lambda in dev, Fargate in prod), [ADR-008](ADR-008-environments-and-profile-setting.md) (what `profile` may change).
- AI assistant architecture: the "Answer a chat question" workflow and CONOPS Enter/Trust.
- AWS: [response streaming for REST APIs](https://aws.amazon.com/about-aws/whats-new/2025/11/api-gateway-response-streaming-rest-apis), [REST private integration with ALB](https://aws.amazon.com/about-aws/whats-new/2025/11/api-gateway-rest-apis-integration-load-balancer), [Lambda response streaming runtimes](https://aws.amazon.com/about-aws/whats-new/2026/04/aws-lambda-response-streaming).
