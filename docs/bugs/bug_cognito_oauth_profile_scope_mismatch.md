# Bug name: Cognito OAuth scope mismatch — "Create Account" / "Sign in" loop back to login instead of showing Hosted UI

## Problem

Clicking either **"Create Account"** or **"Sign in with FinTracker"** briefly shows a loading spinner (rendered by `/auth/callback`) and then redirects back to `/auth/login`. The user never sees the Cognito Hosted UI login/signup form.

Both buttons fail identically because `Login.signIn()` and `Register.createAccount()` both call `AuthService.signIn()` → `signInWithRedirect()`.

### Root cause:

`Amplify.configure()` in `app.config.ts` requests the OAuth scope `profile` in addition to `email` and `openid`:

```typescript
scopes: ['email', 'openid', 'profile'],
```

But the Cognito App Client only allowed:

```json
"AllowedOAuthScopes": ["email", "openid", "phone"]
```

(confirmed via `aws cognito-idp describe-user-pool-client`)

`profile` was not in the allowed list. When `signInWithRedirect()` navigates the browser to Cognito's `/oauth2/authorize` endpoint with `scope=email+openid+profile`, Cognito validates the requested scopes against the App Client's `AllowedOAuthScopes`. Per RFC 6749 §4.1.2.1, when a scope is disallowed, the authorization server does not render its login UI at all — it immediately redirects back to the registered `redirect_uri` (`http://localhost:4200/auth/callback`) with `?error=invalid_scope&error_description=...`.

Resulting sequence:
1. The user never sees Cognito's Hosted UI — the round trip to Cognito's domain and back happens almost instantly.
2. `/auth/callback` mounts and renders its spinner.
3. Amplify's OAuth listener parses the `error` query param on the callback URL and emits a `signInWithRedirect_failure` Hub event.
4. `callback.ts`'s Hub listener handles that event by navigating to `/auth/login` — producing the observed "keeps loading, then bounces to login" symptom.

No AWS infrastructure-as-code manages this Cognito App Client in this repo, so the drift between the app's requested scopes and the App Client's allowed scopes went unnoticed.

### Code with bug:

`fintracker-ui/src/app/app.config.ts`
```typescript
Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: environment.cognito.userPoolId,
      userPoolClientId: environment.cognito.userPoolClientId,
      loginWith: {
        oauth: {
          domain: environment.cognito.oauthDomain,
          scopes: ['email', 'openid', 'profile'],  // 'profile' not allowed on the Cognito App Client
          redirectSignIn: [environment.cognito.redirectSignIn],
          redirectSignOut: [environment.cognito.redirectSignOut],
          responseType: 'code',
        },
      },
    },
  },
});
```

Cognito App Client config (AWS-side, not represented in this repo):
```json
{
  "AllowedOAuthScopes": ["email", "openid", "phone"]
}
```

## Solution

Add `profile` to the Cognito App Client's `AllowedOAuthScopes` so it matches what the Angular app actually requests. No application code change was required — the mismatch was entirely on the AWS side.

1. Confirm the mismatch:
   ```
   aws cognito-idp describe-user-pool-client \
     --user-pool-id us-east-1_XwKqA7fDT \
     --client-id 6vua2jh8u2rp5bhk4rcpvieqvo \
     --region us-east-1
   ```

2. Update the App Client, resending every existing setting alongside the fix — `update-user-pool-client` replaces list-type fields wholesale, so omitted fields are not preserved automatically:
   ```
   aws cognito-idp update-user-pool-client \
     --user-pool-id us-east-1_XwKqA7fDT \
     --client-id 6vua2jh8u2rp5bhk4rcpvieqvo \
     --client-name fintracker-dev \
     --refresh-token-validity 5 \
     --access-token-validity 60 \
     --id-token-validity 60 \
     --token-validity-units AccessToken=minutes,IdToken=minutes,RefreshToken=days \
     --explicit-auth-flows ALLOW_REFRESH_TOKEN_AUTH \
     --supported-identity-providers COGNITO \
     --callback-urls "http://localhost:4200/auth/callback" \
     --allowed-o-auth-flows code \
     --allowed-o-auth-scopes email openid phone profile \
     --allowed-o-auth-flows-user-pool-client \
     --prevent-user-existence-errors ENABLED \
     --enable-token-revocation \
     --auth-session-validity 3 \
     --region us-east-1
   ```

3. Verify: `describe-user-pool-client` now returns `"AllowedOAuthScopes": ["phone", "openid", "profile", "email"]`, and clicking either auth button in the app now lands on the actual Cognito Hosted UI instead of bouncing back to `/auth/login`.

### Fixed Code

No application code changes. Cognito App Client `AllowedOAuthScopes` (AWS-side):
```json
{
  "AllowedOAuthScopes": ["phone", "openid", "profile", "email"]
}
```

**Related fix applied in the same session:** the same App Client had no `LogoutURLs` registered, even though `environment.ts` sets `redirectSignOut: 'http://localhost:4200/auth/login'`. This would have caused an analogous `redirect_mismatch` failure the first time `AuthService.signOut()` performed its Hosted-UI logout redirect. Fixed by adding `http://localhost:4200/auth/login` to `LogoutURLs` in the same `update-user-pool-client` pass.
