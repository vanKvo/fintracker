# SDR-001: Bedrock Call Timeouts, Retries and Failure Breaker

## Service Name: fintracker-ai-assistant

## Status
Accepted (AI assistant architecture doc S8). Applies app doc D25 to Bedrock calls.

## Date
2026-10-25

## Context
The Financial Summary wrapped the Bedrock call in `asyncio.wait_for(asyncio.to_thread(...))`. When that timer fired, the request stopped waiting but the worker thread kept the call running, so Bedrock still generated and billed it. Because the request saw no reply, it recorded no spend, and the daily circuit breaker (AN-FS-21) under-counted. Nothing retried short errors such as throttling, and nothing stopped the service from sending every new request to Bedrock while Bedrock was failing.

Key requirements:
- The request ends with a fallback inside the API Gateway HTTP API's 30 s limit, never a gateway 503.
- A call the service stops waiting for doesn't keep running unseen, and its cost is counted.
- Short errors that happen before Bedrock processes the request (throttling, connection errors, 5xx) are retried; a call that may have been billed is not.
- A provider outage turns into fast fallbacks, but throttling doesn't trip the breaker.

## Options

- **Socket timeout, retries in our code** *(chosen)*: botocore `connect_timeout` 2 s, `read_timeout` = the call timeout, SDK retries off; our code retries only the errors known to happen before processing.
- **App timer and SDK retries**: keep `wait_for` as the per-call timeout and turn on botocore's `standard` retry mode.

## Trade-offs

| Dimension | Socket timeout, own retries | App timer, SDK retries | Edge |
|---|---|---|---|
| **Call keeps running after we stop waiting** | No: the socket closes | Yes, until the socket timeout; billed and unseen | Own |
| **Double-billing risk** | Read timeouts are never retried | The SDK retry modes also retry read timeouts, so one summary can be billed twice | Own |
| **Deadline awareness** | A retry runs only if the remaining time fits a call | SDK backoff doesn't know the 25 s deadline | Own |
| **Code to maintain** | A small error classifier and backoff loop | Config only | SDK, slightly |

**Also considered**
- **60 s read timeout on the request path:** the gateway ends the request at 30 s with a 503 instead of the fallback, and Bedrock still bills the call. 60 s is allowed only in live evaluation runs, which have no gateway.

## Decision
**Socket timeout and retries in our code, plus a failure breaker, the same in both profiles.**

1. **Call timeout:** remaining deadline − 2 s, capped by `call_timeout_cap_s` once measured (about 1.5 × p99 for the pinned model; unset until then). Every call logs `llm_latency_ms`; AN-FS-20 reports p50, p95, p99 and uses the p99 only after 200 calls.
2. **Before processing** (connection errors, connect timeout, 429 `ThrottlingException`, `ServiceUnavailableException`, `InternalServerException`, `ModelNotReadyException`): up to 2 retries, backoff 0.25 s × 2ⁿ with full jitter, capped at 2 s, only while the remaining time fits a call. Two, not one: these errors fail in milliseconds and aren't billed, so the second retry costs little time and no money, and throttling often needs more than one wait to clear. Not three: three waits plus three short failures start eating the time a real generation needs.
3. **After the request was sent** (read timeout): no retry. Log it, keep the spend reservation (SDR-002), count a breaker failure, return the fallback. The breaker and spend tracking are separate: `record_spend`/settle is cost, the breaker is Bedrock's health.
4. **Failure breaker:** counts read timeouts, and connection errors or 5xx still failing after retries. 5 in a row in one container open it for 60 s (`llm_unavailable`); then one trial call. Throttling still failing after retries is `llm_throttled`: a metric and a fallback, not a breaker failure, because the provider is healthy and only our rate is too high.

## Consequences
- One place sets the per-call timeout: the Bedrock client config, fed by the deadline.
- An outage costs at most 5 failed calls per container before requests fall back immediately.
- Persistent throttling shows up as an `llm_throttled` rate to fix with quotas or traffic shaping, not as an open breaker.

## Revisit when
- Summaries switch to streaming responses (the read timeout then measures gaps between chunks, not the total).
- The summary moves to an async job (start, then poll), which would allow longer calls.
- Prod runs many containers and a shared breaker state is worth its extra read.

## Related
- [AN-FS spec](../../../fintracker-analytics/specs/AN-FS-financial-summary-spec.md): AN-FS-10, AN-FS-15, AN-FS-20, AN-FS-21.
- [SDR-002](SDR-002-atomic-spend-reservation.md): how timed-out and failed calls are counted.
- [App architecture](../../../fintracker-architecture/fintracker-architectural-doc.md): 4.6 Recover, D25.
