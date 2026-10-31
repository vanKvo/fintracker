"""LB-IHTTP-03 / LB-IHTTP-04: calling another FinTracker service on a user's behalf.

`iam` mode signs every request with SigV4 (service `execute-api`, credentials from the default chain);
`local` mode sends the caller as X-Internal-Caller-Arn. The three user headers and `traceparent` are always
set by this client; a header of the same name from the library user is replaced, never merged.

One policy for every call: connect 2 s, read 10 s, total deadline 25 s; GET and HEAD retried twice on
connection errors and 502/503/504; every failure is an InternalCallError. Bodies, header values and query
strings are never logged.

__author__ = "Van Vo"
"""
from __future__ import annotations

import asyncio
import json as jsonlib
import logging
import os
import random
import re
import secrets
import time
from collections.abc import Awaitable, Callable, Collection, Mapping
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Protocol, Self

import httpx
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials
from botocore.exceptions import BotoCoreError
from botocore.session import get_session

from . import problems
from .config import InternalSettings, base_url_for, load_settings
from .context import CALLER_ARN_HEADER, TRACEPARENT_HEADER, UserContext, current_traceparent

logger = logging.getLogger("fintracker_internal_http.outbound")


class _RedactQuery(logging.Filter):
    """httpx logs every request URL at INFO, query string included. Strip the query from those records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(arg.copy_with(query=None) if isinstance(arg, httpx.URL) else arg for arg in record.args)
        return True


def _redact_httpx_logs() -> None:
    httpx_logger = logging.getLogger("httpx")
    if not any(isinstance(existing, _RedactQuery) for existing in httpx_logger.filters):
        httpx_logger.addFilter(_RedactQuery())

CONNECT_TIMEOUT = 2.0
READ_TIMEOUT = 10.0
DEADLINE = 25.0
SIGNING_SERVICE = "execute-api"

_IDEMPOTENT_METHODS = frozenset({"GET", "HEAD"})
_RETRY_STATUSES = frozenset({502, 503, 504})
_RETRY_DELAYS = (0.1, 0.3)  # seconds, each jittered by +-50%
_METHODS = frozenset({"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"})
_CODE = re.compile(r"[a-z][a-z0-9_]{0,63}")
_TRACE_ID = re.compile(r"[0-9a-f]{32}")
_RESERVED_PREFIXES = ("x-amz-",)
_RESERVED_HEADERS = frozenset(
    {
        "authorization",
        "host",
        "content-length",
        "x-internal-user-id",
        "x-user-timezone",
        "x-user-currency",
        CALLER_ARN_HEADER.lower(),
        TRACEPARENT_HEADER,
    }
)


class InternalCallError(Exception):
    """An internal call failed. `code` is the callee's problem code when it sent one, else a code of this library.

    The message never carries a response body, header or URL.
    """

    def __init__(self, *, status: int, code: str, trace_id: str) -> None:
        self.status = status
        self.code = code
        self.trace_id = trace_id
        super().__init__(f"internal call failed: {code} ({status})")


@dataclass(frozen=True, slots=True)
class InternalResponse:
    status: int
    body: Any  # parsed JSON; text for other content types; None when empty


# ---- signing ------------------------------------------------------------------------------------------------


class SigningError(Exception):
    """The request could not be signed (no credentials or region). The message names no secret."""


class Signer(Protocol):
    def sign(self, method: str, url: str, headers: dict[str, str], body: bytes) -> dict[str, str]:
        """The headers to send: `headers` plus whatever proves the caller. May block (credential refresh)."""


class SigV4Signer:
    """`iam` mode. Region from AWS_REGION (then AWS_DEFAULT_REGION); credentials from botocore's default chain."""

    def __init__(
        self,
        *,
        credentials_provider: Callable[[], Credentials | None] | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self._credentials_provider = credentials_provider or get_session().get_credentials
        self._environ = os.environ if environ is None else environ

    def _region(self) -> str:
        for variable in ("AWS_REGION", "AWS_DEFAULT_REGION"):
            value = self._environ.get(variable, "").strip()
            if value:
                return value
        raise SigningError("AWS_REGION is not set")  # a guessed region only fails later as an opaque 403

    def sign(self, method: str, url: str, headers: dict[str, str], body: bytes) -> dict[str, str]:
        region = self._region()
        try:
            credentials = self._credentials_provider()
            frozen = credentials.get_frozen_credentials() if credentials is not None else None
        except BotoCoreError:
            raise SigningError("AWS credentials could not be loaded") from None
        if frozen is None:
            raise SigningError("no AWS credentials available")
        request = AWSRequest(method=method, url=url, data=body, headers=dict(headers))
        SigV4Auth(frozen, SIGNING_SERVICE, region).add_auth(request)  # signs the body hash too
        return {str(name): str(value) for name, value in request.headers.items()}


class HeaderSigner:
    """`local` mode: no signature, the caller is a plain header."""

    def __init__(self, caller_arn: str) -> None:
        self._caller_arn = caller_arn

    def sign(self, method: str, url: str, headers: dict[str, str], body: bytes) -> dict[str, str]:
        return {**headers, CALLER_ARN_HEADER: self._caller_arn}


def signer_for(settings: InternalSettings) -> Signer:
    return HeaderSigner(settings.local_caller_arn) if settings.is_local else SigV4Signer()


# ---- tracing ------------------------------------------------------------------------------------------------


def _outbound_traceparent() -> str:
    """Continues the trace of the request being served (new span per call), or starts one."""
    parsed = problems.parse_traceparent(current_traceparent())
    trace_id, flags = (parsed[0], parsed[2]) if parsed else (secrets.token_hex(16), "01")
    return f"00-{trace_id}-{secrets.token_hex(8)}-{flags}"


# ---- client -------------------------------------------------------------------------------------------------


def _checked_path(path: str) -> str:
    # The path is appended to the configured base URL; anything that could change the host or smuggle a
    # query is refused (use `params=`).
    if not path.startswith("/") or path.startswith("//") or "?" in path or "#" in path or "\\" in path:
        raise ValueError("path must start with a single '/' and carry no query or fragment")
    if any(ord(char) < 0x21 for char in path):
        raise ValueError("path must not contain spaces or control characters")
    return path


def _clean_headers(headers: Mapping[str, str] | None) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for name, value in (headers or {}).items():
        lowered = name.lower()
        if lowered in _RESERVED_HEADERS or lowered.startswith(_RESERVED_PREFIXES):
            continue  # reserved: the library sets these
        cleaned[name] = value
    return cleaned


def _problem_code(response: httpx.Response) -> tuple[str, str | None]:
    """(code, trace_id) from a problem+json body, falling back to `upstream_error`. Nothing else is read from it."""
    try:
        data = response.json()
    except ValueError:
        return "upstream_error", None
    if not isinstance(data, dict):
        return "upstream_error", None
    code, trace_id = data.get("code"), data.get("trace_id")
    return (
        code if isinstance(code, str) and _CODE.fullmatch(code) else "upstream_error",
        trace_id if isinstance(trace_id, str) and _TRACE_ID.fullmatch(trace_id) else None,
    )


def _parsed_body(response: httpx.Response) -> Any:
    if not response.content:
        return None
    content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type == "application/json" or content_type.endswith("+json"):
        return response.json()
    return response.text


class InternalClient:
    """Calls one target service. Build it once per process and reuse it; close it with `aclose()`."""

    def __init__(
        self,
        base_url: str,
        *,
        service: str,
        settings: InternalSettings | None = None,
        signer: Signer | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[], float] = lambda: random.uniform(0.5, 1.5),
    ) -> None:
        resolved = settings or load_settings()
        self._base_url = base_url.rstrip("/")
        self._service = service
        self._signer = signer or signer_for(resolved)
        _redact_httpx_logs()
        self._http = httpx.AsyncClient(transport=transport, follow_redirects=False)
        self._sleep = sleep
        self._jitter = jitter

    @classmethod
    def from_env(
        cls,
        service: str,
        *,
        environ: Mapping[str, str] | None = None,
        signer: Signer | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> Self:
        """A client for INTERNAL_BASE_URL_<SERVICE>, in the mode INTERNAL_AUTH_MODE selects.

        Raises:
            InternalConfigError: the mode or the base URL variable is invalid or missing (names the variable).
        """
        settings = load_settings(environ)
        return cls(
            base_url_for(service, environ),
            service=service.strip().lower(),
            settings=settings,
            signer=signer,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        await self.aclose()

    async def get(self, path: str, *, user: UserContext, **options: Any) -> InternalResponse:
        return await self.request("GET", path, user=user, **options)

    async def post(self, path: str, *, user: UserContext, **options: Any) -> InternalResponse:
        return await self.request("POST", path, user=user, **options)

    async def put(self, path: str, *, user: UserContext, **options: Any) -> InternalResponse:
        return await self.request("PUT", path, user=user, **options)

    async def patch(self, path: str, *, user: UserContext, **options: Any) -> InternalResponse:
        return await self.request("PATCH", path, user=user, **options)

    async def delete(self, path: str, *, user: UserContext, **options: Any) -> InternalResponse:
        return await self.request("DELETE", path, user=user, **options)

    async def request(
        self,
        method: str,
        path: str,
        *,
        user: UserContext,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
        headers: Mapping[str, str] | None = None,
        require: tuple[str, ...] = ("user", "timezone", "currency"),
        accept: Collection[int] = (),
        connect_timeout: float = CONNECT_TIMEOUT,
        read_timeout: float = READ_TIMEOUT,
        deadline: float = DEADLINE,
    ) -> InternalResponse:
        """Sends one request on behalf of `user` and returns the parsed response.

        `require` names the user headers this call sends. All three by default; a caller that holds only a user ID
        passes `("user",)`, as the receiving route declares with `get_internal_user(require=("user",))`.

        `accept` lists non-2xx statuses that are a normal answer for this call (a 404 meaning "none", a 409 carrying
        details): they come back as an InternalResponse with the parsed body instead of raising.

        Raises:
            TypeError: `user` is not a UserContext.
            InvalidUserContextError: the user context lacks a timezone or currency. Nothing is sent.
            ValueError: unknown method, or a path that is not a plain absolute path.
            InternalCallError: any failure of the call itself (signing, transport, deadline, non-2xx).
        """
        if not isinstance(user, UserContext):
            raise TypeError("user must be a UserContext")
        forwarded = user.forwarded_headers(require)
        method = method.upper()
        if method not in _METHODS:
            raise ValueError("unsupported HTTP method")
        url = httpx.URL(self._base_url + _checked_path(path), params=params)

        outgoing = {**_clean_headers(headers), **forwarded}
        body = b""
        if json is not None:
            body = jsonlib.dumps(json, separators=(",", ":"), ensure_ascii=False).encode()
            outgoing = {k: v for k, v in outgoing.items() if k.lower() != "content-type"}
            outgoing["Content-Type"] = "application/json"
        outgoing[TRACEPARENT_HEADER] = traceparent = _outbound_traceparent()
        trace_id = problems.trace_id_from(traceparent)

        timeout = httpx.Timeout(connect=connect_timeout, read=read_timeout, write=read_timeout, pool=connect_timeout)
        try:
            async with asyncio.timeout(deadline):
                return await self._with_retries(method, url, outgoing, body, timeout, trace_id, frozenset(accept))
        except TimeoutError:
            self._log(method, url, attempt=0, code="timeout", status=504)
            raise InternalCallError(status=504, code="timeout", trace_id=trace_id) from None

    async def _with_retries(
        self,
        method: str,
        url: httpx.URL,
        headers: dict[str, str],
        body: bytes,
        timeout: httpx.Timeout,
        trace_id: str,
        accept: frozenset[int],
    ) -> InternalResponse:
        attempts = len(_RETRY_DELAYS) + 1 if method in _IDEMPOTENT_METHODS else 1
        for attempt in range(1, attempts + 1):
            try:
                return await self._attempt(method, url, headers, body, timeout, trace_id, attempt, accept)
            except InternalCallError as error:
                if attempt == attempts or error.status not in _RETRY_STATUSES:
                    raise
                await self._sleep(_RETRY_DELAYS[attempt - 1] * self._jitter())
        raise AssertionError("unreachable")  # pragma: no cover

    async def _attempt(
        self,
        method: str,
        url: httpx.URL,
        headers: dict[str, str],
        body: bytes,
        timeout: httpx.Timeout,
        trace_id: str,
        attempt: int,
        accept: frozenset[int],
    ) -> InternalResponse:
        started = time.monotonic()
        try:
            # Signed per attempt: the signature carries a timestamp. Off the loop: credential refresh may block.
            signed = await asyncio.to_thread(self._signer.sign, method, str(url), headers, body)
        except SigningError:
            self._log(method, url, attempt=attempt, code="signing_failed", status=500)
            raise InternalCallError(status=500, code="signing_failed", trace_id=trace_id) from None
        try:
            response = await self._http.send(
                self._http.build_request(method, url, headers=signed, content=body or None, timeout=timeout)
            )
        except httpx.TimeoutException:
            self._log(method, url, attempt=attempt, code="timeout", status=504, started=started)
            raise InternalCallError(status=504, code="timeout", trace_id=trace_id) from None
        except httpx.TransportError:
            self._log(method, url, attempt=attempt, code="service_unavailable", status=503, started=started)
            raise InternalCallError(status=503, code="service_unavailable", trace_id=trace_id) from None

        if 200 <= response.status_code < 300 or response.status_code in accept:
            try:
                parsed = _parsed_body(response)
            except ValueError:
                self._log(method, url, attempt=attempt, code="upstream_error", status=502, started=started)
                raise InternalCallError(status=502, code="upstream_error", trace_id=trace_id) from None
            self._log(method, url, attempt=attempt, code=None, status=response.status_code, started=started)
            return InternalResponse(status=response.status_code, body=parsed)

        code, upstream_trace = _problem_code(response)
        self._log(method, url, attempt=attempt, code=code, status=response.status_code, started=started)
        raise InternalCallError(status=response.status_code, code=code, trace_id=upstream_trace or trace_id)

    def _log(
        self, method: str, url: httpx.URL, *, attempt: int, code: str | None, status: int, started: float | None = None
    ) -> None:
        # Method, path, status and timing only: never a body, a header value or the query string.
        level = logging.INFO if code is None else logging.WARNING
        logger.log(
            level,
            "Internal call",
            extra={
                "target": self._service,
                "method": method,
                "path": url.path,
                "status": status,
                "code": code,
                "attempt": attempt,
                "duration_ms": round((time.monotonic() - started) * 1000) if started is not None else None,
            },
        )
