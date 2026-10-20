# Feature Spec Template

> **For AI models:** This file defines the spec format. When asked to write or review a spec, follow the **Authoring Rules**, fill in the **Template** below, and run the **Review Checklist** before returning it. Keep the section order, headings and ID format exactly as shown. Replace every `<placeholder>`. Delete optional sections only when they would be empty.

---

## Naming and IDs (read first)

Every spec has its **own prefix**, taken from the spec's file name. All requirement IDs in that spec use that prefix.
 
**Never copy a prefix from an example or from another spec.** Example prefixes in this template (`TXT`, `<PREFIX>`) are placeholders only.

### How to determine the prefix

1. **File name already has a prefix** (`<PREFIX>-<feature-name>.md`, e.g., `TXT-transaction-types.md`): use that prefix exactly → `TXT-01`, `TXT-02`, …
2. **File name has no prefix** (e.g., `transaction-types-spec.md`): derive a prefix from the feature name, using the rules below. State it at the top of your response, and recommend renaming the file to `<PREFIX>-<feature-name>.md`.
3. **A registry exists** (`specs/README.md`): check that the prefix is not already used by another spec. If it is, choose another, and add the new prefix to the registry.
4. **Revising an existing spec:** keep its current prefix and existing IDs, even if they don't match these rules. Only flag the mismatch.

### Prefix rules

- 2–4 uppercase letters, unique across all specs in the project.
- Two or more words: initials, or a recognizable abbreviation. *Transaction Types* → `TXT`; *Account Linking* → `ACL`.
- One word: a recognizable abbreviation, or the first three consonants. *Budgets* → `BDG`; *Notifications* → `NTF`.
- It should be obvious from the feature name, without needing the registry to decode it.

### ID formats

| Element | Format | Example (for `TXT-transaction-types.md`) |
|---|---|---|
| Spec file | `<PREFIX>-<feature-name>.md` (kebab-case) | `TXT-transaction-types.md` |
| Spec title | `# <PREFIX>: <Feature Name>` | `# TXT: Transaction Types` |
| Requirement ID | `<PREFIX>-<NN>`, 2-digit, starting at 01 | `TXT-03` |
| Requirement heading | `### <PREFIX>-<NN>: <Short title>` | `### TXT-03: Split transactions` |
| Commit | `<type>(<PREFIX>-<NN>): <summary>` | `feat(TXT-03): support split transactions` |
| Branch | `<type>/<PREFIX>-<NN>-<short-name>` | `feat/TXT-03-split-transactions` |

### ID stability

- **Never renumber.** New requirements get the next unused number, even if they are inserted earlier in the workflow order. The index table stays in workflow order, so numbers may appear out of sequence there.
- **Removed requirements** stay as a placeholder: `### ~~TXT-04~~: Removed (<reason>)`. Their number is never reused.
- **Splitting a requirement:** keep the original ID for the main behavior, and give the split-off parts new IDs. Don't use suffixes like `TXT-03a`.
- **References to other specs** use their full ID, e.g., "Depends on ACL-02".

---

## Authoring Rules

1. **One requirement = one testable behavior.** A tester should be able to verify it in one sitting. If it needs more than 7 acceptance criteria, or has parts that can ship separately, split it.
2. **Order requirements by workflow.** Follow the order a request moves through the system: input/UI → auth → data/compute → integration/AI → validation → rendering → caching → failure → security → observability.
3. **Behavior, not implementation.** Say *what* the system must do. Put *how* (libraries, file paths) in **Refs** or an appendix.
4. **Acceptance criteria use tags:**
   - `[Happy]` the main success path (1–3 items)
   - `[Alt]` alternate paths that change behavior or data: empty state, partial data, limits, edge values
   - `[Fail]` failures: what the user sees **and** what the system does (retry, fallback, log)
