# ADR-{{NNN}}: {{Decision as a short statement}}

<!--
HOW TO USE THIS TEMPLATE
- Copy to fintracker-architecture/architectural_decision_records/ADR-NNN-short-slug.md and add a row to section 7.1 of the app architecture doc.
- Aim for one screen. Every line should help someone choose between the options, or understand what the choice costs.
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

## Options

<!--
List the real alternatives, including ones that were dismissed quickly. Knowing what else exists is part of the value.
Give each a short name; the table uses it.
-->

- **{{Option A}}** *(chosen)*: {{one line on what it is}}
- **{{Option B}}**: {{one line}}
- **{{Option C}}**: {{one line}}

## Trade-offs

<!--
CHOOSING DIMENSIONS
- Pick the 3–5 dimensions that actually separate the options and drove the decision. They are specific to this ADR; there is no fixed list.
  Good dimensions name the real tension, e.g. "Aurora can auto-pause", "Lambdas stay out of the VPC", "Blast radius of a misconfiguration".
  Weak ones are generic labels where every option scores about the same.
- Leave out dimensions where the options tie, unless a reader would assume they differ. Then one "Tie" row prevents the wrong assumption (e.g. cost).

WRITING CELLS
- A few words each, with a number where possible ($/month, ms, count). No "good"/"bad" without the reason.
- Edge: an option name; "{{name}}, slightly"; or "Tie".
- Dev and prod: one table. When a cell differs by environment, write it inline: "dev: …; prod: …".

ALTERNATIVES THAT FAIL A HARD REQUIREMENT
- They don't need a column. Put them under "Also considered" with the one fact that rules them out.
-->

| Dimension | {{Option A}} | {{Option B}} | Edge |
|---|---|---|---|
| **{{Deciding dimension 1}}** | {{…}} | {{…}} | {{…}} |
| **{{Deciding dimension 2}}** | {{…}} | {{…}} | {{…}} |
| **{{Deciding dimension 3}}** | {{…}} | {{…}} | {{…}} |

**Also considered**
- **{{Option C}}:** {{one line: the requirement it fails, or the fact that rules it out}}

<!--
EXAMPLE (from ADR-011, internal API layout)

| Dimension | Shared API | API per service | Edge |
|---|---|---|---|
| **Least privilege** | IAM scoped by path; one `/*` grants every service | IAM scoped by API; a wildcard stays inside one service | Per service |
| **Blast radius** | One stage misconfiguration hits every internal call | Contained to one service | Per service |
| **Ownership** | Every service's routes depend on a shared stack | Each service deploys its own API | Per service |
| **Cost and latency** | $0 fixed; one TLS connection reused across targets | $0 fixed; one extra handshake per target on a cold start | Tie |

**Also considered**
- **Private REST API:** private endpoints exist only for REST APIs, and every calling Lambda would have to join the VPC (see ADR-004).
-->

## Decision
{{The chosen option in one or two sentences, and whether it's the same in both profiles. If the profiles differ, name the `profile` setting that carries the difference (app doc 6.1).}}

1. {{Concrete rule or mechanism}}
2. {{…}}

## Consequences
- **{{What becomes easier or required}}:** {{…}}
- **{{The price paid}}:** {{…}}
- **{{Follow-up work, if any}}:** {{…}}

## Revisit when
- {{A concrete trigger, e.g. "more than 10 receiving services", "a compliance requirement mandates network isolation"}}

## Related
- {{Other ADRs, app doc sections, service docs, specs}}
