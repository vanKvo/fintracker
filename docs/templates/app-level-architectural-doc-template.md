# {{App name}} Architecture

| Status | Owner | Last reviewed | Applies to |
|---|---|---|---|
| {{Draft / Current}} | {{name}} | {{YYYY-MM-DD}} | {{release or commit}} |

<!--
HOW TO USE THIS TEMPLATE
- Text in {{double braces}} is a placeholder. HTML comments like this one are guidance: delete them when you fill a section.
- This document covers what changes slowly: services, how they interact, the rules everyone follows, and how the app is deployed.
- Placement test for any detail: if changing it touches only one service, it goes in that service's architecture doc.
  If it touches two or more services, the security model, or the deployment, it goes here.
- Out of scope here: steps inside a service, schemas, API payloads, prompts, config values. Those live in service docs, specs, or code.
- Length budget: aim for something a new developer can read in 20–30 minutes. Each section notes a rough budget.
-->

---

## 1. Overview

<!--
Answer three questions in plain language. Budget: 2–3 short paragraphs.
- What can the app do? (capabilities, as the user would describe them)
- Who is it for, and what problem does it solve for them?
- Why does it matter to them? (the outcome, not the feature)
Then state the current scope, so readers know what is built today versus planned.
-->

**What it does:** {{One or two sentences describing the main capabilities.}}

**Who it's for and why it matters:** {{Target users, the problem they have today, and the outcome the app gives them.}}

**Current scope:** {{What is built and live today. Main screens or features in one list.}}

