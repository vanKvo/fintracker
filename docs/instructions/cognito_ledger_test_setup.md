# Plan: Local Cognito + Ledger Test Setup

## Context

This document describes how to configure a real AWS Cognito User Pool for local development and populate the PostgreSQL ledger with test data so you can authenticate a real Cognito user and exercise core ledger logic — without going through API Gateway.

Phase 1 (Cognito/Amplify auth) implemented the full PKCE auth flow in the Angular app. The `environment.ts` file contains placeholder Cognito values; this guide explains how to replace them.

---

## How the dev flow works

```
User logs in via Cognito Hosted UI (real PKCE / Authorization Code flow)
     ↓
Amplify stores tokens in sessionStorage
     ↓
Angular API request hits authInterceptor
     ↓  environment.production = false
X-Internal-User-Id: e2b86a8a-b851-460d-8ea9-a1b66df8ae8e   ← hardcoded devUserId
     ↓  proxy.conf.json
localhost:8081  (Spring Boot ledger)
     ↓  UserContextFilter
ThreadLocal userId = e2b86a8a-b851-460d-8ea9-a1b66df8ae8e
     ↓  RlsExecuteListener: SET app.current_user_id = '...'
PostgreSQL RLS: only rows where user_id = 'e2b86a8a-...' are visible
```

The dev interceptor always sends the same hardcoded `devUserId` regardless of which Cognito user is signed in. Every login sees the same seeded dataset — intentional for testing ledger logic. The Cognito auth is real (PKCE, sessionStorage tokens, idle timeout, token revocation on logout).

---

## Cognito Auth Flow Reference

Two different Cognito concepts that are often confused:

| Concept | Where it applies |
|---|---|
| **App Client auth flows** (`ALLOW_USER_SRP_AUTH`, etc.) | Direct SDK calls (custom login form via Amplify `signIn()`) |
| **OAuth 2.0 grant types** (`Authorization code grant`) | Hosted UI browser flows via `signInWithRedirect()` |

Our implementation uses `signInWithRedirect()` — OAuth 2.0 Authorization Code grant with PKCE. This is NOT one of the `ALLOW_*` SDK flows.

### What to enable in the App Client

| Setting | Enable? | Why |
|---|---|---|
| OAuth grant type: `Authorization code grant` | ✅ Yes | Required for `signInWithRedirect()` + PKCE |
| OAuth grant type: `Implicit grant` | ❌ No | Deprecated and insecure |
| App Client flow: `ALLOW_REFRESH_TOKEN_AUTH` | ✅ Yes | Amplify uses refresh tokens for silent renewal |
| App Client flow: `ALLOW_USER_SRP_AUTH` | Optional | Enables future custom login form. Safe to enable — SRP is cryptographically secure. Enable Cognito Advanced Security if you do. |
| App Client flow: `ALLOW_USER_AUTH` | Optional | Enables passwordless/passkeys/OTP in future. Enable Cognito Advanced Security if you do. |
| App Client flow: `ALLOW_USER_PASSWORD_AUTH` | ❌ No | Less secure (password in request body) |

---

## Step 1: Create a Cognito User Pool (AWS Console)

**User Pool settings:**
- Name: `fintracker-dev`
- Sign-in identifier: Email
- MFA: Off (dev)
- Self-registration: Enabled
- Email verification: Required

**App Client settings:**
- Name: `fintracker-ui-dev`
- Client type: **Public client** (no secret)
- OAuth grant types: `Authorization code grant`
- App Client auth flows: `ALLOW_REFRESH_TOKEN_AUTH` (+ optional SRP/USER_AUTH — see above)
- Scopes: `email`, `openid`, `profile`
- Allowed callback URL: `http://localhost:4200/auth/callback`
- Allowed sign-out URL: `http://localhost:4200/auth/login`

**Hosted UI domain:**

Cognito provides the domain — you only choose a globally unique prefix.
1. User Pool → **Branding → Domain**
2. Choose **Cognito domain** (free, no DNS required)
3. Enter prefix: `fintracker-dev`
4. Cognito creates: `fintracker-dev.auth.<region>.amazoncognito.com`

