"""Builders for API Gateway (HTTP API, payload v2) events, with or without a verified IAM caller."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def api_gateway_event(
    *,
    caller_arn: str | None = None,
    headers: Mapping[str, str] | None = None,
    method: str = "GET",
    path: str = "/",
) -> dict[str, Any]:
    """An event as API Gateway delivers it. `caller_arn` is what AWS_IAM authorization verified; None means unauthenticated."""
    request_context: dict[str, Any] = {"http": {"method": method, "path": path}}
    if caller_arn is not None:
        request_context["authorizer"] = {"iam": {"userArn": caller_arn}}
    return {
        "version": "2.0",
        "rawPath": path,
        "headers": {name.lower(): value for name, value in (headers or {}).items()},
        "requestContext": request_context,
    }
