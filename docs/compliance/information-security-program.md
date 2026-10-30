# Information security program

Qualified Individual: Van Vo (owner)
Last reviewed: not yet (draft; the owner sets this date after reading it)
Next review due: 12 months after "Last reviewed"

Satisfies XS-COMP-01 (16 CFR 314.4). Control-by-control status lives in Appendix B of the
[XS-COMP spec](../fintracker-cross-services/specs/XS-COMP-compliance-controls-spec.md); this document
is the program those controls belong to.

## 1. Scope and size

FinTracker holds data on fewer than 5,000 consumers. Under 16 CFR 314.6 the written risk assessment, the
annual board report, penetration testing and the written incident response plan are therefore optional.
The program keeps a short risk list (section 3) and an incident runbook ([incident-response.md](incident-response.md))
anyway, and the FTC and state notices are required regardless. When the count nears 5,000 the optional
items become required: start the penetration test (XS-COMP-11) and the risk assessment before that.

## 2. Data inventory

From architecture doc 4.4. One owner per store.

| Store | Owner | Customer information held |
|---|---|---|
| Aurora PostgreSQL, `ledger` database | Ledger | Accounts (last four only), transactions, budgets, bills, statement records |
| Aurora PostgreSQL, `knowledge` database | Knowledge | Chunks and embeddings of user text (later) |
| DynamoDB tables | User profile, Data pipeline, Document service, AI assistant | Name, email, settings, goals, privacy-notice acceptance; import job status; file metadata; summary cache, usage and audit records |
| S3 buckets | Data pipeline today; Document service (later) | Uploaded statement files |
| CloudWatch logs, CloudTrail | Each service, the AWS account | Operational and audit events; never financial values (architecture doc 4.5, XS-ACCT-06) |

Bank credentials and card numbers are not held: bank sign-ins stay with the bank-data provider, card entry
with the payment provider (XS-ACCT).

## 3. Risk list

| Risk | Safeguard | Owner |
|---|---|---|
| One user reads another's data | Identity only from the verified token; forced row-level security plus owner-scoped queries; cross-tenant requests answer 404 | Van Vo |
| Stolen or guessed sign-in | Required authenticator-app MFA; sign-in threat protection (XS-COMP-03, -04) | Van Vo |
| Malicious file upload | Malware scan before processing (XS-COMP-07) | Van Vo |
| Data exposed at rest or in transit | Customer-managed keys, TLS-only buckets (XS-COMP-06) | Van Vo |
| Secrets or long-lived keys leak | Identity Center with MFA, OIDC deploys, no access keys (XS-COMP-05) | Van Vo |
| Vulnerable dependency or image | Dependabot, Amazon Inspector, patch windows (XS-COMP-10) | Van Vo |
| Misconfigured cloud resource | Security Hub checks with alarms (XS-COMP-09) | Van Vo |
| Sensitive data sent to the model | Allow-listed facts payload, output validation, no prompts in logs | Van Vo |
| Data kept longer than promised | Deletion cascade and retention schedule (XS-DEL, section 5) | Van Vo |

## 4. Safeguards and owners

Every safeguard in Appendix B has one owner, the Qualified Individual, until a second person joins. Providers
own the controls listed in the [service provider register](service-providers.md).

## 5. Retention and disposal schedule (D15)

- Closed account: 30-day grace period, then hard deletion within 7 days.
- Backups and file versions expire on their own schedule: Aurora backups 14 days (prod), DynamoDB point-in-time
  recovery up to 35 days, S3 noncurrent versions 7 days.
- Kept after deletion: a minimal deletion record for 24 months; security audit logs for their normal retention.
- Inactive accounts: customer data disposed of no later than two years after last use.
- Legal hold pauses deletion for the affected users until lifted.

## 6. Change management

Changes reach production through pull requests with CI (unit, service and Terraform tests, the accessibility
check) and ADRs for architectural decisions. Infrastructure is Terraform; the `dev` profile deploys from pull
requests and `prod` from a release tag. Migrations run as a separate deploy step. Compliance changes also update
Appendix B in the XS-COMP spec at the next review.

## 7. Training record

Yearly self-training: security awareness, phishing, handling of customer information, the incident runbook.

| Date | Topic | Who |
|---|---|---|
| none yet | | |

## 8. Review

Reviewed at least every 12 months, before the first invited tester, and before launch (XS-COMP-16). Each review
updates the "Last reviewed" date above.
