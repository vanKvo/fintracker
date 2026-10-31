"""LB-IHTTP-03 / LB-IHTTP-06: the user a call is made for, and the headers that carry it.

The user always travels in headers set by the calling service, never in a path, query or body
(XS-CTX-04). Validation errors name the field, never the value.

__author__ = "Van Vo"
"""
from __future__ import annotations

import re
from contextvars import ContextVar
from dataclasses import dataclass
from zoneinfo import ZoneInfo

USER_ID_HEADER = "X-Internal-User-Id"
TIMEZONE_HEADER = "X-User-Timezone"
CURRENCY_HEADER = "X-User-Currency"
CALLER_ARN_HEADER = "X-Internal-Caller-Arn"
TRACEPARENT_HEADER = "traceparent"

_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
# Shape check before ZoneInfo so odd input never reaches a file-system lookup.
_TIMEZONE = re.compile(r"[A-Za-z0-9_+\-]+(/[A-Za-z0-9_+\-]+){0,2}")
_CURRENCY = re.compile(r"[A-Z]{3}")

# The traceparent of the internal request being served, so calls made while serving it continue the trace.
_current_traceparent: ContextVar[str | None] = ContextVar("fintracker_internal_traceparent", default=None)


class InvalidUserContextError(ValueError):
    """A user context field is missing or malformed. The message names the field, never the value."""

    def __init__(self, field: str) -> None:
        self.field = field
        super().__init__(f"invalid user context field: {field}")


def parse_user_id(raw: str) -> str:
    if not isinstance(raw, str) or not _UUID.fullmatch(raw):
        raise InvalidUserContextError("user_id")
    return raw.lower()


def parse_timezone(raw: str) -> str:
    if not isinstance(raw, str) or not _TIMEZONE.fullmatch(raw):
        raise InvalidUserContextError("timezone")
    try:
        ZoneInfo(raw)
    except (ValueError, OSError, LookupError):  # ZoneInfoNotFoundError is a KeyError
        raise InvalidUserContextError("timezone") from None
    return raw


def parse_currency(raw: str) -> str:
    if not isinstance(raw, str) or not _CURRENCY.fullmatch(raw):
        raise InvalidUserContextError("currency")
    return raw


@dataclass(frozen=True, slots=True)
class UserContext:
    """Who a call is for. Outbound calls need all three fields; inbound routes declare which they need."""

    user_id: str
    timezone: str | None = None
    currency: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "user_id", parse_user_id(self.user_id))
        if self.timezone is not None:
            parse_timezone(self.timezone)
        if self.currency is not None:
            parse_currency(self.currency)

    def forwarded_headers(self, require: tuple[str, ...] = ("user", "timezone", "currency")) -> dict[str, str]:
        """The user headers an internal request carries: by default all three; `require` names the ones this call sends.

        Raises:
            InvalidUserContextError: a field in `require` is missing from this context.
        """
        wanted = set(require)
        headers = {USER_ID_HEADER: self.user_id}
        if "timezone" in wanted:
            if self.timezone is None:
                raise InvalidUserContextError("timezone")
            headers[TIMEZONE_HEADER] = self.timezone
        if "currency" in wanted:
            if self.currency is None:
                raise InvalidUserContextError("currency")
            headers[CURRENCY_HEADER] = self.currency
        return headers


def current_traceparent() -> str | None:
    return _current_traceparent.get()


def set_current_traceparent(value: str | None) -> None:
    _current_traceparent.set(value)
