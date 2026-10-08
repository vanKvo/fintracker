#!/usr/bin/env bash
# Commits every block in pending_commits.txt, top to bottom, one commit per block.
#
# Usage (from anywhere):
#   bash docs/git/commit_pending.sh --dry-run   # show what would be committed, change nothing
#   bash docs/git/commit_pending.sh             # commit
#
# Snapshots: a file line written as `path <= snapshots/...` commits that saved intermediate version
# of the file instead of its current content (for a file changed by two phases, e.g. first by a
# requirement's tests-then-code and again by the next requirement). The file's current content is
# put back right after that commit, and a later block lists the path normally to commit it.
#
# Safety:
#   - Everything is validated first. If any listed path has no changes, or a snapshot is missing,
#     nothing is committed.
#   - Each commit includes ONLY the paths listed in its block (`git commit -- <paths>`), so other
#     staged or unstaged work in the same repo is left alone.
#   - Nothing is pushed.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PENDING="$SCRIPT_DIR/pending_commits.txt"
DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

# Emits one record per block: repo<TAB>message<TAB>entry1<TAB>entry2...
parse_blocks() {
  local repo="" msg="" files="" line
  flush() {
    if [ -n "$msg" ]; then printf '%s\t%s%s\n' "$repo" "$msg" "$files"; fi
    repo=""; msg=""; files=""
  }
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      "#"*) continue ;;
      "[commit]") flush ;;
      "repo: "*) repo="${line#repo: }" ;;
      "message: "*) msg="${line#message: }" ;;
      "") ;;
      *) files="$files"$'\t'"$line" ;;
    esac
  done < "$PENDING"
  flush
}

# Splits "path <= snapshot" into ENTRY_PATH / ENTRY_SNAPSHOT (empty when no snapshot).
split_entry() {
  case "$1" in
    *" <= "*) ENTRY_PATH="${1%% <= *}"; ENTRY_SNAPSHOT="$SCRIPT_DIR/${1#* <= }" ;;
    *) ENTRY_PATH="$1"; ENTRY_SNAPSHOT="" ;;
  esac
}

# Files swapped for a snapshot during a commit, restored on exit even if a commit fails.
SWAPPED=()
restore_swapped() {
  local item target backup
  for item in ${SWAPPED[@]+"${SWAPPED[@]}"}; do
    target="${item%%|*}"; backup="${item#*|}"
    cp "$backup" "$target" && rm -f "$backup"
  done
  SWAPPED=()
}
trap restore_swapped EXIT

# macOS ships bash 3.2 (no mapfile), so collect records with a read loop.
BLOCKS=()
while IFS= read -r record; do BLOCKS+=("$record"); done < <(parse_blocks)
[ "${#BLOCKS[@]}" -gt 0 ] || { echo "No pending commits in $PENDING"; exit 0; }

# Pass 1: validate every block before touching anything.
errors=0
for block in "${BLOCKS[@]}"; do
  IFS=$'\t' read -r -a parts <<< "$block"
  repo="${parts[0]}"; msg="${parts[1]}"; entries=()
  [ "${#parts[@]}" -gt 2 ] && entries=("${parts[@]:2}")
  dir="$ROOT/$repo"
  if ! git -C "$dir" rev-parse --git-dir >/dev/null 2>&1; then
    echo "ERROR: '$repo' is not a git repository"; errors=1; continue
  fi
  if [ "${#entries[@]}" -eq 0 ]; then
    echo "ERROR: no files listed for: $msg"; errors=1; continue
  fi
  for entry in "${entries[@]}"; do
    split_entry "$entry"
    if [ -n "$ENTRY_SNAPSHOT" ] && [ ! -f "$ENTRY_SNAPSHOT" ]; then
      echo "ERROR: snapshot not found: $ENTRY_SNAPSHOT"; errors=1
    fi
    if [ -z "$(git -C "$dir" status --porcelain -- "$ENTRY_PATH")" ]; then
      echo "ERROR: [$repo] no changes in '$ENTRY_PATH' (for: $msg)"; errors=1
    fi
  done
done
[ "$errors" -eq 0 ] || { echo "Nothing committed."; exit 1; }

# Pass 2: commit (or print, in dry-run mode).
for block in "${BLOCKS[@]}"; do
  IFS=$'\t' read -r -a parts <<< "$block"
  repo="${parts[0]}"; msg="${parts[1]}"; entries=("${parts[@]:2}")
  dir="$ROOT/$repo"
  branch="$(git -C "$dir" branch --show-current)"
  echo "== [$repo @ $branch] $msg"
  paths=()
  for entry in "${entries[@]}"; do
    split_entry "$entry"
    paths+=("$ENTRY_PATH")
    if [ -n "$ENTRY_SNAPSHOT" ]; then
      echo "     $ENTRY_PATH  (snapshot)"
      if [ "$DRY_RUN" -eq 0 ]; then
        backup="$(mktemp)"
        cp "$dir/$ENTRY_PATH" "$backup"
        SWAPPED+=("$dir/$ENTRY_PATH|$backup")
        cp "$ENTRY_SNAPSHOT" "$dir/$ENTRY_PATH"
      fi
    else
      echo "     $ENTRY_PATH"
    fi
  done
  if [ "$DRY_RUN" -eq 0 ]; then
    git -C "$dir" add -A -- "${paths[@]}"
    git -C "$dir" commit -q -m "$msg" -- "${paths[@]}"
    restore_swapped
    echo "     -> $(git -C "$dir" log --oneline -1)"
  fi
done

if [ "$DRY_RUN" -eq 1 ]; then
  echo; echo "Dry run: nothing committed."
else
  echo; echo "Done. Clear the committed blocks from pending_commits.txt."
fi
