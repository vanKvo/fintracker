"""LB-IHTTP-01 / LB-IHTTP-02: INTERNAL_AUTH_MODE, the caller allow-list, and the guard that keeps `local` out of AWS.

Strict is the default: an unset mode is `iam`, and any value other than `iam` or `local` stops startup.
`local` never falls back from a typo. Error messages name the variable, never its value.

__author__ = "Van Vo"
"""
from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit

MODE_VARIABLE = "INTERNAL_AUTH_MODE"
ALLOWED_CALLERS_VARIABLE = "INTERNAL_ALLOWED_CALLER_ARNS"
LOCAL_CALLER_VARIABLE = "INTERNAL_LOCAL_CALLER_ARN"
BASE_URL_PREFIX = "INTERNAL_BASE_URL_"
DEFAULT_LOCAL_CALLER_ARN = "arn:local:caller"

# LB-IHTTP-02: any of these means the process runs in AWS (consolidated question 1).
AWS_RUNTIME_MARKERS = (
    "AWS_EXECUTION_ENV",
    "AWS_LAMBDA_FUNCTION_NAME",
    "ECS_CONTAINER_METADATA_URI",
    "ECS_CONTAINER_METADATA_URI_V4",
)

_SERVICE_NAME = re.compile(r"[A-Z][A-Z0-9_]*")
_PRINTABLE = re.compile(r"[\x21-\x7e]+")


class InternalConfigError(RuntimeError):
    """Invalid internal-HTTP configuration. Raised at startup (or client build); the service must not serve."""


class AuthMode(StrEnum):
    IAM = "iam"
    LOCAL = "local"


@dataclass(frozen=True, slots=True)
class InternalSettings:
    mode: AuthMode
    allowed_caller_arns: tuple[str, ...]  # ARN prefixes, as in INTERNAL_ALLOWED_CALLER_ARNS
    local_caller_arn: str

    @property
    def is_local(self) -> bool:
        return self.mode is AuthMode.LOCAL


def _parse_mode(environ: Mapping[str, str]) -> AuthMode:
    raw = environ.get(MODE_VARIABLE)
    if raw is None:
        return AuthMode.IAM
    try:
        return AuthMode(raw.strip())  # case-sensitive: "Local" is invalid
    except ValueError:
        allowed = ", ".join(mode.value for mode in AuthMode)
        raise InternalConfigError(f"{MODE_VARIABLE} must be one of: {allowed}") from None


def _parse_allowed(environ: Mapping[str, str]) -> tuple[str, ...]:
    entries = (entry.strip() for entry in environ.get(ALLOWED_CALLERS_VARIABLE, "").split(","))
    return tuple(dict.fromkeys(entry for entry in entries if entry))  # drops empties and duplicates, keeps order


def _parse_local_caller(environ: Mapping[str, str]) -> str:
    value = environ.get(LOCAL_CALLER_VARIABLE, DEFAULT_LOCAL_CALLER_ARN).strip()
    if not _PRINTABLE.fullmatch(value):
        raise InternalConfigError(f"{LOCAL_CALLER_VARIABLE} must be a non-empty printable string without spaces")
    return value


def _guard_local(environ: Mapping[str, str]) -> None:
    for marker in AWS_RUNTIME_MARKERS:
        if marker in environ:
            raise InternalConfigError(f"{MODE_VARIABLE}=local is not allowed in an AWS runtime ({marker} is set)")


def load_settings(environ: Mapping[str, str] | None = None) -> InternalSettings:
    """Reads and validates the settings. Call it at startup so a bad configuration stops the service.

    Raises:
        InternalConfigError: invalid mode, invalid local caller, or `local` inside an AWS runtime.
    """
    env = os.environ if environ is None else environ
    mode = _parse_mode(env)
    if mode is AuthMode.LOCAL:
        _guard_local(env)
    return InternalSettings(
        mode=mode,
        allowed_caller_arns=_parse_allowed(env),
        local_caller_arn=_parse_local_caller(env),
    )


def base_url_for(service: str, environ: Mapping[str, str] | None = None) -> str:
    """The URL of a target service from INTERNAL_BASE_URL_<SERVICE>, without a trailing slash.

    Raises:
        InternalConfigError: the variable is missing or not an http(s) URL. The message names the variable.
    """
    env = os.environ if environ is None else environ
    name = service.strip().upper().replace("-", "_")
    if not _SERVICE_NAME.fullmatch(name):
        raise ValueError("service must be a name such as 'LEDGER' or 'AI_ASSISTANT'")
    variable = f"{BASE_URL_PREFIX}{name}"
    raw = env.get(variable, "").strip()
    if not raw:
        raise InternalConfigError(f"{variable} is not set")
    parts = urlsplit(raw)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.query or parts.fragment or parts.username:
        raise InternalConfigError(f"{variable} must be an http(s) URL without credentials, query or fragment")
    return raw.rstrip("/")
