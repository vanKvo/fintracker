# User Profile Architecture

| Status | Owner | Last reviewed | Applies to | App architecture |
|---|---|---|---|---|
| Existing | Van Vo | 2026-10-25 | main | [FinTracker architecture](../../fintracker-architecture/fintracker-architectural-doc.md) |

This document describes how the User Profile service works. Rules that apply to every service (identity, events, invariants) are in the app architecture doc, and where this document and the app doc disagree, the app doc wins and this document is corrected. Field-level rules for sign-in and the identity authorizer are in [UP-AUTH](../specs/UP-AUTH-authentication-spec.md). It replaces `services/fintracker-user-profile/docs/fintracker-user-profile-architectural-doc.md` as the reference; the older file keeps the table layout and code map.

---

## 1. Overview

**Purpose:** User Profile is the identity authority. It is the only service that knows how a Cognito `sub` maps to the internal `userId`, so every other service stays independent of the identity provider (app doc D3).

**Responsibilities**
- Create the internal user when Cognito confirms a sign-up.
- Run the **identity authorizer**: verify the token, map `sub` → `userId`, attach the subscription tier, timezone and primary currency (UP-AUTH-02, D23).
- Serve and update the user's profile and settings.
- Manage savings goals.
- Start account deletion and publish `UserAccountDeleted`.

**Does not do**
- Store financial data (the Ledger does).
- Compute goal progress for the AI assistant (the AI assistant does, from the raw goals).
- Delete other services' data (each does its own, on `UserAccountDeleted`).

**Owns**
- Identity mappings, profiles, settings, savings goals: one DynamoDB table, `FinTracker_UserProfile`.

---

## 2. Architecture and workflows

*Component diagram: to be added (`images/user-profile-components.svg`).*

### Workflows

#### Register a user

**Trigger:** Cognito Post-Confirmation trigger · **Result:** identity mapping, profile and settings exist · **On failure:** the trigger fails and Cognito reports the error; the user can retry sign-in

1. Cognito confirms the user and invokes the Post-Confirmation function.
2. Create the `IDENTITY#<sub>` mapping, profile and settings in one transaction.
3. Return the original event to Cognito.

#### Authorize a request

**Trigger:** any public API call · **Result:** a verified user context on the request · **On failure:** deny (fail closed, UP-AUTH-04)

1. Verify the access token against the User Pool's keys.
2. Resolve `sub` → `userId`; an unmapped `sub` is denied.
3. Read subscription tier, timezone and primary currency from the user's records.
4. Return the context; API Gateway caches it for 60 s, except on cost-bearing routes (UP-AUTH-03, UP-AUTH-05).

#### Serve a user's goals to another service

**Trigger:** signed internal request from the AI assistant (chat goals tool) · **Result:** the user's raw goals · **On failure:** 401 `unauthorized` for no verified caller, 403 `caller_not_allowed` for a caller not on the allow-list, 404 for an unknown user

1. API Gateway verifies the SigV4 signature (IAM authorization) on `user-profile-internal`.
2. The handler checks the caller's role ARN against the allow-list; an empty list rejects every call.
3. Take the user from the forwarded `X-Internal-User-Id` header, never from the path (app invariants 2 and 3).
4. Return the goals.

*The shared static API key (`x-internal-api-key`) and the user in the path were removed on 2026-10-25 (invariant 3). See 3.2.*

#### Delete an account

**Trigger:** `DELETE /profile` closes the account; a scheduled job starts hard deletion 30 days later ([XS-DEL](../../fintracker-cross-services/specs/XS-DEL-account-deletion-spec.md)) · **Result:** User Profile records deleted, `UserAccountDeleted` published · **On failure:** the run is retried; nothing a retry needs is removed first

1. Close: mark the account `CLOSED` and disable the Cognito user (XS-DEL-01).
2. After 30 days, publish `UserAccountDeleted` and record the publish (XS-DEL-02). Each service deletes its own share and reports `UserDataDeleted`.
3. Delete all `USER#<id>` items, reading every page of the partition, then the Cognito user.
4. Delete the `IDENTITY#<sub>` mapping last, so a retry after a partial failure can still resolve the user.

---

## 3. Concepts of Operation

### 3.1 Enter: what does this service expose and consume?

