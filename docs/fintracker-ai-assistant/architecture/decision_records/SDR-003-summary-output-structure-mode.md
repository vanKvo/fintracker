# SDR-003: Send the Summary Output Schema in the Prompt, Not as Enforced Structure

## Service Name: fintracker-ai-assistant

## Status
Accepted (AI assistant architecture doc S10). Revisit on the triggers below.

## Date
2026-10-28

## Context
The Financial Summary model (pinned Nova Lite, AN-FS-10) must return `SummaryReply` (AN-FS Appendix B).
There are three ways to give it the schema (the *structure mode*):
- as text in the system prompt;
- as a forced tool, so Nova constrains decoding to the tool's input schema;
- as Bedrock native structured output, which Nova doesn't offer, so it would mean switching models.

The first live `full-once` run (fs-v2, [eval log](../../eval/financial-summary-eval-log.md)) had schema
failures in 11 of 22 fixtures (14 of 34 calls). The raw replies showed two kinds:
- **Fields the model didn't need to write:** invented insight ids and a null `related_insight_id`. Fixed by
  code-assigned ids and nested recommendations (EVL-007, EVL-008).
- **Content-rule breaks:** `type: savings_rate`, an insight about a metric that belongs in highlights.

Key requirements:
- Every reply still passes grounding and the advice guardrails (AN-FS-11, AN-FS-12), whatever the mode.
- A rule break stays visible to validation and the evaluation report, so the prompt can be fixed.
- Fits the 25 s deadline and the cheapest-passing-model rule (AN-FS-10).

## Options

- **Prompt schema + validation + one shared retry** *(chosen)*: the schema block is generated from
  `SummaryReply`. Code repairs syntax, assigns ids and tokenizes numbers; a bad item asks for the retry,
  then only that item is dropped (EVL-009).
- **Forced tool on Nova**: send `SummaryReply` as a tool `inputSchema` with `toolChoice` set to that tool.
  Nova constrains decoding whenever a tool config is passed.

## Trade-offs

| Dimension | Prompt + retry | Forced tool (Nova) | Edge |
|---|---|---|---|
| **Content-rule breaks** | Reach validation as they are (`savings_rate` → dropped, counted) | Decoding forces a valid enum, so `savings_rate` becomes e.g. `income_change` and the break is hidden | Prompt |
| **Shape errors** (keys, types, enum spelling) | Possible; cost a retry or an item | Mostly prevented (AWS reports tool errors down over 95%) | Tool |
| **Cost per summary** | Today's; a retry adds about one call | About the same, plus Nova's `<thinking>` output tokens; the tool schema isn't cacheable | Prompt, slightly |
| **Code change** | None | Tool config, read `toolUse.input`, retry as `toolResult`, structure mode in `version_key` | Prompt |

**Also considered**
- **Native structured output (`outputConfig.textFormat`):** guarantees enums and `pattern`, but Nova doesn't
  support it, so it means Claude Haiku 4.5 at about 15–20× the cost. The first call for a new schema can
  compile for up to about 90 s, past the 25 s deadline, so it would need a warm-up outside the request path.

## Decision
**Prompt schema, validation and one shared retry.** No enforced structure for now.

1. The schema in the prompt is generated from `SummaryReply`, so the prompt and the validator can't drift.
2. Code handles what the model shouldn't have to get right: syntax repair (EVL-001), insight ids (EVL-007),
   literal figures that match a cited fact (EVL-010).
3. A schema problem asks for the shared retry; after it, only the bad item is dropped. Fallback only when
   no usable output is left (EVL-009, EVL-011).

## Rule of thumb: choosing a structure mode
Decide from the evaluation report, by the kind of error, not the count alone:

| Errors the run shows | Do this |
|---|---|
| The model writes values code could produce (ids, links, formats) | Take the field away from the model; produce it in code |
| Syntax slips with one obvious meaning (`{{ }}` around a path, `"null"`) | Repair in code before validation |
| Content-rule breaks (wrong type for the content, metric in an insight) | Fix the prompt; keep them visible. Enforced structure would hide them |
| Shape errors (unknown keys, wrong types, misspelled enums) still above about **5% of calls** across two `full` runs after the steps above | Try a forced tool on the same model |
| Shape errors still above that with the tool, or a consumer can't afford any retry | Native structured output, accepting the model switch, its cost and a warm-up call |

Whatever the mode:
- Validation stays: decoding guarantees shape, never grounding.
- Before a second mode ships, add the mode to `version_key` (or tie each mode to its own prompt version).
  Otherwise a pass in one mode unlocks the other in the required PR check.

## Consequences
- Schema slips can still cost a retry or an item; `schema_drops` and `validation_reason: schema_invalid`
  in the evaluation report show how often.
- No tool or model change; the version key stays prompt, model and schemas.

## Revisit when
- `schema_invalid` stays above about 5% of calls in two `full` runs on fs-v3 or later.
- AN-FS-10's model ladder reaches Claude Haiku 4.5, where native structured output is available.
- Nova adds native structured output.
- The reply schema grows enough that the prompt's schema block becomes a large part of the input.

## Related
- [AN-FS spec](../../../fintracker-analytics/specs/AN-FS-financial-summary-spec.md): AN-FS-10, AN-FS-11, AN-FS-20, Appendix B.
- [Financial Summary evaluation log](../../eval/financial-summary-eval-log.md): EVL-005, EVL-007, EVL-009, EVL-010, EVL-011.
- [SDR-001](SDR-001-bedrock-call-timeouts.md): call timeouts and retries for provider errors.
