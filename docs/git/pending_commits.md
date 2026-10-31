# Pending Commits

The AI agent doesn't commit anything unless you ask. Its uncommitted changes are listed in
**`pending_commits.txt`**: one block per commit, grouped by implementation phase, each with its files
and proposed message.

## How to commit
1. Review `pending_commits.txt`. Edit messages or move files between blocks if you want.
2. Dry run, which checks every listed file has changes and prints the plan:
   `bash docs/git/commit_pending.sh --dry-run`
3. Commit everything in order: `bash docs/git/commit_pending.sh`
4. Delete the committed blocks from `pending_commits.txt`.

Each commit includes only the files in its block, so any other work in progress stays uncommitted.
Nothing is pushed.

## Phases currently pending
| Phase | Repo(s) | Blocks |
|---|---|---|
| ARCH-4.8 error handling and ARCH-9.1 Python layout, plus AN-FS-22 prompt versioning, 2026-10-23 | fintracker-ai-assistant, fintracker-analytics, fintracker-knowledge, root | 4 + 2 + 2 + 2 |
| AN-FS-10/14/15/20/21 review changes, User Profile goals route (S3) and account deletion, 2026-10-25 | fintracker-ai-assistant, fintracker-user-profile, root | 4 + 4 + 1 |
| AI-CHAT-01 to AI-CHAT-15 in-app chat, 2026-10-25 | fintracker-ai-assistant, root | 2 + 1 |
| Import reliability: DP-ING-09/10/11, XS-IMP-01 to -04, XS-DPCAT v3, LG-STMT-04/08, DP-MAP, 2026-10-25 | fintracker-ledger, fintracker-data-pipeline, fintracker-ui, root | 2 + 2 + 2 + 1 |
| temp_doc.md fixes: DP-ING-12, LG-STMT-08, DP-ING-11 cleanup, LG-READ, UP-AUTH-02 route identity, UI reason catalog, 2026-10-26 | fintracker-ledger, fintracker-data-pipeline, fintracker-ai-assistant, fintracker-user-profile, fintracker-ui, root | 2 + 2 + 2 + 2 + 2 + 1 |
| DS-DL-01 Document service download slice, 2026-10-26 | services/fintracker-document-service (new local repo), root | 2 + 1 |
| AN-FS-10/11 retry on grounding problems, first-reply fallback, attempt counter and dropped-item logging, 2026-10-27 | fintracker-ai-assistant | 1 + 1 (plus the retry tests inside the first AN-FS-10 block) |
| AN-FS-20 eval report: per-call call_outcome and validation_outcome with reason, actual per-call token cost, cache tokens, no estimates in live reports, 2026-10-27 | fintracker-ai-assistant | 1 (plus changes inside the AN-FS-10/11 blocks above) |
| AN-FS-12 guardrail retry and banned-term list, prompt version fs-v2, spec and tests doc rows 400 to 416, 2026-10-27 | fintracker-ai-assistant, root | 1 (plus changes inside the AN-FS-10/11 blocks and the root AN-FS-10/11/20 block) |
| AN-FS-22 result folder names and AN-FS-20 run record (temperature, max_tokens, git_sha, github_run_id, cap, deadline, fixtures, prices, start and end), 2026-10-27 | fintracker-ai-assistant, root | 1 + 1 (plus changes inside the blocks that already list test_eval.py, runner.py and __main__.py, and the root AN-FS-10/11/20 block) |
| AN-FS-20 eval report: `client_latency_ms` (was `latency_ms`) and error_code / error_type / error_message on failed calls, 2026-10-27 | fintracker-ai-assistant | 1 (plus changes inside the blocks that already list schemas.py, generation.py, llm.py, runner.py, __main__.py, test_eval.py and test_generation_retries.py, and the root AN-FS-10/11/20 block) |
| ARCH-9.2 testing strategy in the architecture doc, 2026-10-27 | root | 1 |
| EVL-001 to EVL-011 and SDR-003: insight metric_ref, reference path syntax repair, retry text, code-assigned ids, nested recommendations, item-level schema, number tokenization, no half-dropped rule, prompt fs-v3, evaluation log, structure-mode SDR, 2026-10-28 | fintracker-ai-assistant, root | 3 + 2 (plus changes inside the blocks that already list schemas.py, validation.py, loader.py, config.py and the summary tests) |
| EVL-012 to EVL-023 and the replay tool: unit beside a token, ISO dates, metric-type insights without a retry, max_tokens 2000, one insight per candidate, injection echo check, per-field text limits, headline and period-level tokenization, null candidate impact, amounts in words, no self-calculated figures, highlight comments without a token for their own metric (new prompt version fs-v4; fs-v3 stays as run), 2026-10-28 | fintracker-ai-assistant, root | 2 + 1 (replay tool, its tests and the run guide), plus changes inside the blocks that already list schemas.py, validation.py, loader.py, config.py, runner.py, fs-v3 system.md, the summary tests, the evaluation log and the AN-FS spec and tests docs |
| KN-SDOC help docs (12 docs under docs/help) and KN-CHUNK-04 golden question sets, 2026-10-28 | root | 2 |
| ADR-013 restructured to the adr-instruction.md format (Why in Decision, rejected alternatives, pros and cons in Consequences), 2026-10-29 | root | 1 |
| ADR-011, 012, 014, 015 and adr-template.md restructured the same way, optional trade-off table, 2026-10-29 | root | 1 |
| XS-ACCT last four only, XS-COMP compliance controls, app doc §11 and D26, 2026-10-29 | root | 3 |
| Knowledge scope rename `mine` to `user` (docs and code; V1 and V4 edited in place), 2026-10-29 | fintracker-knowledge, root | 2 + 1 |

## Snapshots
A file changed by two requirements can't be committed whole in the first one without breaking the
tests-before-code order. A line like `path <= snapshots/...` commits a saved intermediate version
instead, and a later block commits the final version. The files under `docs/git/snapshots/` are
working copies for the script only. Delete them after committing; don't commit them.

## Delete before committing
The agent can't delete files on your computer, so the old files are still there. Delete them first
(the blocks list them as deletions; the dry run fails while they exist):

- `services/fintracker-ai-assistant`: `src/core/problems.py`, `src/insights/`, `tests/insights/`,
  `src/summary/contract.py`, `src/summary/prompt/v1.py`
- `services/fintracker-analytics`: `src/core/problems.py`, `src/insights/`, `tests/insights/`,
  `src/dashboard/models.py`, `src/reports/context.py`, `src/reports/models.py`,
  `src/summary/schema.py`, `src/summary/profile_client.py`, `tests/summary/test_profile_client.py`
- `services/fintracker-knowledge`: `src/chunking/models.py`, `src/embedding/models.py`,
  `src/model_switch/models.py`, `src/retrieval_quality/models.py`

## Not in the script (needs a manual decision)
- `services/fintracker-ai-assistant/.github/workflows/ci.yml` is in the ARCH-4.8 block but the agent
  can't write it: add `src/tools` to the mypy and redaction-check paths by hand first.
- The Analytics and Knowledge Docker-backed integration tests weren't run here (no Docker). Run
  them before committing: `tests/integration` (Analytics) and the vector-store, search and
  model-switch tests (Knowledge).
- `CLAUDE.md` is gitignored, so there's nothing to commit.
