# LB-IHTTP: Internal HTTP Library

| Field | Value |
|---|---|
| Product | FinTracker |
| Prefix | LB-IHTTP |
| File | fintracker-libraries/specs/LB-IHTTP-internal-http-spec.md |
| Owner | Van Vo |
| Status | Draft |
| Last updated | 2026-10-30 |

---

## 1. Overview

### Problem
Python services call each other, and are called, over internal HTTP APIs behind IAM. Each service has its own copy of the SigV4 signing, the caller allow-list check and the forwarded user headers. The copies have drifted: Analytics' local bypass skips the allow-list, the Data pipeline's `APP_ENV` means an environment name while other services use it for `local`, and Knowledge and User Profile have no local mode at all. A fix, like the 401 to 403 change, must be made in every copy. Local testing of the AI assistant with Knowledge is blocked because each service switches off the IAM check in a different way, or cannot.

### Goals
- One Python package, `fintracker-internal-http`, holds outbound signing, the inbound caller check and user context handling. Services contain no copy of this logic.
- One setting, `INTERNAL_AUTH_MODE`, switches every service between `local` (no signing, caller sent as a plain header) and `iam` (strict) with no call-site change.
- `local` can never run in AWS.
- Behavior in `iam` mode is identical to what the services do today, so the migration changes no deployed behavior.
- Ledger (Java) follows the same header and status contract, proved by shared test vectors.

### Non-Goals
- The library does not verify SigV4 signatures. API Gateway does that at the edge; the library reads the verified caller it passes on.
- No change to the IAM design (ADR-011) or to which services may call which.
- Log redaction is a separate library. How libraries are versioned, released and adopted is in LB-PKG.
- No service discovery, no circuit breaker and no caching of responses.
- No Java library. Ledger keeps its own filter and is held to the same contract by LB-IHTTP-10.

### Design Principles
1. **Strict is the default.** An unset or unknown mode is `iam`, or a startup failure. Nothing is lenient unless `local` is set on purpose.
2. **The caller check comes before everything.** The user headers are not read until the caller passes.
3. **Same code in every environment.** Local and `iam` run the same functions; only the signer and the source of the caller differ.
4. **No leaks.** Error bodies and logs never hold a header value, an ARN from the request, a user ID or a response body.
5. **Contract over code.** The status codes, error codes and header names in Appendix A are the contract. Any implementation, including Ledger's, is tested against it.

---

## 2. Workflow

```
[Service starts] ──► LB-IHTTP-01, LB-IHTTP-02
    │
[Service calls another service]
    ├─ build the request, sign it by mode ──► LB-IHTTP-03
    └─ send, retry, map errors ──► LB-IHTTP-04
    │
[Service receives an internal call]
    ├─ who is the caller? ──► LB-IHTTP-05
    ├─ which user? ──► LB-IHTTP-06
    └─ rejection bodies ──► LB-IHTTP-07
    │
[Developers test and adopt]
    ├─ fakes and conformance suite ──► LB-IHTTP-08
    ├─ replace the copies, keep them out ──► LB-IHTTP-09
    └─ Ledger follows the same contract ──► LB-IHTTP-10
```

---

## 3. Requirements Index

| ID | Title | Area | Priority | Status |
|---|---|---|---|---|
| LB-IHTTP-01 | `INTERNAL_AUTH_MODE` selects strict or local behavior | Security | MVP | Implemented |
| LB-IHTTP-02 | Local mode refuses to start in AWS | Security | MVP | Implemented |
| LB-IHTTP-03 | The outbound client signs by mode and forwards the user | Security | MVP | Implemented |
| LB-IHTTP-04 | The outbound client has one timeout, retry and error policy | Reliability | MVP | Implemented |
| LB-IHTTP-05 | The inbound check rejects missing and unlisted callers | Security | MVP | Implemented |
| LB-IHTTP-06 | User context is read only after the caller passes | Security | MVP | Implemented |
| LB-IHTTP-07 | Rejections are problem+json with fixed codes | Quality | MVP | Implemented |
| LB-IHTTP-08 | The package ships fakes and a conformance suite | Quality | MVP | Implemented |
| LB-IHTTP-09 | Services use the library and keep no copy | Quality | MVP | Implemented |
| LB-IHTTP-10 | Ledger meets the same contract | Quality | MVP | In progress |

