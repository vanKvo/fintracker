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
| TXT follow-ups (2026-10-08) | fintracker-ledger, fintracker-data-pipeline, fintracker-analytics, fintracker-ui, root | 3 + 2 + 3 + 2 + 1 |
| TXT-01 Option A: missing type rejected (2026-10-08) | fintracker-ledger, fintracker-data-pipeline, root | 2 + 1 + 1 |

## Snapshots
A file changed by two requirements can't be committed whole in the first one without breaking the
tests-before-code order. A line like `path <= snapshots/...` commits a saved intermediate version
instead, and a later block commits the final version. The files under `docs/git/snapshots/` are
working copies for the script only. Delete them after committing; don't commit them.

## Not in the script (needs a manual decision)
- `services/fintracker-data-pipeline/README.md`: one line changed by the CsvColMappingConfirmation
  rename (`/jobs/{id}/mapping-confirmation` → `/jobs/{id}/csv-col-mapping-confirmation`). The file
  also has your own uncommitted edits, so commit it together with those.
- `CLAUDE.md` is gitignored, so there's nothing to commit.

## Commits that were already made
The reword of earlier commit messages is handled separately by `reword_messages_data_pipeline.txt` +
`reword_data_pipeline_commits.sh` (data pipeline) and the manual steps for the UI commit `d18d1da`.
