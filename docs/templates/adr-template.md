# ADR-{{NNN}}: {{Decision as a short statement}}

<!--
HOW TO USE THIS TEMPLATE
- Copy to fintracker-architecture/architectural_decision_records/ADR-NNN-short-slug.md and add a row to section 7.1 of the app architecture doc.
- Aim for one screen. Every line should help someone choose between the options, or understand what the choice costs.
- Decision comes first so the key information surfaces first. It names the chosen option and says why.
- Alternatives Considered lists only the options that were not chosen, each with a few key pros and cons.
- Consequences lists what changes because of the chosen option: benefits, costs and neutral facts alike, so its costs are visible next to its benefits.
- Write the ADR when the decision is made, not later.
- Delete these comments when done.
-->

## Service Name: {{service name, or "app-wide (services affected)"}}

## Status
{{Proposed / Accepted / Superseded by ADR-NNN}} (architecture doc D{{n}})

## Date
{{YYYY-MM-DD}}

## Context
{{Two to four sentences: what forced the decision now, and what goes wrong if it's left undecided.}}

Key requirements:
- {{A requirement every option must meet}}
- {{…}}

## Decision
{{The chosen option in one or two sentences, and whether it's the same in both profiles. If the profiles differ, name the `profile` setting that carries the difference (app doc 6.1).}}

**Why:** {{One to three sentences: why this option fits the key requirements. Name the main cost only to say why it's acceptable; list the costs themselves in Consequences.}}

1. {{Concrete rule or mechanism}}
2. {{…}}

## Alternatives Considered

<!--
List the real alternatives that were not chosen, including ones dismissed quickly. Knowing what else exists is part of the value.
- Pros and Cons: only the few that separate the options and drove the decision, 1-3 bullets each. Write each con as "claim, because consequence". Skip points where the options tie. A number ($/month, ms, count) beats an adjective.
- Every alternative ends with "Rejected:", one line giving the deciding reason.
- Dev and prod: when something differs by environment, write it inline: "dev: ...; prod: ...".
- An alternative that fails a hard requirement outright needs no pros/cons. Put it under "Also considered" with the one fact that rules it out.
-->

### {{Option B}}
{{One line on what it is.}}
- Pros: {{Key advantage}}
- Cons:
  - {{Key cost, because consequence}}
  - {{...}}
- Rejected: {{the deciding reason}}

**Also considered**
- **{{Option C}}:** Rejected. {{one line: the requirement it fails, or the fact that rules it out}}

<!--
EXAMPLE (from ADR-013, dashboard and reports ownership)

### Analytics serves both tabs
- Pros: Every derived figure comes from one service; no split rule to apply.
- Cons:
  - The whole Dashboard fails when Analytics is down, which breaks a key requirement.
  - Writes show immediately only while Analytics reads the Ledger directly; if it later copies data, the Dashboard runs seconds behind.
- Rejected: It makes the glance-at-now tab depend on the service built for history.
-->

## Trade-offs (optional)

<!--
Add this table only when the options differ on quantitative criteria such as cost, latency or scale, where numbers side by side help. Delete the whole section otherwise. Don't use it to restate the pros and cons.
- Pick the 1-3 quantitative dimensions that drove the decision. Each cell is a number with its unit ($/month, ms, count). Dev and prod: write "dev: ...; prod: ..." in the cell.
- Columns: the chosen option first, then the alternatives.
- Edge: an option name; "{{name}}, slightly"; or "Tie".
-->

| Dimension | {{Option A (chosen)}} | {{Option B}} | Edge |
|---|---|---|---|
| **{{Cost / latency / scale}}** | {{number}} | {{number}} | {{...}} |

## Consequences

<!--
What becomes true because of this decision: benefits, costs, and neutral facts (a new dependency, a moved responsibility). No Pros/Cons labels, because many consequences are neither or both.
- Each bullet opens with a bold one-line claim, then one or two sentences: who or what it affects, with a number where possible.
- State costs plainly as costs ("X can no longer...", "Y now depends on..."), so they can't be hidden among benefits. At least one bullet names a cost; a decision with none is rarely understood yet.
- Don't repeat the Why from Decision, a con from Alternatives, or the Revisit trigger.
- Not a task list: work the decision creates belongs in specs, not here.
-->

- **{{Claim}}.** {{Who or what it affects, and how much}}
- {{...}}

## Revisit when
- {{A concrete trigger, e.g. "more than 10 receiving services", "a compliance requirement mandates network isolation"}}

## Related
- {{Other ADRs, app doc sections, service docs, specs}}
