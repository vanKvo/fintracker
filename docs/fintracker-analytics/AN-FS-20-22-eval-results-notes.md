# AN-FS-20 / AN-FS-22: evaluation result folders

Implementation notes for the evaluation results bucket. The code is in `services/fintracker-ai-assistant/src/summary/eval/results.py`.

## What is stored

Each run writes one record under `results/`. A passing run also writes to one or both pass indexes.

| Folder | Holds | Read by | Why it exists |
|---|---|---|---|
| `results/<version key>/<tier>/<stamp>.json` | Every run, pass or fail | People (debugging a failed run, comparing runs) | Keeps the full history, including failures, so a regression can be traced |
| `passes/<prompt version>/<model id>/<tier>/<stamp>.json` | Passing runs only | Tier order check (`last_pass`) | Tier order is about one prompt version and one model. A `smoke` pass for model A does not unlock `core` for model B |
| `passes-by-version/<version key>/<tier>/<stamp>.json` | Passing runs only | Eval-required PR check (`has_pass_for_version`) | The PR check asks whether this exact prompt, model and schemas have passed. The version key covers all of them, so a schema-only change needs a new pass |

The **version key** is a hash of the rendered system prompt, the output schema and the facts schema, together with the model ID (`version_key` in `runner.py`). The **prompt version** is the folder name (for example `fs-v1`). A prompt version folder can stay the same while the version key changes, which is why the two pass indexes use different keys.

## Rules

- Records are never overwritten. The latest pass is the largest key under its prefix; the stamp is fixed-width UTC, so keys sort by time.
- Results are kept with no expiry (see the 2026-10-26 decision in the AN-FS spec's decision log).

## Proposed spec changes (not applied: spec files are owner-maintained)

1. **AN-FS spec, Appendix C, "Evaluation results" row:** add the purpose of each folder in one sentence, as in the table above. The row already lists the paths and says what the pass indexes are used for, but not why there are two pass indexes with different keys. Proposed addition: "The tier order check is per prompt version and model; the required PR check is per version key, so a change to any schema also needs a new passing run."
2. **AI-EVAL spec, the required-check requirement (currently "Results are stored in the existing evaluation bucket for 90 days"):** this conflicts with the AN-FS Appendix C row and the 2026-10-26 decision, which keep results with no expiry. Proposed text: "Results are stored in the existing evaluation bucket with no expiry (AN-FS Appendix C)."
