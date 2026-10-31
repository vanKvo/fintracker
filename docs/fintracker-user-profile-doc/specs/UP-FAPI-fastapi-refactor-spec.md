# UP-FAPI: FastAPI Refactor and Terraform Infrastructure

| Field | Value |
|---|---|
| Product | FinTracker |
| Prefix | UP-FAPI |
| File | fintracker-user-profile-doc/specs/UP-FAPI-fastapi-refactor-spec.md |
| Owner | Van Vo |
| Status | Draft |
| Last updated | 2026-10-30 |

---

## 1. Overview

### Problem
User Profile is the only Python service still written as one Lambda handler per route, with a SAM `template.yaml` for local runs and no real infrastructure code (the template says it lives in CDK "once Phase 2 ships"; CDK is no longer the plan). Analytics and the AI assistant are FastAPI apps behind Mangum. As a result User Profile cannot run as a plain container beside the other services, its tests must build raw API Gateway events, and its internal-route rules (caller check, user from the forwarded header) are written by hand in each handler.

### Goals
- Every HTTP route is served by one FastAPI app, with the same URLs, status codes and body shapes as today. The web client does not change.
- Lambda entry points that API Gateway or Cognito call directly, and that are not routes, live in `app/lambda_handlers/`.
- One container image runs the API locally; the same code runs in Lambda behind Mangum.
- All infrastructure is Terraform, in the layout the AI assistant and Data Pipeline already use. No CDK, and no SAM in the deployed path.
- The public API can never reach an internal route, and the internal API can never reach a public route.

### Non-Goals
- No new routes, no behavior change, no DynamoDB schema change.
- No change to the identity authorizer's logic (UP-AUTH-02 to -05); it only moves.
- The authorizer and the Cognito trigger do not become FastAPI apps.
- The hard-delete job (XS-DEL-02) is not built here; this spec only gives it a home.
- The shared internal-call standard (how a service signs and checks internal calls) is its own work: `docs/implementation_plans/2026-10-30_internal_api_standard.md`. This spec uses it.
- Managing the Cognito user pool in Terraform is not decided here (Open Question 2).

### Design Principles
1. **Characterize first.** Every route's current behavior is recorded as a test against the old handlers before any handler moves (UP-FAPI-12).
2. **Routes are thin.** A router parses the request, calls a service and shapes the response. Business rules stay in `service.py`.
3. **Trust comes from one place.** Public identity comes only from the authorizer context; internal identity only from the forwarded header after the caller check. Nothing is read from a path, query or body.
4. **Same artifact everywhere.** Local, dev and prod run the same code (app invariant 12). Local differs only by configuration.

---

## 2. Workflow

```
[Request reaches the API] ──► UP-FAPI-01
    │
[Who is calling?]
    ├─ public route: authorizer context ──► UP-FAPI-02
    └─ internal route: caller check ──► UP-FAPI-03
    │
[Services are resolved, route runs] ──► UP-FAPI-06
    │
[Any failure becomes problem+json] ──► UP-FAPI-04, UP-FAPI-07
    │
[Calls that are not routes: authorizer, Cognito trigger] ──► UP-FAPI-05
    │
[Where it runs]
    ├─ AWS: Terraform ──► UP-FAPI-08, UP-FAPI-09, UP-FAPI-10
    └─ local container ──► UP-FAPI-11
    │
[Move without changing behavior] ──► UP-FAPI-12
```

---

## 3. Requirements Index

