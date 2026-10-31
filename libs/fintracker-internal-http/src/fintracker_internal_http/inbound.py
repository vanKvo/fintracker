"""LB-IHTTP-05 / LB-IHTTP-06: who is calling, and on whose behalf, for an internal route.

The caller is decided first. In `iam` mode it is the ARN API Gateway verified
(requestContext.authorizer.iam.userArn) and nothing the client sent; in `local` mode it is the
X-Internal-Caller-Arn header. Only after the caller passes are the user headers read.

No verified caller -> 401 `unauthorized`; a caller not on INTERNAL_ALLOWED_CALLER_ARNS -> 403
`caller_not_allowed`. The library does not verify SigV4: API Gateway does, and passes the caller on.

__author__ = "Van Vo"
"""
from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable, Iterable, Mapping
from typing import Any, Literal

from fastapi import Depends
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from . import problems
from .config import InternalConfigError, InternalSettings, load_settings
from .context import (
    CALLER_ARN_HEADER,
    CURRENCY_HEADER,
    TIMEZONE_HEADER,
    TRACEPARENT_HEADER,
    USER_ID_HEADER,
    InvalidUserContextError,
    UserContext,
    parse_currency,
    parse_timezone,
    parse_user_id,
    set_current_traceparent,
)

logger = logging.getLogger("fintracker_internal_http.inbound")

Need = Literal["user", "timezone", "currency"]
_NEEDS: frozenset[str] = frozenset(("user", "timezone", "currency"))


class InternalRejection(Exception):
    """A request refused by the internal-HTTP checks. Rendered as problem+json by the installed handler."""

    def __init__(self, code: str, trace_id: str) -> None:
        self.code = code
        self.trace_id = trace_id
        super().__init__(code)

    @property
    def status(self) -> int:
        return problems.PROBLEMS[self.code].status


# ---- framework-free decisions ------------------------------------------------------------------------------


def _clean(value: object) -> str | None:
    return value.strip() or None if isinstance(value, str) else None


def _header(headers: Mapping[str, Any] | None, name: str) -> str | None:
    """Case-insensitive lookup in an untrusted header mapping."""
    if not isinstance(headers, Mapping):
        return None
    wanted = name.lower()
    for key, value in headers.items():
        if isinstance(key, str) and key.lower() == wanted:
            return _clean(value)
    return None


def _child(node: object, key: str) -> object:
    return node.get(key) if isinstance(node, Mapping) else None


def verified_caller_from_event(event: object) -> str | None:
    """requestContext.authorizer.iam.userArn of an API Gateway event. The event is untrusted input."""
    node: object = event
    for key in ("requestContext", "authorizer", "iam", "userArn"):
        node = _child(node, key)
    return _clean(node)


def rejection_code(settings: InternalSettings, *, verified_caller: str | None, header_caller: str | None) -> str | None:
    """None if the caller may proceed, else the rejection code. In `iam` the header is never consulted."""
    caller = header_caller if settings.is_local else verified_caller
    if caller is None:
        return "unauthorized"
    if settings.is_local and not settings.allowed_caller_arns:
        return None  # local: the list applies only when it is set, so 403 stays testable
    if any(caller.startswith(prefix) for prefix in settings.allowed_caller_arns):
        return None
    return "caller_not_allowed"


def _load_settings_or_reject(trace_id: str) -> InternalSettings:
    try:
        return load_settings()
    except InternalConfigError:
        logger.error("Internal HTTP configuration is invalid", extra={"severity": "alarm", "trace_id": trace_id})
        raise InternalRejection("internal_error", trace_id) from None


def _log_rejection(code: str, trace_id: str) -> None:
    # Never the ARN or any header value.
    logger.warning("Rejected internal call", extra={"severity": "security", "code": code, "trace_id": trace_id})


# ---- FastAPI ------------------------------------------------------------------------------------------------


async def require_internal_caller(request: Request) -> str:
    """FastAPI dependency: the caller check, before anything else. Returns the caller ARN."""
    traceparent = _header(request.headers, TRACEPARENT_HEADER)
    trace_id = problems.trace_id_from(traceparent)
    settings = _load_settings_or_reject(trace_id)
    verified = verified_caller_from_event(request.scope.get("aws.event"))
    header_caller = _clean(request.headers.get(CALLER_ARN_HEADER.lower())) if settings.is_local else None
    code = rejection_code(settings, verified_caller=verified, header_caller=header_caller)
    if code is not None:
        _log_rejection(code, trace_id)
        raise InternalRejection(code, trace_id)
    if problems.parse_traceparent(traceparent):
        set_current_traceparent(traceparent)
    caller = header_caller if settings.is_local else verified
    assert caller is not None  # rejection_code returns "unauthorized" otherwise
    return caller


