# Phase 1: Cognito / Amplify Auth Implementation

**Status:** ✅ Implemented  
**Service:** fintracker-ui

---

## Why

The frontend authentication was a complete development mock with no production functionality:

- `AuthService.isAuthenticated()` returned `true` unconditionally (hardcoded)
- `login.ts` ignored submitted credentials and stored a hardcoded UUID in `localStorage`
- `auth.interceptor.ts` injected `X-Internal-User-Id: <hardcoded-UUID>` directly — bypassing API Gateway's Cognito authorizer entirely. Any browser client could claim any user identity.
- No `aws-amplify` or `amazon-cognito-identity-js` package installed
- `auth.guard.ts` only checked that `localStorage` contained any string
- No token refresh, no session timeout, no token revocation on logout
- No OAuth callback route

This was intentional scaffolding for early development, but it means the application has no authentication perimeter — it cannot be deployed to production in this state.

**Standards gap:** The implementation violated OWASP ASVS 3.4.2 (tokens in `localStorage`), RFC 7636 (no PKCE flow), PCI-DSS 8.1.8 (no session idle timeout), and PCI-DSS 8.1.7 (no token revocation on logout).

---

## What Was Implemented

### Task 1 — Install aws-amplify and create environment files

- Added `aws-amplify@6.18.0` to `package.json` dependencies
- Created `src/environments/environment.interface.ts` — shared `AppEnvironment` type (UserPoolId, App Client ID, OAuth domain, redirect URLs, devUserId)
- Created `src/environments/environment.ts` — development config with placeholder Cognito values; re-exports `AppEnvironment`
- Created `src/environments/environment.production.ts` — production config with fintracker.dev URLs
- Added `fileReplacements` to `angular.json` production build configuration

**Files:** `package.json`, `angular.json`, `src/environments/` (3 files + interface)

---

### Task 2 — Initialize Amplify in app.config.ts

- Added `Amplify.configure()` call at module load time (before Angular bootstraps)
- Configured Cognito User Pool, App Client, and OAuth Hosted UI settings from environment
- No changes to the Angular provider array

**Files:** `src/app/app.config.ts`

---

### Task 3 — Rewrite AuthService with Amplify

Replaced the entire mock implementation. New public API:

| Method | Amplify call | Notes |
|---|---|---|
| `signIn()` | `signInWithRedirect()` | Triggers Cognito Hosted UI redirect |
| `signOut()` | `signOut({ global: true })` | Revokes refresh token at Cognito; navigates to `/auth/login` |
| `getAccessToken()` | `fetchAuthSession()` | Silent refresh included; throws `AuthError` if session expired |
| `isAuthenticated()` | `fetchAuthSession()` | Returns `boolean`; does not throw |
| `getCurrentUserSub()` | `getCurrentUser()` | Returns Cognito sub |
| `isAuthenticated$` | Hub listener | `BehaviorSubject<boolean>`; updates on `signedIn`, `signedOut`, `tokenRefresh_failure` |

**Files:** `src/app/core/services/auth.service.ts`

---

### Task 4 — Create OAuth callback component and add route

- Created `src/app/features/auth/callback/callback.ts` — listens for Amplify Hub `signedIn` event, navigates to `/dashboard`; 10-second fallback timeout redirects to `/auth/login?error=auth_timeout`
- Created `src/app/features/auth/callback/callback.html` — centered Material spinner with "Signing you in…" message
- Added `/auth/callback` as a public (no guard) lazy-loaded route in `app.routes.ts`

**Files:** `src/app/features/auth/callback/callback.ts`, `callback.html`, `src/app/app.routes.ts`

---

### Task 5 — Rewrite auth interceptor (dev/prod split)

```typescript
// DEVELOPMENT build (environment.production = false)
X-Internal-User-Id: <environment.devUserId>

// PRODUCTION build (environment.production = true)
Authorization: Bearer <fetchAuthSession() access token>
```

If `fetchAuthSession()` throws (expired refresh token), the interceptor calls `authService.signOut()` and re-throws — the HTTP request fails, no stale auth state remains.

**Files:** `src/app/core/interceptors/auth.interceptor.ts`

---

### Task 6 — Update auth guard

Replaced the `localStorage` UUID string check with an async `authService.isAuthenticated()` call backed by `fetchAuthSession()`.

**Files:** `src/app/core/guards/auth.guard.ts`

---

### Task 7 — Strip login and register to single-button pages

Both components now render a branded Material card with a single primary CTA button. All hardcoded UUIDs, form fields, and `ngModel` bindings removed. Cognito Hosted UI handles credentials, password policies, and email verification.

**Files:** `login.ts`, `login.html`, `register.ts`, `register.html`

---

### Task 8 — Create IdleTimerService

