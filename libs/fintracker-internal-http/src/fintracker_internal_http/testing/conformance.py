"""LB-IHTTP-08: run the Appendix A matrix against a service's real internal route.

    run_conformance(create_app, path="/internal/v1/goals")

`create_app` builds the service's FastAPI app; the route at `path` must use `require_internal_caller` /
`get_internal_user`. The suite sets the environment per row, injects the API Gateway event, and raises
AssertionError listing every row that did not get the status and code of the matrix.
"""
from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from importlib import resources
from typing import Any

from fastapi import FastAPI
from starlette.testclient import TestClient
from starlette.types import ASGIApp, Receive, Scope, Send

from ..config import AWS_RUNTIME_MARKERS, ALLOWED_CALLERS_VARIABLE, MODE_VARIABLE, InternalConfigError, load_settings
from ..inbound import InternalRejection, install_internal_exception_handlers
from .events import api_gateway_event


def load_vectors() -> dict[str, Any]:
    """vectors/internal_auth.json: the Appendix A matrix as data (also used by Ledger's tests, LB-IHTTP-10)."""
    text = (resources.files("fintracker_internal_http") / "vectors" / "internal_auth.json").read_text(encoding="utf-8")
    data: dict[str, Any] = json.loads(text)
    return data


@contextmanager
def _environment(changes: Mapping[str, str | None]) -> Iterator[None]:
    """Applies `changes` (None removes) and clears the AWS markers so the run is the same everywhere."""
    wanted = {**{marker: None for marker in AWS_RUNTIME_MARKERS}, **changes}
    saved = {name: os.environ.get(name) for name in wanted}
    try:
        for name, value in wanted.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


class _EventInjector:
    """What Mangum does in AWS: puts the API Gateway event in the ASGI scope."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.event: dict[str, Any] | None = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and self.event is not None:
            scope["aws.event"] = self.event
        await self.app(scope, receive, send)


def _allowed_value(allowed: list[str] | None) -> str | None:
    return None if allowed is None else ",".join(allowed)


def run_conformance(
    app_factory: Callable[[], FastAPI],
    *,
    path: str,
    method: str = "GET",
    requires: tuple[str, ...] = ("user",),
    own_answers: Mapping[str, tuple[int, str | None]] | None = None,
) -> None:
    """Runs every row of the vectors against the route. `requires` lists what the route declares beyond the user
    ("timezone", "currency"); the matching context-error rows run too.

    `own_answers` maps a row id to the (status, code) a service's own spec gives instead of the matrix's (for
    example User Profile answers a missing user with 400 `invalid_argument`). The row still runs and is checked
    against that answer.

    Raises:
        AssertionError: one or more rows did not match; the message names each row and what was returned.
        ValueError: `own_answers` names a row that is not in the vectors.
    """
    vectors = load_vectors()
    failures: list[str] = []
    own = dict(own_answers or {})
    known = {row["id"] for row in (*vectors["caller_matrix"], *vectors["context_errors"])}
    if unknown := sorted(set(own) - known):
        raise ValueError(f"own_answers names rows that are not in the vectors: {', '.join(unknown)}")

    def check(row_id: str, got: tuple[int, str | None], want: tuple[int, str | None]) -> None:
        want = own.get(row_id, want)
        if got != want:
            failures.append(f"{row_id}: expected {want}, got {got}")

    def call(row: Mapping[str, Any], event: dict[str, Any] | None, headers: Mapping[str, str]) -> tuple[int, str | None]:
        app = app_factory()
        if InternalRejection not in app.exception_handlers:
            install_internal_exception_handlers(app)
        injector = _EventInjector(app)
        injector.event = event
        with TestClient(injector, raise_server_exceptions=False) as client:
            response = client.request(method, path, headers=dict(headers))
        code = response.json().get("code") if response.headers.get("content-type", "").startswith("application/problem+json") else None
        return response.status_code, code

    for row in vectors["caller_matrix"]:
        env: dict[str, str | None] = {MODE_VARIABLE: row["mode"], ALLOWED_CALLERS_VARIABLE: _allowed_value(row["allowed_caller_arns"])}
        headers = dict(row["headers"])
        if row["header_caller"] is not None:
            headers["X-Internal-Caller-Arn"] = row["header_caller"]
        event = api_gateway_event(caller_arn=row["verified_caller"], headers=headers) if row["mode"] == "iam" else None
        with _environment(env):
            check(row["id"], call(row, event, headers), (row["status"], row["code"]))

    valid_caller = vectors["constants"]
    for row in vectors["context_errors"]:
        if row["requires"] not in requires:
            continue
        env = {MODE_VARIABLE: "iam", ALLOWED_CALLERS_VARIABLE: valid_caller["allowed_prefix"]}
        event = api_gateway_event(caller_arn=valid_caller["caller"], headers=row["headers"])
        with _environment(env):
            check(row["id"], call(row, event, row["headers"]), (row["status"], row["code"]))

    for row in vectors["startup"]:
        with _environment(row["env"]):
            try:
                load_settings()
            except InternalConfigError:
                continue
            failures.append(f"{row['id']}: expected startup to fail")

    if failures:
        raise AssertionError("internal HTTP conformance failed:\n" + "\n".join(failures))
