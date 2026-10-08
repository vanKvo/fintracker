#!/usr/bin/env bash
# Rewords every commit listed in reword_messages_data_pipeline.txt in one pass.
# Only commit messages change: code, authors and dates stay the same, and every rewritten
# commit gets a new hash. Rewrites both `main` and `req-dp-09-categorization`.
#
# Usage (from anywhere):  bash docs/git/reword_data_pipeline_commits.sh
# Undo (before deleting backups):  see the note printed at the end.

# -e: Exit immediately if any command returns a non-zero (failure) status.
# -u: Treat unset variables as errors and exit immediately.
# -o pipefail: Makes a pipeline return a failure status if any command in the pipeline fails (not just the last one).
set -euo pipefail

# Calculate absolute path containing this script.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Set the path to the target git repository relative to this script location.
REPO="$SCRIPT_DIR/../../services/fintracker-data-pipeline"
# Export the path to the text file containing new commit messages.
export MSGS="$SCRIPT_DIR/reword_messages_data_pipeline.txt"
# Suppresses Git's built-in warning about git filter-branch being deprecated in favor of git-filter-repo.
export FILTER_BRANCH_SQUELCH_WARNING=1

# Parent of the oldest commit being reworded (1861e09); nothing at or before it changes.
BASE=32c3d9676a5a5e20d678bd5c32e109809e94b6c3

cd "$REPO"

# filter-branch refuses to run on a dirty working tree, so set uncommitted work aside.
# Check if git status --porcelain outputs any text (meaning there are modified or untracked files).
# Stash all untracked and tracked changes with the message "before-reword" and sets STASHED=1 so it can restore them later.
STASHED=0
if [ -n "$(git status --porcelain)" ]; then
  git stash push -u -m "before-reword"
  STASHED=1
fi

# Rewrite commit history for branches main and req-dp-09-categorization, excluding $BASE and its ancestors.
# --msg-filter '...': For every single commit being processed:
# 1. Searches $MSGS for a line starting with the current commit's full SHA ($GIT_COMMIT).
# 2. If found, extracts everything after the space (cut -d" " -f2-) into variable m.
# 3. If a new message m was found for this commit SHA, output m as the new commit message. Otherwise, output the existing commit message unchanged (cat).
git filter-branch -f --msg-filter '
  m=$(grep "^$GIT_COMMIT " "$MSGS" | cut -d" " -f2-)
  if [ -n "$m" ]; then printf "%s\n" "$m"; else cat; fi
' -- main req-dp-09-categorization "^$BASE"

# If uncommitted work was stashed at the start, restores it back to your working tree.
if [ "$STASHED" = 1 ]; then
  git stash pop
fi

# Verification logs
# Print out the new commit log (--oneline) for both main and req-dp-09-categorization from $BASE to the branch tips
echo
echo "== main"
git --no-pagqer log --oneline "$BASE"..main
echo
echo "== req-dp-09-categorization"
git --no-pager log --oneline "$BASE"..req-dp-09-categorization
cat <<'NOTE'

Done. Next steps:
  - origin/main already had 1861e09 and 95c4a44, so publishing the new history needs:
      git push --force-with-lease origin main
  - Undo (instead of pushing). reset --hard discards uncommitted edits, so run
    `git stash push -u` first and `git stash pop` afterwards:
      git reset --hard refs/original/refs/heads/req-dp-09-categorization   # while on that branch
      git branch -f main refs/original/refs/heads/main
  - Remove the backups once you're happy:
      git for-each-ref --format='%(refname)' refs/original/ | xargs -n1 git update-ref -d
  - If executing the script is denied, check the script permission using "ls -l":
  # Option A: no permission change needed
  bash reword_data_pipeline_commits.sh          # from docs/git/

  # Option B: make it executable once, then ./ works
  chmod +x reword_data_pipeline_commits.sh
  ./reword_data_pipeline_commits.sh

NOTE
