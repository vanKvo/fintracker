# XS-COMP-03, -04, -05: identity controls runbook

Nothing here has been run. The Cognito user pool and the AWS accounts are not managed by Terraform in this repo
(the pool ID is in `fintracker-ui/src/environments`), so these are console or CLI steps. Check each command
against the current AWS CLI reference first. Do dev first, then prod.

`update-user-pool` replaces every attribute you do not repeat, so always start from `describe-user-pool`.

## XS-COMP-03: required authenticator-app MFA, no SMS

```bash
aws cognito-idp set-user-pool-mfa-config --user-pool-id <pool-id> \
  --mfa-configuration ON --software-token-mfa-configuration Enabled=true
```
No `--sms-mfa-configuration`, so SMS is not a factor. Enrollment and the code challenge happen in the managed
sign-in pages. The app builds no enrollment screen (Phase 2.3 is superseded). Existing users without MFA are asked
to enroll at their next sign-in. Check: sign up a test user, scan the QR code, sign out, sign in and get the code prompt.

Open question 1 (XS-COMP spec): a user who loses their phone needs a support process with an identity check before
you reset their authenticator. Decide this before the first invited tester; the Settings link to Cognito's reset
flow waits on it.

## XS-COMP-04: Plus tier, enforced threat protection, sign-in event logs

1. Create a log group `/fintracker/<profile>/cognito-auth-events` with the audit retention (1 year dev, 2 years prod).
2. Switch the pool to the Plus tier and set threat protection to full-function (enforce) using `update-user-pool`
   from the described settings, and set the compromised-credential and account-takeover actions with
   `set-risk-configuration` (block high risk, challenge medium).
3. Export sign-in events to the log group:
```bash
aws cognito-idp set-log-delivery-configuration --user-pool-id <pool-id> --log-configurations \
  LogLevel=INFO,EventSource=userAuthEvents,CloudWatchLogsConfiguration={LogGroupArn=<log-group-arn>}
```
4. Alarm on a stopped export: a CloudWatch alarm on the log group's `IncomingLogEvents` with missing data treated as
   breaching, during known activity. Not codified yet.

Do not build the Phase 2.2 and 2.4 Lambda triggers. Cost: about $0.020 per monthly active user.

## XS-COMP-05: workforce access

- Both AWS accounts: sign in through IAM Identity Center with MFA; no IAM users with access keys; root user with MFA
  and no access keys. Check the IAM credential report in both accounts.
- CI: GitHub OIDC roles for the deploy workflows; GitHub account 2FA on.
- A break-glass role protected by MFA, with a CloudWatch alarm on every assumption.
- Security Hub (deployed by `infrastructure/terraform/environments/security`) reports the IAM checks, and its
  critical and high findings alarm.