| ID | Title | Area | Priority | Status |
|---|---|---|---|---|
| UP-FAPI-01 | One FastAPI app serves every HTTP route | Data | MVP | Implemented |
| UP-FAPI-02 | Public routes take the user from the authorizer context | Security | MVP | Implemented |
| UP-FAPI-03 | Internal routes use the standard caller check | Security | MVP | Implemented |
| UP-FAPI-06 | Services come from dependencies, not import-time singletons | Quality | MVP | Implemented |
| UP-FAPI-04 | Every error is problem+json with a code and a trace ID | Reliability | MVP | Implemented |
| UP-FAPI-07 | Log masking and trace IDs are kept | Security | MVP | Implemented |
| UP-FAPI-05 | Lambda entry points that are not routes live in `lambda_handlers/` | Quality | MVP | Implemented |
| UP-FAPI-08 | Terraform builds the table, functions and roles | Reliability | MVP | Implemented |
| UP-FAPI-09 | Terraform keeps public and internal routes on separate APIs | Security | MVP | Implemented |
| UP-FAPI-10 | Infrastructure tests read Terraform, not the SAM template | Quality | MVP | Implemented |
| UP-FAPI-11 | The service runs as a local container | Quality | MVP | In progress |
| UP-FAPI-12 | Behavior is unchanged after the move | Quality | MVP | In progress |

*IDs are not in numeric order in the index because the table follows the workflow order.*

---

## 4. Requirements

### UP-FAPI-01: One FastAPI app serves every HTTP route  `Priority: MVP`

**Problem:** Each route is its own Lambda handler, so routing, errors and identity are repeated eight times.
**Requirement:** `app/main.py` exposes `app` (FastAPI) and `handler` (Mangum). Every route in Appendix A keeps its method, path, status codes and body shape. Routes live in `identity/router.py` and `goals/router.py`, each with a public `router` and, where needed, an `internal_router`.
**Acceptance Criteria:**
- [Happy] Each route in Appendix A returns the same status and JSON body as the old handler for the same input (UP-FAPI-12 tests).
- [Alt] A path that does not exist returns 404 `not_found`, and a known path with another method returns 405 `method_not_allowed`, both as problem+json.
- [Alt] `/docs`, `/redoc` and `/openapi.json` are disabled unless the local container is running.
- [Fail] A request body that is not JSON returns 400 `invalid_argument`, not FastAPI's default 422.
**Refs:** Appendix A; Analytics `src/main.py` for the pattern

### UP-FAPI-02: Public routes take the user from the authorizer context  `Priority: MVP`

**Requirement:** A dependency `get_user_id` reads `requestContext.authorizer.lambda.internal_user_id` from the API Gateway event (`scope["aws.event"]`). Headers, query strings, paths and bodies are never read for identity. When the local flag is set (UP-FAPI-11), `LOCAL_DEV_USER_ID` stands in; startup fails if that variable is set without the local flag. `DELETE /profile` also reads the bearer token and re-verifies it to get the Cognito `sub` for removing the identity mapping, as today.
**Acceptance Criteria:**
- [Happy] A request with a valid authorizer context reaches the route with that user ID.
- [Alt] A client-sent `X-Internal-User-Id` header on a public route is ignored.
- [Fail] No authorizer context, or an `internal_user_id` that is not a UUID, returns 401 `unauthorized` before any service call.
- [Fail] `DELETE /profile` without a bearer token, or with one that does not verify, returns 401 and deletes nothing.
- [Fail] `LOCAL_DEV_USER_ID` set without the local flag stops the process at startup.
**Refs:** UP-AUTH-02; XS-CTX-02; Analytics `src/core/identity.py`

### UP-FAPI-03: Internal routes use the standard caller check  `Priority: MVP`

**Requirement:** Every route on the `internal_router` depends on the standard internal-caller check. No verified caller returns 401 `unauthorized`. A verified caller not on `INTERNAL_ALLOWED_CALLER_ARNS`, or an empty list, returns 403 `caller_not_allowed`. Only after that check is the user read, from `x-internal-user-id`, never from the path. The only internal route is `GET /profile/internal/goals`. The internal settings route is not ported; it returns 404 (XS-CTX-07).
**Acceptance Criteria:**
- [Happy] An allow-listed caller with a valid forwarded user ID gets that user's raw goals.
- [Alt] `GET /profile/internal/users/{userId}/settings` returns 404 `not_found`.
- [Fail] No verified caller returns 401 `unauthorized`; the body does not say why.
- [Fail] A caller not on the list, or an unset list, returns 403 `caller_not_allowed`, and the forwarded user header is not read.
- [Fail] A missing or non-UUID forwarded user ID returns 400 `invalid_argument` without echoing the value.
- [Fail] An unknown user returns 404 `not_found`.
**Refs:** XS-CTX-04; XS-CTX-07; app invariants 2 and 3; the internal-call standard plan