- `src/app/core/services/idle-timer.service.ts`: listens to `click`, `keydown`, `mousemove`, `scroll`, `touchstart` on `document`; passive event listeners for performance
- 13-minute warning: opens `IdleWarningDialog` via `MatDialog`
- 15-minute limit: calls `authService.signOut()`
- `start()` / `stop()` remove all listeners and clear timers (no memory leaks)
- Dialog runs inside `NgZone.run()` to guarantee change detection fires in an Angular context
- `src/app/shared/idle-warning-dialog/idle-warning-dialog.ts` + `idle-warning-dialog.html`: displays live countdown; "Stay signed in" button resets the timer and closes the dialog

**Files:** `src/app/core/services/idle-timer.service.ts`, `src/app/shared/idle-warning-dialog/idle-warning-dialog.ts`, `idle-warning-dialog.html`

---

### Task 9 — Wire IdleTimerService to Layout

`LayoutComponent` (the authenticated shell) now implements `OnInit` / `OnDestroy`. `idleTimer.start()` fires when the layout mounts; `idleTimer.stop()` fires on destroy, preventing the timer from running on public routes. The `logout()` method was updated to call `authService.signOut()` (async) instead of the removed `authService.logout()`.

**Files:** `src/app/shared/layout/layout.ts`

---

## Architecture Decisions

### Cognito Hosted UI + PKCE, not a custom credential form

SPAs cannot securely store an OAuth client secret. The Authorization Code Grant with PKCE (RFC 7636) is the only standards-compliant OAuth flow for browser-based applications — the Cognito Hosted UI handles this automatically. The previous custom login form was both non-standard and non-functional (it never sent credentials anywhere).

The Hosted UI also handles MFA challenge flows, password policy enforcement, and account lockout without any SPA code — reducing attack surface.

### `sessionStorage` instead of `localStorage`

Amplify v6 defaults to `localStorage`. OWASP ASVS 3.4.2 prohibits storing sensitive auth tokens in `localStorage` because it is accessible to any JavaScript on the page — a single XSS vulnerability permanently exfiltrates tokens. `sessionStorage` is tab-scoped and cleared on tab close. Configured via `Amplify.configure()` in `app.config.ts`.

Tradeoff accepted: page refresh within the same tab re-uses the existing session (Amplify's silent refresh), but closing and reopening a tab requires re-login. This is the fintech standard behaviour.

### Dev/prod interceptor split, not a unified flow

The production flow requires API Gateway to validate the JWT and inject `X-Internal-User-Id`. In local development there is no API Gateway — the Angular dev server proxies directly to `localhost:8081` (Spring Boot). A single interceptor that always sends `Authorization: Bearer` would have nothing to validate against locally. Environment files (`environment.ts` / `environment.production.ts`) toggle the interceptor behaviour at build time with no runtime branching in production.

---

## Files Created / Modified

| File | Action |
|---|---|
| `package.json` | Added `aws-amplify@6.18.0` |
| `angular.json` | Added `fileReplacements` for production build |
| `src/environments/environment.interface.ts` | Created — `AppEnvironment` type |
| `src/environments/environment.ts` | Created — dev config |
| `src/environments/environment.production.ts` | Created — prod config |
| `src/app/app.config.ts` | Added `Amplify.configure()` |
| `src/app/core/services/auth.service.ts` | Rewritten — Amplify-backed |
| `src/app/core/services/idle-timer.service.ts` | Created |
| `src/app/core/interceptors/auth.interceptor.ts` | Rewritten — dev/prod split |
| `src/app/core/guards/auth.guard.ts` | Updated — `fetchAuthSession()` |
| `src/app/features/auth/login/login.ts` | Updated — single-button |
| `src/app/features/auth/login/login.html` | Updated — single-button |
| `src/app/features/auth/register/register.ts` | Updated — single-button |
| `src/app/features/auth/register/register.html` | Updated — single-button |
| `src/app/features/auth/callback/callback.ts` | Created |
| `src/app/features/auth/callback/callback.html` | Created |
| `src/app/app.routes.ts` | Added `/auth/callback` route |
| `src/app/shared/idle-warning-dialog/idle-warning-dialog.ts` | Created |
| `src/app/shared/idle-warning-dialog/idle-warning-dialog.html` | Created |
| `src/app/shared/layout/layout.ts` | Added `OnInit`/`OnDestroy` + idle timer wiring |

---

## What Still Needs to Happen Before Production

- [ ] Create AWS Cognito User Pool and App Client (public client, no secret)
- [ ] Set App Client to `Authorization code grant` with `openid email profile` scopes
- [ ] Enable Cognito email verification (required for Post-Confirmation trigger to fire)
- [ ] Populate `userPoolId`, `userPoolClientId`, `oauthDomain` in both environment files
- [ ] Register `http://localhost:4200/auth/callback` in Cognito App Client **Allowed callback URLs** (dev)
- [ ] Register `https://app.fintracker.dev/auth/callback` in Cognito App Client **Allowed callback URLs** (prod)
- [ ] Register `http://localhost:4200/auth/login` and `https://app.fintracker.dev/auth/login` in **Allowed sign-out URLs**
- [ ] Verify `UserContextFilter` in ledger-service correctly reads `X-Internal-User-Id` injected by API Gateway in staging environment