---

## 4. Requirements

### LB-IHTTP-01: `INTERNAL_AUTH_MODE` selects strict or local behavior  `Priority: MVP`

**Requirement:** `load_settings()` reads `INTERNAL_AUTH_MODE`. `iam` (the default when unset) means strict behavior; `local` means no signing and a caller taken from a header. In `iam` mode `INTERNAL_ALLOWED_CALLER_ARNS` (comma-separated) is read; an empty or unset list is valid and makes every internal call a 403. `INTERNAL_BASE_URL_<SERVICE>` gives each target service's URL in both modes.
**Acceptance Criteria:**
- [Happy] With the variable unset, the settings report mode `iam`.
- [Happy] `INTERNAL_AUTH_MODE=local` reports mode `local`.
- [Alt] Mode names are case-sensitive and trimmed of spaces; `Local` or `LOCAL` is invalid.
- [Alt] `INTERNAL_ALLOWED_CALLER_ARNS` entries are trimmed, empty entries dropped, and duplicates ignored.
- [Fail] Any other value (`dev`, `off`, an empty string that is set) raises at startup naming the variable and the allowed values, and never falls back to `local`.
- [Fail] A missing `INTERNAL_BASE_URL_<SERVICE>` raises when that client is built, naming the variable.
**Refs:** ADR-008 invariant 12; Appendix B

### LB-IHTTP-02: Local mode refuses to start in AWS  `Priority: MVP`

**Requirement:** When the mode is `local`, startup fails if any of `AWS_EXECUTION_ENV`, `AWS_LAMBDA_FUNCTION_NAME`, `ECS_CONTAINER_METADATA_URI` or `ECS_CONTAINER_METADATA_URI_V4` is set. Terraform for each service never sets `INTERNAL_AUTH_MODE`; this is asserted by that service's infrastructure tests.
**Acceptance Criteria:**
- [Happy] `local` starts when none of the four markers is set.
- [Alt] `iam` starts whether or not the markers are set.
- [Fail] `local` with any one marker set raises at startup with a message naming the marker (not its value) and the process does not serve requests.
- [Fail] A service's `terraform test` fails if `INTERNAL_AUTH_MODE` appears in any function or task environment.
**Open Questions:** Which markers identify an AWS runtime (consolidated question 1).
**Refs:** ADR-008 invariant 12

### LB-IHTTP-03: The outbound client signs by mode and forwards the user  `Priority: MVP`

**Requirement:** `InternalClient.from_env("<SERVICE>")` builds a client for one target service. Each call takes a `UserContext` (user ID, timezone, currency) and always sends `X-Internal-User-Id`, `X-User-Timezone` and `X-User-Currency`. In `iam` mode the request is signed with SigV4 (service `execute-api`, region from `AWS_REGION`, credentials from the default chain, body hash included). In `local` mode it is not signed and carries `X-Internal-Caller-Arn` set to `INTERNAL_LOCAL_CALLER_ARN` (default `arn:local:caller`).
**Acceptance Criteria:**
- [Happy] In `iam` mode a request has a valid `Authorization: AWS4-HMAC-SHA256` header and the three user headers.
- [Happy] In `local` mode a request has no `Authorization` header, has `X-Internal-Caller-Arn`, and the three user headers.
- [Alt] A call without a `UserContext` is a programming error and raises before any network call.
- [Alt] Header values set by the caller of the library for the reserved names are replaced by the library's, never merged.
- [Fail] If credentials cannot be found in `iam` mode, the call raises `InternalCallError` with code `signing_failed` and sends nothing.
- [Fail] An incomplete `UserContext` (empty user ID, unknown currency format) raises before any network call.
**Refs:** XS-CTX-04; Appendix A

### LB-IHTTP-04: The outbound client has one timeout, retry and error policy  `Priority: MVP`

