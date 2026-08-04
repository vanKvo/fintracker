# Bug name: Auth guard bypassed — unauthenticated users land on dashboard instead of login page

## Problem

When opening the app without a valid Cognito session, the user is taken directly to `/dashboard` with no data instead of being redirected to `/auth/login`.

**Root cause:** `fetchAuthSession()` from `aws-amplify/auth` v6 does **not throw** for unauthenticated users — it returns an `AuthSession` object with `tokens: undefined`. The original `isAuthenticated()` implementation only checked whether the call threw an exception:

```typescript
// BUGGY — fetchAuthSession() never throws for an unauthenticated user
async isAuthenticated(): Promise<boolean> {
  try {
    await fetchAuthSession();
    return true;   // always reached, even with no session
  } catch {
    return false;
  }
}
```

Because the call never threw, `isAuthenticated()` always returned `true`. The `authGuard` trusted this result and activated every protected route unconditionally, so every navigation to `/dashboard`, `/transactions`, etc. succeeded regardless of auth state.

The same incorrect assumption affected `checkSession()` in the `AuthService` constructor, which called `isAuthenticated()` and immediately updated `isAuthenticated$` to `true` on app load.

**Amplify v6 contract (documented):**
- `fetchAuthSession()` returns `{ tokens: undefined, ... }` when no user is signed in
- `fetchAuthSession()` throws only on configuration errors or network failures
- The correct check is `session.tokens !== undefined`

**Observable symptoms:**
- App opens to `/dashboard` with empty/missing data
- No redirect to `/auth/login` on unauthenticated access
- `isAuthenticated$` emits `true` immediately on app load before any login

## Solution

Check `session.tokens` instead of relying on `fetchAuthSession()` throwing. `tokens` is `undefined` when no user is signed in and contains `accessToken` + `idToken` when a valid session exists.

### Fix — `src/app/core/services/auth.service.ts`

```typescript
// BEFORE
async isAuthenticated(): Promise<boolean> {
  try {
    await fetchAuthSession();
    return true;
  } catch {
    return false;
  }
}

// AFTER
async isAuthenticated(): Promise<boolean> {
  try {
    const session = await fetchAuthSession();
    return !!session.tokens;
  } catch {
    return false;
  }
}
```

This is already consistent with `getAccessToken()`, which correctly checks `session.tokens?.accessToken?.toString()` and throws if the token is absent.

### Why this fixes all affected paths

| Path | Before fix | After fix |
|---|---|---|
| `authGuard` | Always returns `true` | Returns `false` → redirects to `/auth/login` |
| `checkSession()` on app load | Sets `isAuthenticated$` to `true` | Sets it to `false` until login completes |
| `Hub signedIn` event | Correct (sets to `true`) | Unchanged |
| `Hub signedOut` event | Correct (sets to `false`) | Unchanged |
| `getAccessToken()` | Already correct | Unchanged |

No other files require changes. The guard, interceptor, and Hub listener all rely on `isAuthenticated()` or `isAuthenticated$` which are now correct.
