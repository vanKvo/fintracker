=========================
F2P TESTS (54)
=========================

--- terraform · s3_statement_bucket/xs_comp_06.tftest.hcl (6) ---
1. a bucket policy denies every s3 request made without TLS, for the bucket and its objects: XS-COMP-06 Fail (an http request is denied with 403).
2. noncurrent versions expire after 7 days and expired delete markers are removed: XS-COMP-06 noncurrent expiry, XS-DEL-07.
3. a customer-managed key makes the bucket encrypt with aws:kms and that key: XS-COMP-06 Happy (D13).
4. no key keeps AWS-managed AES256 encryption: XS-COMP-06 Alt (dev while it holds only the owner's data).
5. with the malware scan on the bucket notifies EventBridge and no longer invokes the processor on ObjectCreated: XS-COMP-07 only clean objects are processed.
6. with the malware scan off the processor stays wired to ObjectCreated: XS-COMP-07 scan is a switch, not a silent change.

--- terraform · dynamodb_table/xs_comp_06.tftest.hcl (3) ---
7. point-in-time recovery is on when requested: XS-COMP-06 prod tables have PITR (app doc 6.1).
8. point-in-time recovery is off by default: XS-COMP-06 Alt (dev).
9. a customer-managed key encrypts the table: XS-COMP-06 Happy (D13).

--- terraform · malware_scan/xs_comp_07.tftest.hcl (3) ---
10. the plan protects the upload bucket with tagging on and only GuardDuty can assume its role: XS-COMP-07 every upload is scanned.
11. only a NO_THREATS_FOUND result for this bucket invokes the processor: XS-COMP-07 Happy (a clean file is processed).
12. any result that is not NO_THREATS_FOUND goes to the alarm topic and not to the processor: XS-COMP-07 Fail (threats, unsupported or failed scans alarm).

--- terraform · security_baseline/xs_comp_09_10.tftest.hcl (5) ---
13. the Foundational Security Best Practices standard is always subscribed: XS-COMP-09 standards.
14. dev subscribes only the foundational standard: XS-COMP-09 Alt (dev saves cost).
15. prod also subscribes NIST SP 800-53 Rev. 5: XS-COMP-09 standards.
16. new critical and high findings go to the alarm topic: XS-COMP-09 Fail (a new critical finding alarms).
17. Inspector scans Lambda functions, Lambda code and ECR images: XS-COMP-10 scanning.

--- terraform · security_headers/xs_comp_12.tftest.hcl (2) ---
18. the policy sets HSTS, nosniff, referrer policy, frame denial and a CSP: XS-COMP-12 Happy (all five headers).
19. the CSP allows scripts only from self, forbids framing and plugins, and limits connect-src to the given origins: XS-COMP-12 Fail (an outside script is blocked).

--- terraform · waf_managed_rules/xs_comp_13.tftest.hcl (3) ---
20. the core set, known-bad-inputs set and a rate rule are attached with metrics on: XS-COMP-13 Happy (bad input blocked and counted).
21. a false positive switches one rule to count inside the still-attached group: XS-COMP-13 Fail (scoped exclusion, never removal).
22. an exclusion without a written reason is rejected: XS-COMP-13 Fail (exclusion recorded with its reason).

--- data-pipeline · TestMalwareScanGate (2) ---
23. a clean scan result starts the pipeline for that object: XS-COMP-07 Happy (a clean PDF is processed).
24. threats, unsupported, denied, failed or empty results never start the pipeline: XS-COMP-07 Fail (infected file never processed), invariant 6.

--- user-profile · TestPrivacyNoticeAcceptance (7) ---
25. a new user must accept the notice: XS-COMP-15 Happy (notice shown at sign-up).
26. accepting records the version and time the user accepted: XS-COMP-15 Happy (sign-up records the notice version).
27. a changed notice asks again and records the new acceptance: XS-COMP-15 Alt (material change shown at next sign-in).
28. accepting a version other than the current one is refused (2026-01-01): XS-COMP-15 acceptance names the version in force.
29. accepting an empty version is refused: XS-COMP-15 acceptance names the version in force.
30. accepting the word latest is refused: XS-COMP-15 acceptance names the version in force.
31. accepting without a version is refused: XS-COMP-15 acceptance names the version in force.

--- ui · privacyNoticeGuard (3) ---
32. a user who accepted the current notice reaches the app: XS-COMP-15 Happy.
33. a new user or one with an outdated acceptance is sent to the notice: XS-COMP-15 Alt (shown again after a material change).
34. when acceptance cannot be checked the app does not load: XS-COMP-15 notice before any app page.

--- ui · ProfileService privacy notice (1) ---
35. acceptance sends only the notice version, no user ID: XS-COMP-15 Happy, invariant 2 (identity only from the token).

--- ui · accessibility.spec (7) ---
36. Dashboard has no serious or critical WCAG 2.2 AA violations: XS-COMP-20 Happy/Fail.
37. Transactions has no serious or critical WCAG 2.2 AA violations: XS-COMP-20 Happy/Fail.
38. Statements has no serious or critical WCAG 2.2 AA violations: XS-COMP-20 Happy/Fail.
39. Budgets has no serious or critical WCAG 2.2 AA violations: XS-COMP-20 Happy/Fail.
40. Reports has no serious or critical WCAG 2.2 AA violations: XS-COMP-20 Happy/Fail.
41. Accounts has no serious or critical WCAG 2.2 AA violations: XS-COMP-20 Happy/Fail.
42. Settings has no serious or critical WCAG 2.2 AA violations: XS-COMP-20 Happy/Fail.

--- scripts · TestProgram (3) ---
43. a named Qualified Individual and a recent review pass: XS-COMP-01 Happy.
44. a review older than 12 months fails: XS-COMP-01 Fail (XS-COMP-16 review fails).
45. a missing name or review date fails: XS-COMP-01 Happy (document names the Qualified Individual and has a date).

--- scripts · TestIncidentResponse (3) ---
46. listed notices and a tabletop within the year pass: XS-COMP-02 Happy.
47. a missed tabletop year fails: XS-COMP-02 Fail.
48. a missing notice table fails: XS-COMP-02 Happy (each notice with deadline and recipient).

--- scripts · TestProviders (3) ---
49. AWS with dated SOC 2 Type II and PCI DSS reports passes: XS-COMP-14 Happy.
50. AWS without report dates fails: XS-COMP-14 Happy (dates recorded).
51. a provider with no attestation and no reason fails: XS-COMP-14 Alt.

--- scripts · TestMatrix (3) ---
52. a recent review and evidence on every Implemented row pass: XS-COMP-16 Happy.
53. an Implemented row without evidence fails: XS-COMP-16 Fail.
54. a review older than 12 months fails: XS-COMP-16 Happy (Last reviewed within 12 months).