5. **Be concrete.** Use numbers for thresholds, limits, timeouts and sizes (e.g., "timeout after 20 s", not "fast"). If a value is unknown, propose a default and add an Open Question.
6. **Include failure handling** for anything that is external, async, AI-based, financial, or security-related.
7. **Detail scales with risk.** Low-risk UI changes may have just a Requirement and 2 ACs. High-risk areas get the full template.
8. **No duplication.** Rules that apply to the whole feature go in **Design Principles**, not in each requirement.
9. **Unresolved items** go in the requirement's **Open Questions** and are repeated in the consolidated table.
10. **Schemas and contracts** go in appendices. Requirements reference them by section name.
11. **When reviewing an existing spec,** also report the changes you made, in the **Change Log** table.

---

## Template

```markdown
# <PREFIX>: <Feature Name>

| Field | Value |
|---|---|
| Product | <product name> |
| Prefix | <PREFIX, from the file name; see Naming and IDs> |
| File | <PREFIX>-<feature-name>.md |
| Owner | <name> |
| Status | Draft / In Review / Approved |
| Last updated | <YYYY-MM-DD> |

---

## 1. Overview

### Problem
<Who is affected, what they struggle with today, and why it matters. 2–4 sentences.>

### Why <Approach> (optional)
<Why this solution, e.g., "Why AI". Include it only when the approach needs justifying.>

### Goals
- <Measurable outcome, e.g., "Users understand X in under 30 s">

### Non-Goals
- <What this feature explicitly will not do>

### Design Principles
1. **<Principle>.** <A one-line rule that applies to every requirement.>

---

## 2. Workflow

<A text diagram of the end-to-end flow. Label each step with the requirement IDs that cover it.>

\```
[Step 1] ──► <ID>
    │
[Step 2] ──► <ID>, <ID>
    │
[Failure at any step → fallback] ──► <ID>
\```

---

## 3. Requirements Index

| ID | Title | Area | Priority |
|---|---|---|---|
| <PREFIX>-01 | <Title> | <UI / Security / Data / AI / Reliability / Quality> | MVP / Later |

---

## 4. Requirements

### <PREFIX>-01: <Title>  `Priority: MVP | Later`

**Problem:** <Why this requirement exists. 1–2 sentences. Optional for small requirements.>
**Requirement:** <What the system must do, as observable behavior. 1–3 sentences.>
**Acceptance Criteria:**
- [Happy] <Expected result on the main path>
- [Alt] <Alternate condition → expected behavior>
- [Fail] <Failure condition → what the user sees + what the system does>
**Out of Scope:** <optional, one line>
**Open Questions:** <optional>
**Refs:** <related IDs, appendix sections, tickets, files>

---

## 5. Open Questions (consolidated)

| # | Question | Blocks |
|---|---|---|
| 1 | <question> | <ID> |

---

## Appendix A: <Schema / Contract Name>

<JSON schema, API contract, data model, prompt, or lookup table. Mark who produces it (code vs. AI vs. user).>

---

## Change Log (when revising an existing spec)

| Change | Reason |
|---|---|
| <what changed> | <why> |
```

---

## Review Checklist

Before returning a spec, confirm:

- [ ] The prefix comes from this spec's file name (or was derived and stated), and is not copied from an example or another spec.
- [ ] Every requirement ID, heading, index row, workflow label and Ref uses this spec's prefix, except intentional references to other specs.
- [ ] Existing IDs were not renumbered or reused. Removed IDs remain as placeholders.

- [ ] Every requirement has an ID, a priority, a Requirement, and at least one `[Happy]` AC.
- [ ] Every requirement with an external, AI, financial or security dependency has at least one `[Fail]` AC.
- [ ] No requirement has more than 7 ACs, or mixes parts that could ship independently.
- [ ] Every AC is testable, with concrete numbers and no vague words ("fast", "appropriate", "user-friendly").
- [ ] The requirements follow the workflow order, and every workflow step maps to an ID.
- [ ] Feature-wide rules appear only in Design Principles.
- [ ] Every Open Question appears in the consolidated table.
- [ ] Refs point to sections that exist. Appendix schemas match the field names used in the ACs.
- [ ] Non-Goals are stated, and no requirement contradicts them.