### UP-FAPI-06: Services come from dependencies, not import-time singletons  `Priority: MVP`

**Problem:** `core/container.py` reads environment variables and builds DynamoDB and EventBridge clients when it is imported, so every test has to patch module-level names.
**Requirement:** Routers receive `IdentityService` and `GoalsService` through FastAPI dependencies. The container builds each once per process, on first use. A missing required variable (`DYNAMODB_TABLE_NAME`, `EVENT_BUS_NAME`) fails the cold start through a startup check, so the deploy fails, not the first user.
**Acceptance Criteria:**
- [Happy] A test replaces a service with `app.dependency_overrides` and runs a route with no AWS client created.
- [Alt] Two requests in one process get the same service instance.
- [Fail] A cold start without `DYNAMODB_TABLE_NAME` raises at startup with the variable's name and no value.
**Refs:** AI assistant `summary/config.py::assert_required_env`

### UP-FAPI-04: Every error is problem+json with a code and a trace ID  `Priority: MVP`

**Requirement:** One error handler, as in Analytics, turns every failure into RFC 9457 `application/problem+json` with `type`, `title`, `status`, `detail`, `code` and `trace_id` (app doc 4.8). Today's `type` URLs and codes (`invalid_setting`, `invalid_notice_version`) are kept. An unexpected error returns 500 `internal_error` with a generic `detail`.
**Acceptance Criteria:**
- [Happy] `PUT /profile/settings` with an invalid timezone returns 400 with `code: invalid_setting` and the same `type` as today, plus `trace_id`.
- [Alt] `trace_id` is taken from `traceparent` when present, else generated.
- [Fail] An unhandled exception returns 500 `internal_error` with no exception text, SQL, ARN or table name, and the traceback is logged once with library messages redacted.
- [Fail] A 4xx `detail` never contains the submitted value.
**Refs:** `docs/fintracker-architecture/error-catalog.md`; Open Question 1

### UP-FAPI-07: Log masking and trace IDs are kept  `Priority: MVP`

**Requirement:** The Powertools logger with `MaskingFormatter`, and `install_record_masking()` for standard-library loggers, stay in force (XS-ACCT-06). Every log line written during a request carries `trace_id` and the API Gateway request ID. Request and response bodies are never logged.
**Acceptance Criteria:**
- [Happy] A route's log lines include the request's `trace_id`.
- [Fail] An email address or a card-number-like value passed to the logger is masked in the output.
- [Fail] No log line from a request to `PUT /profile/settings` or `POST /profile/goals` contains a field from the body.
**Refs:** XS-ACCT-06; `tests/unit/test_log_masking.py`

### UP-FAPI-05: Lambda entry points that are not routes live in `lambda_handlers/`  `Priority: MVP`

**Requirement:** Every Lambda handler that API Gateway or another AWS service calls directly, and that is not an API route, lives in `app/lambda_handlers/<name>.py`. Today that is `authorizer.py` (`authorizer_handler`, for the HTTP API and the chat REST API) and `post_confirmation.py` (`post_confirmation_handler`, the Cognito trigger). A handler only parses its event, calls a service and shapes the result. A later scheduled job (XS-DEL-02) goes in the same folder.
**Acceptance Criteria:**
- [Happy] `app.lambda_handlers.authorizer.authorizer_handler` returns the same simple response for an HTTP API event and the same IAM policy for a REST event as today.
- [Happy] `app.lambda_handlers.post_confirmation.post_confirmation_handler` creates the user and returns the original event.
- [Alt] A structure test fails if any module outside `lambda_handlers/` defines a function taking `(event, context)`.
- [Fail] The authorizer denies on every error and never raises (UP-AUTH-04).
- [Fail] A failure in `post_confirmation_handler` raises, so Cognito does not confirm the user, as today.
**Refs:** UP-AUTH-02, UP-AUTH-04; Appendix B

