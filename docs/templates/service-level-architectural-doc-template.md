# {{Service name}} Architecture

| Status | Owner | Last reviewed | Applies to | App architecture |
|---|---|---|---|---|
| {{Existing / Proposed}} | {{name}} | {{YYYY-MM-DD}} | {{release or commit}} | [{{App}} architecture]({{path}}) |

<!--
HOW TO USE THIS TEMPLATE
- Text in {{double braces}} is a placeholder. HTML comments are guidance: delete them when you fill a section.
- This document describes how the service works TODAY, at the level of components and workflow stages.
  It is updated in the same pull request as any code change that alters what it says.
- Out of scope here (keep in code, OpenAPI/AsyncAPI, schema files or change specs): field-level schemas,
  request/response payloads, prompts, config values, function and class names.
- Rules that apply to every service (identity, events, invariants) are NOT repeated here. Link to the app-level doc instead,
  and only describe what this service adds or how it applies them.
- Length budget: readable in 10–15 minutes.
-->

---

## 1. Overview

<!--
Budget: one short paragraph plus three small lists.
"Does not do" matters as much as "does": it stops responsibilities from drifting into the wrong service.
-->

**Purpose:** {{One or two sentences: what this service is for and why it exists as a separate service.}}

**Responsibilities**
- {{…}}

**Does not do** <!-- Name the service that does it instead. -->
- {{e.g., Parse statement contents (Data pipeline does).}}

**Owns**
- {{Data stores and the data in them, at entity level: "statement records", "upload status"}}

---

## 2. Architecture and workflows

<!--
One component diagram of the inside of this service, plus its neighbors at the edge.
SHOW: internal components (API handler, workers, workflow, internal modules that matter), its owned data stores,
the services and external systems it talks to, arrows labeled sync / event.
RELATIONSHIPS: every component connects to at least one other by an arrow. A box with no arrow is a sign something is missing.
NUMBERED STEPS: when components (or the stages inside one component) run in a fixed order, number them 1, 2, 3…
  (3a / 3b for steps that run side by side), so the workflow can be read from the diagram alone.
  Number an arrow with a small badge when the step is a call rather than a component, e.g. an LLM call.
TEXT vs DIAGRAM: the diagram shows what connects and in what order; the text below it explains only details
  that would clutter the diagram (why a rule exists, limits, edge cases).
Cloud product names are fine here if the service is tied to them (e.g., a workflow engine); otherwise keep it logical.
-->

![{{Service name}} architecture](images/{{service}}-architecture.png)

### Workflows

<!--
One subsection per workflow the service runs. Write STAGES, not code: 3–8 numbered steps, each one line.
Each workflow states its trigger, its result, and what happens on failure.
A stage that only another service performs should link to that service's doc instead of being described here.
-->

#### {{Workflow name, e.g., "Import a statement"}}

**Trigger:** {{API call / event / schedule}} · **Result:** {{what exists afterwards}} · **On failure:** {{retry, DLQ, user-visible status}}

1. {{Stage}}
2. {{Stage}}
3. {{Stage}}

#### {{Workflow name}}

**Trigger:** {{…}} · **Result:** {{…}} · **On failure:** {{…}}

1. {{…}}

---

## 3. Concepts of Operation

<!--
The same seven topics as the app-level CONOPS, scoped to this service. Each answers one question for THIS service only.
Skip a topic only if it is truly empty, and say "Follows app-level rules" rather than deleting the heading,
so every service doc has the same shape and readers know where to look.
  Enter → Trust → Flow → Store → Protect → Recover → Observe
-->

### 3.1 Enter: what does this service expose and consume?

<!-- Its contract surface. Link to the OpenAPI / AsyncAPI / schema file rather than copying it. -->

| Interface | Type | Caller / producer | Purpose |
|---|---|---|---|
| {{`POST /resource`}} | {{Public API / internal API}} | {{Client / Service X}} | {{…}} |
| {{`EventName`}} | {{Event consumed / published}} | {{Service Y}} | {{…}} |

Contract files: {{link}}

### 3.2 Trust: who may call it, and how is each request scoped to a user?

<!-- Allowed callers for each internal route, how the user context is read, any extra authorization rules (plan limits, ownership checks). -->

- {{…}}

### 3.3 Flow: how does it depend on other services?

<!--
Outbound calls and why each is sync or async. What it does when a dependency is slow or down.
Workflows themselves are in section 2; this is about the edges.
-->

| Depends on | How | Why | If unavailable |
|---|---|---|---|
| {{Service X}} | {{sync call / event}} | {{…}} | {{retry / degrade / fail}} |

### 3.4 Store: what data does it keep, and for how long?

<!-- Entities at a level a product manager would recognize, the store for each, retention, and what is deleted on account closure. Schemas live in migrations or code. -->

| Data | Store | Retention | On account deletion |
|---|---|---|---|
| {{…}} | {{…}} | {{…}} | {{…}} |

### 3.5 Protect: what does this service guard beyond the app-level rules?

<!-- Service-specific risks and controls only (e.g., file scanning, PII redaction, LLM output validation, write-path restrictions). -->

- {{…}}

### 3.6 Recover: how does it fail, and how does it recover?

<!-- Idempotency keys, retries and DLQ, compensating actions, partial-failure behavior, replay procedure. -->

- {{…}}

### 3.7 Observe: how do we know it is healthy?

<!-- The 3–5 metrics or alarms that matter, any SLO, cost drivers, and where the dashboard is. -->

- {{…}}

---

## 4. Service decisions

<!--
Decisions that matter inside this service but don't affect others (libraries, internal data model choices, workflow engine settings).
Use the same test as the app-level doc: include it if it is expensive to reverse or a reasonable engineer could have chosen differently.
A decision that turns out to affect other services moves up to the app-level doc.
-->

| # | Decision | Choice | Why | Revisit when | Status |
|---|---|---|---|---|---|
| S1 | {{…}} | {{…}} | {{…}} | {{…}} | {{Accepted}} |

---

## 5. Related documents

- **App architecture:** [{{App}} architecture]({{path}})
- **Contracts:** {{OpenAPI / AsyncAPI / event schema links}}
- **Change specs:** {{link to this service's specs, each marked Proposed / Implemented / Superseded}}
- **Runbook:** {{link}}
- **Diagram source:** `images/{{service}}-architecture.svg`
