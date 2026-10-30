# Privacy notice: claim-to-control map

Notice version in force: 2026-10-29 (`PRIVACY_NOTICE_VERSION` on the user-profile service).
Text: `fintracker-ui/src/app/features/privacy/privacy-notice.html`. Satisfies XS-COMP-15.

**Rule (FTC Act §5):** every sentence in the notice maps to a control below. A claim whose control is not
*Implemented* blocks publication of the notice to real users. Change the text and this map together, and raise
the version when the change is material.

| Claim in the notice | Control | Status | Evidence |
|---|---|---|---|
| We keep only the last four digits of an account or card number | Last four only; card-like text masked on every Ledger write | Implemented | XS-ACCT-01 to -06 |
| We never ask for bank sign-in details or card numbers | Bank credentials stay with the bank-data provider; cards with the payment provider (neither is integrated yet) | Implemented (nothing collects them) | XS-ACCT; no such field exists |
| We do not sell your information or share it beyond service providers | No such flow exists; providers listed in the register | Implemented | [service-providers.md](service-providers.md) |
| AI uses summarized figures, never full account numbers | Allow-listed facts payload; last four only | Implemented | AN-FS, XS-ACCT |
| Your data is not used to train models | Bedrock does not train on prompts or outputs; no training or evaluation on user data without opt-in | Implemented (provider term) | Architecture doc 11.2 and 4.5 |
| Closed accounts: 30 days kept, then deleted within 7 days | Grace period and deletion cascade | **Designed** | XS-DEL-01 to -07 (not built) |
| Backups expire on their normal schedule | Aurora, DynamoDB PITR and S3 version expiry | Implemented (S3 versions, in Terraform); Designed (others) | XS-COMP-06 tests |
| Inactive data is disposed of two years after last use | Retention schedule | **Designed** | D15; no job exists |
| You can download your transactions | CSV export on the Transactions page | Implemented | Transactions page |
| Requests for a copy or deletion go to a contact address | Contact address in `environment.privacyContactEmail` | **Missing** (empty) | Set before launch |

**Blockers to publishing to real users:** the three bold rows. Until XS-DEL ships, either weaken the retention
sentences to what exists, or hold the notice back. The sign-up gate itself works regardless of the text.
