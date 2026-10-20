# ADR-003: Database Access Path: RDS Data API for Python Services, JDBC for the Ledger

## Service Name: app-wide (Ledger, Analytics, Knowledge)

## Status
Accepted (architecture doc D5)

## Date
2026-10-17

## Context
Three services read or write Aurora PostgreSQL Serverless v2:

- **Ledger:** Java 21, Spring Boot, jOOQ and Flyway, built on JDBC. It sets `app.current_user_id` before every query for Row-Level Security (ADR-002).
- **Analytics:** Python on Lambda, read-only queries against the Ledger's database.
- **Knowledge:** Python on Lambda, pgvector queries against its own `knowledge` database.

Key requirements:
- The dev environment must cost close to nothing when idle, so Aurora must be able to auto-pause at 0 ACU.
- Lambda functions can scale to many concurrent instances. Each one holding its own JDBC connection can exhaust the database's connections.
- Lambdas placed in a VPC need NAT or interface endpoints to reach other AWS services, which adds fixed cost in every environment.
- The access path must be the same in dev and prod, so dev tests what ships.
- Tenant isolation through Row-Level Security must keep working on every path.

## Decision
- **Analytics and Knowledge use the RDS Data API**, in both profiles. They run outside the VPC and call Aurora over HTTPS, authenticated with their IAM roles and a Secrets Manager secret for the database credentials.
- **The Ledger uses JDBC with an IAM database auth token**, in both profiles. No password is stored; the token is generated locally from the Ledger's IAM role.
- **No RDS Proxy.**

Rules that make this work:
1. Data API callers set the user context **inside the same transaction** as their queries (`set_config('app.current_user_id', :uid, true)`), because each Data API call is otherwise a separate session and Row-Level Security would return zero rows.
2. Analytics connects with a **read-only database role**.
3. In dev, the database parameter `idle_session_timeout` is 60 seconds, so JDBC sessions held by idle Ledger Lambdas close and Aurora can pause.

## Alternatives Considered

### RDS Proxy for every service
- Pros: Pools and shares connections, so Lambda concurrency can't exhaust the database. Every service keeps a normal driver. Faster failover.
- Cons: On Aurora Serverless v2 it is billed as at least 8 ACUs, roughly $90/month in each environment. It holds connections open, which stops Aurora from auto-pausing. Every caller must run inside the VPC.
- Rejected: It removes the dev cost model and adds a VPC requirement to every Python service, to solve a connection problem the Data API already avoids.

### Data API for every service, including the Ledger
- Pros: One access path; no service in the VPC; no connection management anywhere.
- Cons: The Data API is an AWS SDK call, not a JDBC driver. jOOQ execution, Flyway migrations and the per-query RLS listener (ADR-002) all assume JDBC. The Ledger's data layer would need a rewrite.
- Rejected: Too large a change to the service where correctness matters most, for a cost saving that is small in dev and gone in prod.

### Direct JDBC from every service
- Pros: Standard drivers everywhere; no extra AWS service.
- Cons: Python Lambdas would need to be in the VPC. Each Lambda instance opens its own connection, so a traffic spike can exhaust the database.
- Rejected: Brings back both the VPC cost and the connection-exhaustion problem.

## Consequences
- **Analytics reads the writer instance**, because the Data API runs only on writers. If analytical load ever affects Ledger latency, Analytics moves to JDBC on an Aurora reader. That change is contained to Analytics.
- **Data API limits apply:** responses over 1 MiB fail, so Analytics and Knowledge page large results.
- **Each Data API caller needs a Secrets Manager secret** for the database credentials (about $0.40/month each).
- **Dev idle cost stays near zero:** Aurora pauses because nothing holds a connection open. The first query after a pause waits about 15 seconds, so callers use timeouts above that and retry.
- **Two access paths to maintain.** Shared helpers in `common` set the user context the same way for every Data API caller, and isolation tests cover both paths.
