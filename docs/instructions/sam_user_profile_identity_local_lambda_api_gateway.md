# New Added Files
template.yaml — a SAM template with 3 functions: GetProfileFunction and DeleteAccountFunction (both wired as HttpApi routes on /profile), and PostConfirmationFunction (no API event — it's a Cognito trigger, invoked directly). All point DYNAMODB_ENDPOINT_URL at http://host.docker.internal:8000, reaching your persistent local dynamodb-local from inside SAM's Lambda containers.

Fixed identity/repository.py — DynamoDBUserRepository was silently ignoring DYNAMODB_ENDPOINT_URL and would've always hit real AWS. Now it reads the env var (no-op when unset, so production is unaffected).

events/get_profile_event.json and events/post_confirmation_event.json — hand-built sample payloads matching the real API Gateway HTTP-API-v2 and Cognito trigger shapes.
requirements.txt (generated, gitignore-worthy) via poetry export.

# How to run it

cd services/fintracker-user-profile

## one-time: needed to export poetry deps to requirements.txt for SAM's builder
poetry self add poetry-plugin-export   # if not already installed

## build (--use-container avoids needing python3.12 on your host PATH)
## --without-hashes: Tells Poetry to exclude the SHA-256 security hash digests from the exported file. Without this flag, Poetry generates long lines containing --hash=sha256:... for each package, which can make the file harder to read and sometimes causes compatibility issues with simpler installation tools.
poetry export -f requirements.txt --without-hashes -o requirements.txt
sam build --use-container

Option 1 — sam local start-lambda (direct Lambda Invoke API, tests business logic + response shape without HTTP):

sam local start-lambda --port 3001
## separate terminal:
aws lambda invoke --function-name GetProfileFunction \
  --endpoint-url http://127.0.0.1:3001 \
  --payload file://events/get_profile_event.json \
  --cli-binary-format raw-in-base64-out /tmp/out.json && cat /tmp/out.json

I ran this against your dev user's real seeded DynamoDB data — it returned the actual profile/settings record (e2b86a8a-..., dev@example.com, etc.) end-to-end.

Option 2 — sam local start-api (real HTTP layer, real API Gateway proxy-event construction):

sam local start-api --port 3000
## separate terminal:
curl -i http://127.0.0.1:3000/profile

# Important: these are two independent local servers, not a chain
I initially framed your ask ("run via start-lambda, then expose via start-api") as if start-api sits on top of a running start-lambda process — that's not how it works. Each command independently builds its own local runtime from the same template.yaml; they don't talk to each other. Run either one alone, or both simultaneously in separate terminals for different testing styles — start-lambda for direct Invoke-API testing, start-api for HTTP-contract testing.

# The gap start-api genuinely exposes
I ran curl http://127.0.0.1:3000/profile and it returned a 500 — KeyError: 'authorizer', because _cognito_sub() reads event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"], and there's no authorizer configured on this route yet, so SAM CLI never populates that key on an HTTP-triggered invocation. This isn't a mistake in the template — it's the real gap we discussed earlier: SAM CLI can't emulate the built-in Cognito JWT authorizer locally at all, and no custom authorizer exists in the codebase yet to fill in that context. start-lambda works because you supply the full event yourself (authorizer context included), sidestepping the missing piece; start-api can't, because API Gateway is supposed to be the one constructing that context from a real verified JWT.

This is exactly where the custom Lambda-authorizer path from earlier becomes necessary — if you want curl-style HTTP testing against start-api to actually work (not just direct Invoke-API testing), the next step is writing that authorizer as a real AWS::Serverless::Function with Type: RequestAuthorizer wired into this same template, since that authorizer type is one SAM CLI does support locally. Want me to build that next?

# How SAM CLI works, briefly
template.yaml is a declarative description of your serverless app — functions, their code location, runtime, env vars, and what triggers them (Events:). SAM CLI doesn't execute anything from the template directly; it parses it and derives two separate things from the same data:

A function registry — name → code/handler/runtime/env vars. This is all sam local start-lambda needs: it reads this registry, and for each function, exposes a fake "Lambda Invoke API" endpoint. When you call aws lambda invoke --function-name X, it looks up X in the registry, spins up a Docker container matching that function's runtime, mounts the built code in read-only, and runs your handler with whatever event payload you handed it. It has zero awareness of HTTP routes — you're driving it directly.

A routing table — built only from the Events: blocks of type Api/HttpApi. This is what sam local start-api reads: for each (Path, Method) pair, it knows which function to invoke. It runs a real local HTTP server (Werkzeug, as you saw in the logs), and when a request comes in matching a route, it does the same container-invoke step as start-lambda — build/mount/run the handler — except now it constructs the event payload itself from the incoming HTTP request (method, path, headers, body, query string) instead of you supplying one.

So start-lambda and start-api are two different front doors into the identical function-execution mechanism. That's why one template drives both: the Resources: block (code, handler, runtime, env) is what both doors ultimately invoke, and the Events: block is purely extra metadata that only start-api (and real deployed API Gateway) reads to know which door maps to which URL. PostConfirmationFunction has no Events: block, which is exactly why it's invisible to start-api's routing table but still fully invokable through start-lambda or sam local invoke.

The KeyError you saw earlier is a direct consequence of point 2 — start-api synthesizes the event from the raw HTTP request, and since no authorizer is configured on that route, it has no sub claim to put in requestContext.authorizer. start-lambda never hit that problem because you handed it a complete, pre-authorized event yourself.