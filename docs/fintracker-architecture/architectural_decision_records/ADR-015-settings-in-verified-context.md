# ADR-015: Timezone and Primary Currency Travel in the Verified User Context

## Service Name: app-wide (User profile, Analytics, Ledger, AI assistant)

## Status
Accepted (architecture doc D23)

## Date
2026-10-20

## Context
Analytics needs the user's timezone to know which day "today" is, and primary currency to know which transactions count. The Ledger now needs the timezone too, to decide which month the Dashboard shows (ADR-013). Today Analytics calls User profile's internal settings route and caches the answer for 5 minutes; what happens on a cache miss while User profile is down was never specified. A wrong currency or timezone produces numbers that look right, so a guessed default is not acceptable.

Key requirements:
- Values come from a trusted source, never from the client.
- No service fails because User profile is briefly unavailable, beyond what sign-in already requires.
- Works for internal calls from the AI assistant, where no client is involved.
- No new store or event in any service.

## Decision
**The verified user context carries `userId`, subscription tier, timezone and primary currency, in both profiles.**

**Why:** The only runtime dependency is the authorizer every request already needs, and the AI assistant's internal calls get the values in the signed context. Settings changes don't need to apply within seconds and no job needs settings today, so the cache delay is acceptable. The alternatives need cache and outage handling in every caller, or an event pipeline.

1. The identity authorizer reads the user's settings with the profile it already loads, and returns both values in its context.
2. The AI assistant forwards the same fields in the signed user context on internal requests (invariant 3).
3. Receivers read the values only from that context. Values in headers, query strings, bodies or tool arguments are ignored.
4. Receivers validate them: an IANA timezone name and an ISO 4217 code. A missing or invalid value fails the request with a retryable error. There is no default.
5. User profile ensures every user has both values from sign-up.

## Alternatives Considered

### Sync call, cached (today)
Each service calls User profile's settings route and caches the result.
- Pros: Already in place for Analytics.
- Cons:
  - User profile must answer on every cache miss, and the outage behavior was never specified.
  - Every caller needs its own cache, timeouts and outage handling.
  - A changed setting is stale for up to the cache time (5 minutes today).
- Rejected: It leaves the unspecified outage case and spreads that code across every caller.

### Event-fed copy
User profile publishes `UserSettingsChanged`; each service keeps its own copy.
- Pros: No runtime dependency on User profile, and a change shows up within seconds.
- Cons: An event, a queue, a consumer, a table and a backfill in each consuming service.
- Rejected: It breaks the requirement of no new store or event in any service.

**Also considered**
- **Client-sent header:** Rejected. The client can set any value, so a tampered or stale header would change which transactions count. It also does not exist on internal calls.
- **JWT claims:** Rejected. Settings would stay stale until the token refreshes, and Cognito claims would tie the settings to the identity provider (D3).

## Consequences

**Pros**
- Analytics no longer calls User profile: its only internal request disappears from the app doc's 4.3 and the high-level diagram.
- Values come from a trusted source, never from the client, and no service gets a new store or event.

**Cons**
- A settings change takes effect after the authorizer cache expires. The Settings page tells the user changes can take up to a minute (the 60 s cache TTL set by UP-AUTH-03).
- The authorizer's contract grows: a change to these fields affects every receiver, so the context shape is versioned with the authorizer.
- A scheduled job has no request context. If Analytics or the Ledger ever needs settings in a job, it reads them from User profile at that point. None does today; the Ledger's budget-close job runs in UTC.

## Revisit when
- A scheduled job needs settings for many users at once (add an event-fed copy for that service).
- Settings changes must apply within seconds.

## Related
- [ADR-013](ADR-013-dashboard-reports-ownership.md): why the Ledger needs the timezone.
- App architecture doc: 4.2 Trust, 4.3 Flow, 7.1 D3 and D23, invariants 2 and 3. Spec: AN-FS-02.
