# ADR-004: Internal API: Regional HTTP API with IAM Authorization in Both Profiles

## Service Name: app-wide (all services that make or receive internal requests)

## Status
Accepted (architecture doc D7). The layout, one internal API per receiving service, is decided in [ADR-011](ADR-011-internal-api-per-service.md).

## Date
2026-10-17

## Context
Some calls between services must be synchronous: AI assistant tool calls, the Data pipeline's ownership check and import into the Ledger, and Analytics' settings lookup in User profile. The receiving service must know two things: **which service is calling** and **on whose behalf**.

Key requirements:
- Only allow-listed FinTracker services may call internal routes. End users must never reach them directly.
- Most callers are Lambdas that run outside the VPC (ADR-003). The production AI assistant and Ledger run on Fargate inside the VPC.
- The same mechanism must work in dev and prod, so dev tests the real security model.
- The dev environment should add no fixed network cost.

## Decision
Internal routes are served by a **regional API Gateway HTTP API with IAM authorization**, in both profiles.

1. The caller signs each request with SigV4 using its own IAM role. API Gateway rejects unsigned requests, and requests from roles without `execute-api:Invoke` on that route, before any code runs.
2. Each caller's IAM policy grants `execute-api:Invoke` only on the routes it needs.
3. The receiving service also checks the caller against an allow-list, as a second layer.
4. The verified user context travels in its own header. SigV4 occupies the `Authorization` header.

## Alternatives Considered

### Private REST API with an `execute-api` VPC endpoint
- Pros: The API is unreachable from the internet, which adds network isolation on top of IAM.
- Cons:
  - Private endpoints exist only for REST APIs, not HTTP APIs.
  - Every calling Lambda would have to run in the VPC, which needs interface endpoints or NAT.
  - The `execute-api` endpoint costs about $7.30/month per AZ.
  - In dev, this would undo the "no VPC Lambdas" design.
- Rejected: It adds cost and VPC placement everywhere to protect routes that already reject any request not signed by an allowed role.

### VPC Lattice service network with IAM auth
- Pros: Service-to-service networking with IAM auth policies and no API Gateway in the path.
- Cons: Callers must be associated with the VPC, so it has the same VPC-placement problem for Lambdas. It is a newer service with more concepts to learn for a small team.
- Rejected for now: worth reconsidering if the number of internal services grows.

### Direct Lambda invocation between services
- Pros: No API layer; IAM `lambda:InvokeFunction` controls access.
- Cons: The caller is coupled to how the target is hosted. It breaks when the Ledger and AI assistant run on Fargate in prod (ADR-007).
- Rejected: The internal contract must not depend on the target's hosting.

## Consequences
- **The internal endpoint is reachable from the internet, but only signed requests from allowed roles get through.** IAM is the security boundary, so caller policies are least-privilege per route and reviewed like code.
- **HTTP APIs support neither WAF nor resource policies.** Access control is identity-based only (caller IAM policies plus the service allow-list), and all callers must be in the same AWS account.
- **In prod, Fargate callers reach the regional endpoint through the NAT gateway**, which adds NAT data-processing cost on internal traffic.
- **The receiver still verifies the forwarded user context** and never trusts a user ID from any other source.
- **Revisit if** a compliance requirement mandates network isolation for internal traffic. The migration path is a private REST API, with callers moved into the VPC.
