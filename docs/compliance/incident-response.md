# Incident response and breach notification

Last reviewed: not yet (draft; the owner sets this date after reading it)

Satisfies XS-COMP-02 (16 CFR 314.4(h), (j); state breach laws). Below 5,000 consumers the written plan is
optional under 16 CFR 314.6, but the FTC and state notices are not.

## 1. Severity and who decides

| Level | Meaning | Decides |
|---|---|---|
| SEV1 | Customer information confirmed or likely accessed by someone not authorized | Van Vo (Qualified Individual) |
| SEV2 | A control failed or was bypassed, no evidence of access yet | Van Vo |
| SEV3 | Suspicious event or finding, contained | Van Vo |

## 2. First hour

1. Stop the bleeding: disable the user or credential, revoke the token or key, block the source in WAF (prod).
2. Preserve evidence before changing anything: export the CloudTrail events, the audit log group, the Cognito
   sign-in event log (XS-COMP-04) and the affected `trace_id`s (architecture doc 4.7, *Investigating an incident*).
3. Open a GitHub issue with the timeline. Add to it as you go.

## 3. Notices

| Notice | When | Deadline | Recipient | Template |
|---|---|---|---|---|
| FTC | Unencrypted customer information of 500 or more consumers acquired without authorization | Within 30 days of discovery | FTC (online form) | [ftc-notice](#ftc-notice) |
| Affected users | Personal information of a state's residents breached, as that state's law defines it | As the state law requires; Virginia first | Each affected user | [user-notice](#user-notice) |
| State attorneys general | Same, above each state's threshold | As the state law requires; Virginia first | The state attorney general | [ag-notice](#attorney-general-notice) |
| AWS, Teller, payment provider | Their systems are involved | Without delay | Their security contact | [provider-notice](#provider-notice) |

Counsel confirms each state's deadline and threshold before the notice goes out.

### FTC notice
What happened and when; the kinds of information involved; the number of consumers; the date or estimated date of
discovery; whether law enforcement asked to delay notice; contact for questions.

### User notice
Plain language: what happened, what information was involved (never repeat the data itself), what FinTracker has done,
what the user should do (change password, watch statements), how to reach us, and the date.

### Attorney general notice
The user notice, plus the number of the state's residents affected and the steps taken.

### Provider notice
Which of their systems or credentials are involved, the time window, and what you need from them.

## 4. After

Close the issue with root cause and fixes. Update the risk list in the [security program](information-security-program.md)
and the controls in Appendix B if a control was missing.

## 5. Tabletop exercises

At least once a year, recorded with its date. Scenario: a leaked access token, walked end to end (detect, revoke,
preserve evidence, decide, notify). A missed year fails XS-COMP-16.

| Date | Scenario | Outcome |
|---|---|---|
| none yet | | |
