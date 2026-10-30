# Service provider register

Last reviewed: not yet (draft; the owner sets this date after reading it)

Satisfies XS-COMP-14 (16 CFR 314.4(f)). Reviewed yearly. A provider integrated without an entry here fails the
XS-COMP-16 review.

| Provider | What it does for FinTracker | Attestation | Checked | Stays with FinTracker |
|---|---|---|---|---|
| AWS (all services used) | Hosting, database, storage, identity (Cognito), encryption keys, model hosting (Bedrock), OCR (Textract) | SOC 2 Type II: not yet downloaded. PCI DSS Attestation of Compliance: not yet downloaded. Both come from AWS Artifact in the console | not yet checked | Configuration, IAM, data, application code (architecture doc 11.2) |

**Open:** download the current AWS SOC 2 Type II report and PCI DSS Attestation of Compliance from AWS Artifact and
write their report dates into the AWS row's Attestation and Checked columns. Until then the evidence check
(`scripts/compliance/check_compliance_evidence.py`) fails on this file.

Teller (bank sync) and the payment provider (paid plans) get a row when they are integrated (XS-COMP-17, -18).
A provider with no independent attestation is listed with the reason it is accepted, or is not used.
