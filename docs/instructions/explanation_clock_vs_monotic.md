clock vs monotonic in service.py
The service is given two different time sources because they answer two different questions:

clock → datetime.now(timezone.utc)	monotonic → time.monotonic()
Question	"What time is it?"	"How much time has passed?"
Used for	created_at, generated_at, the UTC day for quotas and spend, TTLs	the 25 s request Deadline, per-call timeouts, latency_ms
Value	a real date that means something to people and DynamoDB	an arbitrary number; only the difference between two readings means anything
Why durations need a clock that only moves forward, even for real users: the wall clock can jump. NTP corrections, VM or container clock syncs, a Lambda resuming from a frozen state, or an operator fixing the system time can all move it backward or forward in the middle of a request. If the deadline were built on wall-clock time:

Jump backward: remaining() grows, so the request can run past 25 s, retry when it shouldn't, and go past API Gateway's timeout. The user sees a gateway error instead of the facts-only fallback.
Jump forward: remaining() drops to zero or below, so a healthy request falls back to llm_timeout (or skips its retry) for no reason.
latency_ms: it could come out negative or wildly wrong in audit records and metrics.
time.monotonic() is guaranteed never to go backward and isn't affected by changes to the system time, so "25 s from now" really is 25 s. Real users are exactly why it matters: these jumps happen on production machines, not just in tests.

The second benefit is testability. Both clocks are injected (clock=, monotonic=), so tests can pass fake functions to simulate "14 s elapsed, no retry allowed" or "it's 23:59 UTC" without sleeping or patching globals.

Rule of thumb: use wall-clock time for timestamps people or storage read, and monotonic time for timeouts, deadlines and measuring durations. Never subtract two datetime.now() values to time something.