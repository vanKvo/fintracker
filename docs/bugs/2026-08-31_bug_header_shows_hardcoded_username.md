# Bug name: Header and Settings showed hardcoded "John Doe" / "Alex Morgan" instead of the signed-in user's real name

## Problem

The top-nav header always showed "John Doe" regardless of who was actually logged in. The
Settings page's Profile tab had the identical problem with a different name ("Alex Morgan") and
pre-filled email (`alex.morgan@example.com`). Neither reflected the real signed-in user.

### Root cause

No frontend service called the User Profile Lambda's `GET /profile` at all — it was never wired
up. `layout.html` hardcoded the header name as a literal string, and `settings.ts` initialized
its `profileForm` with literal placeholder values instead of loading anything:

```html
<!-- layout.html -->
<span class="username">John Doe</span>
```

```ts
// settings.ts
this.profileForm = this.fb.group({
  firstName: ['Alex', Validators.required],
  lastName: ['Morgan', Validators.required],
  email: ['alex.morgan@example.com', [Validators.required, Validators.email]],
  phone: ['+1 (555) 123-4567']
});
```

A second, deeper issue surfaced while wiring the fix: the user-profile service's local
`template.yaml` had placeholder Cognito values (`COGNITO_USER_POOL_ID: local-mock-pool-id`, etc.)
on the `AuthorizerFunction` added earlier (REQ-UP-02) — these would have made the authorizer
reject every real access token, since it verifies signatures against a specific User Pool's JWKS.
There was also no local dev proxy route for the identity service at all
(`proxy.conf.json` had no `/api/v1/identity` entry), and the existing dev-mode `authInterceptor`
branch sent `X-Internal-User-Id` for every `/api/` request — correct for the Ledger (no
authorizer locally), but wrong for the identity service, which runs its own real Lambda
authorizer in every environment and needs `Authorization: Bearer <token>` instead, dev included.

## Solution

1. Added `ProfileService` (`core/services/profile.service.ts`) calling the real
   `GET /api/v1/identity/profile`.
2. Fixed the `authInterceptor` to branch per-target rather than per-environment: only
   `/api/v1/ledger` gets the dev-only `X-Internal-User-Id` bypass; every other backend (including
   the identity service, dev or prod) gets a real bearer token via `AuthService.getAccessToken()`.
3. Corrected the placeholder Cognito values in
   `services/fintracker-user-profile/template.yaml`'s `AuthorizerFunction` to the real User Pool
   ID / App Client ID from `fintracker-ui/src/environments/environment.ts`, so a real Hosted UI
   login's token actually verifies locally (`sam local start-api`).
4. Added a `/api/v1/identity` → `http://localhost:3000` proxy route (`proxy.conf.json`),
   matching `sam local start-api`'s documented default port.
5. `layout.ts` now fetches the profile in `ngOnInit()` and renders `firstName lastName`, falling
   back to a static `"Account"` label (never a fabricated name) if the call fails — a slow or
   down identity service must never block or break the rest of the page.
6. `settings.ts` now loads the same real profile into `profileForm` and the profile-tab header,
   including the real `subscriptionTier` ("Premium Member" / "Free Member") instead of the
   hardcoded "Pro Member".

**Verification boundary, stated plainly:** the full path (real Hosted UI login → real signed
Cognito JWT → local Lambda authorizer verifying against real Cognito JWKS → DynamoDB profile
read) cannot be exercised by an automated check here — it requires a real login with real
credentials, which this environment doesn't have. What *is* verified: the app builds and all
existing unit/e2e tests pass; a Playwright check confirms the header falls back to "Account"
with zero console errors when the identity service is unreachable (the realistic case for this
sandbox, since no `sam local start-api` process is running); and the interceptor/template changes
were reviewed against the exact contract `get_profile_handler`/`authorizer_handler` already
implement and unit-test in the user-profile service. Full confirmation that a real login shows
the correct name needs to happen in a real browser session with real Cognito credentials.

### Fixed Code

```ts
// auth.interceptor.ts
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  if (!req.url.includes('/api/')) {
    return next(req);
  }
  const authService = inject(AuthService);

  if (!environment.production && req.url.includes('/api/v1/ledger')) {
    return from(authService.getCurrentUserId()).pipe(
      switchMap((userId) => next(req.clone({ setHeaders: { 'X-Internal-User-Id': userId } }))),
    );
  }

  return from(authService.getAccessToken()).pipe(
    switchMap((token) => next(req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }))),
  );
};
```

```ts
// layout.ts
ngOnInit(): void {
  this.idleTimer.start();
  this.profileService.getProfile().pipe(
    catchError(() => of(null))
  ).subscribe(profile => {
    if (profile) {
      this.displayName = `${profile.firstName} ${profile.lastName}`.trim() || 'Account';
    }
  });
}
```

## Related follow-ups (not fixed here)

- `services/fintracker-user-profile/template.yaml` still has no route/handler for editing a
  profile (`saveProfile()` in `settings.ts` still only logs to console) — Settings' Save button
  doesn't persist anything yet.
- `get_profile_handler`'s response has no `phoneNumber` field even though `UserProfile` has one;
  the Settings phone field has no real backend source at all.
