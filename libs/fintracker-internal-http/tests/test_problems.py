"""LB-IHTTP-07: rejections are problem+json with fixed codes."""
import json

import pytest
from starlette.testclient import TestClient

from conftest import ALLOWED_PREFIX, USER_ID
from fintracker_internal_http import caller_rejection, load_settings
from fintracker_internal_http import inbound, problems
from fintracker_internal_http.testing import api_gateway_event
from test_inbound import Injected, make_app

OFF_LIST = "arn:aws:iam::999999999999:role/x"
TRACEPARENT = "00-" + "f" * 32 + "-" + "1" * 16 + "-01"


def rejected(monkeypatch: pytest.MonkeyPatch, headers: dict[str, str] | None = None):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("INTERNAL_ALLOWED_CALLER_ARNS", ALLOWED_PREFIX)
    event = api_gateway_event(caller_arn=OFF_LIST)
    with TestClient(Injected(make_app(), event), raise_server_exceptions=False) as client:
        return client.get("/internal/who", headers={"X-Internal-User-Id": USER_ID, **(headers or {})})


class TestProblems:
    def test_a_403_body_has_the_code_type_and_a_trace_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LB-IHTTP-07: happy path."""
        response = rejected(monkeypatch)
        body = response.json()
        assert response.status_code == 403
        assert response.headers["content-type"].startswith("application/problem+json")
        assert body["code"] == "caller_not_allowed" and body["status"] == 403
        assert body["type"].endswith("/caller-not-allowed") and len(body["trace_id"]) == 32
        assert {"type", "title", "status", "detail", "code", "trace_id"} <= body.keys()

    def test_trace_id_comes_from_a_valid_traceparent_else_is_generated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LB-IHTTP-07: trace id."""
        assert rejected(monkeypatch, {"traceparent": TRACEPARENT}).json()["trace_id"] == "f" * 32
        generated = rejected(monkeypatch, {"traceparent": "not-a-traceparent"}).json()["trace_id"]
        assert len(generated) == 32 and generated != "f" * 32

    def test_the_lambda_adapter_returns_the_same_body_in_the_api_gateway_shape(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LB-IHTTP-07: adapter."""
        monkeypatch.setenv("INTERNAL_ALLOWED_CALLER_ARNS", ALLOWED_PREFIX)
        result = caller_rejection(api_gateway_event(caller_arn=OFF_LIST, headers={"traceparent": TRACEPARENT}))
        assert result is not None and result["statusCode"] == 403
        assert result["headers"]["content-type"] == "application/problem+json"
        assert json.loads(result["body"]) == problems.problem_body("caller_not_allowed", "f" * 32)

    def test_a_rejection_for_an_unlisted_arn_does_not_contain_that_arn(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LB-IHTTP-07: no leaks."""
        response = rejected(monkeypatch)
        assert "999999999999" not in response.text and OFF_LIST not in response.text
        monkeypatch.setenv("INTERNAL_ALLOWED_CALLER_ARNS", ALLOWED_PREFIX)
        adapter = caller_rejection(api_gateway_event(caller_arn=OFF_LIST))
        assert adapter is not None and "999999999999" not in adapter["body"]

    def test_an_error_while_building_a_rejection_returns_a_bare_500(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LB-IHTTP-07: never an unchecked exception."""

        def boom(*args: object, **kwargs: object) -> dict[str, object]:
            raise RuntimeError("cannot build")

        monkeypatch.setattr(problems, "problem_body", boom)
        response = rejected(monkeypatch)
        assert response.status_code == 500 and response.json()["code"] == "internal_error"
        monkeypatch.setenv("INTERNAL_ALLOWED_CALLER_ARNS", ALLOWED_PREFIX)
        adapter = caller_rejection(api_gateway_event(caller_arn=OFF_LIST), settings=load_settings())
        assert adapter is not None and adapter["statusCode"] == 500
        assert json.loads(adapter["body"])["code"] == "internal_error"
        assert inbound  # module under test stays imported
