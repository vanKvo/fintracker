# Bug name: The Data Pipeline API identifies users by Cognito sub and lets anyone resume any upload

## Problem
The Data Pipeline's two user-facing routes, `GET /jobs/{jobId}` (upload status) and `POST /jobs/{jobId}/csv-col-mapping-confirmation` (resume a paused CSV upload), had two problems once deployed to AWS.

1. **Status polling always answered 404.** The HTTP API's Cognito JWT authorizer copied the token's `sub` claim into the `X-Internal-User-Id` header. The status handler compared that header with the job's `user_id`. But jobs store the internal user id (verified by the Ledger owner lookup), and the Cognito `sub` is a different value. No user ever matched their own job.
2. **Any signed-in user could resume or alter another user's upload.** The confirmation handler never checked who owned the job. With a job id (it is the statement id), any authenticated user could confirm a column mapping for someone else's paused upload. That would resume it and write a mapping correction for that bank.

The handlers also put raw exception text in error responses, for example `Malformed request: 'confirmed_mapping'`.

### Root cause:
- The API was wired to Cognito directly instead of the User Profile identity authorizer. That authorizer is the only component that maps a Cognito `sub` to the internal user id (architecture doc D3, invariant 2).
- The confirmation handler took the job id from the path and resumed the execution without comparing the job's owner with the caller.

### Code with bug:
```hcl
# modules/http_api/main.tf
resource "aws_apigatewayv2_authorizer" "cognito" {
  authorizer_type  = "JWT"
  ...
}

resource "aws_apigatewayv2_integration" "status" {
  ...
  request_parameters = {
    "overwrite:header.X-Internal-User-Id" = "$context.authorizer.jwt.claims.sub"
  }
}
```
```python
# status_handler.py
requesting_user_id = (event.get("headers") or {}).get("X-Internal-User-Id") or ...
job = get_job(job_id)
if not job or job.get("user_id") != requesting_user_id:   # Cognito sub vs internal id: never equal
    return _response(404, ...)

# csv_col_mapping_confirmation_handler.py: no owner check at all
job_id = event["pathParameters"]["jobId"]
...
confirm_column_mapping(job_id, bank_id, confirmed_mapping)
...
except (KeyError, json.JSONDecodeError) as e:
    return _problem_response(400, "INVALID_REQUEST", f"Malformed request: {e}")
```

## Solution
1. The HTTP API uses the User Profile identity authorizer: a Lambda REQUEST authorizer with simple responses, passed in as `identity_authorizer_function_arn`, with an invoke permission scoped to this API's authorizer. The `sub` header mapping is removed.
2. A new helper, `src/shared/identity.py::authorized_user_id`, reads the internal user id from `requestContext.authorizer.lambda.internal_user_id`, the only identity source the architecture allows for Python services. A client-sent `X-Internal-User-Id` header is ignored.
3. Both handlers answer 401 without an authorizer identity. The status route answers 404 for another user's job.
4. The confirmation handler loads the job and answers 404, without resuming anything, unless the job belongs to the caller.
5. Error details are fixed, user-safe texts. No exception text reaches the client.

Regression tests: `tests/test_http_api_identity.py` covers:
- the owner reading their job's status and confirming its mapping;
- another user's job answering 404 on both routes, and not being resumed;
- a forged header being ignored;
- no identity answering 401;
- a malformed body answering 400 without exception text;
- the Terraform authorizer type.

### Fixed Code
```hcl
resource "aws_apigatewayv2_authorizer" "identity" {
  api_id                            = aws_apigatewayv2_api.this.id
  authorizer_type                   = "REQUEST"
  authorizer_uri                    = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${var.identity_authorizer_function_arn}/invocations"
  authorizer_payload_format_version = "2.0"
  enable_simple_responses           = true
  identity_sources                  = ["$request.header.Authorization"]
  authorizer_result_ttl_in_seconds  = 300
  name                              = "UserProfileIdentityAuthorizer"
}
```
```python
# src/shared/identity.py
def authorized_user_id(event: dict[str, Any]) -> Optional[str]:
    authorizer = (event.get("requestContext") or {}).get("authorizer") or {}
    user_id = (authorizer.get("lambda") or {}).get("internal_user_id")
    return user_id or None

# csv_col_mapping_confirmation_handler.py
user_id = authorized_user_id(event)
if not user_id:
    return _problem_response(401, "UNAUTHORIZED", "Sign in to confirm the column mapping.")
...
job = get_job(job_id)
if not job or job.get("user_id") != user_id:
    return _problem_response(404, "JOB_NOT_FOUND", "No such upload job.")
confirm_column_mapping(job_id, bank_id, confirmed_mapping)
```
