"""A fake internal server for outbound tests: records requests, replays chosen responses, injects failures."""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from typing import Any, Self

import httpx


@dataclass(frozen=True, slots=True)
class RecordedRequest:
    method: str
    path: str
    query: str
    headers: dict[str, str]  # names lower-cased
    body: bytes
    url: str


class FakeInternalServer(httpx.AsyncBaseTransport):
    """Pass as `transport=` to InternalClient. Responses are replayed in the order they were scripted."""

    def __init__(self) -> None:
        self.requests: list[RecordedRequest] = []
        self._script: deque[httpx.Response | Exception | float] = deque()

    def reply(self, status: int = 200, *, json: Any = None, headers: dict[str, str] | None = None) -> Self:
        self._script.append(httpx.Response(status, json=json if json is not None else None, headers=headers))
        return self

    def fail(self, error: Exception) -> Self:
        """The next request raises `error` (e.g. httpx.ConnectError)."""
        self._script.append(error)
        return self

    def stall(self, seconds: float) -> Self:
        """The next request waits `seconds` before it is answered with an empty 200."""
        self._script.append(seconds)
        return self

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(
            RecordedRequest(
                method=request.method,
                path=request.url.path,
                query=request.url.query.decode(),
                headers={name.lower(): value for name, value in request.headers.items()},
                body=request.content,
                url=str(request.url),
            )
        )
        if not self._script:
            raise AssertionError("FakeInternalServer received a request with no scripted reply")
        step = self._script.popleft()
        if isinstance(step, Exception):
            raise step
        if isinstance(step, float | int):
            await asyncio.sleep(step)
            return httpx.Response(200)
        return step
