# Phase 2: Security Hardening

**Status:** 🔲 Not started  
**Service:** fintracker-ui

---

## Why

Phase 1 established the core auth flow. The following gaps from the auth analysis remain open and are grouped here as the next hardening phase:

- **No Content Security Policy (CSP)** — without CSP, a successful XSS can exfiltrate `sessionStorage` tokens, make authenticated API calls on behalf of the user, or load malicious scripts. PCI-DSS 6.3.2 requires script integrity controls.
- **No auth event audit logging** — successful logins, logouts, and idle-timeout signouts are not captured in structured logs. PCI-DSS 10.2 requires audit trails for all auth events. SOC 2 CC7.2 requires security event monitoring.
- **No MFA enrollment UI** — Cognito supports TOTP (time-based one-time password) but there is no enrollment or management flow in the Settings page. NIST SP 800-63B AAL2 requires a second factor for financial applications.
- **No brute-force protection** — Cognito Advanced Security (Adaptive Authentication) is not enabled. PCI-DSS 8.1.6 requires lockout after ≤6 failed attempts.

---

## Scope

### 2.1 Content Security Policy headers

Add `Content-Security-Policy` as a response header in API Gateway (or CloudFront distribution) covering all SPA routes. The Angular build itself does not serve HTTP headers, so CSP must be enforced at the CDN/proxy layer.

Minimum policy for Angular + Cognito:
```
Content-Security-Policy:
  default-src 'self';
  script-src 'self';
  connect-src 'self' https://cognito-idp.<region>.amazonaws.com https://<api-gateway-id>.execute-api.<region>.amazonaws.com;
  style-src 'self' 'unsafe-inline';
  img-src 'self' data:;
  frame-ancestors 'none';
```

Angular Material uses `'unsafe-inline'` for styles by default — this is a known tradeoff.

### 2.2 Auth event audit logging

Add structured log entries for the following events using Lambda Powertools in the user-profile service:
- Successful login (`signedIn` Hub event) — log `user_id`, timestamp, IP (from event context)
- Logout (manual or idle-timeout) — log `user_id`, `logout_reason: manual | idle_timeout`
- Token refresh failure — log `user_id`, timestamp

These can be implemented via Cognito Pre-Authentication and Post-Authentication triggers (Lambda functions that fire before/after each sign-in).

### 2.3 MFA enrollment UI in Settings

Add a new Angular route `/settings/security` with:
- Current MFA status display (enabled / disabled)
- TOTP setup flow: call Amplify `setUpTOTP()`, display QR code, prompt for verification token, call `verifyTOTPSetup()`
- Disable MFA: call Amplify `updateMFAPreference({ totp: 'DISABLED' })`
- Requires Cognito User Pool to have Software Token MFA enabled (infrastructure config)

### 2.4 Brute-force protection (infrastructure)

Enable Cognito Advanced Security in the CDK stack (`advancedSecurityMode: AdvancedSecurityMode.ENFORCED`). This activates:
- Account lockout after configurable failed attempts
- IP-based risk scoring and adaptive authentication challenges
- Compromised credential detection

No Angular code changes required — this is a CDK/infrastructure task.

---

## Status

🔲 Not started — acceptance criteria and file-level task breakdown to be written when this phase begins.