**Requirement:** Every call has a connect timeout of 2 s and a read timeout of 10 s unless the caller sets others, and a total deadline of 25 s. Idempotent calls (GET, HEAD) are retried at most 2 times on connection errors and on 502, 503 and 504, with jittered delays of 100 ms and 300 ms. Other methods are never retried. The `traceparent` header is sent on every call, taken from the current request or generated. Every failure becomes `InternalCallError` with `status`, `code` and `trace_id`.
**Acceptance Criteria:**
- [Happy] A 200 response returns the parsed body and the status.
- [Alt] A GET that gets 503 then 200 returns the 200 after one retry.
- [Alt] A 4xx response is never retried and surfaces its `code` from the problem+json body, or `upstream_error` if the body has none.
- [Fail] A POST that gets 503 is not retried and raises `InternalCallError(status=503)`.
- [Fail] After the deadline the call raises `InternalCallError(code="timeout")`, not a raw transport exception.
- [Fail] No log line from a call holds a request or response body, a header value or the full URL query string.
**Refs:** XS-ERR error catalog (`timeout`, `service_unavailable`)

### LB-IHTTP-05: The inbound check rejects missing and unlisted callers  `Priority: MVP`

**Requirement:** `require_internal_caller` (a FastAPI dependency) and `caller_rejection(event)` (for services still written as Lambda handlers) decide on the caller before anything else. In `iam` mode the caller is `requestContext.authorizer.iam.userArn` of the API Gateway event only; a client-sent `X-Internal-Caller-Arn` is ignored. In `local` mode the caller is the `X-Internal-Caller-Arn` header. No caller is a 401 `unauthorized`. A caller that is not on `INTERNAL_ALLOWED_CALLER_ARNS` is a 403 `caller_not_allowed`. In `local` mode the list is applied only when it is set, so the 403 path can be tested locally.
**Acceptance Criteria:**
- [Happy] `iam`: a caller on the list passes.
- [Happy] `local`: a request with the header and no list set passes.
- [Alt] `iam`: an `X-Internal-Caller-Arn` header on a request whose event has no verified caller is a 401, not a pass.
- [Alt] `local`: the header present and a list set that does not include it is a 403.
- [Fail] `iam`: no verified caller is 401 `unauthorized`; a caller off the list, or an empty or unset list, is 403 `caller_not_allowed`.
- [Fail] `local`: no header is 401 `unauthorized`.
**Refs:** XS-CTX-04; ADR-011; Appendix A matrix

### LB-IHTTP-06: User context is read only after the caller passes  `Priority: MVP`

**Requirement:** `get_internal_user` returns a `UserContext` built from `X-Internal-User-Id` (a UUID), `X-User-Timezone` (an IANA name) and `X-User-Currency` (an ISO 4217 code), and runs only after `require_internal_caller` succeeded. Which of the three a route needs is declared on the dependency (`get_internal_user(require=("user",))`); a route that needs timezone or currency but receives none gets the response in the table in Appendix A. The user is never taken from a path, query or body.
**Acceptance Criteria:**
- [Happy] A valid user ID returns the context, with timezone and currency when sent.
- [Alt] A route that declares only `user` accepts a request without timezone and currency.
- [Fail] A missing or non-UUID user ID is 401 `user_context_missing` when missing, 400 `invalid_argument` when malformed, and the value is not echoed.
- [Fail] A missing timezone on a route that requires it is 409 `user_settings_incomplete`; an invalid timezone or currency is 500 `user_context_invalid` (XS-CTX-05).
- [Fail] When the caller check fails, the user headers are not read (a test makes the header access raise).
**Open Questions:** Missing user ID: 401 here and in Ledger, 400 in UP-FAPI-03 (see consolidated question 3).
**Refs:** XS-CTX-04, XS-CTX-05; Appendix A

### LB-IHTTP-07: Rejections are problem+json with fixed codes  `Priority: MVP`

