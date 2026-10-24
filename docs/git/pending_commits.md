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
