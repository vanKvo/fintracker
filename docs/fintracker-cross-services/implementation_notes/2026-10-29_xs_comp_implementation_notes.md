# XS-COMP implementation notes (2026-10-29)

Nothing was applied to AWS. Terraform was checked with `terraform validate` and `terraform test` (mocked provider);
the Cognito and workforce steps are a runbook, not code.

## Status by requirement
| ID | State | What exists | What is left |
|---|---|---|---|
| XS-COMP-20 | Implemented | axe check on the 7 pages (`fintracker-ui/e2e/accessibility.spec.ts`), UI CI workflow, 4 real violations fixed | Run once in GitHub Actions |
| XS-COMP-06 | In progress | Data pipeline bucket: TLS-only policy, 7-day noncurrent expiry, delete-marker removal, optional customer-managed key; tables: PITR and key; dev `cmk`, `dynamodb_pitr` settings and a key with role grants | Other stores (Aurora, other services' tables and buckets) have no IaC. The Ledger role needs `kms:GenerateDataKey` once `cmk` is on. Not applied |
| XS-COMP-07 | In progress | GuardDuty module; processor starts only from a clean scan result; non-clean results alarm | No user-facing failure for a rejected statement (needs a catalog reason code across XS-IMP, Ledger and UI). The "not scanned within 15 minutes" alarm. The Document service quarantine bucket (not built). Not applied |
| XS-COMP-09, -10 | In progress | Security Hub (+ NIST in prod) and Inspector module; critical/high alarm | Monthly score export; overdue-critical alarm; Dependabot per repo is a GitHub setting |
| XS-COMP-12 | In progress | Response headers policy module (the Phase 2.1 CSP) | Attach `response_headers_policy_id` to the CloudFront distribution, which is not in IaC; confirm the CSP in a browser against the deployed app |
| XS-COMP-13 | In progress | Web ACL module (prod only in `environments/security`) | Associate with the distribution and chat API stage |
| XS-COMP-15 | In progress | Acceptance stored per version; sign-up gate; notice page; claim map | Contact address empty; three claims not yet true (see the map). Notice must not go to real users yet |
| XS-COMP-01, -02, -14 | In progress | Drafts in `docs/compliance/` | The owner reads them and sets "Last reviewed"; first tabletop; AWS Artifact report dates |
| XS-COMP-16 | In progress | `scripts/compliance/check_compliance_evidence.py` | Run it before each review |
| XS-COMP-03, -04, -05 | Proposed | Runbook with commands | Run the steps; open question 1 |
| -08, -11, -17, -18, -19 | Proposed | none | Later |

`scripts/.venv/bin/python scripts/compliance/check_compliance_evidence.py` currently exits 1 on purpose: the three
drafts have no review date and no tabletop, and the AWS report dates are missing.

## Where
- Data pipeline: `infrastructure/terraform/modules/{s3_statement_bucket,dynamodb_table,malware_scan}`, `environments/dev`, `orchestrator.py`.
- Root: `infrastructure/terraform/modules/{security_baseline,security_headers,waf_managed_rules}`, `environments/security`, `scripts/compliance`, `docs/compliance`.
- User profile: privacy notice record in `identity/` (`PUT /profile/privacy-notice`, `privacyNotice` on `GET /profile`, env `PRIVACY_NOTICE_VERSION`).
- UI: `features/privacy`, `core/guards/privacy-notice.guard.ts`, accessibility fixes in layout, transactions, financial summary.
- Run Terraform tests: `terraform init -backend=false && terraform test` inside each module folder.

## Things to know
- Turning the malware scan on (default in dev) means a non-clean upload leaves the statement unprocessed with an alarm
  but no message to the user. Set `-var malware_scan=false` to keep the old direct trigger until that is designed.
- The privacy notice version lives in two places (the UI text and `PRIVACY_NOTICE_VERSION`); the claim map says to change them together.
- `ng build` reports the initial bundle 17 kB over the 1 MB error budget. I did not confirm whether this predates my changes.
- Module-level `.terraform.lock.hcl` files created by `terraform test` are git-ignored; they and `.terraform/` folders can be removed.

## Proposed spec changes (the spec is read-only for the agent)
1. XS-COMP-07 Fail 3: a statement-import failure needs a catalog reason code (XS-IMP Appendix A) before the user can see why a file was refused; today only the Document service has `document_not_ready`.
2. XS-COMP-12: the policy sets `X-Frame-Options: DENY` as the fifth header, with `frame-ancestors 'none'` inside the CSP; the spec says "five headers" without naming them.
3. XS-COMP-15: acceptance is recorded per version by the User profile service, and the sign-up gate runs after the first sign-in, because Cognito's hosted sign-up cannot show app content.
4. XS-COMP-04 Fail: say how the export-stopped alarm is measured; the runbook proposes `IncomingLogEvents` with missing data as breaching.
