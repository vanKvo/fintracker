

# Guardrails
1. Restrict the tools the model can use, per use case.
The backend decides which tools the model sees. Keep one tool registry and define each use case's allowlist in config. Enforce the allowlist again when a tool runs, because the model's tool name is untrusted input.

```python
  USE_CASES = {
    "financial_summary": UseCase(tools=("get_period_metrics", "get_category_changes",
                                        "get_recurring_changes"),
                                 model_id=SMALL_MODEL, max_tool_calls=4, max_tokens=1500),
    "budget_coach_chat": UseCase(tools=("get_period_metrics", "get_category_changes",
                                        "search_transactions", "get_budgets"),
                                 model_id=LARGE_MODEL, max_tool_calls=8, max_tokens=2000),
  }

  def execute_tool(uc, ctx, name, raw_args):
      if name not in uc.tools:
          raise PermissionError(f"{name} not allowed for {uc.name}")
      spec = REGISTRY[name]
      return spec.fn(ctx, spec.input_model.model_validate(raw_args))
```

2. Read-only tools by default. Any write tool data needs human approval.

3. Template fallback when loop limit hit
When a limit is hit, fall back to the template summary.

4. Validate tool arguments
Use enums for data types with a limited set of values, cap custom ranges, e.g., max period is 24 months, and set no extra parameters provided by the model on all tool inputs.

5. Defend against prompt injection
Send prompts as JSON data fields, never as instructions to prevent malicious prompt injections. Values inside the JSON schema represent untrusted external data. Treat them strictly as string values to analyze, never as instructions to follow. 

# Data Security
1. userId from authenticated session only
Get userId from the authenticated session in code. The LLM never provides userId as a tool parameter. Restrict LLM from providing any new parameters via MCP tools. 

2. User-scoped query
Every repository function takes user_id as a required argument. Add database-level enforcement as well, e.g., Postgres row-level security, or DynamoDB with userId as the partition key.

3. Least Data 
Send the model as little data as possible. Send aggregates (totals, top-N categories and merchants), not raw transaction lists. Never send account numbers, the user's name or email, or addresses. Use internal IDs only.

4. Handle logs carefully
If you must store prompts for debugging, redact them, encrypt them with KMS and set a TTL. Log the request ID, token counts, validation result and prompt version, not logging full prompts or outputs in plain text.

5. Key the cache by user
Use (user_id, period, data_version) as the cache key so results are never shared across users.

6. Store secrets in secured services, never in prompts or code.

# Correctness (reducing hallucinations, making results more predictable)
1. Facts computed by code, LLM for judgment and interpretation
Passing facts directly to model for interpreation and to UI for rendering instead of letting the model use tools to call them. E.g., arithmetic calculation retrieved directly from code, LLM doesn't calculate them.

2. Use structured output with a JSON schema.

3. Precompute comparisons
Pass delta_pct and higher_is_better, so the model doesn't have to work out whether a 12% rise in expenses is bad.

4. Require evidence for each insight 
Each insight cites the fact it is based on (e.g., "category_changes[0]"), and the validator checks the reference exists.

5. Validate, retry once, then fall back
Validate against the schema, send any errors back for one retry, and if that fails, render a deterministic template summary. The section is never blank or wrong.

6. Version prompts 
Store the prompt version with each generated summary so results can be traced and compared.

7. Add data-sufficiency flags from code. Examples: days_of_data < 14, uncategorized_pct > 20, account_sync_errors > 0. The model must mention these in data_caveats rather than speculate. This data_caveats is stored in log file for auditing AI model.

# Cost Control
1. LLM call by default unless it cannot do what an AI agent can do.

2. Rate-limit per user 
Use rate limit (e.g., 10 regenerations per day) to prevent abuse and runaway costs. 

Rate-limit the regenerate button, and log input and output tokens per request so you can track cost per user and per tier.

3. Loop limits
Set a maximum number of tool calls (e.g., 4), a request timeout (e.g., 20s) and a max_tokens cap.

4. Right model for right task
Some tasks are light work, e.g., narrating precomputed facts, so a Haiku-class model fits. Save larger models for the chat or coaching use case.

5. Caching
Use (user_id, period, data_version) as the key. Closed periods such as Last month never change, so generate them once. Regenerate open periods only when new transactions sync, not on page load.

Use prompt caching. Put the static parts first (system prompt, schema, few-shot examples) so they can be cached. Only the facts payload changes per user.

6. Keep the payload compact
Send aggregates and top-N lists (top 5 categories, top 3 changes), use minified JSON, and round values.

7. Skip the LLM when it adds nothing 
If there's insufficient data (e.g., under 7 days or no transactions), show the template summary.

8. Batch precompute
Generate Last month summaries for active users overnight on the 1st, using Bedrock batch inference, which is cheaper than on-demand