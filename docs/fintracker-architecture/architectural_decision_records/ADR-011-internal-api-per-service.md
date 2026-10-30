# ADR-011: One Internal API per Receiving Service

## Service Name: app-wide (Analytics, Ledger, Knowledge, User profile; Document service later)

## Status
Accepted (architecture doc D18). Refines [ADR-004](ADR-004-internal-api-regional-iam.md), which chose the mechanism; this record chooses the layout.

## Date
2026-10-18

## Context
ADR-004 settled *how* services call each other: a regional API Gateway HTTP API with IAM authorization (SigV4) plus a caller allow-list, the same in both profiles. It didn't settle *how many* internal APIs there are. The Refactor phase adds the first Analytics internal routes (facts payload, section tools), so the layout should be decided before routes and IAM policies multiply.

Internal requests today:

| Caller | Target |
|---|---|
| AI assistant | Analytics, Knowledge, Ledger, User profile |
| Data pipeline | Ledger |
| Analytics | User profile |
| Knowledge *(later)* | Document service |

Key requirements:
- Least privilege: each caller may invoke only the routes it needs (ADR-004).
- The same layout in dev and prod. URLs and IAM policies are part of the core security model, which `profile` must not change (app doc 6.1).
- Each service owns and deploys its own interface.
- No added fixed cost in dev.

## Decision
**One internal HTTP API per receiving service, in both profiles.** The mechanism stays as in ADR-004: IAM authorization, SigV4, a caller allow-list and the forwarded user context.

**Why:** IAM scoped by API keeps a wildcard inside one service, a misconfiguration hits one service instead of every internal call, and each service deploys its own interface. The costs are small: one Terraform module keeps the extra APIs to one block per service, the fixed cost is $0 either way, and a TLS handshake is small next to an LLM or database call. Least privilege and ownership are the core security model, which `profile` must not change.

1. **Which services get one:** every service that receives internal requests: Analytics, Ledger, Knowledge and User profile, plus the Document service when Knowledge starts indexing user documents. The AI assistant and the Data pipeline only make calls, so they have none.
2. **One Terraform module, `internal_api`:** its inputs are the service name, the routes and their integrations, and the allowed caller roles. Each service's stack instantiates it, and the module:
   - creates the HTTP API with IAM authorization on every route, and no route without it;
   - writes the allowed caller roles to the service's allow-list configuration;
   - outputs route ARNs for the callers' IAM policies.
3. **Callers' IAM policies name exact routes:** `arn:aws:execute-api:<region>:<account>:<api-id>/$default/<METHOD>/<path>`. Wildcards across APIs are not allowed.
4. **Finding the URLs:** each internal API publishes its invoke URL to SSM Parameter Store at `/fintracker/<profile>/internal-api/<service>/url`. Callers read these at startup. URLs are never hard-coded.
5. **Routing to the target:**
   - In dev, every internal API integrates directly with the service's Lambda.
   - In prod, `ledger-internal` integrates through the VPC link to the Ledger's internal load balancer. The other APIs integrate with Lambda.

## Alternatives Considered

### Shared API
One HTTP API, `fintracker-internal`, with a path prefix per service (`/analytics/*`, `/ledger/*`, …).
- Pros: 1 API and 1 base URL; $0 fixed cost; one TLS connection reused across targets.
- Cons:
  - IAM is scoped by path, so one `/*` grants every service.
  - One stage misconfiguration hits every internal call, including Ledger imports.
  - Every service's routes depend on a shared platform stack.
- Rejected: It gives up least privilege and shares one blast radius on the path every internal call takes, to save a few base URLs.

**Also considered**
- **Shared now, split later:** Rejected. Splitting changes every URL and every caller's IAM policy, so the layout is cheapest to fix before the Refactor phase adds routes.
- **A different mechanism** (private REST API, VPC Lattice, direct Lambda invocation): decided in [ADR-004](ADR-004-internal-api-regional-iam.md).

## Consequences

**Pros**
- Least privilege is reviewable per service: each caller's policy lists the APIs it may call, and each API's allowed callers are in one place.
- Each service owns its interface end to end: routes, throttles, access logs and alarms live in that service's Terraform and deploy with it.
- A misconfiguration or throttle affects one service, and prod can throttle or disable one API alone.

**Cons**
- More resources: 4 APIs now and 5 later, each with a stage and a log group. The shared module keeps this to one block per service.
- Callers need several base URLs: the AI assistant reads 4 SSM parameters at startup.
- Dev: the first call to each target from a cold Lambda pays a separate TLS handshake (prod: none). This is small next to an LLM or database call.

**Follow-up**
- The service architecture docs list their internal API in CONOPS "Enter", and the Analytics refactor creates `analytics-internal` from the module.

## Revisit when
- Receiving services grow past about 10, and per-API configuration becomes a burden.
- Internal traffic moves to a different mechanism (for example VPC Lattice, ADR-004). The layout question then reopens with it.

## Related
- [ADR-004](ADR-004-internal-api-regional-iam.md): internal API mechanism (regional HTTP API with IAM auth).
- [ADR-007](ADR-007-compute-per-profile.md): Lambda in dev, Fargate in prod. This is why the Ledger's API uses a VPC link in prod.
- [ADR-008](ADR-008-environments-and-profile-setting.md): what `profile` may and may not change.
- App architecture doc: 4.3 Flow, 6.2–6.3 Deployment, 7.1 D7 and D18, invariant 3.
