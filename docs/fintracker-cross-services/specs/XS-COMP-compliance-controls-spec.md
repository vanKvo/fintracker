# XS-COMP: Compliance Controls

| Field | Value |
|---|---|
| Product | FinTracker |
| Prefix | XS-COMP |
| File | fintracker-cross-services/specs/XS-COMP-compliance-controls-spec.md |
| Owner | Van Vo |
| Status | Draft |
| Last updated | 2026-10-29 |

**Services:** all of them, plus the AWS accounts, CI and the written policies. The app doc §11 lists the standards. This spec tracks, per standard, which controls exist, which are missing, and which a certified third party should own instead of FinTracker code.

---

## 1. Overview

### Problem
FinTracker's obligations come from several standards: the GLBA Safeguards and Privacy Rules, state breach-notification laws, and engineering baselines. The controls that satisfy them are spread across ADRs, specs and phase docs. Nothing shows which obligations are met, which are missing, and which could be bought from a certified provider instead of built. Some planned work (a custom MFA screen, sign-in audit triggers) duplicates what AWS already offers for a few dollars a month.

### Goals
- One matrix (Appendix B) answers "which control satisfies which obligation, and is it built?" for every standard in app doc §11.
- Every missing control is a requirement with an ID and a status in this spec.
- Every control a certified provider can own at reasonable cost is offloaded, and the work that stays with FinTracker is written down (Appendix C).

### Non-Goals
- Legal advice. Counsel confirms applicability before launch; until then app doc §11 says *Applies (to confirm)*.
- A SOC 2 or PCI DSS audit. FinTracker keeps PCI out of scope (XS-ACCT) and starts SOC 2 only when a partner or customer asks for a report.
- Restating controls already specified elsewhere. The matrix points to them (XS-ACCT, XS-DEL, UI-AUTH, AI-CHAT, AN-FS and others).

### Design Principles
1. **Offload first.** When a certified provider can own a control at reasonable cost and with less upkeep than our code, use the provider. Record what remains ours under the shared-responsibility split (Appendix C).
2. **Keep scope small.** Data FinTracker doesn't hold needs no controls. Last four only (XS-ACCT); bank credentials stay with the bank-data provider; card data stays with the payment provider.
3. **Evidence or it isn't done.** A control is *Implemented* only when a test, a configuration check or a dated document proves it, and the matrix links that proof.
4. **Same controls in both profiles.** Identity, encryption, MFA, audit logging and malware scanning never differ between dev and prod (app doc invariant 12). Only defense-in-depth layers and cost guards differ.

---

## 2. Workflow

```
[Policies: security program, privacy notice, incident response, vendors] ──► XS-COMP-01, -02, -14, -15
    │
[Identity: users' MFA, sign-in threat protection, workforce access] ──► XS-COMP-03, -04, -05
    │
[Data: encryption and TLS-only, malware scan, sensitive-data discovery] ──► XS-COMP-06, -07, -08
    │
[Edge: security headers, WAF] ──► XS-COMP-12, -13
    │
[Assurance: configuration monitoring, vulnerability scans, penetration test, accessibility] ──► XS-COMP-09, -10, -11, -20
    │
[Feature triggers: bank sync, payments, SMS and marketing] ──► XS-COMP-17, -18, -19
    │
[Review the matrix every 12 months and before launch] ──► XS-COMP-16
```

---

## 3. Requirements Index

