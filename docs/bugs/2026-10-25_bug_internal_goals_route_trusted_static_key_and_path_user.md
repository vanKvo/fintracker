# Bug name: The internal goals route trusted a static API key and a user ID from the path

## Problem
User Profile's internal goals route, called by the AI assistant's goals tool, authenticated callers with one shared static key (`x-internal-api-key`) and read the user from the URL path. Anyone holding the key could read any user's goals, and the user did not come from a verified context. This broke app invariants 2 and 3 and User Profile architecture S3. A bad user ID was also echoed in the 400 body.

### Root cause:
The route was written before User Profile had an IAM-authorized internal API, so it fell back to a shared secret and a path parameter.

### Code with bug:
```python
# app/goals/handlers.py
supplied_key = (event.get("headers") or {}).get(_INTERNAL_API_KEY_HEADER)
expected_key = os.environ.get("INTERNAL_API_KEY")
...
user_id = UUID(event["pathParameters"]["userId"])
...
return problem(400, "Bad Request", f"Invalid request: {exc}")
```

## Solution
1. New `app/shared/internal_auth.py`: the caller allow-list check (moved from the settings handler) and `forwarded_user_id`.
2. The route is now `GET /profile/internal/goals`: IAM authorization plus `INTERNAL_ALLOWED_CALLER_ARNS` (unset rejects every call); the user comes only from `X-Internal-User-Id`. An unknown user is 404; error bodies are generic.
3. The AI assistant calls the new path with its SigV4 signature and the forwarded context; `USER_PROFILE_INTERNAL_API_KEY` is gone.

### Fixed Code
```python
if not is_allowed_caller(event):
    return problem(401, "Unauthorized", "Caller is not allowed to use this route.")
user_id = forwarded_user_id(event)
if user_id is None:
    return problem(400, "Bad Request", "A valid forwarded user ID is required.")
```
