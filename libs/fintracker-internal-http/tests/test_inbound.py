"""LB-IHTTP-05 / LB-IHTTP-06: the caller check comes first; the user is read only after it passes."""
import pytest
from fastapi import Depends, FastAPI
from starlette.testclient import TestClient
from starlette.types import Receive, Scope, Send

from conftest import ALLOWED_PREFIX, CALLER, USER_ID
from fintracker_internal_http import (
    UserContext,
    caller_rejection,
    get_internal_user,
    install_internal_exception_handlers,
    require_internal_caller,
)
from fintracker_internal_http.testing import api_gateway_event, load_vectors

VALID_USER = {"X-Internal-User-Id": USER_ID, "X-User-Timezone": "Europe/Berlin", "X-User-Currency": "EUR"}
OTHER = "arn:aws:sts::999999999999:assumed-role/other/session"


class Injected:
    """Puts the API Gateway event in the scope, as Mangum does in AWS."""

    def __init__(self, app: FastAPI, event: dict | None) -> None:  # type: ignore[type-arg]
        self.app, self.event = app, event

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self.event is not None and scope["type"] == "http":
            scope["aws.event"] = self.event
        await self.app(scope, receive, send)


def make_app(*, require: tuple[str, ...] = ("user",)) -> FastAPI:
    app = FastAPI()
    install_internal_exception_handlers(app)

    @app.get("/internal/who", dependencies=[Depends(require_internal_caller)])
    async def who(user: UserContext = Depends(get_internal_user(require=require))) -> dict[str, str | None]:  # type: ignore[arg-type]
        return {"user": user.user_id, "timezone": user.timezone, "currency": user.currency}

    return app


def call(
    monkeypatch: pytest.MonkeyPatch,
    *,
    mode: str,
    verified: str | None = None,
    header: str | None = None,
    allowed: str | None = None,
    user: dict[str, str] | None = None,
    require: tuple[str, ...] = ("user",),
    app: FastAPI | None = None,
) -> tuple[int, dict]:  # type: ignore[type-arg]
    monkeypatch.setenv("INTERNAL_AUTH_MODE", mode)
    if allowed is not None:
        monkeypatch.setenv("INTERNAL_ALLOWED_CALLER_ARNS", allowed)
    headers = dict(VALID_USER if user is None else user)
    if header:
        headers["X-Internal-Caller-Arn"] = header
    event = api_gateway_event(caller_arn=verified) if mode == "iam" else None
    with TestClient(Injected(app or make_app(require=require), event), raise_server_exceptions=False) as client:
        response = client.get("/internal/who", headers=headers)
    return response.status_code, response.json()


