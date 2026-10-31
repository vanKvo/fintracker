# UI-AUTH: Session Security

| Field | Value |
|---|---|
| Product | FinTracker |
| Prefix | UI-AUTH |
| File | fintracker-ui-doc/specs/UI-AUTH-session-security-spec.md |
| Owner | Van Vo |
| Status | Draft |
| Last updated | 2026-10-23 |

---

## 1. Overview

### Problem
Two parts of the UI's sign-in behavior differ from what the architecture requires. Tokens sit in Amplify's default storage (`localStorage`), so one injected script could read them for good, although Phase 1 recorded `sessionStorage` as the decision and the UI architecture (S9) now accepts it. And the Ledger's local-development shortcut (`X-Internal-User-Id`) is still in the client, although the app architecture allows no path around the identity authorizer (invariant 2).

### Goals
- Tokens live only for the life of one browser tab.
- Every API request in every build is authenticated the same way: a bearer token checked by the gateway.

### Non-Goals
- Content Security Policy, CORS, auth audit events and the MFA screen. They stay in [Phase 2](../phases/phase-2-security-hardening.md). `sessionStorage` limits how long a stolen token lasts; it does not stop XSS.
- Changing the idle timeout (13 min warning, 15 min sign-out).

### Design Principles
1. **No fallback to weaker storage.** If `sessionStorage` is unavailable, sign-in fails; it never falls back to `localStorage`.
2. **One authentication path.** A build never behaves differently for auth than production does.

---

## 2. Workflow

```
[App start: configure token storage = sessionStorage] ──► UI-AUTH-01
    │
[Sign in, reload, new tab, sign out] ──► UI-AUTH-01
    │
[Every /api/ call: Authorization: Bearer only] ──► UI-AUTH-02
```

---

## 3. Requirements Index

| ID | Title | Area | Priority | Status |
|---|---|---|---|---|
| UI-AUTH-01 | Tokens in `sessionStorage` | Security | MVP | Proposed |
| UI-AUTH-02 | Remove the local-development auth bypass | Security | MVP | Proposed |

---

## 4. Requirements

### UI-AUTH-01: Tokens in `sessionStorage`  `Priority: MVP`

**Problem:** `app.config.ts` configures Amplify without a storage setting, so tokens go to `localStorage`, which every script on the page can read and which survives closing the browser.
**Requirement:** Amplify keeps the Cognito tokens and the sign-in redirect state in `sessionStorage`, set before the first auth call. Nothing in `localStorage` holds a token.
**Acceptance Criteria:**
- [Happy] After sign-in, the tokens are in `sessionStorage` and no `localStorage` key starts with `CognitoIdentityServiceProvider`.
- [Happy] The Hosted UI redirect round trip in one tab still completes: the code exchange succeeds and the user lands on the Dashboard.
- [Happy] A reload in the same tab keeps the session while the refresh token is valid.
- [Alt] A new tab starts with no app session and goes to login. If the user's Cognito Hosted UI session is still active, it returns to the callback without asking for a password.
- [Alt] On first load after this change, old Cognito keys in `localStorage` are deleted, so tokens from before the change don't linger.
- [Fail] If `sessionStorage` is unavailable, sign-in shows "Your browser is blocking session storage. Enable it and try again." and does not retry with `localStorage`.
**Out of Scope:** Protection against XSS (Phase 2, CSP).
**Refs:** UI architecture S9 and 3.2; [Phase 1](../phases/phase-1-cognito-auth-implementation.md) "`sessionStorage` instead of `localStorage`" (the code never did this); OWASP ASVS 3.4.2.

### UI-AUTH-02: Remove the local-development auth bypass  `Priority: MVP`

**Problem:** In non-production builds, calls to `/api/v1/ledger` send `X-Internal-User-Id` (from `devUserMap`/`devUserId`) and the user's settings as headers, because the local Ledger has no gateway. Invariant 2 says no entry bypasses the identity authorizer. The committed dev user map also puts real dev identifiers in source.
**Requirement:** The auth interceptor sends `Authorization: Bearer <access token>` on every `/api/` request in every build. The dev headers, `devUserId`, `devUserMap`, and `AuthService.getCurrentUserId` are removed. The Ledger is reached through the gateway (or a local stand-in for its authorizer) even in development.
**Acceptance Criteria:**
- [Happy] No request carries `X-Internal-User-Id`, `X-User-Timezone` or `X-User-Currency`.
- [Happy] `environment.ts` and the environment interface contain no user IDs or Cognito `sub` mappings.
- [Alt] Two local Cognito users each see only their own data through the authorizer, replacing the `devUserMap` check.
- [Fail] CI fails if the source contains `X-Internal-User-Id`.
**Depends on:** The Ledger behind the gateway (app doc 6.2, planned); UI-STMT-01 (the only other user of `getCurrentUserId`).
**Open Questions:** How do the end-to-end tests sign in without the `__e2eAuthOverrideSub__` hook? How does a developer run the Ledger locally behind an authorizer (SAM local for the identity authorizer)?
**Refs:** UI architecture S7 and 3.2; app doc invariant 2; XS-CTX-03.

---

## 5. Open Questions (consolidated)

| # | Question | Blocks |
|---|---|---|
| 1 | How do end-to-end tests authenticate once the override hook is removed? | UI-AUTH-02 |
| 2 | What is the local setup for running the Ledger behind the identity authorizer? | UI-AUTH-02 |