def user_context_from_headers(
    headers: Mapping[str, Any] | None, *, require: Iterable[Need] = ("user",), trace_id: str | None = None
) -> UserContext:
    """The user context from forwarded headers. Call it only after the caller check passed.

    Raises:
        InternalRejection: user ID missing (401) or malformed (400); timezone missing where required (409);
            a timezone or currency that is present but invalid, or a required currency that is missing (500).
    """
    needs = frozenset(require)
    unknown = needs - _NEEDS
    if unknown:
        raise ValueError(f"unknown user context requirement: {', '.join(sorted(unknown))}")
    trace = trace_id or problems.trace_id_from(_header(headers, TRACEPARENT_HEADER))

    def reject(code: str, field: str) -> InternalRejection:
        if code == "user_context_invalid":  # XS-CTX-05: alarms on the first occurrence; the value is never logged
            logger.error("Invalid user context", extra={"severity": "alarm", "field": field, "trace_id": trace})
        else:
            logger.warning("Rejected internal call", extra={"code": code, "field": field, "trace_id": trace})
        return InternalRejection(code, trace)

    raw_user = _header(headers, USER_ID_HEADER)
    if raw_user is None:
        raise reject("user_context_missing", "user_id")
    try:
        user_id = parse_user_id(raw_user)
    except InvalidUserContextError:
        raise reject("invalid_argument", "user_id") from None

    timezone = _header(headers, TIMEZONE_HEADER)
    if timezone is None and "timezone" in needs:
        raise reject("user_settings_incomplete", "timezone")
    currency = _header(headers, CURRENCY_HEADER)
    if currency is None and "currency" in needs:
        raise reject("user_context_invalid", "currency")
    try:
        if timezone is not None:
            parse_timezone(timezone)
        if currency is not None:
            parse_currency(currency)
    except InvalidUserContextError as exc:
        raise reject("user_context_invalid", exc.field) from None
    return UserContext(user_id=user_id, timezone=timezone, currency=currency)


def get_internal_user(require: Iterable[Need] = ("user",)) -> Callable[..., Awaitable[UserContext]]:
    """Builds a FastAPI dependency returning the forwarded UserContext.

    `require` says which of "user", "timezone" and "currency" the route needs; the user is always required.
    The dependency runs `require_internal_caller` first, so the user headers are never read for a rejected caller.
    """
    needs = tuple(require)
    unknown = frozenset(needs) - _NEEDS
    if unknown:
        raise ValueError(f"unknown user context requirement: {', '.join(sorted(unknown))}")

    async def dependency(request: Request, caller: str = Depends(require_internal_caller)) -> UserContext:
        return user_context_from_headers(request.headers, require=needs)

    return dependency


async def internal_rejection_handler(request: Request, exc: Exception) -> Response:
    """Renders an InternalRejection as problem+json. Building the response can never raise."""
    try:
        assert isinstance(exc, InternalRejection)
        return JSONResponse(
            problems.problem_body(exc.code, exc.trace_id),
            status_code=exc.status,
            media_type=problems.PROBLEM_MEDIA_TYPE,
        )
    except Exception:  # noqa: BLE001 - a rejection must never raise
        return Response(
            json.dumps(problems.FALLBACK_BODY),
            status_code=problems.FALLBACK_STATUS,
            media_type=problems.PROBLEM_MEDIA_TYPE,
        )


def install_internal_exception_handlers(app: Any) -> None:
    """Registers the problem+json handler on a FastAPI/Starlette app (once per app)."""
    app.add_exception_handler(InternalRejection, internal_rejection_handler)


# ---- Lambda handlers ----------------------------------------------------------------------------------------


def caller_rejection(event: object, *, settings: InternalSettings | None = None) -> dict[str, Any] | None:
    """For services still written as Lambda handlers: the API Gateway response to return, or None if the caller passes."""
    headers = _child(event, "headers")
    traceparent = _header(headers if isinstance(headers, Mapping) else None, TRACEPARENT_HEADER)
    try:
        resolved = settings or load_settings()
        header_caller = _header(headers if isinstance(headers, Mapping) else None, CALLER_ARN_HEADER) if resolved.is_local else None
        code = rejection_code(resolved, verified_caller=verified_caller_from_event(event), header_caller=header_caller)
    except Exception:  # noqa: BLE001 - fail closed with a generic 500, never an unchecked exception
        logger.error("Internal caller check failed", extra={"severity": "alarm"})
        return problems.lambda_response("internal_error", traceparent)
    if code is None:
        return None
    _log_rejection(code, problems.trace_id_from(traceparent))
    return problems.lambda_response(code, traceparent)
