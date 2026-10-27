# Bug name: Profile and goals routes read JWT claims that the authorizer never sets

## Problem

Every public User Profile route except the authorizer itself — `GET /profile`, `PUT /profile/settings`,
`DELETE /profile`, and the goals routes — failed with a 500 in a deployed environment. The Settings
page could not save a timezone, and the profile never loaded.

### Root cause

The handlers read the caller from `requestContext.authorizer.jwt.claims.sub`, the shape produced by
API Gateway's built-in JWT authorizer. UP-AUTH-02 B1 rules that authorizer out: the identity authorizer is
a Lambda `REQUEST` authorizer with simple responses, whose context arrives under
`requestContext.authorizer.lambda` (`internal_user_id`, `subscription_tier`, `timezone`, `currency`).
There is no `jwt` key, so every call raised `KeyError`, caught by the handler's broad `except` and
answered as a 500. The unit tests built their events in the JWT shape, so they passed.

### Code with bug

`services/fintracker-user-profile/app/identity/handlers.py` (the same helper was copied into `app/goals/handlers.py`)

```python
def _cognito_sub(event: dict) -> str:
    return event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
```

## Solution

- A new `app/shared/request_context.py` reads `internal_user_id` from `requestContext.authorizer.lambda`.
  A request without it (the route is not behind the authorizer, or the old shape) is a 401, never a 500.
- The profile, settings and goals handlers use that user ID. `IdentityService` gains
  `get_profile_and_settings_for_user(user_id)`, and `save_settings` and `delete_account` take the user ID, so
  none of them looks up the Cognito sub again.
- `DELETE /profile` still has to remove the `IDENTITY#<sub>` mapping. The authorizer context carries no
  Cognito identifier (XS-CTX-02 fixes its four fields), so the handler verifies the bearer token again to get the
  `sub`, and the service refuses to delete unless that `sub` maps to the authorizer's user.
- The tests now build events in the shape API Gateway produces, and one test per route checks that the old
  JWT shape gets a 401.

### Fixed Code

```python
def internal_user_id(event: dict) -> UUID:
    """The internal user ID the identity authorizer attached after verifying the token."""
    try:
        return UUID(str(_authorizer_context(event).get("internal_user_id")))
    except ValueError:
        raise UnauthenticatedError("the authorizer context has no valid internal_user_id") from None
```
