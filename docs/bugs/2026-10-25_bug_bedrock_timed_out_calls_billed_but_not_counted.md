# Bug name: Timed-out Bedrock calls kept running, were billed, and were never counted

## Problem
The Financial Summary gave up on a slow Bedrock call after an app-level timer, but the call kept running in its worker thread and Bedrock still generated and billed it. Because the request saw no reply, no spend was recorded, so the daily budget breaker (AN-FS-21) under-counted. Short errors such as throttling were never retried, nothing stopped requests from going to Bedrock while it was failing (AN-FS-15), and a client error's AWS message (which can carry ARNs) was copied into the exception text.

### Root cause:
- `asyncio.wait_for(asyncio.to_thread(...))` cancels the wait, not the thread or its socket.
- Spend was added only from a reply's token counts (`record_spend` after `generate`).
- The client had no error classification, so every error was handled the same way.

### Code with bug:
```python
# src/summary/llm.py
response = await asyncio.wait_for(
    asyncio.to_thread(client.converse, ...),
    timeout=timeout_s,
)
...
raise LlmError(f"The model call failed ({error_code}): {error_message}") from exc
```

## Solution
Applied SDR-001: the timeout lives at the socket, retries live in our code, and errors are classified.

1. `llm.py`: no app timer. `read_timeout` = the call timeout (rounded down), `connect_timeout` 2 s, SDK `max_attempts` 1. Errors map to `LlmTimeout`, `LlmUnavailable`, `LlmThrottled`, `LlmBadResponse` or `LlmError`, each flagged `retryable` / `provider_failure` / `may_be_billed`; messages are generic.
2. `generation.py`: each call gets remaining − 2 s (capped by `call_timeout_cap_s` once measured; unset by default). Retryable errors are retried twice with full-jitter backoff (0.25 s × 2ⁿ, cap 2 s) while a call still fits. Every attempt logs `llm_latency_ms`.
3. `breaker.py`: 5 provider failures in a row open the breaker for 60 s (`llm_unavailable`), then one trial call. Throttling is `llm_throttled` with a metric and never trips it.
4. Spend: a timed-out call keeps its reservation (see the spend-overshoot bug of the same date).

### Fixed Code
```python
# src/summary/llm.py
config = Config(read_timeout=read_timeout, connect_timeout=CONNECT_TIMEOUT_S, retries={"max_attempts": 1})
...
response = await asyncio.to_thread(client.converse, ...)
except Exception as exc:
    error_class, code = _classify(exc)
    raise error_class("The model call failed.") from exc
```
