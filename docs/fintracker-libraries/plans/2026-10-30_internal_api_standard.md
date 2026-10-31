# Plan: One Standard for Internal API Calls (Python Services)

Date: 2026-10-30 · Owner: Van Vo · Status: Proposed

> Requirements and tests are now in [LB-IHTTP](../specs/LB-IHTTP-internal-http-spec.md); versioning and releases in [LB-PKG](../specs/LB-PKG-library-packaging-spec.md). This plan keeps the reasoning and the phase order.

## 1. Goal

Every Python service sends and receives internal calls the same way, and one setting switches between:

- **`local`**: no SigV4, no caller allow-list. The caller sends plain headers. Runs only in a local container.
- **`iam`**: strict. SigV4 signing outbound; verified caller ARN checked against an allow-list inbound. Used in deployed dev and prod.

Switching is one environment variable, `INTERNAL_AUTH_MODE`, and no call-site changes.

## 2. Constraints

- **ADR-008 invariant 12:** deployed dev and prod have the same security model. `local` must be impossible to run in AWS.
- The user always comes from the forwarded `X-Internal-User-Id` (plus `X-User-Timezone`, `X-User-Currency`), per XS-CTX-04. The bypass removes the *caller* check only, never the user-context requirement.
- Status codes: no verified caller 401 `unauthorized`; unlisted caller 403 `caller_not_allowed`; missing user context 401/400 as each spec says.

## 3. What exists today (drift)

| Service | Outbound signing | Inbound check | Local bypass |
|---|---|---|---|
| Analytics | own `sigv4.py` | `core/internal_auth.py` | `APP_ENV=local` skips the whole check, **including the allow-list** |
| AI assistant | own `core/sigv4.py`, `forwarded_headers` | `core/identity.py` | `APP_ENV=local` + `LOCAL_DEV_USER_ID`, assert at startup |
| Knowledge | none (inbound only) | handler-level check | none |
| User Profile | none | `shared/internal_auth.py` | none |
| Data pipeline | own `shared/sigv4.py` | n/a | none; `APP_ENV` means "Dev" here and collides with `local` |
| Ledger (Java) | n/a | `InternalCallerFilter` | none |