| ID | Title | Area | Priority | Status |
|---|---|---|---|---|
| XS-COMP-01 | Written information security program | Security | MVP | In progress |
| XS-COMP-02 | Incident response and breach notification | Security | MVP | In progress |
| XS-COMP-14 | Service provider register | Security | MVP | In progress |
| XS-COMP-15 | Privacy notice and policy | Quality | MVP | In progress |
| XS-COMP-03 | MFA for every user through Cognito managed sign-in | Security | MVP | Proposed |
| XS-COMP-04 | Sign-in threat protection and auth event logs (Cognito Plus) | Security | MVP | Proposed |
| XS-COMP-05 | Workforce access with MFA and no long-lived keys | Security | MVP | Proposed |
| XS-COMP-06 | Customer-managed keys and TLS-only access on every store | Security | MVP | In progress |
| XS-COMP-07 | Malware scan on upload (GuardDuty) | Security | MVP | In progress |
| XS-COMP-08 | Sensitive-data discovery on file buckets (Macie) | Security | Later | Proposed |
| XS-COMP-12 | Security headers and CSP at CloudFront | Security | MVP | In progress |
| XS-COMP-13 | WAF managed rules in prod | Security | MVP | In progress |
| XS-COMP-09 | Continuous configuration checks (Security Hub CSPM) | Security | MVP | In progress |
| XS-COMP-10 | Vulnerability scanning and patching | Security | MVP | In progress |
| XS-COMP-11 | Annual penetration test | Security | Later | Proposed |
| XS-COMP-20 | Accessibility check in CI | Quality | MVP | Implemented |
| XS-COMP-17 | Bank sync consent and data limits | Security | Later | Proposed |
| XS-COMP-18 | Payment provider and PCI SAQ A | Security | Later | Proposed |
| XS-COMP-19 | SMS and marketing consent | Quality | Later | Proposed |
| XS-COMP-16 | Compliance review and evidence | Quality | MVP | In progress |

MVP here means before invited testers' real data arrives in dev, except XS-COMP-04, -09 and -13, which are needed before customers arrive in prod.

---

## 4. Requirements

### XS-COMP-01: Written information security program  `Priority: MVP`

**Problem:** The Safeguards Rule requires a written program and a named Qualified Individual. App doc §11 already says "written security program … still needed".
**Requirement:** `docs/compliance/information-security-program.md` names the Qualified Individual (the owner) and covers: a data inventory (from app doc 4.4), a risk assessment, the safeguards in Appendix B with their owners, the retention and disposal schedule (D15), change management (pull requests, Terraform, CI), and a yearly self-training record. Each section is reviewed at least every 12 months.
**Acceptance Criteria:**
- [Happy] The document exists, names the Qualified Individual, and has a "Last reviewed" date within the past 12 months.
- [Alt] While FinTracker holds data on fewer than 5,000 consumers, the written risk assessment and the annual board report are optional (16 CFR 314.6). The program says so and keeps a short risk list anyway.
- [Fail] XS-COMP-16's review fails if the review date is older than 12 months.
**Refs:** 16 CFR 314.4(a)–(c), (e), (g), (i); FTC "Safeguards Rule: What Your Business Needs to Know".

### XS-COMP-02: Incident response and breach notification  `Priority: MVP`

**Requirement:** `docs/compliance/incident-response.md` defines severity levels, who decides, how evidence is preserved (CloudTrail, the audit log group, trace IDs), and the notices to send. Notices: the FTC within 30 days of discovering unencrypted customer information acquired without authorization for 500 or more consumers; affected users and state attorneys general under each state's breach law, starting with Virginia's; and AWS, Teller or the payment provider when their systems are involved.
**Acceptance Criteria:**
- [Happy] The runbook lists each notice with its deadline, recipient and a template.
- [Alt] Below 5,000 consumers the written plan is optional under 16 CFR 314.6, but the FTC notice and state-law notices are not, so the notice section is required regardless.
- [Fail] A tabletop exercise, at least once a year and recorded with its date, walks one scenario (a leaked access token) end to end. A missed year fails XS-COMP-16.
**Refs:** 16 CFR 314.4(h) and (j) (FTC notice, in effect since May 2024); app doc 4.7 *Investigating an incident*.

### XS-COMP-14: Service provider register  `Priority: MVP`

