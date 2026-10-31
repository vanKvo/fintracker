"""LB-IHTTP-03: the outbound client signs by mode and forwards the user."""
import datetime
import re

import pytest
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials

from conftest import USER_ID
from fintracker_internal_http import (
    InternalCallError,
    InternalClient,
    InvalidUserContextError,
    SigV4Signer,
    UserContext,
    load_settings,
)
from fintracker_internal_http.testing import FakeInternalServer

BASE = "https://ledger.internal.example"
CREDENTIALS = Credentials("AKIDEXAMPLE", "secret-example-key")
USER = UserContext(USER_ID, "Europe/Berlin", "EUR")
ENV_IAM = {"AWS_REGION": "eu-central-1"}


def iam_client(server: FakeInternalServer, credentials: Credentials | None = CREDENTIALS) -> InternalClient:
    return InternalClient(
        BASE,
        service="ledger",
        settings=load_settings({}),
        signer=SigV4Signer(credentials_provider=lambda: credentials, environ=ENV_IAM),
        transport=server,
    )


def local_client(server: FakeInternalServer, environ: dict[str, str] | None = None) -> InternalClient:
    env = {"INTERNAL_AUTH_MODE": "local", "INTERNAL_BASE_URL_LEDGER": BASE, **(environ or {})}
    return InternalClient.from_env("LEDGER", environ=env, transport=server)


