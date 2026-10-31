"""LB-IHTTP-04: one timeout, retry and error policy."""
import logging

import httpx
import pytest

from conftest import USER_ID
from fintracker_internal_http import InternalCallError, InternalClient, UserContext, load_settings, set_current_traceparent
from fintracker_internal_http.testing import FakeInternalServer

USER = UserContext(USER_ID, "Europe/Berlin", "EUR")
PROBLEM = {"code": "not_found", "trace_id": "c" * 32, "detail": "SECRET-BODY"}


def client(server: FakeInternalServer, sleeps: list[float] | None = None, **kwargs: object) -> InternalClient:
    async def record(seconds: float) -> None:
        if sleeps is not None:
            sleeps.append(seconds)

    return InternalClient(
        "http://ledger.local",
        service="ledger",
        settings=load_settings({"INTERNAL_AUTH_MODE": "local"}),
        transport=server,
        sleep=record,
        jitter=lambda: 1.0,
        **kwargs,  # type: ignore[arg-type]
    )


class TestOutboundPolicy:
    async def test_a_200_returns_the_parsed_body_and_status(self) -> None:
        """LB-IHTTP-04: happy path."""
        response = await client(FakeInternalServer().reply(200, json={"ok": True})).get("/x", user=USER)
        assert (response.status, response.body) == (200, {"ok": True})

    async def test_a_get_that_gets_503_then_200_returns_the_200_after_one_retry(self) -> None:
        """LB-IHTTP-04: retry."""
        server = FakeInternalServer().reply(503).reply(200, json={"ok": 1})
        response = await client(server).get("/x", user=USER)
        assert response.body == {"ok": 1} and len(server.requests) == 2

    async def test_a_get_is_retried_at_most_twice_with_jittered_delays_in_their_bands(self) -> None:
        """LB-IHTTP-04: retry limits (100 ms and 300 ms, each jittered by +-50%)."""
        server = FakeInternalServer().reply(503).fail(httpx.ConnectError("x")).reply(502).reply(200)
        sleeps: list[float] = []
        with pytest.raises(InternalCallError) as error:
            await client(server, sleeps).get("/x", user=USER)
        assert error.value.status == 502 and len(server.requests) == 3  # the 200 is never reached
        assert sleeps == [pytest.approx(0.1), pytest.approx(0.3)]
        for factor, expected in ((0.5, (0.05, 0.15)), (1.5, (0.15, 0.45))):
            banded: list[float] = []
            low_high = client(FakeInternalServer().reply(503).reply(503).reply(200), banded)
            low_high._jitter = lambda factor=factor: factor  # noqa: SLF001
            await low_high.get("/x", user=USER)
            assert banded == [pytest.approx(expected[0]), pytest.approx(expected[1])]

    async def test_a_4xx_is_never_retried_and_surfaces_the_bodys_code_or_upstream_error(self) -> None:
        """LB-IHTTP-04: 4xx."""
        server = FakeInternalServer().reply(404, json=PROBLEM).reply(400, json={"detail": "no code"})
        with pytest.raises(InternalCallError) as first:
            await client(server).get("/x", user=USER)
        assert (first.value.status, first.value.code, first.value.trace_id) == (404, "not_found", "c" * 32)
        assert "SECRET-BODY" not in str(first.value)
        with pytest.raises(InternalCallError) as second:
            await client(server).get("/x", user=USER)
        assert second.value.code == "upstream_error" and len(server.requests) == 2

    async def test_a_post_that_gets_503_is_not_retried(self) -> None:
        """LB-IHTTP-04: non-idempotent."""
        server = FakeInternalServer().reply(503, json={"code": "service_unavailable"}).reply(200)
        with pytest.raises(InternalCallError) as error:
            await client(server).post("/x", user=USER, json={})
        assert error.value.status == 503 and len(server.requests) == 1

    async def test_a_response_slower_than_the_deadline_raises_timeout(self) -> None:
        """LB-IHTTP-04: total deadline."""
        with pytest.raises(InternalCallError) as error:
            await client(FakeInternalServer().stall(1.0)).get("/x", user=USER, deadline=0.05)
        assert (error.value.code, error.value.status) == ("timeout", 504)

    async def test_a_read_timeout_is_a_timeout_error_not_a_transport_exception(self) -> None:
        """LB-IHTTP-04: never a raw transport exception."""
        with pytest.raises(InternalCallError) as error:
            await client(FakeInternalServer().fail(httpx.ReadTimeout("slow"))).post("/x", user=USER)
        assert error.value.code == "timeout"

    async def test_default_timeouts_are_2s_connect_10s_read_and_can_be_overridden(self) -> None:
        """LB-IHTTP-04: timeouts."""
        seen: list[httpx.Timeout] = []

        class Spy(FakeInternalServer):
            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                seen.append(httpx.Timeout(**request.extensions["timeout"]))
                return await super().handle_async_request(request)

        server = Spy().reply(200).reply(200)
        c = client(server)
        await c.get("/x", user=USER)
        await c.get("/x", user=USER, connect_timeout=1.0, read_timeout=3.0)
        assert (seen[0].connect, seen[0].read) == (2.0, 10.0)
        assert (seen[1].connect, seen[1].read) == (1.0, 3.0)

    async def test_traceparent_continues_the_current_request_or_is_generated(self) -> None:
        """LB-IHTTP-04: trace propagation."""
        server = FakeInternalServer().reply(200).reply(200)
        c = client(server)
        set_current_traceparent("00-" + "d" * 32 + "-" + "e" * 16 + "-01")
        await c.get("/x", user=USER)
        set_current_traceparent(None)
        await c.get("/x", user=USER)
        continued, generated = (r.headers["traceparent"] for r in server.requests)
        assert continued.split("-")[1] == "d" * 32 and continued.split("-")[2] != "e" * 16
        assert len(generated.split("-")[1]) == 32 and generated.split("-")[1] != "d" * 32

    async def test_no_log_line_holds_a_body_header_value_or_query_string(self, caplog: pytest.LogCaptureFixture) -> None:
        """LB-IHTTP-04: no leaks."""
        caplog.set_level(logging.DEBUG)
        server = FakeInternalServer().reply(503, json={"detail": "RESPONSE-SECRET"}).reply(200, json={"a": "RESPONSE-SECRET"})
        await client(server).get(
            "/x", user=USER, params={"token": "QUERY-SECRET"}, headers={"X-Other": "HEADER-SECRET"}
        )
        await client(FakeInternalServer().reply(200)).post("/y", user=USER, json={"k": "REQUEST-SECRET"})
        assert caplog.records
        text = " ".join(f"{r.getMessage()} {r.__dict__}" for r in caplog.records)
        for secret in ("RESPONSE-SECRET", "QUERY-SECRET", "HEADER-SECRET", "REQUEST-SECRET", USER_ID, "arn:local:caller"):
            assert secret not in text