### UP-FAPI-08: Terraform builds the table, functions and roles  `Priority: MVP`

**Requirement:** `infrastructure/terraform/` has `modules/` and `environments/dev`, `environments/prod` (ADR-008: one `profile` setting per environment). It creates the DynamoDB table `FinTracker_UserProfile` (`PK`/`SK`, on-demand, TTL attribute `ttl`, point-in-time recovery), the three functions (`api`, `authorizer`, `post-confirmation`), each with its own least-privilege role, the Cognito permission to invoke `post-confirmation`, and an output of the authorizer's ARN for the other services' APIs. The `api` function's role can read and write the table and put events on the account-deletion bus only. The `authorizer` role can read the table only.
**Acceptance Criteria:**
- [Happy] `terraform plan` for `dev` creates the resources above and no CDK or SAM resource.
- [Alt] `INTERNAL_ALLOWED_CALLER_ARNS` is built from the caller roles' ARNs (ADR-011), never typed by hand.
- [Alt] The `INTERNAL_AUTH_MODE` setting appears nowhere in the Terraform (the local mode must not be deployable).
- [Fail] A plan in which the `authorizer` role has write access to the table fails the infrastructure tests (UP-FAPI-10).
**Refs:** ADR-007, ADR-008, ADR-011; AI assistant `infrastructure/terraform/`; Open Questions 2 and 3

### UP-FAPI-09: Terraform keeps public and internal routes on separate APIs  `Priority: MVP`

**Requirement:** The public HTTP API `user-profile` lists only the public routes of Appendix A explicitly, with no `$default` or catch-all route, and every route uses the Lambda authorizer (simple responses, identity source `Authorization`, result cached 60 s, UP-AUTH-03). The internal HTTP API `user-profile-internal` lists only `GET /profile/internal/goals`, with `AWS_IAM` authorization. Both integrate with the `api` function.
**Acceptance Criteria:**
- [Happy] Every public route in Appendix A is a route on the public API with the authorizer attached.
- [Fail] A request to `/profile/internal/goals` on the public API returns 404 from API Gateway and never reaches the Lambda.
- [Fail] A request to `/profile` on the internal API returns 404 from API Gateway.
- [Fail] A route on either API without its authorization type fails the infrastructure tests.
**Refs:** ADR-004, ADR-011; UP-AUTH-03

### UP-FAPI-10: Infrastructure tests read Terraform, not the SAM template  `Priority: MVP`

**Problem:** `tests/unit/test_authorizer_caching_config.py` and `test_settings_route_config.py` parse `template.yaml`. They stop protecting anything once the template is gone.
**Requirement:** The same checks run against the Terraform plan (`terraform show -json`) or its HCL: authorizer TTL 60 s, identity source, simple responses, every route's authorizer, no catch-all route, role permissions of UP-FAPI-08 and the absence of `INTERNAL_AUTH_MODE`.
**Acceptance Criteria:**
- [Happy] The checks pass against the `dev` plan.
- [Fail] Setting the cache TTL to 0 in the plan fails the TTL check.
- [Fail] Adding a `$default` route to the public API fails the route check.
**Refs:** UP-AUTH-03; UP-FAPI-08, UP-FAPI-09; Open Question 4

### UP-FAPI-11: The service runs as a local container  `Priority: MVP`

**Requirement:** A `Dockerfile` builds one image that runs `uvicorn app.main:app`. A compose service starts it with DynamoDB Local and the shared LocalStack (EventBridge for account deletion). The local flag (`INTERNAL_AUTH_MODE=local`, from the internal-call standard) and `LOCAL_DEV_USER_ID` are set only in the compose file.
**Acceptance Criteria:**
- [Happy] With a seeded user, `GET /profile` through the container returns 200 with no token.
- [Alt] Without the local flag, `GET /profile/internal/goals` returns 401 and a public route returns 401.
- [Fail] The container started with `LOCAL_DEV_USER_ID` and `AWS_EXECUTION_ENV` both set exits at startup.
- [Fail] If DynamoDB Local is down, a route returns 503 `service_unavailable`, not a stack trace.
**Refs:** `docs/instructions/setup_local_dynamodb.md`; the internal-call standard plan

