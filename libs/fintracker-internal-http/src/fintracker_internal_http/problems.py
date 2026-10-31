"""LB-IHTTP-07: the rejections this library produces, as RFC 9457 problem+json with fixed codes.

`detail` is one fixed sentence per code. A body never holds the caller ARN, a header value, a user ID, or
a reason that says which check failed beyond the code.

__author__ = "Van Vo"
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

PROBLEM_MEDIA_TYPE = "application/problem+json"
TYPE_BASE = "https://api.fintracker.com/problems/"

_TRACEPARENT = re.compile(r"(?P<version>[0-9a-f]{2})-(?P<trace>[0-9a-f]{32})-(?P<span>[0-9a-f]{16})-(?P<flags>[0-9a-f]{2})")
_ZERO_TRACE = "0" * 32
_ZERO_SPAN = "0" * 16


@dataclass(frozen=True, slots=True)
class ProblemSpec:
    status: int
    code: str
    title: str
    detail: str


# Appendix A: the codes and statuses are the contract with Ledger (LB-IHTTP-10).
PROBLEMS: dict[str, ProblemSpec] = {
    spec.code: spec
    for spec in (
        ProblemSpec(401, "unauthorized", "Unauthorized", "The request has no verified caller."),
        ProblemSpec(403, "caller_not_allowed", "Caller Not Allowed", "The caller is not allowed to use this route."),
        ProblemSpec(401, "user_context_missing", "User Context Missing", "The request has no user context."),
        ProblemSpec(400, "invalid_argument", "Invalid Request", "The request contains a value that is not valid."),
        ProblemSpec(409, "user_settings_incomplete", "User Settings Incomplete", "The user's settings are incomplete."),
        ProblemSpec(500, "user_context_invalid", "User Context Invalid", "The user context could not be read."),
        ProblemSpec(500, "internal_error", "Internal Server Error", "Something went wrong on our side."),
    )
}


def parse_traceparent(value: str | None) -> tuple[str, str, str] | None:
    """(trace_id, span_id, flags) of a valid W3C traceparent, else None."""
    if not isinstance(value, str):
        return None
    match = _TRACEPARENT.fullmatch(value.strip())
    if match is None or match["version"] == "ff" or match["trace"] == _ZERO_TRACE or match["span"] == _ZERO_SPAN:
        return None
    return match["trace"], match["span"], match["flags"]


def trace_id_from(traceparent: str | None) -> str:
    """The trace ID of a valid traceparent, else a new one."""
    parsed = parse_traceparent(traceparent)
    return parsed[0] if parsed else uuid.uuid4().hex


def problem_body(code: str, trace_id: str) -> dict[str, Any]:
    spec = PROBLEMS[code]
    return {
        "type": f"{TYPE_BASE}{spec.code.replace('_', '-')}",
        "title": spec.title,
        "status": spec.status,
        "detail": spec.detail,
        "code": spec.code,
        "trace_id": trace_id,
    }


# Used when building a rejection itself fails: static, so it cannot fail again.
FALLBACK_STATUS = 500
FALLBACK_BODY: dict[str, Any] = {
    "type": f"{TYPE_BASE}internal-error",
    "title": "Internal Server Error",
    "status": 500,
    "detail": "Something went wrong on our side.",
    "code": "internal_error",
    "trace_id": "0" * 32,
}


def lambda_response(code: str, traceparent: str | None) -> dict[str, Any]:
    """The rejection in the API Gateway response shape (`statusCode`, `headers`, `body`)."""
    try:
        status, body = PROBLEMS[code].status, problem_body(code, trace_id_from(traceparent))
    except Exception:  # noqa: BLE001 - a rejection must never raise
        status, body = FALLBACK_STATUS, FALLBACK_BODY
    return {"statusCode": status, "headers": {"content-type": PROBLEM_MEDIA_TYPE}, "body": json.dumps(body)}