Find the full domain after creation at:
**AWS Console → Cognito → User Pool → Branding tab → Domain section**

---

## Step 2: Update `environment.ts`

File: `fintracker-ui/src/environments/environment.ts`

Replace the three `REPLACE_WITH_*` placeholders:

```typescript
cognito: {
  userPoolId:       'us-east-1_AbCdEfGhI',          // User Pool → Overview
  userPoolClientId: 'abc123xyz...',                  // App Client → Client ID
  oauthDomain:      'fintracker-dev.auth.us-east-1.amazoncognito.com',
  redirectSignIn:   'http://localhost:4200/auth/callback',
  redirectSignOut:  'http://localhost:4200/auth/login',
},
devUserId: 'e2b86a8a-b851-460d-8ea9-a1b66df8ae8e',  // keep unchanged
```

---

## Step 3: Seed the PostgreSQL ledger database

File: `services/fintracker-ledger/test-data/dev_seed_data.sql`

V3 migration enabled `FORCE ROW LEVEL SECURITY` on all ledger tables. The `SET app.current_user_id` at the top of the script is required so RLS allows the inserts.

Run once, after Spring Boot has started and Flyway has applied all migrations:

```bash
psql $DB_URL -U $DB_USERNAME -f services/fintracker-ledger/test-data/dev_seed_data.sql
```

Seed data created:
- 2 accounts (Chase Checking, Amex Gold) for `devUserId`
- 17 transactions across May–June 2026 (mix of categories, POSTED + PENDING_APPROVAL)
- 1 budget for June 2026 with 4 category lines
- 2 upcoming bills (Rent, Comcast)

---

## Step 4 (optional): Bootstrap DynamoDB identity record

Only needed if you want to test user-profile endpoints (`GET /profile`, goals, etc.) locally. Not required for ledger testing.

Find your Cognito sub:
**AWS Console → Cognito → User Pool → Users tab → click your test user → `sub` attribute**

Then run:

```bash
export AWS_DEFAULT_REGION=us-east-1
export DYNAMODB_TABLE_NAME=FinTracker_UserProfile
python scripts/dev_setup_user.py --sub <cognito_sub> --email <your_email>
```

This creates the `IDENTITY#<sub> MAPPING → devUserId` record in DynamoDB, simulating what the Post-Confirmation trigger does in production.

---

## Run the local stack

```bash
# 1. Start PostgreSQL
cd services/fintracker-ledger && docker compose up -d

# 2. Start Spring Boot ledger (Flyway runs migrations automatically)
mvn spring-boot:run

# 3. Seed test data (one-time, after Flyway completes)
psql $DB_URL -U $DB_USERNAME -f test-data/dev_seed_data.sql

# 4. Start Angular dev server
cd fintracker-ui && ng serve
```

---

## Verification checklist

- [ ] `http://localhost:4200/auth/login` shows "Sign in with FinTracker" button
- [ ] Clicking opens Cognito Hosted UI (`fintracker-dev.auth.<region>.amazoncognito.com/login?...`)
- [ ] After login → `/auth/callback` → spinner → navigates to `/dashboard`
- [ ] Dashboard API calls return 200 (Network tab: `GET /api/v1/ledger/...`)
- [ ] DevTools → Application → Session Storage: Amplify tokens under `CognitoIdentityServiceProvider.*`
- [ ] Clicking logout → sessionStorage cleared → `/auth/login`
- [ ] Ledger server logs show `userId=e2b86a8a-...` on every request

---

## Limitation and future improvement

The dev interceptor sends the hardcoded `devUserId` regardless of who is logged in. This is intentional for testing ledger logic — all Cognito users see the same seeded data. If multi-user isolation testing is needed, the interceptor would need to resolve the Cognito sub to an internal UUID by calling the user-profile service locally. This is a future enhancement, not needed for core ledger testing.
