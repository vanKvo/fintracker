# UP-FAPI implementation summary

Date: 2026-10-30. Spec: `specs/UP-FAPI-fastapi-refactor-spec.md` (read-only; this note proposes its changes).
Tests: `specs/UP-FAPI-fastapi-refactor-tests.md`. Result: 172 tests pass (`poetry run pytest`), `ruff` clean,
`terraform validate` passes in `environments/dev` and `environments/prod`.

## What was built
- One FastAPI app (`app/main.py`: `app` and Mangum `handler`); routers in `identity/router.py` and `goals/router.py`.
- `app/lambda_handlers/authorizer.py` and `post_confirmation.py` (moved, logic unchanged).
- Services come from `core/container.py` (`get_identity_service`, `get_goals_service`, built once on first use);
  `core/config.py` holds the startup checks.
- `shared/`: `errors.py` + `error_handlers.py` (problem+json with `trace_id`), `identity.py` (`get_user_id`),
  `internal_auth.py` (`get_internal_user_id`), `request_context.py` (trace and request IDs).
- Email masking added to the log formatter and the standard-library record factory (UP-FAPI-07).
- Terraform in `infrastructure/terraform/` (`modules/lambda_function`, `modules/user_profile`, `environments/dev|prod`).
- `Dockerfile`, `docker-compose.yml` (also included from the root compose), `.dockerignore`.
- Removed (approved): the three handler modules, `app/shared/responses.py`, `template.yaml`, the four handler test
  files, the two SAM-template test files (replaced by `tests/unit/test_terraform_config.py`).

## Decisions on the spec's open questions (proposed defaults taken)
1. `invalid_notice_version` is already in the error catalog.
2. Cognito pool stays outside Terraform; the Post-Confirmation trigger is attached by hand (README in `infrastructure/terraform`).
3. One `api` function serves both APIs; the route split in API Gateway is the wall between them.
4. Infrastructure tests parse the HCL with `python-hcl2` (no credentials, no provider download).
5. Not decided: the 2.5 s cold-start target needs a measurement in `dev`.

## Behavior that changed (for the spec's Change Log, UP-FAPI-12)
| Case | Before | After | Reason |
|---|---|---|---|
| `POST /profile/goals`, body not JSON | 500 | 400 `invalid_argument` | UP-FAPI-01 fail case |
| `POST /profile/goals`, field missing | 400 `Bad Request`, message echoed the field name from `KeyError` | 400 `invalid_argument`, detail names the fields only | UP-FAPI-04: a 4xx never echoes values |
| `DELETE /profile/goals/{id}`, id not a UUID | 500 | 400 `invalid_argument` | Unhandled `ValueError` was a bug |
| Problem bodies | `request_id` on two routes | `trace_id` on all | UP-FAPI-04 |
| Internal goals, missing/invalid forwarded user | 400 `Bad Request` | 400 `invalid_argument` | Shared code |
| Problem `code` on 401/404 | absent on most | `unauthorized`, `not_found`, ... | UP-FAPI-04 |

## Proposed spec changes
- UP-FAPI-02/11 say "the local flag" without naming it; the code uses `INTERNAL_AUTH_MODE=local` from the internal-call standard.
- UP-FAPI-08: `INTERNAL_ALLOWED_CALLER_ARNS` is built from caller role **names** (`arn:aws:sts::<account>:assumed-role/<name>`),
  because API Gateway reports an assumed role as an `sts` ARN and the receiver matches by prefix; an `iam` role ARN would never match.
- UP-FAPI-08 lists no settings keys; the module has `dynamodb_pitr` and `log_retention_days` (both rows exist in app doc 6.1).
- UP-FAPI-11: the shared LocalStack is not in the root compose any more; `EVENTBRIDGE_ENDPOINT_URL` is optional and only account deletion needs it.
- `DELETE /profile` cannot verify a Cognito token in the local container, so it returns 401 there.

## Not done / needs you
- **UP-FAPI-11 is In progress:** Docker was not running, so the image was not built. The same app was run with
  `uvicorn` and checked by hand: DynamoDB down gave 503 `service_unavailable`, the internal route gave 401 without a caller,
  `/docs` served locally. Build and run `docker compose up --build user-profile` to finish the happy path with a seeded user.
- **UP-FAPI-12 is In progress:** the 20-cold-start p95 and the manual run of register, sign-in, settings, goals and delete in `dev` need a deployed `dev`.
  No characterization run against the old handlers was recorded before they moved; the expected values were taken from the old
  handler tests (which passed, 136 tests) and re-asserted through the new app.
- **Files left for you to decide** (not in the approved list): `docs/instructions/sam_user_profile_identity_local_lambda_api_gateway.md`
  (the SAM instructions the spec says to remove), and the untracked SAM leftovers `.aws-sam/`, `events/` and `requirements.txt` in the service.
- Pre-existing mypy errors in `repository.py`, `service.py`, `goals/service.py` and `log_masking.py` (`serialize` override) are untouched.
- A stray `jwt` package (1.4.0) in the service virtualenv shadowed PyJWT and broke every import of `PyJWKClient`; I uninstalled it and reinstalled PyJWT 2.13.0.