class TestInboundCaller:
    def test_iam_a_caller_on_the_list_passes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LB-IHTTP-05: happy path."""
        assert call(monkeypatch, mode="iam", verified=CALLER, allowed=ALLOWED_PREFIX)[0] == 200

    def test_iam_no_verified_caller_is_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LB-IHTTP-05 / Appendix A row 1."""
        status, body = call(monkeypatch, mode="iam", allowed=ALLOWED_PREFIX)
        assert (status, body["code"]) == (401, "unauthorized")

    def test_iam_the_caller_header_without_a_verified_caller_is_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LB-IHTTP-05: the header is ignored in iam."""
        status, body = call(monkeypatch, mode="iam", header=CALLER, allowed=ALLOWED_PREFIX)
        assert (status, body["code"]) == (401, "unauthorized")

    def test_iam_a_caller_off_the_list_is_403(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LB-IHTTP-05 / Appendix A row 3."""
        status, body = call(monkeypatch, mode="iam", verified=OTHER, allowed=ALLOWED_PREFIX)
        assert (status, body["code"]) == (403, "caller_not_allowed")

    @pytest.mark.parametrize("allowed", [None, ""])
    def test_iam_an_empty_or_unset_list_is_403(self, monkeypatch: pytest.MonkeyPatch, allowed: str | None) -> None:
        """LB-IHTTP-05 / Appendix A row 4."""
        status, body = call(monkeypatch, mode="iam", verified=CALLER, allowed=allowed)
        assert (status, body["code"]) == (403, "caller_not_allowed")

    def test_local_header_present_and_no_list_passes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LB-IHTTP-05: local happy path."""
        assert call(monkeypatch, mode="local", header=CALLER)[0] == 200

    def test_local_header_missing_is_401_and_off_a_set_list_is_403(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LB-IHTTP-05: local rows."""
        assert call(monkeypatch, mode="local")[1]["code"] == "unauthorized"
        status, body = call(monkeypatch, mode="local", header=OTHER, allowed=ALLOWED_PREFIX)
        assert (status, body["code"]) == (403, "caller_not_allowed")

    def test_the_raw_event_adapter_agrees_with_the_dependency_for_every_row(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LB-IHTTP-05: adapters agree (vectors rows that decide on the caller)."""
        for row in load_vectors()["caller_matrix"]:
            if row["status"] == 200 or row["code"] in ("unauthorized", "caller_not_allowed"):
                monkeypatch.setenv("INTERNAL_AUTH_MODE", row["mode"])
                allowed = row["allowed_caller_arns"]
                if allowed is None:
                    monkeypatch.delenv("INTERNAL_ALLOWED_CALLER_ARNS", raising=False)
                else:
                    monkeypatch.setenv("INTERNAL_ALLOWED_CALLER_ARNS", ",".join(allowed))
                headers = dict(row["headers"])
                if row["header_caller"]:
                    headers["X-Internal-Caller-Arn"] = row["header_caller"]
                result = caller_rejection(api_gateway_event(caller_arn=row["verified_caller"], headers=headers))
                if row["status"] == 200:
                    assert result is None, row["id"]
                else:
                    assert result is not None and result["statusCode"] == row["status"], row["id"]


class TestUserContext:
    def test_a_valid_user_returns_the_context_with_timezone_and_currency(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LB-IHTTP-06: happy path."""
        status, body = call(monkeypatch, mode="local", header=CALLER)
        assert (status, body) == (200, {"user": USER_ID, "timezone": "Europe/Berlin", "currency": "EUR"})

    def test_a_route_declaring_only_user_accepts_a_request_without_timezone_and_currency(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """LB-IHTTP-06: requirement per route."""
        status, body = call(monkeypatch, mode="local", header=CALLER, user={"X-Internal-User-Id": USER_ID})
        assert status == 200 and body["timezone"] is None

    def test_a_missing_user_id_is_401_user_context_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LB-IHTTP-06 / Appendix A."""
        status, body = call(monkeypatch, mode="local", header=CALLER, user={"X-User-Timezone": "Europe/Berlin"})
        assert (status, body["code"]) == (401, "user_context_missing")

    def test_a_user_id_that_is_not_a_uuid_is_400_and_not_echoed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LB-IHTTP-06: malformed."""
        status, body = call(monkeypatch, mode="local", header=CALLER, user={"X-Internal-User-Id": "ECHO-ME-not-a-uuid"})
        assert (status, body["code"]) == (400, "invalid_argument")
        assert "ECHO-ME" not in str(body)

    def test_a_missing_timezone_on_a_route_that_requires_it_is_409(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LB-IHTTP-06 / XS-CTX-05."""
        status, body = call(
            monkeypatch, mode="local", header=CALLER, user={"X-Internal-User-Id": USER_ID, "X-User-Currency": "EUR"},
            require=("user", "timezone"),
        )
        assert (status, body["code"]) == (409, "user_settings_incomplete")

    @pytest.mark.parametrize(
        ("extra", "require"),
        [
            ({"X-User-Timezone": "Mars/Olympus"}, ("user",)),
            ({"X-User-Currency": "eur"}, ("user",)),
            ({"X-User-Timezone": "Europe/Berlin"}, ("user", "currency")),  # required currency missing
        ],
    )
    def test_an_invalid_timezone_or_currency_is_500_user_context_invalid(
        self, monkeypatch: pytest.MonkeyPatch, extra: dict[str, str], require: tuple[str, ...]
    ) -> None:
        """LB-IHTTP-06 / XS-CTX-05."""
        status, body = call(monkeypatch, mode="local", header=CALLER, user={"X-Internal-User-Id": USER_ID, **extra}, require=require)
        assert (status, body["code"]) == (500, "user_context_invalid")

    def test_when_the_caller_check_fails_the_user_headers_are_never_read(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LB-IHTTP-06: order. Reading any user header raises in this test."""
        import starlette.datastructures as ds

        real_get = ds.Headers.get

        def guarded(self: ds.Headers, key: str, default: str | None = None) -> str | None:
            if key.lower().startswith(("x-internal-user", "x-user-")):
                raise AssertionError("user header read before the caller check passed")
            return real_get(self, key, default)

        monkeypatch.setattr(ds.Headers, "get", guarded)
        status, body = call(monkeypatch, mode="iam", verified=OTHER, allowed=ALLOWED_PREFIX)
        assert (status, body["code"]) == (403, "caller_not_allowed")