**Requirement:** `docs/compliance/service-providers.md` lists every provider that handles customer information: AWS, plus Teller and the payment provider when they ship. For each it records what the provider does, its attestation (from AWS Artifact or the provider's trust page), the date checked, and the controls that stay with FinTracker. It is reviewed yearly.
**Acceptance Criteria:**
- [Happy] AWS's current SOC 2 Type II report and PCI DSS Attestation of Compliance are downloaded from AWS Artifact, and their dates are recorded.
- [Alt] A provider without an independent attestation is listed with the reason it is accepted, or not used.
- [Fail] A new provider integrated without a register entry fails XS-COMP-16.
**Refs:** 16 CFR 314.4(f); app doc §11.2.

### XS-COMP-15: Privacy notice and policy  `Priority: MVP`

**Requirement:** A privacy notice that meets the GLBA Privacy Rule (Regulation P) is shown at sign-up and is available from Settings. It states: what is collected; that data isn't sold or shared with nonaffiliated third parties except service providers; how AI is used (Bedrock; no training on user data); retention and deletion (D15, including backup expiry); and how to request access or deletion. Every promise in it maps to a control in Appendix B.
**Acceptance Criteria:**
- [Happy] Sign-up records which notice version the user accepted.
- [Alt] A material change to the notice shows it again at the next sign-in, and records the new acceptance.
- [Fail] A claim with no matching control (for example "we never log X") blocks publication until the control exists. This keeps FTC Act §5 claims true.
**Refs:** 12 CFR 1016 (Reg P); D15; app doc 4.5 *Privacy*.

### XS-COMP-03: MFA for every user through Cognito managed sign-in  `Priority: MVP`

**Problem:** Phase 2.3 plans a custom TOTP enrollment screen in Settings. Cognito's managed sign-in already enrolls and challenges TOTP when the user pool requires MFA, at no extra cost.
**Requirement:** The user pool sets MFA to *required* with authenticator-app (TOTP) codes. Enrollment and challenge happen in Cognito's managed sign-in pages. SMS is not offered as a factor. The app builds no enrollment screen. Settings only links to a Cognito-hosted flow to reset the authenticator.
**Acceptance Criteria:**
- [Happy] A new user signs up, is asked to scan a QR code and enter a code, and reaches the Dashboard. The next sign-in asks for a code.
- [Alt] An existing user without MFA is asked to enroll at their next sign-in, before any app page loads.
- [Fail] Repeated wrong codes are throttled or locked out by Cognito; the app shows Cognito's message and offers no path around it.
**Open Questions:** Does managed sign-in's "reset authenticator" flow need a support process (identity check) for a user who lost their phone?
**Refs:** supersedes Phase 2.3; 16 CFR 314.4(c)(5); NIST SP 800-63B (AAL2).

### XS-COMP-04: Sign-in threat protection and auth event logs (Cognito Plus)  `Priority: MVP`

**Problem:** Phase 2.2 plans Pre- and Post-Authentication Lambda triggers to log sign-ins, and Phase 2.4 enables advanced security. Both are what Cognito's Plus tier provides: adaptive authentication, compromised-credential detection and exportable sign-in event logs.
**Requirement:** The user pool uses the Plus tier with threat protection in full-function (enforce) mode. Sign-in events are exported to a CloudWatch log group kept as long as the audit log group (app doc 6.1). No custom auth-logging Lambda triggers are built.
**Acceptance Criteria:**
- [Happy] A successful sign-in, a failed sign-in and a sign-out each appear in the exported event log with the user's `sub`, time, IP and risk decision.
- [Alt] A high-risk sign-in, such as a new device and country with a known-breached password, is blocked or challenged, per the configured action.
- [Fail] A stopped event export fires an alarm, through a CloudWatch metric on delivery failures or an hourly no-events check during known activity.
**Refs:** supersedes Phase 2.2 and 2.4; PCI DSS-style lockout is not required because XS-ACCT keeps PCI out of scope. Cost: Appendix C.

### XS-COMP-05: Workforce access with MFA and no long-lived keys  `Priority: MVP`

**Requirement:** People reach the AWS accounts only through IAM Identity Center with MFA, using short-lived role sessions. CI deploys with GitHub OIDC roles. No IAM user has long-lived access keys. The root user has MFA and no access keys. GitHub requires 2FA.
**Acceptance Criteria:**
- [Happy] The IAM credential report shows no active access keys and root MFA on, in both accounts.
- [Alt] A break-glass role exists, protected by MFA, and every use alarms.
- [Fail] Security Hub's IAM checks (XS-COMP-09) failing on any of these creates a finding that alarms.
**Refs:** 16 CFR 314.4(c)(1) and (c)(5); `docs/instructions/configure_aws_dev_profile.md`.

### XS-COMP-06: Customer-managed keys and TLS-only access on every store  `Priority: MVP`

**Problem:** D13 decides customer-managed KMS keys before invited testers arrive. The data-pipeline statement bucket uses S3-managed keys (`AES256`), has no bucket policy denying non-TLS requests, and keeps old versions forever. DynamoDB tables have no point-in-time recovery.
**Requirement:** Every store uses the customer-managed key for its data type (D13). Every S3 bucket denies requests where `aws:SecureTransport` is false, and expires noncurrent versions after 7 days. DynamoDB tables holding user data have point-in-time recovery on in prod (app doc 6.1).
**Acceptance Criteria:**
- [Happy] Security Hub reports no failing S3 encryption or SSL-only checks, and no failing DynamoDB or Aurora encryption checks, for FinTracker resources.
- [Alt] Dev keeps AWS-managed keys only while it holds the owner's data alone (D13 stage presets); the switch happens before the first invite.
- [Fail] An `http://` request to a bucket is denied with 403.
**Refs:** D13; `fintracker-data-pipeline/infrastructure/terraform/modules/s3_statement_bucket/main.tf`; XS-DEL-07.

### XS-COMP-07: Malware scan on upload (GuardDuty)  `Priority: MVP`

**Requirement:** GuardDuty Malware Protection for S3 scans every object written to the upload (quarantine) bucket. Only objects tagged clean are processed, and only they move to the clean bucket. FinTracker runs no antivirus engine of its own.
**Acceptance Criteria:**
- [Happy] A clean PDF is tagged `NO_THREATS_FOUND` and processed.
- [Fail] The EICAR test file is tagged `THREATS_FOUND`, never processed, and the user sees the existing "file failed its malware scan" message (`document_not_ready`).
- [Fail] An object not scanned within 15 minutes is treated as failed and alarms.
**Refs:** app doc 4.4 *File lifecycle*, invariant 6; DS-DL-01. Cost: Appendix C.

### XS-COMP-08: Sensitive-data discovery on file buckets (Macie)  `Priority: Later`

**Requirement:** When user documents ship (roadmap *Next*), Macie's automated sensitive-data discovery samples the clean bucket and reports objects containing full card numbers or SSNs. This shows where XS-ACCT's minimization ends, since original files are kept as uploaded.
**Acceptance Criteria:**
- [Happy] A seeded test file with a test card number is reported within one discovery cycle.
- [Fail] A finding alarms, and its handling follows XS-COMP-02.
**Refs:** XS-ACCT Non-Goals.

### XS-COMP-12: Security headers and CSP at CloudFront  `Priority: MVP`

**Requirement:** CloudFront adds HSTS, `X-Content-Type-Options`, `Referrer-Policy`, `frame-ancestors 'none'` and the Content-Security-Policy from Phase 2.1 through a response headers policy. The app code sets no headers itself.
**Acceptance Criteria:**
- [Happy] A request for `/` returns all five headers.
- [Fail] A script injected from an origin outside `script-src` is blocked, and the browser reports a CSP violation.
**Refs:** supersedes Phase 2.1 (the same policy, set at CloudFront); OWASP ASVS V14.

### XS-COMP-13: WAF managed rules in prod  `Priority: MVP`

**Requirement:** The prod web ACLs on CloudFront and the chat REST API (app doc 6.1) use AWS Managed Rules: the core rule set, known bad inputs, and a rate-based rule. FinTracker writes no custom WAF rules until a finding needs one.
**Acceptance Criteria:**
- [Happy] A request with a known bad input pattern is blocked with 403 and counted in the WAF metrics.
- [Fail] A false positive on an app route is handled by a scoped rule exclusion, recorded with its reason, never by removing the rule group.
**Refs:** app doc 6.1 (WAF prod-only); D19.

### XS-COMP-09: Continuous configuration checks (Security Hub CSPM)  `Priority: MVP`

**Requirement:** Security Hub CSPM is on in both accounts, with the AWS Foundational Security Best Practices standard and NIST SP 800-53 Rev. 5. Critical and high findings go to the alarm SNS topic. A finding is fixed or suppressed with a written reason.
**Acceptance Criteria:**
- [Happy] The Security Hub security score and its open findings are exported monthly as XS-COMP-16 evidence.
- [Alt] Dev may run Foundational Security Best Practices only, to save cost.
- [Fail] A new critical finding alarms within 1 hour.
**Refs:** AWS Audit Manager is closed to new customers since 2026-04-30, so it isn't an option. Cost: Appendix C.

### XS-COMP-10: Vulnerability scanning and patching  `Priority: MVP`

**Requirement:** Dependabot alerts and security updates are on in every repository. Amazon Inspector scans the Lambda functions and the Fargate container images. A critical vulnerability is patched within 15 days and a high one within 30, or an exception is recorded.
**Acceptance Criteria:**
- [Happy] Inspector and Dependabot show no open critical finding older than 15 days.
- [Fail] An overdue critical finding alarms through Security Hub.
**Refs:** 16 CFR 314.4(d)(2) (scans every 6 months; continuous scanning meets it); OWASP ASVS V14.

### XS-COMP-11: Annual penetration test  `Priority: Later`

**Requirement:** A qualified third party tests the prod app every 12 months, and after a major change. Findings are tracked like XS-COMP-10's.
**Acceptance Criteria:**
- [Happy] A dated report, and the fixes for its findings, are stored as evidence.
- [Alt] Not required while FinTracker holds data on fewer than 5,000 consumers (16 CFR 314.6). It starts before that number is reached, or when a partner asks.
**Refs:** 16 CFR 314.4(d)(2).

### XS-COMP-20: Accessibility check in CI  `Priority: MVP`

**Requirement:** CI runs an automated WCAG 2.2 AA check (axe) on the main pages: Dashboard, Transactions, Statements, Budgets, Reports, Accounts and Settings.
**Acceptance Criteria:**
- [Happy] The check passes with no serious or critical violations.
- [Fail] A new serious violation fails the UI build.
**Refs:** app doc §11.1.

### XS-COMP-17: Bank sync consent and data limits  `Priority: Later`

**Requirement:** Before bank sync ships: the user consents to each connection in the bank-data provider's own flow; FinTracker collects only balances and transactions (no full account numbers, XS-ACCT-07); the user can revoke a connection in Settings, which revokes the provider token; and consent is renewed at least yearly. The design follows the current state of the CFPB's Personal Financial Data Rights rule (§1033), which is being reconsidered, so its final terms are checked when the work starts.
**Acceptance Criteria:**
- [Happy] Revoking a connection calls the provider's revoke API and stops syncing within 1 minute.
- [Fail] A sync with a revoked or expired token stops, and the Accounts page shows "Reconnect", never a silent failure.
**Refs:** XS-ACCT-07; roadmap *Later*.

### XS-COMP-18: Payment provider and PCI SAQ A  `Priority: Later`

**Requirement:** Paid plans use a PCI DSS Level 1 service provider's hosted checkout and billing (Stripe Checkout and Billing recommended; Appendix C), per XS-ACCT-08. FinTracker completes the PCI self-assessment that fits a fully outsourced card flow (SAQ A) each year, and keeps the provider's Attestation of Compliance in the register (XS-COMP-14).
**Acceptance Criteria:**
- [Happy] The completed SAQ A and the provider's attestation are stored with dates.
- [Fail] A design that would put card data on a FinTracker page or API is rejected at review (XS-ACCT Design Principle 4).
**Refs:** XS-ACCT-08.

### XS-COMP-19: SMS and marketing consent  `Priority: Later`

**Requirement:** When SMS alerts or marketing emails ship (Settings *Notifications*): SMS requires prior express consent and honors STOP (TCPA). Marketing email carries an unsubscribe link honored within 10 business days, and a postal address (CAN-SPAM). Both are opt-in toggles that are off by default.
**Acceptance Criteria:**
- [Happy] A user who turns SMS on gets a confirmation text, and the consent and its time are recorded.
- [Fail] A STOP reply turns SMS off within 1 minute, and no further texts are sent.
**Refs:** `fintracker-ui-features.md` Settings → Notifications.

### XS-COMP-16: Compliance review and evidence  `Priority: MVP`

**Requirement:** The owner reviews Appendix B every 12 months, before the first invited tester, and before launch. Each row is updated to *Implemented* (with its evidence link), *Designed* or *Missing*. Applicability (app doc §11) is re-confirmed with counsel before launch.
**Acceptance Criteria:**
- [Happy] Appendix B has a "Last reviewed" date within 12 months, and every *Implemented* row links evidence: a test, a config check or a dated document.
- [Fail] A row marked *Implemented* without evidence is changed back to *Designed* at review.
**Refs:** Design Principle 3.

---

## 5. Open Questions (consolidated)

| # | Question | Blocks |
|---|---|---|
| 1 | Does managed sign-in's "reset authenticator" flow need a support process (identity check) for a user who lost their phone? | XS-COMP-03 |

---

## Appendix A: Applicability

| Standard | Applies | Trigger or reason |
|---|---|---|
| GLBA Safeguards Rule (16 CFR 314) | Yes (confirm with counsel) | A personal-finance app holding consumers' financial data |
| GLBA Privacy Rule (Reg P) | Yes (confirm) | Same |
| FTC Act §5 | Yes | Privacy and security claims must be true |
| State breach-notification laws | Yes | Residents' personal information in a breach |
| State consumer privacy laws (CCPA/CPRA and others) | Partly, at their size thresholds | GLBA-covered data is exempt under CCPA. Virginia's VCDPA exempts GLBA financial institutions entirely |
| CFPB §1033 | When bank sync ships | Authorized third party |
| TCPA, CAN-SPAM | When SMS or marketing email ships | Settings *Notifications* |
| PCI DSS | No, while XS-ACCT holds; SAQ A once paid plans ship | No card data stored; payments through a hosted checkout |
| GDPR | No | No EU users |
| OWASP ASVS (Level 2), OWASP Top 10 for LLM Applications, WCAG 2.2 AA, NIST SP 800-63B | Adopted baselines | Engineering standards, not laws |

---

## Appendix B: Control matrix

Status: **Implemented** (built and proven by a test or config) · **Designed** (in an ADR, spec or the app doc, not yet built) · **Missing**. *Last reviewed: 2026-10-29.*

**GLBA Safeguards Rule**

| Element | FinTracker control | Status | Evidence / tracking |
|---|---|---|---|
| Qualified Individual, written program (a), (b) | Security program document | Missing | XS-COMP-01 |
| Risk assessment (b)(1), exempt under 5,000 consumers | Short risk list in the program | Missing | XS-COMP-01 |
| Access controls, customers (c)(1) | Identity authorizer; identity only from the token; forced RLS plus owner-scoped queries; cross-tenant 404; SigV4 and allow-list on internal calls | Implemented (Ledger, Knowledge); In progress (context forwarding) | ADR-002, LG-CORE-1.1, KN-VS isolation tests, XS-CTX |
| Access controls, workforce (c)(1) | Identity Center, OIDC deploys, no long-lived keys | Missing | XS-COMP-05 |
| Data inventory (c)(2) | Store and owner table | Designed | App doc 4.4; XS-COMP-01 |
| Encryption at rest (c)(3) | AWS encryption everywhere; customer-managed keys per data type | Implemented (AWS-managed keys); Designed (customer-managed) | D13; XS-COMP-06 |
| Encryption in transit (c)(3) | TLS on every AWS endpoint and CloudFront; TLS-only bucket policies | Implemented (endpoints); Missing (bucket policy) | XS-COMP-06 |
| Data minimization | Last four only; no account numbers to Analytics or the LLM | Designed | XS-ACCT; D22 |
| Secure development (c)(4) | Tests first; no exception text to clients; CI log-redaction check (AI assistant) | Implemented | App doc 4.8, §10; AI-CHAT-13 |
| MFA (c)(5) | Users: required TOTP. Workforce: Identity Center MFA | Missing | XS-COMP-03, XS-COMP-05 |
| Disposal and retention (c)(6) | 30-day grace period, hard deletion within 7 days, disposal 2 years after last use | Designed; deletion In progress | D15; XS-DEL |
| Change management (c)(7) | Pull requests, Terraform, CI deploys, ADRs | Implemented (repos and CI); Designed (all infrastructure in Terraform) | App doc 6.4 |
| Monitoring and logging (c)(8) | Audit helper and log group; CloudTrail; sign-in events | Designed; sign-in events Missing | D20; XS-COMP-04 |
| Testing (d)(2), exempt under 5,000 consumers | Continuous vulnerability scanning; yearly penetration test | Missing | XS-COMP-10, XS-COMP-11 |
| Training (e) | Yearly self-training record | Missing | XS-COMP-01 |
| Service providers (f) | Provider register, attestations | Missing | XS-COMP-14 |
| Incident response plan (h), exempt under 5,000 consumers | Runbook and notice templates | Missing | XS-COMP-02 |
| Annual report (i), exempt under 5,000 consumers | Section of the program review | Missing | XS-COMP-01 |
| FTC notice (j): 500+ consumers, within 30 days | Notice step in the runbook | Missing | XS-COMP-02 |

**Other standards**

| Standard | Concept | FinTracker control | Status | Evidence / tracking |
|---|---|---|---|---|
| GLBA Privacy Rule | Privacy notice | Notice at sign-up and in Settings | Missing | XS-COMP-15 |
| State breach laws | Notice to residents and attorneys general | Runbook | Missing | XS-COMP-02 |
| State privacy laws | Deletion; access | Deletion cascade (XS-DEL); download of statements and transactions | Designed / In progress | XS-DEL, DS-DL; CSV export on the Transactions tab |
| FTC Act §5 | Claims match controls | Notice-to-control mapping | Missing | XS-COMP-15 |
| OWASP ASVS L2 | Authentication | Cognito sign-in, MFA, threat protection | Designed | XS-COMP-03, -04 |
| OWASP ASVS L2 | Session management | Tokens in `sessionStorage`; no dev auth bypass | Designed | UI-AUTH-01, UI-AUTH-02 |
| OWASP ASVS L2 | Access control | As GLBA (c)(1) | Implemented | ADR-002 |
| OWASP ASVS L2 | Files | Type and size checks; malware scan; short-lived download links | Implemented (checks); Missing (scan) | LG-STMT, DS-DL-01, XS-COMP-07 |
| OWASP ASVS L2 | Errors and logging | RFC 9457 with no exception text; no financial values in logs; masking | Implemented (errors); Designed (masking) | App doc 4.8; XS-ACCT-06 |
| OWASP ASVS L2 | Headers and CSP | CloudFront response headers policy | Missing | XS-COMP-12 |
| OWASP LLM Top 10 | Prompt injection | Untrusted text as JSON data, cleaned and capped | See SPECS.md | AI-CHAT-10 |
| OWASP LLM Top 10 | Sensitive information disclosure | Allow-listed facts payload; no prompts in logs | See SPECS.md | AN-FS, AI-CHAT-13, AI-GUARD |
| OWASP LLM Top 10 | Excessive agency | Read-only tools; user fixed from the token | See SPECS.md | App doc 4.3, AI-CHAT |
| OWASP LLM Top 10 | Unbounded consumption | Per-user and app-wide limits; Bedrock budget deny policy | See SPECS.md | AN-FS-21, SDR-002 |
| WCAG 2.2 AA | Automated checks | axe in CI | Missing | XS-COMP-20 |
| PCI DSS | Scope | No card data stored; vault later | Designed | XS-ACCT, XS-COMP-18 |

---

## Appendix C: Offload decisions

Prices are AWS list prices in us-east-1 and the providers' published rates, checked 2026-10-29. Recheck them before enabling a service.

| Control | Build it ourselves | Offload to | Cost | Decision | What stays ours |
|---|---|---|---|---|---|
| Card data and payments | Card forms, tokenization, PCI SAQ D | Stripe Checkout and Billing (PCI Level 1) | 2.9% + 30¢ per US card charge, plus 0.7% of billing volume (Billing, pay as you go) | **Offload** when paid plans ship | Webhook verification; the stored tier; SAQ A |
| Bank credentials | Storing bank sign-ins | Teller Connect (mTLS, per-user tokens) | Teller's pricing | **Offload** when bank sync ships | Token storage (KMS or Secrets Manager); consent and revoke |
| User MFA enrollment and challenge | Custom TOTP screen (Phase 2.3) | Cognito managed sign-in, MFA required | Included in the current tier | **Offload** (XS-COMP-03) | Pool configuration |
| Brute force, compromised passwords, adaptive auth, sign-in event logs | Lambda triggers and a lockout store (Phase 2.2, 2.4) | Cognito Plus threat protection | $0.020 per MAU, no free tier (about $20/month at 1,000 MAU) | **Offload** (XS-COMP-04) | Choosing the risk actions; alarms |
| Malware scanning | ClamAV Lambda with signature updates and size limits | GuardDuty Malware Protection for S3 | $0.09/GB scanned plus a per-object fee; 1,000 objects and 1 GB free each month | **Offload** (XS-COMP-07) | Acting on the scan tag |
| Configuration compliance evidence | Custom scripts | Security Hub CSPM (plus AWS Config recording) | About $0.001 per check for the first 100,000 a month; 30-day free trial | **Offload** (XS-COMP-09) | Fixing findings |
| Evidence collection for audits | — | AWS Audit Manager | — | **Not available**: closed to new customers since 2026-04-30 | — |
| SOC 2 program (GRC platforms such as Vanta or Drata) | Spreadsheets | GRC platform | Quote-based annual subscription | **Defer** until a partner or customer asks for SOC 2 | Policies and fixes |
| Sensitive data in stored files | Custom scanners | Amazon Macie | $0.10 per bucket a month, plus $1/GB inspected (first 1 GB free) | **Later** (XS-COMP-08) | Handling findings |
| Vulnerability scanning | — | Amazon Inspector; GitHub Dependabot | Inspector per function and image monthly (see its pricing page); Dependabot free | **Offload** (XS-COMP-10) | Patching |
| Security headers and CSP | App or Lambda@Edge code | CloudFront response headers policy | No charge | **Offload** (XS-COMP-12) | The CSP content |
| Web attack filtering | Custom rules | AWS WAF managed rule groups | $5 per web ACL plus $1 per rule a month, plus $0.60 per million requests | **Offload** in prod (XS-COMP-13) | Exclusions |
| Key management | — | AWS KMS | $1 per customer-managed key a month, plus requests | **Already offloaded** (D13) | Key policies |
| Secrets (Teller token and certificate) | Encrypted columns | AWS Secrets Manager | $0.40 per secret a month | **Offload** when bank sync ships | Rotation |
| DDoS protection | — | AWS Shield Standard | No charge | **Already offloaded** | — |

**Must stay in FinTracker code:** tenant isolation (RLS and owner scoping), authorization, data minimization (XS-ACCT), deletion across services (XS-DEL), log hygiene, LLM guardrails and output validation, and the content of the privacy notice and incident runbook. No provider can own these, because they depend on FinTracker's data model.

---

## Change Log

| Change | Reason |
|---|---|
| New spec, 2026-10-29 | Track compliance per standard, and record which controls to offload |
