# Authentication & Token Issuance

## REQ-UP-01: Cognito Hosted UI Login (OAuth2 + PKCE)

A. Business Rules:
A1. Hosted UI Credential Check 
Cognito Hosted UI collects credentials and performs the actual authentication check directly against the User Pool — no custom SPA login form. **[Implemented — `fintracker-ui/src/app/core/services/auth.service.ts::signIn`]**

A2. Token Exchange
Amplify exchanges the OAuth2 authorization code for ID/access/refresh tokens via Authorization Code Grant + PKCE (RFC 7636) after Cognito redirects back to `redirectSignIn`. **[Implemented — Amplify `fetchAuthSession`/Hub listener]**

A3. Bearer Attachment 
The UI attaches `Authorization: Bearer <access token>` to every `/api/` request in production builds; dev builds attach `X-Internal-User-Id` directly instead, since there's no local API Gateway. **[Implemented — `auth.interceptor.ts`]**

A4. No Authorizer at Login: 
Login itself never passes through API Gateway or any authorizer — that only happens on the *next* authenticated API call. **[Implemented by design — not a gap, documented here so it isn't re-litigated]**

B. Constraints:
B1. Cognito User Pool is on the **Basic (Lite) feature plan** — Pre-Token Generation V2/V3 access-token claim customization is unavailable. This is why subscription cannot be embedded in the access token and must be resolved server-side (see REQ-UP-02).

C. Data Impacts: None — no changes to this flow.

D. Component Mapping:
Location: `fintracker-ui/src/app/core/services/auth.service.ts`, `fintracker-ui/src/app/core/interceptors/auth.interceptor.ts`

E. Interface Details: None new.

F. Error Handling:
F1. **TOKEN_REFRESH_FAILURE**: `fetchAuthSession()` throws (expired refresh token) — interceptor calls `signOut()` and re-throws; no stale auth state remains. **[Implemented]**

---

# Identity & Subscription Resolution

## REQ-UP-02: Lambda Authorizer — JWT Verification + sub → internal_user_id + Subscription Lookup

A. Business Rules:
A1. JWT Signature Verification
The authorizer verifies the incoming access token's signature and expiry against the Cognito User Pool's JWKS before trusting any claim in it. JWKS keys are cached in the Lambda's execution environment memory across warm invocations to avoid a network round trip per invocation. **[Not Implemented]**

A2. Sub Resolution
The authorizer extracts `sub` from the verified token and calls `IdentityService.resolve_sub(sub)` to obtain the internal `user_id`. **[Partially Implemented — `resolve_sub()` already exists in `app/identity/service.py` and is exercised by `get_profile_handler`/`delete_account_handler`, but nothing invokes it from an API-Gateway-facing Lambda authorizer yet]**

A3. Subscription Lookup
The authorizer reads `subscription_tier` off the same user's `PROFILE` item (`USER#<user_id>` / `PROFILE`) via a second DynamoDB read. Sourced from this record — never from a Cognito custom attribute — so identity-provider independence isn't compromised. **[Not Implemented]**

A4. Context Injection
On success, the authorizer returns an Allow (simple response) plus `context: { internal_user_id, subscription_tier }`. The `HttpApi` route's parameter mapping copies these into `X-Internal-User-Id` / `X-Subscription-Tier` request headers before forwarding to the backend. **[Not Implemented]**

A5. Deny on Unmapped Sub
If `resolve_sub` raises `UserNotFoundError` (e.g. a race against the Post-Confirmation trigger not yet completing), the authorizer denies the request rather than forwarding with a null/empty identity header. **[Not Implemented]**

B. Constraints:
B1. Must be a **Lambda REQUEST authorizer with simple responses** on `HttpApi` (API Gateway v2) — matches what's already scaffolded in `services/fintracker-user-profile/template.yaml`. The built-in Cognito/JWT authorizer type is explicitly ruled out: it can validate a token but cannot call out to DynamoDB, so it cannot perform either the sub-resolution or the subscription lookup this flow requires.

B2. Cognito's Basic/Lite plan rules out Pre-Token Generation V2/V3 access-token claims — this authorizer's live DynamoDB lookup is the only available mechanism for subscription data, not a stopgap.

C. Data Impacts: None new — reuses the existing `FinTracker_UserProfile` single table (`IDENTITY#<sub>`/`MAPPING` and `USER#<id>`/`PROFILE` items already exist and already carry `subscription_tier`).

D. Component Mapping:
Location: `services/fintracker-user-profile/app/identity/` (new `authorizer_handler`, reusing existing `IdentityService`/`DynamoDBUserRepository`), `services/fintracker-user-profile/template.yaml` (new `AWS::Serverless::Function` wired as the `HttpApi`'s authorizer)

E. Interface Details:
Location: `services/fintracker-user-profile/app/identity/handlers.py` (proposed)

```python
def authorizer_handler(event: dict, context: LambdaContext) -> dict:
    """
    Lambda REQUEST authorizer (HttpApi, simple response format).
    1. Verifies the Authorization header's JWT against the Cognito JWKS.
    2. Resolves sub -> internal_user_id via IdentityService.resolve_sub.
    3. Reads subscription_tier from the same user's PROFILE item.
    Returns {"isAuthorized": bool, "context": {"internal_user_id": str, "subscription_tier": str}}.
    Denies (isAuthorized=False) on invalid/expired token or unmapped sub —
    never forwards a request with a missing or unverified identity.
    """
```

F. Error Handling:
F1. **INVALID_OR_EXPIRED_TOKEN**: JWT signature/expiry check fails — deny (`isAuthorized: false`), no DynamoDB calls attempted.

F2. **UNMAPPED_SUB**: `resolve_sub` raises `UserNotFoundError` — deny; this is expected for a brand-new signup racing the Post-Confirmation trigger, not necessarily an attack signal.

F3. **DYNAMODB_UNAVAILABLE**: Sub-resolution or subscription read fails after the existing `tenacity` retry policy is exhausted — deny (fail closed). Accepted trade-off: an outage denies access rather than granting it with stale/default data.

---

# Caching & Performance

## REQ-UP-03: API Gateway Authorizer Result Caching

A. Business Rules:
A1. Cache authorizer results per access token (`IdentitySource: $request.header.Authorization`) with a **60-second TTL**. **[Not Implemented]**
*Why 60s:* a page load typically fires several API calls in a tight burst (dashboard tiles, recent transactions, budget summary) — a 60s window collapses that entire burst into a single authorizer invocation (one JWT verify + two DynamoDB reads) instead of one per call, which is where most of the cost reduction comes from. It's short enough that a subscription downgrade is reflected for ordinary reads within about a minute — in line with the "not urgent, but not indefinite" tolerance already established for this data — while long enough to meaningfully cut Lambda/DynamoDB volume against a chatty SPA. This is a single config value (`AuthorizerResultTtlInSeconds`), not a code change, so it can be tuned per-environment without a redeploy of the authorizer itself.

A2. Cost-sensitive routes (see REQ-UP-05) are excluded from this cache regardless of the global TTL. **[Not Implemented]**

B. Constraints:
B1. `AuthorizerResultTtlInSeconds` is capped at 3600s by API Gateway; 60s is well within range.

B2. There is no built-in mechanism to evict a single cached entry early (e.g. the instant an admin downgrades a user) — only the full stage cache can be flushed (`aws apigateway flush-stage-authorizers-cache`), which resets caching for every user on that stage. Accepted as a known limitation, not solved here.

C. Data Impacts: None.

D. Component Mapping:
Location: `services/fintracker-user-profile/template.yaml` (HttpApi authorizer `AuthorizerResultTtlInSeconds` config)

E. Interface Details: None — infrastructure/config only.

F. Error Handling:
F1. **STALE_SUBSCRIPTION_WINDOW**: Not an error condition — documented expected behavior. Maximum staleness after a subscription change is bounded by the 60s TTL for any cached route.

---

# Multi-Tenant Security

## REQ-UP-04: Fail-Closed Authorization

**Problem:**
An authorizer that fails open (allows the request through when verification or lookup errors out) would let an unverifiable identity reach backend services that unconditionally trust `X-Internal-User-Id` — the same trust violation the architecture already prohibits for user-supplied IDs.

**Requested Changes:**
- Every authorizer failure mode (bad signature, expired token, unmapped sub, DynamoDB unavailable) must deny the request. No code path may forward a request to a backend without a verified `internal_user_id` in the authorizer's context.

**Constraints (if applicable):**
- None beyond what's already listed under REQ-UP-02's error handling.

**Interface (if applicable):**
- None new.

## REQ-UP-05: Live, Uncached Check for Cost-Bearing Actions

**Problem:**
REQ-UP-03's 60-second cache is a reasonable default for cheap, frequent reads, but it is not safe as the sole gate on any action that spends real money externally (e.g. statement upload triggering Textract/Bedrock calls). A user downgraded mid-session could keep invoking a cost-bearing endpoint at their old tier for up to the full cache TTL.

**Requested Changes:**
- Cost-bearing routes (statement upload, and any future AI-insight endpoint) must not rely on the cached authorizer context alone for subscription/quota enforcement. Either exclude that route from authorizer caching (`AuthorizerResultTtlInSeconds: 0` for that route) or perform a second, live subscription check inside the handler itself before doing the expensive work. This matches the ledger architecture doc's own separate "Subscription Lambda" design for the upload-gating path — that mechanism should be kept, not replaced by REQ-UP-02/03.

**Constraints (if applicable):**
- Applies only to routes that trigger external paid inference calls or enforce a hard usage quota — not a blanket exclusion from caching.

**Interface (if applicable):**
- None new — reuses the same `IdentityService`/DynamoDB read, just invoked live instead of via the cached authorizer path.
