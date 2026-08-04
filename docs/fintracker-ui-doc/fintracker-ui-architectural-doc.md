# fintracker-ui — Architectural Document

## App Overview

fintracker-ui is the Angular 21 single-page application (SPA) for the FinTracker platform. It is a standalone-component app using Angular Material for UI, RxJS for reactive state, and AWS Amplify v6 for authentication.

**Tech stack:** Angular 21 · Angular Material 21 · AWS Amplify v6 (`aws-amplify`) · RxJS 7 · ng2-charts / Chart.js

**Route structure:**

| Route | Guard | Purpose |
|---|---|---|
| `/auth/login` | None (public) | Single-button Cognito Hosted UI redirect |
| `/auth/register` | None (public) | Single-button Cognito Hosted UI redirect |
| `/auth/callback` | None (public) | OAuth authorization code exchange handler |
| `/dashboard` | `authGuard` | Main dashboard (authenticated) |
| `/transactions` | `authGuard` | Transaction list and filter |
| `/statements` | `authGuard` | Statement upload and history |
| `/budgets` | `authGuard` | Budget management |
| `/reports` | `authGuard` | Spending reports and analytics |
| `/settings` | `authGuard` | User profile and preferences |

---

## Auth Architecture

### Flow

```
1. User visits /dashboard (or any protected route)
   └── authGuard calls fetchAuthSession()
       ├── Session valid → route activates
       └── No session → redirect to /auth/login

2. User clicks "Sign in with FinTracker" on /auth/login
   └── authService.signIn() → Amplify.signInWithRedirect()
       └── Browser navigates to Cognito Hosted UI

3. User authenticates in Cognito Hosted UI (email + password, MFA if enabled)
   └── Cognito redirects to /auth/callback?code=<auth_code>&state=<state>

4. /auth/callback component loads
   └── Amplify automatically exchanges the auth code for tokens (PKCE)
       └── Hub emits 'signedIn' event
           └── CallbackComponent navigates to /dashboard

5. AuthService Hub listener updates isAuthenticated$ to true
   └── Subsequent API requests:
       DEV build  → X-Internal-User-Id: <devUserId from environment.ts>
       PROD build → Authorization: Bearer <access_token from fetchAuthSession()>
       Amplify silently refreshes the access token before expiry

6. User is idle for 13 minutes
   └── IdleTimerService opens IdleWarningDialog (2-min countdown)
       ├── User clicks "Stay signed in" → timer resets
       └── Countdown reaches 0 → authService.signOut()

7. User clicks logout (or idle timeout fires)
   └── authService.signOut() → Amplify.signOut({ global: true })
       └── Refresh token revoked at Cognito
           └── Navigate to /auth/login; sessionStorage cleared
```

### Key services

| Service | File | Responsibility |
|---|---|---|
| `AuthService` | `src/app/core/services/auth.service.ts` | Wraps Amplify auth; exposes `signIn()`, `signOut()`, `getAccessToken()`, `isAuthenticated()`, `isAuthenticated$` |
| `IdleTimerService` | `src/app/core/services/idle-timer.service.ts` | DOM event listener; 13-min warning / 15-min auto-logout |
| `authGuard` | `src/app/core/guards/auth.guard.ts` | Async `fetchAuthSession()` check on every protected route |
| `authInterceptor` | `src/app/core/interceptors/auth.interceptor.ts` | Adds auth header to all `/api/` requests (dev vs. prod logic) |
| `CallbackComponent` | `src/app/features/auth/callback/callback.ts` | Handles Cognito redirect; Hub listener; 10 s fallback |
| `IdleWarningDialog` | `src/app/shared/idle-warning-dialog/` | Live countdown dialog; "Stay signed in" button |

### Architecture decisions

**Cognito Hosted UI with PKCE over a custom credential form** — SPAs cannot store a client secret, so the OAuth 2.0 Authorization Code flow with PKCE (RFC 7636) is mandatory. The Hosted UI handles credentials, MFA challenges, and password policy enforcement without any of that logic living in the SPA.

**`sessionStorage` for token storage** — Amplify v6 defaults to `localStorage`, which is accessible to any JavaScript on the page (XSS risk). `sessionStorage` is scoped to the tab, cleared on tab close, and not accessible to other browser tabs or origins. Configured in `Amplify.configure()` in `app.config.ts`. Tradeoff: page refresh requires re-login if the session has expired (Amplify handles silent refresh within the tab lifetime).

**Dev/prod interceptor split via environment files** — In development the app proxies directly to a local Spring Boot ledger service (`localhost:8081`) with no API Gateway in between. The prod interceptor (`Authorization: Bearer`) would have no JWT to validate locally. The dev interceptor injects `X-Internal-User-Id: <devUserId>` from `environment.ts`, preserving the dev workflow without a local Cognito pool.

---

## Environment Configuration

| Key | Dev value | Prod value | Purpose |
|---|---|---|---|
| `production` | `false` | `true` | Switches interceptor between dev and prod auth headers |
| `cognito.userPoolId` | `REPLACE_WITH_DEV_USER_POOL_ID` | `REPLACE_WITH_PROD_USER_POOL_ID` | Cognito User Pool ID |
| `cognito.userPoolClientId` | `REPLACE_WITH_DEV_APP_CLIENT_ID` | `REPLACE_WITH_PROD_APP_CLIENT_ID` | Cognito App Client ID (public, no secret) |
| `cognito.oauthDomain` | `REPLACE_WITH_DEV_COGNITO_DOMAIN` | `auth.fintracker.dev` | Cognito domain for Hosted UI |
| `cognito.redirectSignIn` | `http://localhost:4200/auth/callback` | `https://app.fintracker.dev/auth/callback` | Must be registered in Cognito App Client |
| `cognito.redirectSignOut` | `http://localhost:4200/auth/login` | `https://app.fintracker.dev/auth/login` | Must be registered in Cognito App Client |
| `devUserId` | `e2b86a8a-b851-460d-8ea9-a1b66df8ae8e` | `""` (unused) | Fixed UUID injected in dev interceptor |

**Files:** `src/environments/environment.ts` (dev + interface), `src/environments/environment.production.ts` (prod), `src/environments/environment.interface.ts` (type contract).

---

## Phase Tracker

| # | Phase | Status | Detail |
|---|---|---|---|
| 1 | Cognito / Amplify Auth Implementation | ✅ Implemented | [phase-1-cognito-auth-implementation.md](phases/phase-1-cognito-auth-implementation.md) |
| 2 | Security Hardening (CSP, CORS, Audit Logging, MFA UI) | 🔲 Planned | [phase-2-security-hardening.md](phases/phase-2-security-hardening.md) |

---

## Open Issues (not yet assigned to a phase)

- **No Content Security Policy (CSP)** — Angular build and API Gateway don't set `Content-Security-Policy` headers. An XSS attack could abuse `sessionStorage` tokens. → Assigned to Phase 2.
- **No CORS policy on backend services** — Ledger (Spring Boot) and Analytics (FastAPI) have no explicit `Access-Control-Allow-Origin` restrictions. → Tracked in ledger and analytics services; surfaced here for UI testing.
- **No auth event audit logging** — successful logins, failed attempts, and idle logouts are not captured in structured logs. → Assigned to Phase 2 (via Cognito Pre-Auth trigger + Lambda Powertools).
- **No MFA UI** — Cognito supports TOTP but there is no enrollment flow in Settings. → Assigned to Phase 2.
- **No brute-force protection** — Cognito Advanced Security (Adaptive Authentication) is not configured. → Infrastructure/CDK task, not an Angular task.