**Status labels used in this document:** *Existing* (running today), *Proposed* (designed, not built). See [Related documents](#11-related-documents) for the roadmap.

---

## 2. Services

<!--
One row per service. Budget: one table, plus one line per service on why it is separate.
- "Owns" is the most important column: the data or responsibility no other service may take over.
- Keep compute and cloud details out; those belong in section 6.
-->

| Service | Status | Purpose (one line) | Owns | Workload type |
|---|---|---|---|---|
| {{Service A}} | {{Existing}} | {{What it is for}} | {{Data / responsibility it alone owns}} | {{Synchronous, read-heavy / async, retry-heavy / streaming / …}} |
| {{Service B}} | {{Proposed}} | {{…}} | {{…}} | {{…}} |

**Why each service is separate**

<!-- One line each: the reason this is its own service rather than part of another (different consistency needs, different scaling, single owner of a risk, …). -->

- **{{Service A}}:** {{reason}}
- **{{Service B}}:** {{reason}}

---

## 3. High-level architecture

<!--
A logical block diagram: what talks to what, and how. Platform-neutral.
SHOW
- External actors: users, identity provider, third-party APIs, AI model provider. Use generic names ("Identity provider", "LLM provider"), not product names.
- Every service as one box. Optionally, its owned data store attached to it.
- Arrows labeled by interaction style: synchronous request, asynchronous event, file transfer.
DON'T SHOW
- Cloud products, networks, compute types, regions. Those go in section 6.
Keep it to one diagram. Store it as PNG plus an editable SVG next to this file.
-->

![{{App name}} high-level architecture](images/{{app}}-high-level.png)

**How to read the diagram** <!-- 3–6 bullets. Point out the few things a newcomer would otherwise miss. -->

- {{e.g., Every user request enters through one gateway, which establishes identity.}}
- {{e.g., Services never share a database; solid arrows are requests, dashed arrows are events.}}

---

## 4. Concepts of Operation (CONOPS)

<!--
CONOPS explains the rules and mechanisms that every service follows. It explains HOW THE SYSTEM WORKS IN GENERAL, not any one scenario.
Concrete scenarios belong in section 5.

The seven topics follow the life of a request, then the life of the system, so each one builds on the one before:
  Enter → Trust → Flow → Store → Protect → Recover → Observe
  - Enter:   how users and systems get in
  - Trust:   once in, who are they and what may they do
  - Flow:    once trusted, how work moves between services
  - Store:   as work flows, where data lands, who owns it, and when it is deleted
  - Protect: what guards that data beyond identity
  - Recover: what happens when any of the above fails
  - Observe: how we know all of it is working and what it costs

Each topic answers one question in 3–8 bullets or one small table. If a topic is getting long, the extra detail
probably belongs in a service doc. Domain features (for example AI or file handling) don't get their own topic:
their app-wide rules go into the topic they belong to (an AI isolation rule goes under Protect, a file lifecycle under Store).
-->

### 4.1 Enter: how do users and systems get in?

<!-- Actors, client apps, entry points (gateway, streaming endpoint, webhooks, scheduled jobs). Every entry point should be listed. -->

| Actor | Entry point | Notes |
|---|---|---|
| {{End user (web/mobile)}} | {{API gateway}} | {{…}} |
| {{Scheduler / partner system}} | {{…}} | {{…}} |

### 4.2 Trust: who is the caller, and what may they do?

<!--
- How a user is authenticated, and where the internal user ID comes from.
- How authorization is decided (roles, plans/tiers, ownership).
- How a service proves its identity to another service, and how the user context travels with it.
- How tenant isolation is enforced in the data layer, not only in handlers.
-->

- **User identity:** {{…}}
- **Authorization:** {{…}}
- **Service identity:** {{…}}
- **Tenant isolation:** {{…}}

### 4.3 Flow: how does work move between services?

<!--
- When to use a synchronous call versus an asynchronous event, and the default.
- The event catalog: event, producer, consumers. (Event payload schemas live in code or a schema registry.)
- Idempotency and ordering expectations for events.
-->

| | Synchronous | Asynchronous |
|---|---|---|
| Use when | {{caller needs the answer now}} | {{something happened; others may react}} |
| Mechanism | {{…}} | {{…}} |

| Event | Producer | Consumers |
|---|---|---|
| {{EventName}} | {{Service}} | {{Services}} |

### 4.4 Store: where does data live, who owns it, and when does it end?

<!--
- One owner per data store, and any exceptions.
- Which kinds of data store exist (relational, key-value, object, vector) and which service owns each.
- Data lifecycle: created → retained → deleted, including deletion when a user closes their account.
-->

- **Ownership rule:** {{…}}
- **Stores:** {{…}}
- **Lifecycle and deletion:** {{…}}

### 4.5 Protect: what guards the data beyond identity?

<!--
Encryption in transit and at rest, secrets handling, input and file scanning, privacy rules (redaction, purpose limitation),
AI-specific guards (prompt injection, output validation), logging rules (what must never be logged).
-->

- {{…}}

### 4.6 Recover: what happens when something fails?

<!--
- Retry and dead-letter strategy for events and workflows.
- Timeouts and how a slow dependency is isolated.
- Graceful degradation: what the user sees when a non-critical service is down.
- Backup and restore targets (RPO / RTO) for each data store type.
-->

- {{…}}

### 4.7 Observe: how do we know it works and what it costs?

<!--
Logs, metrics, traces, correlation IDs across services, key alarms, service-level objectives, cost guards and budgets.
-->

- {{…}}

---

## 5. Cross-service flows

<!--
WHY THIS IS SEPARATE FROM CONOPS
- CONOPS (section 4) is the rule set. These flows are concrete scenarios that apply the rules.
- They change at different rates: a new feature adds a flow without changing any rule, while a rule change touches many flows.
  Keeping them apart keeps CONOPS short and stable, and makes flows easy to find by scenario.

HOW TO WRITE A FLOW
- One line per hop between services or external actors: "A → B: what is asked or announced."
- Never describe steps inside a service; link to the service doc instead.
- Tag each flow with the CONOPS topics it relies on, so a rule change shows which flows to re-check.
- Include only flows that cross two or more services. Cover the main user journeys and the account-deletion path.
-->

### {{Flow name, e.g., "User uploads a statement"}}

*Relies on: {{Enter, Trust, Flow, Store}}*

1. {{Client → Service A: …}}
2. {{Service A → event bus: publishes `EventName`.}}
3. {{Service B consumes `EventName` → …}}

### {{Flow name}}

*Relies on: {{…}}*

1. {{…}}

---

## 6. Deployment

<!--
This is where the cloud provider appears for the first time. One subsection per environment.
For each environment: one diagram, a concise "how it runs" explanation, and the decisions specific to that environment.
Budget per environment: one diagram plus 5–8 bullets.
-->

### 6.1 Environments and what differs between them

<!--
List every intended difference between environments in one table. Rule of thumb: environments may differ in
capacity, availability, network perimeter and cost guards, but never in application code or the security model.
If a difference isn't in this table, it shouldn't exist.
-->

| Environment | Account / project | Purpose | Who uses it |
|---|---|---|---|
| {{dev}} | {{…}} | {{…}} | {{…}} |
| {{prod}} | {{…}} | {{…}} | {{…}} |

| Setting | dev | prod |
|---|---|---|
| {{Database capacity / availability}} | {{…}} | {{…}} |
| {{Compute for service X}} | {{…}} | {{…}} |
| {{Network perimeter (WAF, private subnets, egress)}} | {{…}} | {{…}} |
| {{Encryption keys}} | {{…}} | {{…}} |
| {{Log retention / cost guards}} | {{…}} | {{…}} |

**How the setting is applied:** {{e.g., one `profile` variable in IaC selects a settings map.}}

### 6.2 Dev deployment

![{{App name}} dev deployment](images/{{app}}-deploy-dev.png)

**How it runs** <!-- How a request travels through the cloud services in this environment, in 3–5 bullets. -->

- {{…}}

**Key decisions for this environment** <!-- Why it is built this way, in 2–4 bullets: cost, cold starts, trade-offs accepted. -->

- {{…}}

### 6.3 Prod deployment

![{{App name}} prod deployment](images/{{app}}-deploy-prod.png)

**How it runs**

- {{…}}

**Key decisions for this environment**

- {{…}}

### 6.4 Build and release

<!-- IaC tool and layout, CI/CD triggers per environment, how database migrations run. 3–5 bullets. -->

- {{…}}

---

## 7. Architectural decisions

<!--
WHAT BELONGS HERE: include a decision when at least two of these are true:
  1. It is expensive to reverse (data migrations, rewriting several services, changing a vendor).
  2. It affects more than one service, or the security, compliance or cost model.
  3. A reasonable engineer could have chosen differently, because a real alternative existed.
  4. It constrains future work, so a new developer would otherwise "fix" it by accident.
WHAT DOESN'T: choices inside one service (they go in its service doc), defaults nobody would question,
and settings that can be changed in minutes.
Append-only: when a decision changes, mark the old row "Superseded by …" rather than deleting it.
-->

<!--
ROW OR FULL ADR? Every decision gets a row. Write a full ADR file (Context, Decision, Alternatives, Consequences) only when:
  - several credible alternatives were weighed and the reasons won't fit in one sentence, or
  - it changes the security, compliance or cost model, or
  - you find yourself explaining it more than once.
Write the ADR when the decision is made, not later. Mark rows that deserve one but don't have it yet as "Candidate".
Write ADRs from docs/templates/adr-template.md: one short trade-off table on the 3–5 dimensions that decided it (Dimension | options | Edge), plus the alternatives considered.
-->

### 7.1 Decisions

| # | Decision | Choice | Alternatives considered | Why | Revisit when | Status | ADR |
|---|---|---|---|---|---|---|---|
| D1 | {{e.g., Service-to-service auth}} | {{…}} | {{…}} | {{…}} | {{trigger that would reopen it}} | {{Accepted / Superseded by Dn}} | {{link / — / Candidate}} |

### 7.2 Open decisions

<!-- Questions not yet decided. When one is decided, move it to 7.1 as a row. -->

| Decision | Options | Notes |
|---|---|---|
| {{…}} | {{…}} | {{…}} |

---

## 8. Invariants

<!--
Rules that hold for every service, in every environment. A spec or design that conflicts with one is wrong.
Write each as a short, testable sentence. Where possible, name the test or check that enforces it.
Budget: 5–12 rules. If you have more, some are probably decisions or service-level rules.
-->

1. **{{Rule name}}.** {{One sentence.}} *Enforced by: {{test, policy, review check}}.*
2. **{{Rule name}}.** {{…}}

---

## 9. Tech stack

<!-- One row per area. "Why" is one clause: the property that made it the right choice. Service-internal libraries go in service docs. -->

| Area | Choice | Why |
|---|---|---|
| {{Backend (service group)}} | {{…}} | {{…}} |
| {{Frontend}} | {{…}} | {{…}} |
| {{Data stores}} | {{…}} | {{…}} |
| {{Messaging / workflows}} | {{…}} | {{…}} |
| {{AI}} | {{…}} | {{…}} |
| {{IaC and CI/CD}} | {{…}} | {{…}} |

---

## 10. Compliance and standards

<!--
List each law, regulation or standard the app follows, with an honest status.
Status values: Applies (required, work not started) · In progress · Implemented · Out of scope (with the reason).
"Implemented" should point to evidence: a controls document, test suite, audit report or policy.
Typical candidates for a consumer finance app (keep only those that apply):
  - Laws and regulations: GLBA / FTC Safeguards Rule, state privacy laws (e.g., VCDPA, CCPA/CPRA), GDPR if serving EU users
  - Industry standards: PCI DSS (often kept out of scope by never storing card numbers), SOC 2, ISO/IEC 27001
  - Engineering baselines: OWASP ASVS, OWASP Top 10 for LLM Applications, NIST CSF, CIS Benchmarks for the cloud provider
  - Accessibility: WCAG 2.2 AA
Legal applicability should be confirmed with counsel; note that in the Status column until it is.
-->

| Standard / regulation | Why it applies | How the architecture supports it | Status | Evidence |
|---|---|---|---|---|
| {{e.g., GLBA / FTC Safeguards Rule}} | {{…}} | {{e.g., encryption, MFA, access control, deletion}} | {{Applies}} | {{link}} |

---

## 11. Related documents

<!-- Every service in section 2 must appear in the first table. -->

**Service architecture documents**

| Service | Architecture doc | Owner |
|---|---|---|
| {{Service A}} | [{{service-a}}/architecture.md]({{path}}) | {{…}} |
| {{Service B}} | [{{service-b}}/architecture.md]({{path}}) | {{…}} |

**Other documents**

- **Roadmap:** {{link}}
- **Specs (proposed and implemented changes):** {{link to specs folder}}
- **Diagram sources:** `images/` (editable SVG for every PNG in this document)
- **Runbooks / operations:** {{link}}
