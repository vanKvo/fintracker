# ADR-007: Compute per Profile: Lambda in Dev, Fargate in Prod for the Ledger and AI Assistant

## Service Name: app-wide (Ledger, AI assistant; deployment)

## Status
Accepted (architecture doc D11)

## Date
2026-10-17

## Context
Most FinTracker services are short, event-driven Python functions that fit Lambda in every environment. Two services are different:

- **Ledger:** a Spring Boot application with a JDBC connection pool and virtual threads, on the synchronous path of almost every screen.
- **AI assistant:** streams chat responses, waits on slow LLM calls, and runs multi-step agent loops.

Key requirements:
- **Dev** serves one developer, a test user and a few invited testers. It should cost close to nothing when idle.
- **Prod** must give consistent latency: no JVM cold starts on the Ledger, and chat without a 15-minute limit or cold starts.
- **One artifact per service:** the same build runs in both environments, so dev tests what ships (invariant 12).

## Decision
The `profile` setting chooses the compute for these two services. Everything else runs on Lambda in both profiles.

| Service | `dev` | `prod` |
|---|---|---|
| Ledger | Lambda in the VPC, Java 21 with SnapStart, through a Spring Boot adapter | ECS Fargate, 2 tasks across 2 AZs, behind an API Gateway VPC link |
| AI assistant | Lambda with a Function URL and response streaming, through Lambda Web Adapter | ECS Fargate, 2 tasks, behind an ALB |

Each service is built once, as a container image or JAR. Only the host and its entry adapter differ.

## Alternatives Considered

### Fargate everywhere
- Pros: Dev matches prod exactly. No adapters, no cold starts.
- Cons: Always-on tasks plus an ALB and public IPv4 addresses cost about $30–40/month in dev before any use. It also needs NAT or endpoints for tasks in private subnets.
- Rejected: Dev's whole purpose is a near-zero idle cost.

### Lambda everywhere, including prod
- Pros: One hosting model; scale to zero in prod too.
- Cons:
  - Ledger: JVM cold starts on user-facing requests (SnapStart reduces but doesn't remove them). Many concurrent instances, each with its own JDBC connection, would need RDS Proxy, which ADR-003 avoids.
  - AI assistant: chat is capped at 15 minutes per invocation, and long agent loops pay for idle waiting on the LLM.
- Rejected: It trades prod latency and simplicity for idle savings that matter only in dev.

### AWS App Runner for the two services
- Pros: Simple container hosting with scale-to-low.
- Cons: Not a fit for long-lived streaming connections or VPC-heavy setups, and a third hosting model to learn.
- Rejected.

## Consequences
- **Two hosts to keep working for each of these services.** The build must start cleanly behind both the Lambda adapter and the Fargate entry point. CI runs smoke tests against both. The Ledger's adapter choice is an open decision (architecture doc 7.2).
- **Dev does not exercise Fargate-only behavior**, such as long-lived pool tuning, ALB idle timeouts for streaming, or task health checks. Those are verified in prod deploy smoke tests.
- **Dev accepts cold starts:** the first Ledger request after idle pays JVM startup (reduced by SnapStart), and Aurora resume can add about 15 seconds.
- **Ledger Lambdas hold JDBC sessions while warm.** The dev-only `idle_session_timeout` setting (ADR-003) lets Aurora pause anyway.
- **Database migrations never run at startup**, because they would run on every Lambda cold start. They run as a separate deploy step.
