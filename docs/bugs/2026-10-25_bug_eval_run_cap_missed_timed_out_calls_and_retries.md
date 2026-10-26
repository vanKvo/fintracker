# Bug name: Live evaluation runs could pass their cost cap

## Problem
A live evaluation run (AN-FS-22) could cost more than `--cap-usd` in three ways. A call that timed out or lost its connection after it was sent counted as $0, even though Bedrock may still bill it. The cap was checked only between runs, so a run's validation retry still went out after spend had passed the cap. And the up-front estimate assumed one call per fixture, so the "abort before any call" check could be too low by up to 2×. Separately, live runs used the 25 s production deadline, so calls slower than about 23 s were cut off and the latency report (AN-FS-20) under-stated the p99.

### Root cause:
`live_run` priced each run from the reply tokens in `GenerationResult`, which a failed call doesn't add to, and checked `spent > cap_usd` only at the top of each run.

### Code with bug:
```python
for run in range(1, runs_per_fixture + 1):
    if spent > cap_usd:
        status = "aborted_cost_over_cap"
        break
    result = await generate(case.facts, llm, settings, Deadline(settings.request_deadline_s))
    cost = settings.cost_usd(settings.model_id, result.input_tokens, result.output_tokens)
```

## Solution
1. New `_RunBudget` call guard, passed to `generate`. Before every LLM call (the validation retry included) it stops once spend has passed the cap. After the call it adds the actual cost from the reply, the worst-case cost when the error `may_be_billed`, or $0 for an error before processing.
2. The estimate check uses the worst case, two calls per fixture (`estimated_cost_with_retry_usd`). The dry run prints both figures and the total input tokens.
3. `live_run(request_deadline_s=...)` and the CLI option `--deadline-s` (default 62 s, so each call gets a 60 s timeout) let the latency report see the slow tail.

### Fixed Code
```python
budget = _RunBudget(settings, cap_usd)
result = await generate(case.facts, llm, settings, Deadline(deadline_s), guard=budget)
cost = budget.spent - before
```
