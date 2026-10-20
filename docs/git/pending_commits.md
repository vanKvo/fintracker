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
| FS Financial Summary MVP (2026-10-09), re-split by the AI refactor (2026-10-18) | fintracker-ledger, fintracker-user-profile, fintracker-analytics, fintracker-ai-assistant, fintracker-ui, root | 2 + 2 + 7 + 8 + 2 + 1 |
| Architecture doc review (2026-10-15) | root | 1 |
| AI refactor notes (2026-10-18) | root | 1 |
| DP-Ledger Categories Phase 2: Ledger ingest and review (T4–T7, plus the REQ-1.1 RLS fix and review follow-ups), 2026-10-20 | fintracker-ledger, root | 17 + 2 |
| DP-Ledger Categories Phase 3: Data Pipeline (T8–T13), 2026-10-20 | fintracker-data-pipeline, root | 12 + 1 |
| DP-Ledger Categories Phase 4: UI (T14–T15), 2026-10-20 | fintracker-ui | 4 |
| DP-Ledger Categories Phase 5: docs and runbook (T16), 2026-10-20 | root | 1 |

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

### AI refactor (2026-10-18): what changed in the blocks
- Every LLM file moved from `fintracker-analytics` to the new `services/fintracker-ai-assistant`
  (a local `git init` repo with no commits and no remote). The FS-10, FS-21, FS-20 (eval) and FS-22
  blocks now commit there, so Analytics' history never contains LLM code. Analytics keeps FS-02,
  FS-03, an FS-20 block for the fixture builder and fixtures, and two ARCH-D4 blocks for its
  facts API and internal routes.
- The FS-02 Analytics block no longer lists `src/ai_agent/*`, `src/insights/router.py` or their
  tests (moved). `src/dashboard/router.py` and `src/reports/router.py` now commit pre-refactor
  snapshots there (`snapshots/fintracker-analytics/*_fs02.py`), and the ARCH-D4 block commits
  the final files.
- The UI FS-13 blocks already include the switch of summary/refresh calls to `/api/v1/ai/summary`
  (specs in the tests block, service, component and proxy in the implementation block).

### FS: files with earlier uncommitted work
Before the FS work started, `fintracker-analytics` already had uncommitted changes: the move to
feature folders (`src/api`, `src/crud`, `src/schemas`, `src/services` deleted; `src/dashboard`,
`src/reports`, `src/insights`, `src/ai_agent`, `tests/ai_agent`, `tests/insights` untracked) and
edits to `README.md` and `src/main.py`. The FS-02 blocks change some of those same files, so
committing them as listed also commits that earlier work inside the FS-02 commits:
- Tests block: `tests/conftest.py`.
- Implementation block: `src/main.py`, `src/dashboard/router.py`, `src/reports/router.py`.
- Not in any block, and needed for the FS commits to import cleanly: `src/__init__.py`,
  `src/core/__init__.py`, the other `__init__.py`/`models.py` files of the feature folders,
  `tests/__init__.py`, `tests/insights/__init__.py` (now empty; its tests moved to the AI assistant),
  `.gitignore` and the deleted old-layout files. (`README.md` is now in the ARCH-D4 block.)

Recommended: commit the feature-folder restructure first in its own commit (you choose the message).
For a clean split, the FS-02 files above need pre-FS-02 snapshots; ask and they'll be prepared.

In `fintracker-user-profile`, `tests/unit/identity/test_internal_settings.py` needs the untracked
`tests/conftest.py` (sets the env vars the DI container reads), which is your earlier work and not
in any block.

### FS: snapshots
- `snapshots/fintracker-analytics/main_fs02.py`, `dashboard_router_fs02.py` and
  `reports_router_fs02.py` are the FS-02 versions (no summary or internal routes). The ARCH-D4
  block commits the final files. Delete the snapshots after committing.

### DP-Ledger Categories, Phases 2–5 (2026-10-20)
- **Order.** The Ledger blocks must commit after the FS-23 blocks: V24 belongs to FS-23, and these blocks add V25–V27. The file lists them in that order.
- **Snapshots.** Files changed by more than one requirement commit saved intermediate copies first. The final copies are committed by a later block. The copies are in:
  - `snapshots/fintracker-ledger/DP-LEDGER-CATEGORIES-04-columns/`
  - `snapshots/fintracker-ledger/DP-LEDGER-CATEGORIES-05/`
  - `snapshots/fintracker-ledger/DP-LEDGER-CATEGORIES-04-recategorize/`
  - `snapshots/fintracker-ledger/DP-LEDGER-CATEGORIES-02-404/`
  - `snapshots/fintracker-data-pipeline/DP-LEDGER-CATEGORIES-06/`
  - `snapshots/fintracker-data-pipeline/DP-LEDGER-CATEGORIES-03/`
  - `snapshots/fintracker-data-pipeline/DP-LEDGER-CATEGORIES-02-infra/`

  Delete them after committing.
- **Verified states.** Every implementation commit's state was rebuilt from HEAD plus the blocks before it and tested. Each failing-tests commit fails, and each implementation commit passes.
- **Infra-only commit.** The DP-LEDGER-CATEGORIES-02 infra block (Normalizer Ledger URL, alarm, outputs) has no failing-tests commit. It is Terraform only, checked with `terraform validate`.
- **Root file staged by you.** The Phase 5 docs block includes `docs/fintracker-cross-services/dp-ledger-categories-tests.md`, which you staged as part of the docs move. Committing that block also commits the file's new location. The deletion of its old path stays in your docs-move commit.
- **Not in any block.** `terraform.tfvars` is gitignored, so it isn't committed. Before applying, change it by hand: add `identity_authorizer_function_arn` and remove the two `cognito_*` values (see `docs/instructions/deploy_dp_ledger_categories.md`).

### Blocks that currently fail the dry run (not from this work)
The FS-01 root block lists `docs/fintracker-analytics/FS-financial-summary-updated.md`, `docs/fintracker-analytics/fs-tests-01.md` and `docs/instructions/run_financial_summary.md`. Those files were moved in the docs reorganization. They now appear to be `docs/fintracker-analytics/FS-financial-summary-spec.md`, `docs/fintracker-analytics/FS-tests.md` and `docs/fintracker-ai-assistant/evaluation/run_financial_summary.md`. Until that block names the new paths, `commit_pending.sh` stops before committing anything.

## Commits that were already made
The reword of earlier commit messages is handled separately by `reword_messages_data_pipeline.txt` +
`reword_data_pipeline_commits.sh` (data pipeline) and the manual steps for the UI commit `d18d1da`.