### UP-FAPI-12: Behavior is unchanged after the move  `Priority: MVP`

**Requirement:** Before any handler moves, characterization tests record the request and response of every route in Appendix A and of both `lambda_handlers`. The same cases run unchanged against the FastAPI app. The old per-route handlers, `template.yaml`, the SAM instructions and every mention of CDK for this service are removed in the change that switches the deployment.
**Acceptance Criteria:**
- [Happy] All recorded cases pass against the new app with no edits to expected values.
- [Alt] The cold start of the `api` function in `dev` has a p95 of at most 2.5 s over 20 cold starts.
- [Alt] The web client's register, sign-in, settings, goals and delete-account flows pass a manual run against `dev` before the old functions are deleted.
- [Fail] A case whose expected value had to change is listed in the Change Log with the reason, or the change is reverted.
**Refs:** Design Principle 1; Open Question 5

---

## 5. Open Questions (consolidated)

| # | Question | Blocks |
|---|---|---|
| 1 | The catalog has no row for `invalid_notice_version` (the privacy-notice route's code). Add it in this change? Proposed: yes. | UP-FAPI-04 |
| 2 | Terraform does not manage the Cognito user pool today (see the XS-COMP-03/04/05 runbook), so the Post-Confirmation trigger cannot be attached by Terraform. Import the pool into Terraform, or attach the trigger by hand and document it? | UP-FAPI-08 |
| 3 | One `api` function for public and internal routes (proposed, as Analytics does), or two functions with separate roles? One means a shared role; the API Gateway route split (UP-FAPI-09) is then the only wall between them. | UP-FAPI-08 |
| 4 | Parse HCL (`python-hcl2`) or `terraform show -json` of a plan for the infrastructure tests? The plan needs credentials or a mock provider. | UP-FAPI-10 |
| 5 | Is a 2.5 s cold-start p95 acceptable in `dev`? | UP-FAPI-12 |

---

## Appendix A: Routes (unchanged contract)

| Method and path | API | Success | Failures | Body |
|---|---|---|---|---|
| `GET /profile` | public | 200 | 401, 404 | `userId`, `email`, `firstName`, `lastName`, `subscriptionTier`, `settings`, `privacyNotice` |
| `DELETE /profile` | public | 204 | 401, 404 | none |
| `PUT /profile/settings` | public | 200 | 400 `invalid_setting`, 401, 404 | `currency`, `timezone`, `notificationPrefs` {`channel`, `budgetAlerts`, `statementProcessed`} |
| `PUT /profile/privacy-notice` | public | 204 | 400 `invalid_notice_version`, 401 | none |
| `GET /profile/goals` | public | 200 | 401, 404 | list of `goalId`, `goalName`, `targetAmount`, `currentAmount`, `deadline` |
| `POST /profile/goals` | public | 201 | 400, 401, 404 | one goal, same fields |
| `DELETE /profile/goals/{id}` | public | 204 | 401, 404 | none |
| `GET /profile/internal/goals` | internal | 200 | 400, 401, 403, 404 | list of goals, same fields |

## Appendix B: Lambda entry points

| Handler path | Caller | Event | Returns |
|---|---|---|---|
| `app.lambda_handlers.authorizer.authorizer_handler` | API Gateway (public HTTP API, chat REST API) | REQUEST authorizer, payload v2 or REST | simple response, or IAM policy for REST |
| `app.lambda_handlers.post_confirmation.post_confirmation_handler` | Cognito Post-Confirmation | Cognito trigger | the original event |
| `app.main.handler` | API Gateway (both APIs) | HTTP API payload v2 | via Mangum |

---

## Change Log

| Change | Reason |
|---|---|
| New spec | Move User Profile to FastAPI and Terraform, and give the non-HTTP handlers a home |
