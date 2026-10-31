# fintracker-internal-http

One way for FinTracker Python services to call each other and be called over internal HTTP APIs
([LB-IHTTP](../../docs/fintracker-libraries/specs/LB-IHTTP-internal-http-spec.md)). Import name: `fintracker_internal_http`.

Outbound: SigV4 signing (or a plain caller header locally), forwarded user headers, one timeout/retry/error policy.
Inbound: the caller allow-list check, then the forwarded user context. The library does **not** verify
signatures; API Gateway does, and passes the verified caller on.

## Install

```
pip install ./libs/fintracker-internal-http
```

## Settings

| Variable | Values | Default | Notes |
|---|---|---|---|
| `INTERNAL_AUTH_MODE` | `iam`, `local` | `iam` | Case-sensitive. Anything else stops startup. **Never set by Terraform.** `local` also stops startup when `AWS_EXECUTION_ENV`, `AWS_LAMBDA_FUNCTION_NAME`, `ECS_CONTAINER_METADATA_URI` or `ECS_CONTAINER_METADATA_URI_V4` is set |
| `INTERNAL_ALLOWED_CALLER_ARNS` | comma-separated ARN **prefixes** | empty | Empty or unset: every internal call is 403 in `iam`; in `local` the list applies only when set |
| `INTERNAL_BASE_URL_<SERVICE>` | http(s) URL | none | One per target service, e.g. `INTERNAL_BASE_URL_LEDGER` |
| `INTERNAL_LOCAL_CALLER_ARN` | string | `arn:local:caller` | `local` only |
| `AWS_REGION` | region | none | `iam` outbound; falls back to `AWS_DEFAULT_REGION`; no guess |

## Usage

Startup (fail fast on a bad configuration):

```python
from fintracker_internal_http import load_settings
load_settings()   # raises InternalConfigError; do not serve
```

Inbound (FastAPI):

```python
from fastapi import Depends
from fintracker_internal_http import UserContext, get_internal_user, install_internal_exception_handlers, require_internal_caller

install_internal_exception_handlers(app)   # problem+json for rejections

@router.get("/internal/v1/goals", dependencies=[Depends(require_internal_caller)])
async def goals(user: UserContext = Depends(get_internal_user(require=("user", "timezone")))): ...
```

Inbound (Lambda handler):

```python
from fintracker_internal_http import caller_rejection
if (rejection := caller_rejection(event)) is not None:
    return rejection
```

Outbound:

```python
client = InternalClient.from_env("LEDGER")                  # INTERNAL_BASE_URL_LEDGER
response = await client.get("/internal/v1/accounts", user=UserContext(user_id, "Europe/Berlin", "EUR"))
```

A caller that holds only a user ID passes `require=("user",)` to send just that header; the default sends all three.

Errors are `InternalCallError(status, code, trace_id)`; the message never holds a body, header or URL.

## Public API

Exactly the names in `fintracker_internal_http.__all__`, their signatures and documented behavior, and the settings above
(LB-PKG-02). Services import only these names. Anything else, including every submodule, is internal and may change in any release.

| Area | Names |
|---|---|
| Version | `__version__` (read from the installed package; set only in `pyproject.toml`) |
| Settings | `load_settings`, `base_url_for`, `InternalSettings`, `AuthMode`, `InternalConfigError` |
| Outbound | `InternalClient`, `InternalResponse`, `InternalCallError`, `SigV4Signer`, `HeaderSigner`, `SigningError` |
| Inbound | `require_internal_caller`, `get_internal_user`, `user_context_from_headers`, `caller_rejection`, `install_internal_exception_handlers`, `internal_rejection_handler`, `InternalRejection` |
| User context | `UserContext`, `InvalidUserContextError`, `set_current_traceparent` (trace of the request being served) |

`fintracker_internal_http.testing` (fakes, `api_gateway_event`, `run_conformance`, `load_vectors`) is for tests only and is
not imported by production code paths.

## Tests

```
pip install -e . pytest pytest-asyncio mypy && pytest && mypy src
```
