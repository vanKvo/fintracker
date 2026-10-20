# ADR-008: Separate AWS Accounts per Environment, with One `profile` Setting

## Service Name: app-wide (deployment and IaC)

## Status
Accepted (architecture doc D12)

## Date
2026-10-17

## Context
FinTracker runs in two environments:
- **Demo (dev):** the developer, a test user for multi-tenant checks, and a few invited testers who may upload real bank statements.
- **Production:** customers.

Key requirements:
- **Real financial data must be isolated** from experiments, broad debugging permissions and test tooling.
- **Every difference between environments must be deliberate and visible.** Untracked drift means dev stops testing what ships.
- **Dev must stay cheap**, so the environments must be allowed to differ in capacity and perimeter.
- **The security model and application code must be identical** in both, so isolation and identity are tested for real.

## Decision
1. **One AWS account per environment** (FinTracker-dev, FinTracker-prod) under AWS Organizations, with a separate management account.
2. **One `profile` variable** (`dev` or `prod`) per Terraform environment folder. Modules read every environment-specific value from a single settings map keyed by profile.
3. **Profiles may differ only in capacity, availability, network perimeter and cost guards**, never in application code, data access path or security model (invariant 12). Every difference is listed in the architecture doc's profile table (section 6.1) and in the settings map. A difference that isn't in both doesn't exist.
4. **Both accounts keep the full security baseline:** Cognito MFA, CloudTrail, backups, malware scanning, Row-Level Security and least-privilege IAM. Experiments belong in local development (SAM, Testcontainers), not in either account.

## Alternatives Considered

### One shared AWS account, separated by naming and tags
- Pros: Simpler setup; one place to look.
- Cons: IAM mistakes, a broad debug role or a misnamed resource can expose prod data. Costs and limits are mixed together. Account-wide guardrails can't differ by environment.
- Rejected: Account boundaries are the strongest isolation AWS offers, and they cost nothing.

### Separate accounts, with per-environment values scattered across modules
- Pros: Flexible; each module decides what differs.
- Cons: Differences become invisible. Nobody can answer "what is different in prod?" without reading every module.
- Rejected: The point is that dev tests what ships. Hidden differences defeat it.

### A third environment (staging) now
- Pros: A prod-shaped environment for final testing, including Fargate-only behavior (ADR-007).
- Cons: A second always-on bill before there are customers.
- Deferred: Revisit when paying customers depend on prod. Adding it means a third key in the settings map and a third column in the profile table.

## Consequences
- **Deployment uses one role per account.** GitHub Actions assumes a deploy role in each account through OIDC, so no long-lived keys. The `dev` profile deploys from pull requests and `prod` from release tags.
- **Organization-level guardrails (SCPs)** can protect both accounts: for example, denying CloudTrail deletion and limiting regions.
- **Costs are separated by account**, so dev spend is visible and its Budgets alerts are meaningful.
- **Adding an environment-specific setting is a reviewed change** to the settings map and the profile table, which keeps drift visible.
- **Invited testers' data in dev is real data.** Dev follows the same retention and deletion rules as prod, including account-deletion cascades.
