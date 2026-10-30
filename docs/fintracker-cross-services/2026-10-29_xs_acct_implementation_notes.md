# XS-ACCT implementation notes (2026-10-29)

Implements XS-ACCT-01 to -06. XS-ACCT-07 and -08 are Later and untouched.

## Where
- Ledger: `account/` (DTOs, service, repository), `shared/CardNumberMasker`, `shared/CardNumberValueMasker`,
  `shared/PatchField`, `shared/RejectUnknownFields`, `config/RejectUnknownFieldsConfig`,
  `config/JooqLoggingConfig`, `config/GlobalExceptionHandler` (unreadable body), `logback-spring.xml`,
  `V32__Account_Last_Four.sql`, `V33__Rewrite_Accounts_Table.sql`, masking in `TransactionServiceImpl`.
- UI: `features/accounts/last-four.ts`, `accounts.*`, `add-account-dialog/*`, `account.service.ts`.
- Python services: `log_masking.py` in analytics, ai-assistant, data-pipeline, document-service, knowledge (`src/core`)
  and user-profile (`app/core`), wired into each Powertools `Logger`. Document service and Knowledge got a new
  `src/core/observability.py` (and the `aws-lambda-powertools` dependency); their existing standard-library loggers
  are masked through the log record factory, installed when `error_handlers` is imported.
- Operational steps: `docs/instructions/xs_acct_04_account_number_purge_runbook.md`.

## Not run here
The Ledger integration tests (`*IT`, Testcontainers) need Docker, which was not running. Their behavior was
checked by hand against a scratch PostgreSQL database (migrations V1 to V33 with seeded rows, then the API with
curl in the `dev` and a deployed-style profile). Run `mvn verify` in `services/fintracker-ledger` before
setting XS-ACCT-02 to -06 to Implemented.

## Proposed spec changes (the spec is read-only for the agent)
1. XS-ACCT-05, Alt "Masking happens before the import's row fingerprint is computed": the Data pipeline computes
   the row fingerprint from the raw merchant and the Ledger stores it as sent, so the Ledger masking cannot change
   it. Suggested wording: "The Ledger keeps the fingerprint the pipeline sent, so re-importing the same file stays
   idempotent."
2. XS-ACCT-02 Refs: say that a request type is marked to reject unknown fields (the Ledger's mapper ignores them
   elsewhere), and that an unreadable request body now answers 400 `invalid_argument` instead of 500.
3. XS-ACCT-01: the Link New Account dialog no longer requires an account number for non-cash accounts; the field is
   optional for every type, as the requirement says.
4. XS-ACCT-06 Refs (Document service and Knowledge are covered too): the Python formatter also masks values that are objects (such as the exception in a stack trace),
   and user-profile masks standard-library loggers through a log record factory.

## Seen, not changed
- Updating another user's account answers 400 (an `IllegalArgumentException`), not 404 as invariant 5 requires.