| Interface | Type | Caller / producer | Purpose |
|---|---|---|---|
| Identity authorizer | Lambda REQUEST authorizer | API Gateway (every public API, chat streaming API) | Verified user context |
| `GET`, `DELETE /profile` | Public API | Web client | Read profile and settings; delete the account |
| `PUT /profile/settings` | Public API | Web client | Save timezone and currency (XS-CTX) |
| `GET`, `POST /profile/goals`, `DELETE /profile/goals/{id}` | Public API | Web client | Manage savings goals |
| `GET /profile/internal/users/{userId}/settings` | Internal API (`user-profile-internal`) | Analytics | Timezone and currency. Superseded by settings in the verified context (D23); retire once no caller uses it |
| `GET /profile/internal/goals` | Internal API (`user-profile-internal`) | AI assistant | Raw savings goals for the user in the forwarded context |
| Post-Confirmation | Cognito trigger | Cognito | Create the user |
| `UserAccountDeleted` | Event published | → every service that stores user data | Start deletion |
| `UserDataDeleted` *(proposed)* | Event consumed | Each service | Track deletion completion |

### 3.2 Trust: who may call it, and how is each request scoped to a user?

- **Public routes:** the user comes from the identity authorizer's context, never from the request.
- **Internal routes** (ADR-004, ADR-011), on the `user-profile-internal` HTTP API:
  - every route uses IAM authorization (SigV4); there is no route without it;
  - the handler checks the caller's role against `INTERNAL_ALLOWED_CALLER_ARNS`; unset means every call is rejected;
  - allowed callers: Analytics (settings, until retired), AI assistant (goals);
  - the user comes from the forwarded context headers (XS-CTX-04), which are trusted only on an IAM-verified call.
- **No static API keys.** The goals route's shared key was removed when the route moved to IAM authorization; the AI assistant no longer has `USER_PROFILE_INTERNAL_API_KEY` and sends only its signature and the forwarded context.

### 3.3 Flow: how does it depend on other services?

| Depends on | How | Why | If unavailable |
|---|---|---|---|
| Cognito | Trigger; token keys | Sign-up and token verification | Sign-in fails; the authorizer denies |
| EventBridge | Event published | Account deletion fan-out | Deletion call fails and can be retried |

User Profile calls no other FinTracker service.

### 3.4 Store: what data does it keep, and for how long?

| Data | Store | Retention | On account deletion |
|---|---|---|---|
| Identity mapping (`sub` → `userId`) | DynamoDB | Life of the account | Deleted (last, after the `USER#` items) |
| Profile, settings, subscription tier | DynamoDB | Life of the account | Deleted |
| Savings goals | DynamoDB | Until the user deletes them | Deleted |

### 3.5 Protect: what does this service guard beyond the app-level rules?

- The Cognito `sub` is stored only in the identity mapping and never leaves the identity feature.
- The subscription tier comes from the profile record, never from a token claim the client could influence.
- The authorizer fails closed on every error (UP-AUTH-04).

### 3.6 Recover: how does it fail, and how does it recover?

- Registration is one transaction, so a failed trigger leaves no partial user.
- A `sub` that is not mapped yet (sign-up racing the trigger) is denied, not forwarded empty (UP-AUTH-02).
- DynamoDB errors are retried, then the request is denied.

### 3.7 Observe: how do we know it is healthy?

- Authorizer denies by reason (invalid token, unmapped `sub`, store down).
- Internal calls rejected by the allow-list (a warning log; a spike means a misconfigured caller).
- Post-Confirmation failures.

---

## 4. Service decisions

| # | Decision | Choice | Why | Revisit when | Status |
|---|---|---|---|---|---|
| S1 | Data layout | One DynamoDB table; the identity mapping under its own `IDENTITY#` key, apart from `USER#` records | The `sub` never sits next to profile data | Access patterns need a second index | Accepted |
| S2 | Authorizer | Lambda REQUEST authorizer with a DynamoDB lookup, not the built-in JWT authorizer | The built-in one can't map `sub` or read the tier (UP-AUTH-02) | Cognito plan allows custom access-token claims | Accepted |
| S3 | Internal route authentication | IAM authorization plus caller allow-list, user in the forwarded context, on every internal route; no API keys | App invariant 3; same mechanism as every other service (ADR-004, ADR-011) | Never | Accepted |

---

## 5. Related documents

- **App architecture:** [FinTracker architecture](../../fintracker-architecture/fintracker-architectural-doc.md): D3, D7, D18, D23, invariants 2 and 3.
- **ADRs:** [ADR-004](../../fintracker-architecture/architectural_decision_records/ADR-004-internal-api-regional-iam.md), [ADR-011](../../fintracker-architecture/architectural_decision_records/ADR-011-internal-api-per-service.md), [ADR-015](../../fintracker-architecture/architectural_decision_records/ADR-015-settings-in-verified-context.md).
- **Specs:** [UP-AUTH](../specs/UP-AUTH-authentication-spec.md), [XS-CTX](../../fintracker-cross-services/specs/XS-CTX-verified-user-context-spec.md).
- **Flows:** [Registration and login](../registration_and_login_flow.md).
- **Code map and table layout:** `services/fintracker-user-profile/docs/fintracker-user-profile-architectural-doc.md`.
