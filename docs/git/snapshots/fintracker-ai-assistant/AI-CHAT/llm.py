"""Bedrock Converse client for the Financial Summary (AN-FS-10, AN-FS-21; SDR-001).

Pinned model ID, temperature 0, `maxTokens` cap. The call timeout is enforced at the socket only:
`read_timeout` = the timeout the caller derives from the request deadline, `connect_timeout` 2 s,
SDK retries off (botocore's retry modes would also retry read timeouts, billing a summary twice).
No app-level timer wraps the call, so a call is never left running unseen after we stop waiting.

Every failure becomes an LlmError subclass that tells the caller whether to retry, count a breaker
failure, or keep the spend reservation (exceptions.py). Messages are generic; only the error type
and AWS error code are logged, never the exception text (it can carry ARNs or request content).

__author__ = "Van Vo"
"""

from __future__ import annotations

import asyncio
import math
import os
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectionError as BotoConnectionError,
    HTTPClientError,
    ReadTimeoutError,
)

from ..core.observability import MetricUnit, logger, metrics
from .exceptions import LlmBadResponse, LlmError, LlmThrottled, LlmTimeout, LlmUnavailable
from .schemas import JsonObject, LlmReply

CONNECT_TIMEOUT_S = 2
# AN-FS-10: errors Bedrock returns before processing the request; retried by generation.py.
_UNAVAILABLE_CODES = frozenset({"ServiceUnavailableException", "InternalServerException", "ModelNotReadyException"})


def estimate_tokens(text: str) -> int:
    """FS-21 pre-call count: UTF-8 bytes ÷ 3, rounded up — above real counts for English JSON."""
    return math.ceil(len(text.encode("utf-8")) / 3)


def _classify(exc: Exception) -> tuple[type[LlmError], str | None]:
    """(error class, AWS error code if any). Read timeouts are checked first: they subclass HTTPClientError."""
    if isinstance(exc, ReadTimeoutError):
        return LlmTimeout, None
    if isinstance(exc, BotoConnectionError):  # endpoint unreachable, connect timeout: nothing was sent
        return LlmUnavailable, None
    if isinstance(exc, ClientError):
        error = exc.response.get("Error", {})
        code = str(error.get("Code", "Unknown"))
        status = int(exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0) or 0)
        if code == "ThrottlingException":
            return LlmThrottled, code
        if code == "ModelTimeoutException":  # the model ran out of time while processing: billed
            return LlmTimeout, code
        if code in _UNAVAILABLE_CODES or status >= 500:
            return LlmUnavailable, code
        return LlmError, code
    if isinstance(exc, HTTPClientError):  # connection dropped after the request was sent
        return LlmBadResponse, None
    if isinstance(exc, BotoCoreError):  # local problems such as missing credentials: nothing was sent
        return LlmError, None
    return LlmBadResponse, None  # unknown: assume the request may have been processed (fails safe)


def _latency_ms(response: dict[str, Any]) -> int | None:
    value = (response.get("metrics") or {}).get("latencyMs")
    return int(value) if value is not None else None


class BedrockConverseClient:
    def __init__(self, region: str | None = None) -> None:
        self._region = region or os.environ.get("BEDROCK_REGION") or os.environ.get("AWS_REGION", "us-east-1")
        self._clients: dict[int, Any] = {}  # boto3 clients are untyped

    def _client(self, timeout_s: float) -> Any:
        # Whole seconds, rounded down so the socket never outlives the deadline; one client per value.
        read_timeout = max(1, math.floor(timeout_s))
        if read_timeout not in self._clients:
            config = Config(read_timeout=read_timeout, connect_timeout=CONNECT_TIMEOUT_S,
                            retries={"max_attempts": 1})
            self._clients[read_timeout] = boto3.client("bedrock-runtime", region_name=self._region, config=config)
        return self._clients[read_timeout]

    async def converse(
        self, *, model_id: str, system: list[JsonObject], messages: list[JsonObject],
        max_tokens: int, temperature: float, timeout_s: float,
    ) -> LlmReply:
        try:
            client = self._client(timeout_s)
        except Exception as exc:
            logger.error("Bedrock client could not be created", model_id=model_id, error_type=type(exc).__name__)
            raise LlmError("The model client could not be created.") from exc

        try:
            response = await asyncio.to_thread(
                client.converse, modelId=model_id, system=system, messages=messages,
                inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
            )
        except Exception as exc:
            error_class, code = _classify(exc)
            log = logger.warning if error_class.retryable else logger.error
            log("Bedrock converse failed", model_id=model_id, error_type=type(exc).__name__, error_code=code,
                error_class=error_class.__name__)
            raise error_class("The model call failed.") from exc

        try:
            blocks = response["output"]["message"]["content"]
            usage = response.get("usage", {})
            truncated = response.get("stopReason") == "max_tokens"
            reply = LlmReply(
                text="".join(b["text"] for b in blocks if "text" in b),
                input_tokens=int(usage.get("inputTokens", 0)),
                output_tokens=int(usage.get("outputTokens", 0)),
                truncated=truncated,
                bedrock_latency_ms=_latency_ms(response),
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.error("Bedrock reply was malformed", model_id=model_id, error_type=type(exc).__name__)
            raise LlmBadResponse("The model reply could not be read.") from exc

        if reply.truncated:  # Bedrock returns a cut-off reply as a success; it will fail output parsing
            logger.warning("Bedrock reply hit max_tokens", model_id=model_id, max_tokens=max_tokens,
                           output_tokens=int(usage.get("outputTokens", 0)))
            metrics.add_metric(name="SummaryLlmTruncated", unit=MetricUnit.Count, value=1)
        return reply
