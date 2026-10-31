# Changelog

## Unreleased

### Added
- LB-IHTTP-01 to LB-IHTTP-08: settings and the local-in-AWS guard, outbound client (SigV4 or caller header,
  forwarded user headers, timeout/retry/error policy), inbound caller check and user context, problem+json
  rejections, and `fintracker_internal_http.testing` with the conformance suite and `vectors/internal_auth.json`.
- `set_current_traceparent`: lets a service that only makes outbound calls (no inbound dependency) tell the client which
  trace the request being served belongs to.
- `run_conformance(..., own_answers=...)`: a service whose own spec answers a matrix row differently names that row and the
  answer it gives; the row is still run and checked.
- `request(..., require=...)`: the outbound mirror of the inbound `require`, for callers that hold a user ID and no settings
  (the Data pipeline). The default is unchanged: all three user headers.
- `request(..., accept=...)`: non-2xx statuses that are a normal answer for a call (a 404 meaning "none", a 409 carrying details)
  come back as an `InternalResponse` with the parsed body instead of raising.