Four hand-copied SigV4 and caller-check implementations. Fixes (like today's 401 to 403) have to be made in each.

## 4. Design

### 4.1 One shared package: `fintracker-internal-http`

A small pure-Python library in the repo (`libs/fintracker-internal-http/`), installed into each service by path dependency. No AWS SDK beyond `botocore` (already present for signing).

```
fintracker_internal/
  config.py      # InternalAuthMode, load_settings()
  outbound.py    # InternalClient (httpx) + signer strategies
  inbound.py     # caller_rejection(), get_internal_user(), FastAPI + raw-event adapters
  headers.py     # constants: X-Internal-User-Id, X-User-Timezone, X-User-Currency, X-Internal-Caller-Arn
  errors.py      # problem+json bodies for 401 / 403 / 400
```

### 4.2 Settings

| Variable | Values | Notes |
|---|---|---|
| `INTERNAL_AUTH_MODE` | `iam` (default), `local` | Anything else fails startup. Unset means `iam`. |
| `INTERNAL_ALLOWED_CALLER_ARNS` | comma list | Required in `iam`. Empty means every internal call gets 403. |
| `INTERNAL_BASE_URL_<SERVICE>` | URL | Outbound target, e.g. `INTERNAL_BASE_URL_LEDGER`. |
| `INTERNAL_LOCAL_CALLER_ARN` | string | `local` only; the caller identity stamped on requests, default `arn:local:caller`. |

**Safety guard (startup, every service):** if `INTERNAL_AUTH_MODE=local` and any of `AWS_EXECUTION_ENV`, `AWS_LAMBDA_FUNCTION_NAME`, `ECS_CONTAINER_METADATA_URI*` is set, the process exits. Deployed Terraform never sets the variable (infra test in each service). This replaces each service's own `APP_ENV=local` check for internal calls. `APP_ENV` is left alone, so the Data pipeline collision goes away.

### 4.3 Outbound

```python
client = InternalClient.from_env("LEDGER")        # reads INTERNAL_BASE_URL_LEDGER
resp = await client.get("/internal/transactions", user=user_ctx, params=...)
```

- `user_ctx` carries user ID, timezone, currency; the client always forwards them (replaces each service's `forwarded_headers`).
- Signer strategy by mode: `SigV4Signer` (`iam`, region and service from the URL, credentials from the default chain) or `HeaderSigner` (`local`, adds `X-Internal-Caller-Arn: $INTERNAL_LOCAL_CALLER_ARN`).
- One timeout, one retry policy (idempotent GETs only, 2 retries with jitter), trace ID propagated via `traceparent`.
- Errors map to one `InternalCallError(status, code, trace_id)`. Response bodies are never logged.

### 4.4 Inbound

```python
@router.get("/internal/goals", dependencies=[Depends(require_internal_caller)])
async def goals(user: InternalUser = Depends(get_internal_user)): ...
```

- `iam`: caller from `requestContext.authorizer.iam.userArn` (API Gateway) only. None: 401. Not on the list: 403.
- `local`: caller from `X-Internal-Caller-Arn` (any value, default accepted); the allow-list is **still applied** if `INTERNAL_ALLOWED_CALLER_ARNS` is set, so local can exercise the 403 path. Missing header in local: 401, same as prod.
- Then `get_internal_user` reads the forwarded headers. The user header is never read when the caller check fails.
- A raw-event adapter (`caller_rejection(event)`) serves the Lambda-handler services (Knowledge) until they move to FastAPI. Same function, same bodies.

### 4.5 Ledger (Java)

Not part of the shared package. Keep `InternalCallerFilter` and add the same guard: a `local` profile property `fintracker.internal.auth-mode=local` that reads `X-Internal-Caller-Arn` without requiring API Gateway, and a startup check against AWS env. Python callers behave identically against Ledger because the header contract is the same.

### 4.6 Edge in AWS

Unchanged: API Gateway verifies SigV4 (`AWS_IAM`) and puts the caller ARN in the request context. The library does not verify signatures itself, so in `iam` mode a service reachable without API Gateway in front of it would have no authentication. Hence the startup guard cannot protect that case; infra tests must assert internal routes exist only on an `AWS_IAM` API.

## 5. Phases

| Phase | Work | Done when |
|---|---|---|
| 1 | Create the library with unit tests: mode parsing, guard, 401/403 matrix, header forwarding, signer selection | Tests cover every row of 6 |
| 2 | Adopt in Analytics (replace `internal_auth.py`, `sigv4.py`; remove the allow-list skip) | Existing Analytics tests pass; a new test proves the allow-list applies in `local` |
| 3 | Adopt in AI assistant (`tools/clients.py`, `summary/facts_client.py`, `core/sigv4.py`, `forwarded_headers`) | Chat and summary tests pass unchanged |
| 4 | Adopt in User Profile and Knowledge inbound; Data pipeline outbound | Per-service 401/403 tests pass |
| 5 | Ledger `local` mode and guard | `InternalApiSecurityIT` plus a local-mode test |
| 6 | Delete the old copies; add a grep-style CI check that no service imports `botocore.auth` outside the library | CI check green |

Phases 2 and 3 are the ones that unblock local testing of AI Chat; do them first.

## 6. Test matrix (library and per service)

| Mode | Caller | On list | User header | Result |
|---|---|---|---|---|
| iam | none | n/a | any | 401 `unauthorized` |
| iam | ARN | no | any | 403 `caller_not_allowed`, user header not read |
| iam | ARN | yes | missing | 401 `user_context_missing` |
| iam | ARN | yes | valid | 200 |
| local | none | n/a | any | 401 |
| local | header | list set, not on it | any | 403 |
| local | header | no list or on it | valid | 200 |
| startup | `local` + `AWS_LAMBDA_FUNCTION_NAME` | n/a | n/a | process exits |
| startup | invalid mode string | n/a | n/a | process exits |

## 7. Risks and open questions

- **Library distribution:** a path dependency means each service's Docker build context must include `libs/`. Compose and Lambda packaging both need to build from the repo root. Alternative: publish to a private index; heavier than this repo needs.
- **Lambda size:** `httpx` plus `botocore` signing is already in Analytics and the AI assistant; Knowledge and User Profile gain a small dependency.
- **Header spoofing in `local`:** acceptable because the local network is the developer's machine; enforced by the guard, not by trust.
- **Open:** keep `APP_ENV=local` as an alias for `INTERNAL_AUTH_MODE=local` during migration? Proposed: no, to avoid two switches.
- **Open:** Ledger's 401 tests in five files still assert the old status and need the 403 update from the earlier change.
