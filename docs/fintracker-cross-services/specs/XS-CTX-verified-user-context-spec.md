# XS-CTX: Settings in the Verified User Context

| Field | Value |
|---|---|
| Product | FinTracker |
| Prefix | XS-CTX |
| File | fintracker-cross-services/specs/XS-CTX-verified-user-context-spec.md |
| Owner | Van Vo |
| Status | Draft |
| Last updated | 2026-10-20 |

**Services:** User profile (identity authorizer, settings), AI assistant (forwards the context), Analytics and Ledger (consume it). Decision record: [ADR-015](../../fintracker-architecture/architectural_decision_records/ADR-015-settings-in-verified-context.md).

---

## 1. Overview

### Problem
Analytics needs the user's timezone to know which day "today" is, and the primary currency to know which transactions count. The Ledger now needs the timezone to decide which month the Dashboard shows. Today Analytics calls User profile's internal settings route and caches the answer, and nothing defines what happens on a cache miss while User profile is down. A wrong timezone or currency produces numbers that look right, so guessing a default is not acceptable.

### Goals
- No service calls User profile at request time to read settings.
- Every request that needs settings gets trusted values, or fails clearly. It never uses a default.
- A settings change takes effect everywhere within 5 minutes.

### Non-Goals
- Currency conversion. Only the primary currency counts (Analytics S8).
- Notification or display preferences. They stay in User profile.
- Scheduled jobs that need settings without a request. None exists today (ADR-015, "Revisit when").

### Design Principles
1. **One source, one carrier.** User profile stores the settings; the verified user context carries them. Nothing else holds a copy.
2. **Trusted or nothing.** Values come only from the identity authorizer or a signed internal request. Client-sent headers, query strings, bodies and tool arguments are ignored.
3. **Fail closed, never default.** A receiver that needs a setting and doesn't get a valid one returns an error.

---

## 2. Workflow

```
[Sign-up; first app load saves the browser timezone] ──► XS-CTX-01
    │
[Request → identity authorizer reads PROFILE + SETTINGS in one query] ──► XS-CTX-02
    │
[Gateway maps context to headers; client copies are overwritten] ──► XS-CTX-03
    │
[AI assistant forwards the same fields on signed internal calls] ──► XS-CTX-04
    │
[Receiver validates; missing or invalid → fail closed] ──► XS-CTX-05
    │
[Settings change → effective after the authorizer cache expires] ──► XS-CTX-06
    │
[Retire the internal settings route] ──► XS-CTX-07
```

---

## 3. Requirements Index

| ID | Title | Area | Priority | Status |
|---|---|---|---|---|
| XS-CTX-01 | Every user has a timezone and a primary currency | Data | MVP | Implemented |
| XS-CTX-02 | Authorizer attaches timezone and currency | Security | MVP | Implemented |
| XS-CTX-03 | Trusted headers on public routes | Security | MVP | In progress |
| XS-CTX-04 | Forwarding on internal requests | Security | MVP | In progress |
| XS-CTX-05 | Receivers validate and fail closed | Reliability | MVP | In progress |
| XS-CTX-06 | Settings changes | UI | MVP | Implemented |
| XS-CTX-07 | Retire the internal settings route | Security | MVP | In progress |

---

## 4. Requirements

### XS-CTX-01: Every user has a timezone and a primary currency  `Priority: MVP`

**Problem:** The server can't know a new user's timezone, and a settings item without one would fail every Dashboard request.
**Requirement:** The sign-up confirmation hook creates the `SETTINGS` item with `currency = USD` and no timezone. On the first app load after sign-in, the client reads the profile and, if `timezone` is missing, saves the browser's IANA timezone (`Intl.DateTimeFormat().resolvedOptions().timeZone`) before loading the Dashboard. A one-time backfill sets both values for existing users.
**Acceptance Criteria:**
- [Happy] A new user's first app load saves `America/New_York` (from the browser) and the Dashboard then loads normally.
- [Alt] A browser that reports no timezone, or an invalid one, shows a timezone picker before the Dashboard, defaulting to nothing.
- [Alt] The backfill script takes the timezone as an explicit argument per user, and refuses to run without one.
- [Fail] Saving a timezone that isn't an IANA name, or a currency that isn't on the supported list, returns 400 `invalid_setting` and stores nothing.
**Currency:** FinTracker supports one currency, USD. The primary currency is read-only in Settings, every account is created in USD, and imported rows take their account's currency, because bank statements and CSV exports carry plain numbers in the account's currency. Multi-currency later adds account currencies, exchange rates and conversion at read time, without changing stored data.
**Refs:** Appendix A; UP-AUTH-01

### XS-CTX-02: Authorizer attaches timezone and currency  `Priority: MVP`

**Requirement:** The identity authorizer (UP-AUTH-02) reads the user's `PROFILE` and `SETTINGS` items in one DynamoDB `Query` on `PK = USER#<user_id>`, and returns `timezone` and `currency` in its context alongside `internal_user_id` and `subscription_tier`. The same authorizer serves the gateway and the chat REST API (ADR-012).
**Acceptance Criteria:**
- [Happy] An allowed request's authorizer context contains all four fields from Appendix B.
- [Happy] The authorizer still makes one DynamoDB call per uncached request, not two.
- [Alt] A user with no timezone yet is still allowed; the context carries `timezone: ""`, and receivers handle it under XS-CTX-05.
- [Fail] A DynamoDB failure after retries denies the request, as UP-AUTH-02 F3 already requires.
**Refs:** UP-AUTH-02; UP-AUTH-03 (authorizer result caching); Appendix B

