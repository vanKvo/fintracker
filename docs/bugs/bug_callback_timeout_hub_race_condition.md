# Bug name: OAuth callback times out — Amplify Hub event missed due to race condition

## Problem

After clicking **"Create Account"** (or **"Sign in with FinTracker"**), the Cognito Hosted UI opens correctly and the user interacts with it. Cognito then redirects the browser back to `/auth/callback`. The callback page shows a spinner and, after 10 seconds, redirects to `/auth/login?error=auth_timeout`.

**Observed authorize URL:**
```
https://us-east-1xwkqa7fdt.auth.us-east-1.amazoncognito.com/oauth2/authorize
```

The redirect back to `/auth/callback` proves that Cognito accepted the request and returned an authorization code. The failure happens _after_ the redirect, inside the Angular callback component.

---

### Root cause: Amplify v6 OAuth code exchange starts before Angular components mount

In Amplify v6, the OAuth authorization code exchange is triggered as soon as `Amplify.configure()` runs. This happens at module load time in `app.config.ts` — **before Angular bootstraps any component**.

The sequence on page load at `/auth/callback?code=XXX&state=YYY`:

```
1. Browser loads /auth/callback?code=XXX&state=YYY
2. app.config.ts executes → Amplify.configure() runs
   └── Amplify detects ?code=...&state=... in the URL
   └── Starts async OAuth code exchange immediately
3. Angular bootstraps the application
4. Router matches /auth/callback → creates CallbackComponent
5. CallbackComponent.ngOnInit() runs → registers Hub.listen()
   └── *** Hub listener registered HERE ***
   └── But the 'signedIn' event from step 2 already fired BEFORE step 5
6. Hub listener never fires → 10-second timeout triggers
7. User is redirected to /auth/login?error=auth_timeout
```

The `signedIn` event is emitted once — if no listener is registered when it fires, it is gone. The callback component registered its listener too late.

### Secondary issue: oauthDomain format

The authorize URL shows `us-east-1xwkqa7fdt` as the domain prefix — this appears to be a User Pool ID-derived value rather than a custom human-readable prefix (e.g. `fintracker-dev`). This is not a code bug, but it indicates the `oauthDomain` value in `environment.ts` may have been set to the User Pool ID or a non-standard value. The correct value is the **Cognito Hosted UI domain prefix** created under:

> AWS Console → Cognito → User Pool → Branding → Domain

If the Cognito domain prefix was never explicitly configured, the redirect URI registered in the App Client will not match what Amplify sends, causing a silent token exchange failure even if the race condition is fixed.

---

### Buggy code — `CallbackComponent.ngOnInit()`

```typescript
// BEFORE — Hub listener registered after Amplify has already exchanged the code
ngOnInit(): void {
  this.hubUnsubscribe = Hub.listen('auth', ({ payload }) => {
    if (payload.event === 'signedIn') {
      this.clearTimeout();
      this.router.navigate(['/dashboard']);
    }
    if (payload.event === 'signInWithRedirect_failure') {
      this.clearTimeout();
      this.router.navigate(['/auth/login'], { queryParams: { error: 'auth_failed' } });
    }
  });

  // If the 'signedIn' event fired before the listener above was registered,
  // it is lost and this timeout triggers instead.
  this.timeoutId = setTimeout(() => {
    this.router.navigate(['/auth/login'], { queryParams: { error: 'auth_timeout' } });
  }, 10_000);
}
```

## Solution

Add a `checkExistingSession()` call immediately after registering the Hub listener. It calls `fetchAuthSession()` — if Amplify already completed the code exchange, valid tokens will be present and we navigate directly. The Hub listener remains as a fallback for the case where the exchange hasn't finished yet.

A `navigated` guard prevents both paths (session check and Hub event) from triggering navigation twice.

### Fixed code — `src/app/features/auth/callback/callback.ts`

```typescript
ngOnInit(): void {
  // Register Hub listener FIRST to avoid any gap.
  this.hubUnsubscribe = Hub.listen('auth', ({ payload }) => {
    if (payload.event === 'signedIn') {
      this.complete('/dashboard');
    }
    if (payload.event === 'signInWithRedirect_failure') {
      this.complete('/auth/login', { error: 'auth_failed' });
    }
  });

  // Check whether Amplify already exchanged the code before this component
  // mounted. If valid tokens exist, navigate immediately.
  this.checkExistingSession();

  // Safety fallback: if neither path resolves within 10 s, redirect to login.
  this.timeoutId = setTimeout(
    () => this.complete('/auth/login', { error: 'auth_timeout' }),
    10_000,
  );
}

private async checkExistingSession(): Promise<void> {
  try {
    const session = await fetchAuthSession();
    if (session.tokens) {
      this.complete('/dashboard');
    }
  } catch {
    // No session yet — Hub listener will handle it.
  }
}

private complete(path: string, queryParams?: Record<string, string>): void {
  if (this.navigated) return;   // guard against double navigation
  this.navigated = true;
  this.clearTimers();
  this.hubUnsubscribe?.();
  this.router.navigate([path], queryParams ? { queryParams } : {});
}
```

### How it covers both timing scenarios

| Scenario | Handler |
|---|---|
| Amplify finishes code exchange **before** `ngOnInit` | `checkExistingSession()` finds tokens → navigate |
| Amplify finishes code exchange **after** `ngOnInit` | Hub listener fires `signedIn` → navigate |
| Amplify code exchange fails | Hub fires `signInWithRedirect_failure` → navigate to `/auth/login?error=auth_failed` |
| Neither resolves within 10 s | Timeout → `/auth/login?error=auth_timeout` |

### Configuration fix (if oauthDomain is incorrect)

Verify the `oauthDomain` value in `fintracker-ui/src/environments/environment.ts` is the full Cognito Hosted UI domain, not the User Pool ID:

```typescript
// WRONG — User Pool ID, not a hosted UI domain
oauthDomain: 'us-east-1_XwKqA7fdt',

// CORRECT — full Cognito hosted UI domain
oauthDomain: 'fintracker-dev.auth.us-east-1.amazoncognito.com',
```

The correct value is shown in:
> AWS Console → Cognito → User Pool → **Branding → Domain**
