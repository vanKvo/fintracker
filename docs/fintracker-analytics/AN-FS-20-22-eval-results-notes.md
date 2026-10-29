# AN-FS-20 / AN-FS-22: evaluation result folders

Implementation notes for the evaluation results bucket. The code is in `services/fintracker-ai-assistant/src/summary/eval/results.py`.

## What is stored

Each run writes one record under `results/`. A passing run also writes to one or both pass indexes.

| Folder | Holds | Read by | Why it exists |
|---|---|---|---|
| `results/<prompt version>/<model>/<tier>/<stamp>__<model>__<outcome>__r<runs>__<hash8>.json` | Every run, pass or fail | People (debugging a failed run, comparing runs) | Keeps the full history, including failures, so a regression can be traced |
| `passes/<prompt version>/<model id>/<tier>/<stamp>.json` | Passing runs only | Tier order check (`last_pass`) | Tier order is about one prompt version and one model. A `smoke` pass for model A does not unlock `core` for model B |
| `passes-by-version/<version key>/<tier>/<stamp>.json` | Passing runs only | Eval-required PR check (`has_pass_for_version`) | The PR check asks whether this exact prompt, model and schemas have passed. The version key covers all of them, so a schema-only change needs a new pass |

The **version key** is a hash of the rendered system prompt, the output schema and the facts schema, together with the model ID (`version_key` in `runner.py`). The **prompt version** is the folder name (for example `fs-v1`). A prompt version folder can stay the same while the version key changes, which is why the two pass indexes use different keys.

## Reading a `results/` name

Example: `results/fs-v2/anthropic.claude-haiku-4-5-20251001-v1_0/full/20261027T194100__anthropic.claude-haiku-4-5-20251001-v1_0__pass__r2__a1b2c3d4.json`

| Part | Meaning |
|---|---|
| `fs-v2` | Prompt version (the folder in `prompt/versions/`) |
| `anthropic.claude-haiku-4-5-20251001-v1_0` | Model ID with `:` and `/` replaced by `_`. The report holds the real ID |
| `full` | Tier |
| `20261027T194100` | UTC start of the save, fixed width, so names sort by time |
| `anthropic.claude-haiku-4-5-20251001-v1_0` | Model ID again, in the file name, so a file can be told apart without its folder. Same `_` form as the folder |
| `pass` | `pass`, `fail`, or `capped` (stopped by the cost cap, before or during the run) |
| `r2` | Runs per fixture |
| `a1b2c3d4` | First 8 characters of the version key. The same prompt label with a different hash means the prompt text or a schema changed under it |

Runs saved before 2026-10-27 stay at `results/<version key>/<tier>/<stamp>.json` (the CLI role can't delete or rename).
The two pass indexes keep their keys: the PR check reads `passes-by-version/` by hash.

## What the report records beyond the version key

The version key hashes the prompt text, model ID and both schemas. These also decide a result, so every live report keeps them:

| Field | Why |
|---|---|
| `temperature`, `max_tokens` | Change the output (a lower `max_tokens` truncates replies) but are not in the key |
| `git_sha` | Pins the code, fixtures, validation and banned-term list, none of which are in the key; lets you check out the exact code. From `GITHUB_SHA`, null outside Actions |
| `github_run_id` | Links the report to its workflow run: logs, the approval in the `llm-eval` environment, the uploaded `report.json` and the inputs used. From `GITHUB_RUN_ID`, null outside Actions |
| `cap_usd`, `deadline_s`, `runs_per_fixture`, `fixtures` | What the run was asked to do |
| `prices_per_1k_usd` | The prices behind `cost_usd`, so a later price change doesn't rewrite history |
| `started_at`, `finished_at` | UTC start and end of the run |

## Reading a call in the report

| Field | Meaning |
|---|---|
| `client_latency_ms` | Our round trip around the Converse call: network, SDK and model time. Called `latency_ms` before 2026-10-27 |
| `bedrock_latency_ms` | Bedrock's own processing time (`metrics.latencyMs`). `client_latency_ms` minus this is network and SDK overhead. Null when no reply came back |
| `call_outcome` | `success`, or the error class: `LlmError` (not retried, e.g. access or a bad request), `LlmThrottled`, `LlmUnavailable`, `LlmTimeout`, `LlmBadResponse` |
| `error_code`, `error_type`, `error_message` | Why a call failed: the AWS error code (e.g. `AccessDeniedException`, `ValidationException`), the SDK exception class (`ClientError`, `NoCredentialsError`), and AWS's text with account IDs masked. Null on success. Reports before 2026-10-27 have none of them |

The same reason is printed under the failed call when the CLI runs. These fields live in the report only: logs and audit records never carry them.

## Rules

- Records are never overwritten. The latest pass is the largest key under its prefix; the stamp is fixed-width UTC, so keys sort by time.
- Results are kept with no expiry (see the 2026-10-26 decision in the AN-FS spec's decision log).

## Proposed spec changes (not applied: spec files are owner-maintained)

1. **AN-FS spec, Appendix C, "Evaluation results" row:** add the purpose of each folder in one sentence, as in the table above. The row already lists the paths and says what the pass indexes are used for, but not why there are two pass indexes with different keys. Proposed addition: "The tier order check is per prompt version and model; the required PR check is per version key, so a change to any schema also needs a new passing run."
2. **AI-EVAL spec, the required-check requirement (currently "Results are stored in the existing evaluation bucket for 90 days"):** this conflicts with the AN-FS Appendix C row and the 2026-10-26 decision, which keep results with no expiry. Proposed text: "Results are stored in the existing evaluation bucket with no expiry (AN-FS Appendix C)."