### XS-CTX-03: Trusted headers on public routes  `Priority: MVP`

**Requirement:** For services behind the HTTP API that read headers (the Ledger), the route's parameter mapping sets `X-User-Timezone` and `X-User-Currency` from the authorizer context, overwriting any client-sent value. Lambda-integrated services (Analytics) read the authorizer context directly and ignore these headers from clients.
**Acceptance Criteria:**
- [Happy] The Ledger receives the mapped headers on every authorized request.
- [Fail] A client request that sends `X-User-Timezone: Pacific/Auckland` reaches the Ledger with the user's stored timezone instead.
- [Fail] In prod the Ledger is reachable only through the VPC link (app doc 6.3), so no request can reach it without the mapping.
**Refs:** Appendix B; app doc 4.2 Trust

### XS-CTX-04: Forwarding on internal requests  `Priority: MVP`

**Requirement:** When the AI assistant calls Analytics, the Ledger or Knowledge, it forwards `X-Internal-User-Id`, `X-User-Timezone` and `X-User-Currency` from its own authorizer context on the SigV4-signed request. Receivers read these headers only on internal routes, and only after the caller check passes.
**Acceptance Criteria:**
- [Happy] A chat tool call to Analytics carries the same three values the chat request's authorizer produced.
- [Fail] A tool argument named `timezone`, `currency` or `user_id` is rejected by schema validation in `execute_tool` and logged as a security event.
- [Fail] The same headers on a request from a role not on the allow-list are ignored, and the request is rejected with 403.
**Refs:** ADR-004; ADR-011; invariant 3; AI-CHAT-04

### XS-CTX-05: Receivers validate and fail closed  `Priority: MVP`

**Requirement:** A route that needs a setting validates it before any other work: the timezone must be a valid IANA name and the currency must be on the supported list (Appendix A). A missing or invalid value returns 409 `user_settings_incomplete` (missing timezone) or 500 `user_context_invalid` (anything else), with no fallback. Routes that don't need settings don't check them.
**Acceptance Criteria:**
- [Happy] Ledger Dashboard summary and Analytics spending pace use the context values and nothing else.
- [Alt] The client treats 409 `user_settings_incomplete` by showing the timezone picker from XS-CTX-01.
- [Fail] An empty or invalid currency returns 500 `user_context_invalid`, increments the `user_context_invalid` metric and raises an alarm on the first occurrence.
- [Fail] No code path substitutes `UTC` or `USD` for a missing value; a unit test asserts this for each receiver.
**Refs:** Appendix C; ADR-015

### XS-CTX-06: Settings changes  `Priority: MVP`

**Requirement:** A timezone change is saved through User profile and takes effect when the user's cached authorizer result expires (at most the authorizer cache TTL, 300 s). The Settings page says so after saving.
**Acceptance Criteria:**
- [Happy] After a change, the Settings page shows "Saved. It can take up to 5 minutes to apply everywhere."
- [Alt] A request made within the TTL still uses the previous value, consistently across the Ledger and Analytics, because both read the same cached context.
- [Fail] A save that fails validation (XS-CTX-01) leaves the previous value in place.
**Refs:** UP-AUTH-03

### XS-CTX-07: Retire the internal settings route  `Priority: MVP`

**Requirement:** Once Analytics and the AI assistant read settings from the context, User profile's internal settings route (added for AN-FS-02) is removed, with its allow-list entries and the callers' IAM permissions.
**Acceptance Criteria:**
- [Happy] No service's IAM policy grants access to the settings route, and the route no longer exists on `user-profile-internal`.
- [Alt] The Analytics settings cache and its tests are removed in the same change.
- [Fail] A deploy that still calls the route fails its integration test, because the route returns 404.
**Refs:** ADR-015 Consequences; app doc 4.3

---

## 5. Open Questions (consolidated)

None.

---

## Appendix A: Supported values

| Setting | Format | Supported values today |
|---|---|---|
| `timezone` | IANA time zone name | Any name in the IANA database (validated with `zoneinfo` in Python and `ZoneId` in Java) |
| `currency` | ISO 4217 code | `USD` |

---

## Appendix B: Context and headers

Produced by: the User profile identity authorizer (code).

| Context key | Header (public, Ledger) | Header (internal, signed) | Example |
|---|---|---|---|
| `internal_user_id` | `X-Internal-User-Id` | `X-Internal-User-Id` | `d781b133-…` |
| `subscription_tier` | `X-Subscription-Tier` | — | `free` |
| `timezone` | `X-User-Timezone` | `X-User-Timezone` | `America/New_York` |
| `currency` | `X-User-Currency` | `X-User-Currency` | `USD` |

---

## Appendix C: Errors

Body: RFC 9457 `application/problem+json`, as every service (app doc 4.8; [error catalog](../../fintracker-architecture/error-catalog.md)):
`{ "type", "title", "status", "detail", "code", "retryable", "trace_id" }`. `detail` is generic; `request_id` is logged, never returned.

| HTTP | Code | When |
|---|---|---|
| 400 | `invalid_setting` | A settings save with an invalid value |
| 409 | `user_settings_incomplete` | A route needs the timezone and the user hasn't set one |
| 500 | `user_context_invalid` | A value is present but invalid, or the currency is missing |