class TestOutboundRequest:
    async def test_iam_signs_with_sigv4_and_sends_the_three_user_headers(self) -> None:
        """LB-IHTTP-03: iam request."""
        server = FakeInternalServer().reply(200, json={})
        await iam_client(server).get("/internal/v1/accounts", user=USER)
        sent = server.requests[0].headers
        assert sent["authorization"].startswith("AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/")
        assert "/eu-central-1/execute-api/aws4_request" in sent["authorization"]
        assert (sent["x-internal-user-id"], sent["x-user-timezone"], sent["x-user-currency"]) == (
            USER_ID,
            "Europe/Berlin",
            "EUR",
        )
        assert "x-internal-caller-arn" not in sent

    async def test_the_signature_covers_the_body_hash(self) -> None:
        """LB-IHTTP-03: body hash included."""
        server = FakeInternalServer().reply(200, json={})
        await iam_client(server).post("/internal/v1/import", user=USER, json={"rows": [1, 2]})
        sent = server.requests[0]

        def signature_for(body: bytes) -> str:
            request = AWSRequest(method="POST", url=sent.url, data=body, headers={})
            signed = re.search(r"SignedHeaders=([^,]+)", sent.headers["authorization"])
            assert signed
            for name in signed[1].split(";"):
                if name != "host":
                    request.headers[name] = sent.headers[name]
            request.context["timestamp"] = datetime.datetime.strptime(sent.headers["x-amz-date"], "%Y%m%dT%H%M%SZ").strftime(
                "%Y%m%dT%H%M%SZ"
            )
            SigV4Auth(CREDENTIALS, "execute-api", "eu-central-1").add_auth(request)
            match = re.search(r"Signature=([0-9a-f]+)", request.headers["Authorization"])
            assert match
            return match[1]

        actual = re.search(r"Signature=([0-9a-f]+)", sent.headers["authorization"])
        assert actual and signature_for(sent.body) == actual[1]
        assert signature_for(sent.body + b" ") != actual[1]

    async def test_local_sends_no_authorization_but_the_caller_and_user_headers(self) -> None:
        """LB-IHTTP-03: local request."""
        server = FakeInternalServer().reply(200, json={})
        await local_client(server).get("/internal/v1/accounts", user=USER)
        sent = server.requests[0].headers
        assert "authorization" not in sent
        assert sent["x-internal-caller-arn"] == "arn:local:caller"
        assert sent["x-internal-user-id"] == USER_ID

    async def test_local_caller_arn_can_be_overridden(self) -> None:
        """LB-IHTTP-03: INTERNAL_LOCAL_CALLER_ARN overrides arn:local:caller."""
        server = FakeInternalServer().reply(200, json={})
        await local_client(server, {"INTERNAL_LOCAL_CALLER_ARN": "arn:local:ai"}).get("/x", user=USER)
        assert server.requests[0].headers["x-internal-caller-arn"] == "arn:local:ai"

    async def test_a_call_without_a_user_context_raises_before_any_network_call(self) -> None:
        """LB-IHTTP-03: programming error."""
        server = FakeInternalServer()
        with pytest.raises(TypeError):
            await local_client(server).get("/x", user=None)  # type: ignore[arg-type]
        assert server.requests == []

    async def test_reserved_headers_from_the_caller_are_replaced_not_merged(self) -> None:
        """LB-IHTTP-03: reserved headers."""
        server = FakeInternalServer().reply(200, json={})
        hostile = {
            "X-Internal-User-Id": "22222222-2222-4222-8222-222222222222",
            "x-user-currency": "USD",
            "Authorization": "Bearer attacker",
            "X-Internal-Caller-Arn": "arn:attacker",
            "traceparent": "00-" + "a" * 32 + "-" + "b" * 16 + "-01",
            "X-Request-Source": "kept",
        }
        await local_client(server).get("/x", user=USER, headers=hostile)
        sent = server.requests[0].headers
        assert sent["x-internal-user-id"] == USER_ID
        assert sent["x-user-currency"] == "EUR"
        assert "authorization" not in sent
        assert sent["x-internal-caller-arn"] == "arn:local:caller"
        assert "a" * 32 not in sent["traceparent"]
        assert sent["x-request-source"] == "kept"

    async def test_missing_credentials_in_iam_raise_signing_failed_and_send_nothing(self) -> None:
        """LB-IHTTP-03: credentials cannot be found."""
        server = FakeInternalServer()
        with pytest.raises(InternalCallError) as error:
            await iam_client(server, credentials=None).get("/x", user=USER)
        assert error.value.code == "signing_failed"
        assert server.requests == []

    def test_an_empty_user_id_or_malformed_currency_raises_before_any_network_call(self) -> None:
        """LB-IHTTP-03: incomplete context."""
        with pytest.raises(InvalidUserContextError):
            UserContext("", "Europe/Berlin", "EUR")
        with pytest.raises(InvalidUserContextError):
            UserContext(USER_ID, "Europe/Berlin", "euro")

    async def test_a_context_without_timezone_or_currency_cannot_be_sent(self) -> None:
        """LB-IHTTP-03: the three user headers are always sent."""
        server = FakeInternalServer()
        with pytest.raises(InvalidUserContextError):
            await local_client(server).get("/x", user=UserContext(USER_ID))
        assert server.requests == []

    async def test_a_call_that_declares_it_needs_only_the_user_sends_only_the_user_header(self) -> None:
        """LB-IHTTP-03 / LB-IHTTP-06: the outbound mirror of `require=("user",)`, for callers that have no settings.

        The default stays all three; a caller (the Data pipeline, which holds a user ID and nothing else) must ask.
        """
        server = FakeInternalServer().reply(200, json={})
        await local_client(server).get("/x", user=UserContext(USER_ID), require=("user",))
        sent = server.requests[0].headers
        assert sent["x-internal-user-id"] == USER_ID
        assert "x-user-timezone" not in sent and "x-user-currency" not in sent

    async def test_a_declared_need_that_the_context_cannot_meet_is_refused_before_any_network_call(self) -> None:
        """LB-IHTTP-03: declaring `timezone` without having one is still an error."""
        server = FakeInternalServer()
        with pytest.raises(InvalidUserContextError):
            await local_client(server).get("/x", user=UserContext(USER_ID), require=("user", "timezone"))
        assert server.requests == []

    async def test_a_status_the_caller_accepts_is_an_answer_with_its_parsed_body_not_an_error(self) -> None:
        """LB-IHTTP-04: `accept=(409,)` for callers whose protocol uses a non-2xx status as a normal reply."""
        server = FakeInternalServer().reply(409, json={"existingStatementId": "s-1"}).reply(409, json={}).reply(500, json={})
        c = local_client(server)
        accepted = await c.patch("/x", user=USER, json={}, accept=(409,))
        assert (accepted.status, accepted.body) == (409, {"existingStatementId": "s-1"})
        with pytest.raises(InternalCallError) as error:  # not listed: still an error, even though 409 was accepted before
            await c.patch("/x", user=USER, json={})
        assert error.value.status == 409
        with pytest.raises(InternalCallError) as server_error:
            await c.patch("/x", user=USER, json={}, accept=(409,))
        assert server_error.value.status == 500