**Requirement:** Every rejection the library produces is `application/problem+json` with `type`, `title`, `status`, `detail`, `code` and `trace_id`, using exactly the codes and statuses of Appendix A. `detail` is a fixed sentence per code. Bodies never contain the caller ARN, a header value, a user ID or a reason that tells an attacker which check failed beyond the code.
**Acceptance Criteria:**
- [Happy] A 403 body has `code: caller_not_allowed` and a `trace_id`.
- [Alt] `trace_id` comes from `traceparent` when valid, else is generated.
- [Alt] The Lambda-handler adapter returns the same body inside the API Gateway response shape (`statusCode`, `headers`, `body`).
- [Fail] A rejection for the ARN `arn:aws:iam::999999999999:role/x` does not contain that string.
- [Fail] An error while building a rejection returns a bare 500 `internal_error`, never an unchecked exception.
**Refs:** `docs/fintracker-architecture/error-catalog.md`

### LB-IHTTP-08: The package ships fakes and a conformance suite  `Priority: MVP`

**Requirement:** The package includes `fintracker_internal_http.testing` with: a fake internal server for outbound tests (records requests, replays chosen responses, injects failures), helpers that build API Gateway events with or without a verified caller, and a conformance suite (`run_conformance(app_factory)`) that exercises the matrix in Appendix A against a service's real internal route. It also ships `vectors/internal_auth.json`, the matrix as data, used by the Python suite and by Ledger (LB-IHTTP-10). The testing module is not imported by production code paths.
**Acceptance Criteria:**
- [Happy] A service that wires a FastAPI route with the dependencies passes `run_conformance` with no extra code beyond the factory.
- [Happy] The fake server lets a service test a retry without a network.
- [Alt] The vectors file is plain JSON with one row per Appendix A case, and the package's own tests read it.
- [Fail] A service whose route skips `require_internal_caller` fails the conformance suite on the 401 case.
- [Fail] Importing `fintracker_internal_http` in a clean interpreter does not import `fintracker_internal_http.testing` (checked in the package's tests).
**Refs:** LB-IHTTP-10; Appendix A

### LB-IHTTP-09: Services use the library and keep no copy  `Priority: MVP`

**Requirement:** Analytics, the AI assistant, User Profile, Knowledge and the Data pipeline replace their own signing, caller check and forwarded-header code with the library, in the order in LB-PKG adoption (AI assistant and Analytics first). When a service is adopted, its copy is deleted in the same change. A repository check fails the build if a service imports `botocore.auth`, `botocore.awsrequest.AWSRequest` for signing, or defines its own `X-Internal-Caller-Arn` handling outside the library. Services stop using `APP_ENV=local` for internal calls; `APP_ENV` is left as it is.
**Acceptance Criteria:**
- [Happy] Each service's existing tests for internal routes pass unchanged except for the setting name.
- [Happy] Each service passes `run_conformance` in CI.
- [Alt] Analytics' local mode applies the allow-list when a list is set (the old skip is gone).
- [Fail] A change that adds a signing helper to a service fails the repository check.
- [Fail] A service pinned to a library version that fails its own conformance run does not build.
**Refs:** LB-PKG-05; plan `fintracker-libraries/plans/2026-10-30_internal_api_standard.md`

### LB-IHTTP-10: Ledger meets the same contract  `Priority: MVP`

**Requirement:** Ledger's `InternalCallerFilter` and `UserContextFilter` return the statuses, codes and header names of Appendix A. A Ledger test reads `vectors/internal_auth.json` (a copy checked in with the version of the library it came from, recorded in the file) and runs every row against the filter. Ledger gets a `local` mode with the same guard as LB-IHTTP-02: `fintracker.internal.auth-mode=local` reads the caller from the header, and startup fails if an AWS runtime marker is set.
**Acceptance Criteria:**
- [Happy] Every row of the vectors passes against Ledger's filters.
- [Alt] A Python service in `local` mode calls a Ledger in `local` mode and gets a 200 with the same headers.
- [Fail] A Ledger started in `local` mode with `AWS_EXECUTION_ENV` set exits at startup.
- [Fail] Updating the vectors without updating the recorded library version fails a Ledger test.
**Open Questions:** How Ledger gets the vectors (consolidated question 2).
**Refs:** LB-IHTTP-02, LB-IHTTP-08

---

## 5. Open Questions (consolidated)

| # | Question | Blocks |
|---|---|---|
| 1 | Which environment variables mark an AWS runtime for the guard? Proposed: the four in LB-IHTTP-02. A container started by another AWS service (CodeBuild, App Runner) would need its own marker. | LB-IHTTP-02 |
| 2 | Copy the vectors file into Ledger on each release, or have Ledger's build fetch it from the library at the pinned version? Proposed: copy, with the version recorded, so Ledger's build needs no Python package. | LB-IHTTP-10 |
| 3 | A missing forwarded user ID is 401 `user_context_missing` in Ledger and in this spec, but UP-FAPI-03 says 400 `invalid_argument`. Proposed: follow this spec (missing is 401, malformed is 400) and change UP-FAPI-03 and its tests to match. | LB-IHTTP-06 |

---

## Appendix A: Contract

**Headers**

| Header | Direction | Meaning |
|---|---|---|
| `X-Internal-User-Id` | caller to service | UUID of the user the call is for |
| `X-User-Timezone` | caller to service | IANA timezone name |
| `X-User-Currency` | caller to service | ISO 4217 code |
| `X-Internal-Caller-Arn` | caller to service, `local` mode and Ledger only | Caller identity. Ignored by Python services in `iam` mode |
| `traceparent` | both | W3C trace context |

**Caller matrix** (each row is one entry of `vectors/internal_auth.json`)

| Mode | Verified caller | On list | User headers | Status | Code |
|---|---|---|---|---|---|
| iam | none | n/a | any | 401 | `unauthorized` |
| iam | `X-Internal-Caller-Arn` only, no verified caller | n/a | any | 401 | `unauthorized` |
| iam | yes | no | any | 403 | `caller_not_allowed` |
| iam | yes | list empty or unset | any | 403 | `caller_not_allowed` |
| iam | yes | yes | user ID missing | 401 | `user_context_missing` |
| iam | yes | yes | user ID not a UUID | 400 | `invalid_argument` |
| iam | yes | yes | valid | 200 | none |
| local | header missing | n/a | any | 401 | `unauthorized` |
| local | header | list set, not on it | any | 403 | `caller_not_allowed` |
| local | header | list unset, or on it | valid | 200 | none |
| startup | `local` with an AWS marker set | n/a | n/a | process exits | n/a |
| startup | invalid mode string | n/a | n/a | process exits | n/a |

**Context errors (when a route requires them)**

| Case | Status | Code |
|---|---|---|
| Timezone missing | 409 | `user_settings_incomplete` |
| Timezone or currency present but invalid, or currency missing when required | 500 | `user_context_invalid` |

## Appendix B: Settings

| Variable | Values | Default | Notes |
|---|---|---|---|
| `INTERNAL_AUTH_MODE` | `iam`, `local` | `iam` | Never set by Terraform |
| `INTERNAL_ALLOWED_CALLER_ARNS` | comma-separated ARNs | empty | Built from role ARNs in Terraform (ADR-011) |
| `INTERNAL_BASE_URL_<SERVICE>` | URL | none | One per target service, e.g. `INTERNAL_BASE_URL_LEDGER` |
| `INTERNAL_LOCAL_CALLER_ARN` | string | `arn:local:caller` | `local` mode only |

## Appendix C: Package layout

```
libs/fintracker-internal-http/
  pyproject.toml
  CHANGELOG.md
  src/fintracker_internal_http/
    __init__.py        # public API, __all__
    config.py          # load_settings, mode, guard
    outbound.py        # InternalClient, signers, retry policy
    inbound.py         # require_internal_caller, get_internal_user, caller_rejection
    context.py         # UserContext and validation
    problems.py        # problem+json bodies
    testing/           # fakes, event builders, run_conformance
    vectors/internal_auth.json
  tests/
```

---

## Change Log

| Change | Reason |
|---|---|
| New spec | Turn the internal API standard plan into requirements and tests developers can build against |
