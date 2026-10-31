#!/usr/bin/env python3
"""One-time migration: move every spec and tests file to <service-folder>/specs/ with a
<SVC>-<FEAT>-<feature-name>-spec.md name, rewrite requirement IDs to <SVC>-<FEAT>-<NN>,
fix every Markdown link that pointed at a moved file, and build docs/SPECS.md.

Usage (from anywhere):
    python3 docs/scripts/migrate_spec_prefixes.py            # dry run: print the plan, change nothing
    python3 docs/scripts/migrate_spec_prefixes.py --apply --commit   # do it, as two commits (recommended)
    python3 docs/scripts/migrate_spec_prefixes.py --apply    # do it, leave everything uncommitted
    python3 docs/scripts/migrate_spec_prefixes.py --apply --force   # also when affected files have uncommitted changes

Run it after the blocks in docs/git/pending_commits.txt are committed: those blocks list files by
their current paths. Then commit the result as one docs commit.

Rules:
- Files are moved with `git mv` (untracked files with a plain move), so history follows them.
- IDs are rewritten in the moved specs and tests and in living docs (architecture docs, decision
  records, flows, instructions). Dated notes, bug reports and docs/git/ keep their original IDs as a
  historical record; SPECS.md lists every old file name and ID pattern so they stay findable.
- Links are fixed in every Markdown file, including the historical ones.
Standard library only.
"""
import os
import re
import shutil
import subprocess
import sys

DOCS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(DOCS)
TODAY_NOTE = "renamed 2026-10"

L, A, I, K, D, X, U = ("fintracker-ledger-doc", "fintracker-analytics", "fintracker-ai-assistant",
                       "fintracker-knowledge", "fintracker-data-pipelines", "fintracker-cross-services",
                       "fintracker-user-profile-doc")

# old path (relative to docs) -> (new path, kind, title or tests-for, title mode, old ID pattern)
MOVES = [
    (f"{L}/ledger-spec.md", f"{L}/specs/LG-CORE-ledger-core-spec.md", "spec",
     "LG-CORE: Ledger Core Requirements (legacy; partly superseded, see Ledger architecture doc)", "replace", "REQ-x.y → LG-CORE-x.y; bills REQ-5.2–5.4 → LG-CORE-6.2–6.4"),
    (f"{L}/ledger-budget-spec-01.md", f"{L}/specs/LG-BUD-budgets-spec.md", "spec",
     "LG-BUD: Budgets", "replace", "REQ-5.1 … REQ-5.4 → LG-BUD-01 … LG-BUD-04"),
    (f"{L}/ledger-budget-tests-01-req.5.1.md", f"{L}/specs/LG-BUD-budgets-tests-01.md", "tests",
     f"{L}/specs/LG-BUD-budgets-spec.md", None, None),
    (f"{L}/ledger-budget-tests-01-req.5.2.md", f"{L}/specs/LG-BUD-budgets-tests-02.md", "tests",
     f"{L}/specs/LG-BUD-budgets-spec.md", None, None),
    (f"{L}/ledger-budget-tests-01-req.5.3.md", f"{L}/specs/LG-BUD-budgets-tests-03.md", "tests",
     f"{L}/specs/LG-BUD-budgets-spec.md", None, None),
    (f"{L}/ledger-statement-spec-01.md", f"{L}/specs/LG-STMT-statement-upload-spec-01.md", "spec",
     "LG-STMT: Statement Upload, Part 01 (Implemented Behavior)", "replace", "REQ-STMT-NN → LG-STMT-NN"),
    (f"{L}/ledger-statement-spec-02.md", f"{L}/specs/LG-STMT-statement-upload-spec-02.md", "spec",
     "LG-STMT: Statement Upload, Part 02 (Planned Changes and Known Gaps)", "replace", "REQ-STMT-NN → LG-STMT-NN"),
    (f"{L}/ledger-statement-spec-03.md", f"{L}/specs/LG-STMT-statement-upload-spec-03.md", "spec",
     "LG-STMT: Statement Upload, Part 03 (Auto-filled Statement Dates)", "replace", "REQ-STMT-NN → LG-STMT-NN"),
    (f"{L}/ledger-statement-tests-02-v1.md", f"{L}/specs/LG-STMT-statement-upload-tests-02-v1.md", "tests",
     f"{L}/specs/LG-STMT-statement-upload-spec-02.md", None, None),
    (f"{L}/ledger-statement-tests-02-v2.md", f"{L}/specs/LG-STMT-statement-upload-tests-02-v2.md", "tests",
     f"{L}/specs/LG-STMT-statement-upload-spec-02.md", None, None),
    (f"{L}/ledger-transaction-spec-01.md", f"{L}/specs/LG-CAT-custom-categories-spec.md", "spec",
     "LG-CAT: Custom Categories", "replace", "REQ-TS-01 → LG-CAT-01"),
    (f"{L}/ledger-transaction-tests-01.md", f"{L}/specs/LG-CAT-custom-categories-tests.md", "tests",
     f"{L}/specs/LG-CAT-custom-categories-spec.md", None, None),
    (f"{L}/TXT-transaction-types-spec.md", f"{L}/specs/LG-TXT-transaction-types-spec.md", "spec",
     "LG-TXT: Transaction Types", "replace", "TXT-NN → LG-TXT-NN"),
    (f"{L}/TXT-transaction-types-tests.md", f"{L}/specs/LG-TXT-transaction-types-tests.md", "tests",
     f"{L}/specs/LG-TXT-transaction-types-spec.md", None, None),
    (f"{A}/FS-financial-summary-spec.md", f"{A}/specs/AN-FS-financial-summary-spec.md", "spec",
     "AN-FS: Financial Summary", "replace", "FS-NN → AN-FS-NN"),
    (f"{A}/FS-tests.md", f"{A}/specs/AN-FS-financial-summary-tests.md", "tests",
     f"{A}/specs/AN-FS-financial-summary-spec.md", None, None),
    (f"{I}/ai-open-chat-spec.md", f"{I}/specs/AI-CHAT-open-chat-spec.md", "spec",
     "AI-CHAT: In-App Open Chat", "replace", "none"),
    (f"{I}/ai-chat-support.md", f"{I}/specs/AI-EXT-external-assistant-spec.md", "spec",
     "AI-EXT: User's Own AI Assistant", "replace", "none"),
    (f"{I}/ai-evaluation-auditing-spec.md", f"{I}/specs/AI-EVAL-evaluation-auditing-spec.md", "spec",
     "AI-EVAL: Evaluations and Auditing", "replace", "none"),
    (f"{I}/ai-data-access-rules.md", f"{I}/specs/AI-GUARD-data-access-rules-spec.md", "spec",
     "AI-GUARD: AI Data Access Rules", "insert", "none"),
    (f"{K}/ai-rag-pipelines-spec.md", f"{K}/specs/KN-RAG-rag-use-cases-spec.md", "spec",
     "KN-RAG: RAG Use Cases", "replace", "REQ-FA-NN → KN-RAG-NN"),
    (f"{D}/data-pipeline-spec-01.md", f"{D}/specs/DP-ING-statement-ingestion-spec.md", "spec",
     "DP-ING: Statement Ingestion", "insert", "REQ-DP-01 … REQ-DP-08 → DP-ING-01 … DP-ING-08"),
    (f"{D}/data-pipeline-tests-01.md", f"{D}/specs/DP-ING-statement-ingestion-tests.md", "tests",
     f"{D}/specs/DP-ING-statement-ingestion-spec.md", None, None),
    (f"{D}/data-pipeline-spec-02.md", f"{D}/specs/DP-CAT-categorization-spec.md", "spec",
     "DP-CAT: Categorization", "replace", "REQ-DP-09 → DP-CAT-01"),
    (f"{D}/data-pipeline-tests-02.md", f"{D}/specs/DP-CAT-categorization-tests.md", "tests",
     f"{D}/specs/DP-CAT-categorization-spec.md", None, None),
    (f"{D}/DPTXT-data-pipeline-transactions-type-category-spec.md", f"{D}/specs/DP-TXT-transaction-type-category-spec.md",
     "spec", "DP-TXT: Transaction Type and Category", "replace", "DPTXT → DP-TXT; problems keep P-NN"),
    (f"{X}/dp-ledger-categories-spec.md", f"{X}/specs/XS-DPCAT-dp-ledger-categories-spec.md", "spec",
     "XS-DPCAT: Data Pipeline and Ledger Categories", "replace", "DP-LEDGER-CATEGORIES-NN → XS-DPCAT-NN"),
    (f"{X}/dp-ledger-categories-tests.md", f"{X}/specs/XS-DPCAT-dp-ledger-categories-tests-01.md", "tests",
     f"{X}/specs/XS-DPCAT-dp-ledger-categories-spec.md", None, None),
    (f"{X}/dp-ledger-categories-tests-02.md", f"{X}/specs/XS-DPCAT-dp-ledger-categories-tests-02.md", "tests",
     f"{X}/specs/XS-DPCAT-dp-ledger-categories-spec.md", None, None),
    (f"{U}/user-profile-spec-01.md", f"{U}/specs/UP-AUTH-authentication-spec.md", "spec",
     "UP-AUTH: Authentication and Token Issuance", "insert", "REQ-UP-NN → UP-AUTH-NN"),
    (f"{U}/user-profile-tests-01.md", f"{U}/specs/UP-AUTH-authentication-tests.md", "tests",
     f"{U}/specs/UP-AUTH-authentication-spec.md", None, None),
]
MOVE_MAP = {old: new for old, new, *_ in MOVES}

NO_PREFIX = r"(?<![\w-])"
# Applied to moved files and living docs. Budget and ledger-core numbering are handled per file first.
ID_RULES = [
    (NO_PREFIX + r"DP-LEDGER-CATEGORIES-(\d{2})\b", r"XS-DPCAT-\1"),
    (NO_PREFIX + r"REQ-STMT-(\d{2})\b", r"LG-STMT-\1"),
    (NO_PREFIX + r"REQ-TS-(\d{2})\b", r"LG-CAT-\1"),
    (NO_PREFIX + r"REQ-DP-09\b", r"DP-CAT-01"),
    (NO_PREFIX + r"REQ-DP-0([1-8])\b", r"DP-ING-0\1"),
    (NO_PREFIX + r"REQ-UP-(\d{2})\b", r"UP-AUTH-\1"),
    (NO_PREFIX + r"REQ-FA-(\d{2})\b", r"KN-RAG-\1"),
    (NO_PREFIX + r"REQ-([1-46])\.(\d)\b", r"LG-CORE-\1.\2"),
    (NO_PREFIX + r"FS-(\d{2})\b", r"AN-FS-\1"),
    (NO_PREFIX + r"TXT-(\d{2})\b", r"LG-TXT-\1"),
    (NO_PREFIX + r"DPTXT\b", r"DP-TXT"),
    (NO_PREFIX + r"TXT(?![\w-])", r"LG-TXT"),
    (NO_PREFIX + r"FS(?![\w-])", r"AN-FS"),
]
LEDGER_CORE_FIRST = [  # ledger-spec.md numbers its Module 6 bill requirements 5.2–5.4 by mistake
    ("### REQ-5.2: Manage Upcoming Fixed Bills", "### LG-CORE-6.2: Manage Upcoming Fixed Bills"),
    ("### REQ-5.3: Track Paid Bills", "### LG-CORE-6.3: Track Paid Bills"),
    ("### REQ-5.4: Action Hub", "### LG-CORE-6.4: Action Hub"),
    ("REQ-5.1", "LG-CORE-5.1"),
]
BUDGET_FIRST = [
    ("(REQ-5.2.1)", "(Template Inheritance, LG-BUD-01)"),
    (re.compile(NO_PREFIX + r"REQ-5\.([1-4])\b"), r"LG-BUD-0\1"),
]
HEADING_FIRST = {  # specs whose requirements had no IDs
    f"{I}/ai-open-chat-spec.md": [("## 1: In-App Open Chat Support", "## AI-CHAT-01: In-App Open Chat Support")],
    f"{I}/ai-chat-support.md": [("## 1: User AI Assistant", "## AI-EXT-01: User AI Assistant")],
}

LINK_RE = re.compile(r"(\]\()([^)\s]+)(\))")


def is_history(rel):
    base = os.path.basename(rel)
    return (rel.startswith(("bugs/", "git/")) or re.match(r"\d{4}-\d{2}-\d{2}[_-]", base) is not None
            or "notes" in base or "_considered" in base or base.startswith("requirements_implementation")
            or base == "ledger-5-budget-code-enhance.md")


def skip_ids(rel):
    return is_history(rel) or rel.startswith("templates/") or rel == "SPECS.md"


def all_text_files():
    out = []
    for root, dirs, files in os.walk(DOCS):
        dirs[:] = [d for d in dirs if d not in (".git", "snapshots", "node_modules")]
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), DOCS)
            if rel.startswith("git/") or rel.startswith("scripts/"):
                continue
            if f.endswith(".md") or "." not in f:
                out.append(rel)
    return sorted(out)


def fix_links(text, old_rel, new_rel):
    old_dir, new_dir = os.path.dirname(old_rel), os.path.dirname(new_rel)
    changed = 0

    def repl(m):
        nonlocal changed
        target = m.group(2)
        if re.match(r"^[a-z]+:", target) or target.startswith(("#", "/")):
            return m.group(0)
        path, sep, anchor = target.partition("#")
        if not path:
            return m.group(0)
        resolved = os.path.normpath(os.path.join(old_dir, path))
        moved_target = MOVE_MAP.get(resolved)
        if moved_target is None and old_dir == new_dir:
            return m.group(0)
        dest = moved_target or resolved
        new_target = os.path.relpath(dest, new_dir or ".") + (sep + anchor if sep else "")
        if new_target != target:
            changed += 1
        return m.group(1) + new_target + m.group(3)

    return LINK_RE.sub(repl, text), changed


def fix_path_mentions(text):
    n = 0
    for old, new in MOVE_MAP.items():
        for a, b in ((f"docs/{old}", f"docs/{new}"), (old, new)):
            if a in text:
                n += text.count(a)
                text = text.replace(a, b)
    for old, new in MOVE_MAP.items():
        pat = re.compile(r"(?<![\w./-])" + re.escape(os.path.basename(old)) + r"(?![\w-])")
        text, k = pat.subn(os.path.basename(new), text)
        n += k
    return text, n


def rewrite_ids(text, old_rel):
    n = 0
    if old_rel == f"{L}/ledger-spec.md":
        for a, b in LEDGER_CORE_FIRST:
            n += text.count(a)
            text = text.replace(a, b)
    if "ledger-budget-" in old_rel:
        for a, b in BUDGET_FIRST:
            if isinstance(a, str):
                n += text.count(a)
                text = text.replace(a, b)
            else:
                text, k = a.subn(b, text)
                n += k
    for a, b in HEADING_FIRST.get(old_rel, []):
        n += text.count(a)
        text = text.replace(a, b)
    # Protect link targets and inline code paths from ID rewriting.
    protected = []

    def protect(m):
        protected.append(m.group(0))
        return f"\x00{len(protected) - 1}\x00"

    text = re.sub(r"\]\([^)\s]+\)", protect, text)
    for pat, rep in ID_RULES:
        text, k = re.subn(pat, rep, text)
        n += k
    text = re.sub(r"\x00(\d+)\x00", lambda m: protected[int(m.group(1))], text)
    return text, n


def add_header(text, entry):
    old, new, kind, info, mode, old_ids = entry
    lines = text.split("\n")
    if kind == "spec":
        ids = "no requirement IDs" if old_ids == "none" else f"IDs {old_ids}"
        meta = f"> **Formerly:** `{os.path.basename(old)}`, {ids} ({TODAY_NOTE}; see [SPECS.md]({os.path.relpath('SPECS.md', os.path.dirname(new))}))"
        title = f"# {info}"
        idx = next((i for i, l in enumerate(lines) if l.strip()), 0)
        first = lines[idx] if lines else ""
        if mode == "replace" and (first.startswith("# ") or not first.startswith("#")) and not first.startswith("=="):
            lines[idx:idx + 1] = [title, "", meta]
        else:
            lines[idx:idx] = [title, "", meta, ""]
    else:
        spec_rel = os.path.relpath(info, os.path.dirname(new))
        meta = f"> **Tests for:** [{os.path.basename(info)}]({spec_rel}) · **Formerly:** `{os.path.basename(old)}` ({TODAY_NOTE})"
        lines[0:0] = [meta, ""]
    return "\n".join(lines)


def git(*args):
    return subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True)


def main():
    apply = "--apply" in sys.argv
    force = "--force" in sys.argv
    missing = [old for old in MOVE_MAP if not os.path.exists(os.path.join(DOCS, old))]
    already = [new for new in MOVE_MAP.values() if os.path.exists(os.path.join(DOCS, new))]
    if missing or already:
        for m in missing:
            print("MISSING (already moved or renamed?):", m)
        for a in already:
            print("TARGET EXISTS:", a)
        sys.exit(1)

    files = all_text_files()
    before_broken = broken_links({f: open(os.path.join(DOCS, f), encoding="utf-8", errors="replace").read() for f in files}, files)
    plan, touched = {}, []
    for rel in files:
        text = open(os.path.join(DOCS, rel), encoding="utf-8", errors="replace").read()
        new_rel = MOVE_MAP.get(rel, rel)
        out, n_links = fix_links(text, rel, new_rel)
        n_paths = n_ids = 0
        if not skip_ids(rel):
            out, n_paths = fix_path_mentions(out)
            out, n_ids = rewrite_ids(out, rel)
        entry = next((e for e in MOVES if e[0] == rel), None)
        if entry:
            out = add_header(out, entry)
        if out != text or new_rel != rel:
            plan[rel] = (new_rel, out)
            touched.append((rel, new_rel, n_links, n_paths, n_ids))

    after_files = [plan[f][0] if f in plan else f for f in files]
    after_text = {plan[f][0] if f in plan else f: (plan[f][1] if f in plan else open(os.path.join(DOCS, f), encoding="utf-8", errors="replace").read()) for f in files}
    after_broken = broken_links(after_text, after_files)
    new_broken = sorted(set(after_broken) - {(MOVE_MAP.get(s, s), t) for s, t in before_broken})

    print(f"{'APPLY' if apply else 'DRY RUN'}: {len(MOVES)} files move, {len(touched)} files change\n")
    for rel, new_rel, nl, npth, nid in touched:
        arrow = f" -> {new_rel}" if new_rel != rel else ""
        print(f"  {rel}{arrow}  [links {nl}, paths {npth}, ids {nid}]")
    print(f"\nBroken links before: {len(before_broken)}; new broken links: {len(new_broken)}")
    for s, t in new_broken:
        print("  NEW BROKEN:", s, "->", t)
    report_external()

    if not apply:
        print("\nNothing changed. Re-run with --apply.")
        return
    if new_broken:
        print("Refusing to apply: the migration would break links above.")
        sys.exit(1)
    dirty = []
    for rel in plan:
        st = git("status", "--porcelain", "--", os.path.join("docs", rel)).stdout.strip()
        if st:
            dirty.append(st)
    if dirty and not force:
        print("\nThese files have uncommitted changes. Commit them first (see docs/git/pending_commits.txt),")
        print("or re-run with --force to include those changes in the migration commit:")
        for d in dirty:
            print("  ", d)
        sys.exit(1)
    commit = "--commit" in sys.argv
    renamed = []
    for rel, (new_rel, _) in plan.items():
        if new_rel == rel:
            continue
        os.makedirs(os.path.join(DOCS, os.path.dirname(new_rel)), exist_ok=True)
        r = git("mv", os.path.join("docs", rel), os.path.join("docs", new_rel))
        if r.returncode == 0:
            renamed += [os.path.join("docs", rel), os.path.join("docs", new_rel)]
        else:
            shutil.move(os.path.join(DOCS, rel), os.path.join(DOCS, new_rel))
    if commit and renamed:
        # Pure renames first, so git keeps every file's history even where the content changes a lot.
        r = git("commit", "-q", "-m", "DOCS: Moved every spec and tests file into its service's specs folder (rename only).", "--", *renamed)
        print(r.stdout + r.stderr if r.returncode else "Committed the renames.")
    for rel, (new_rel, out) in plan.items():
        with open(os.path.join(DOCS, new_rel), "w", encoding="utf-8") as fh:
            fh.write(out)
    subprocess.run([sys.executable, os.path.join(DOCS, "scripts", "build_spec_index.py")])
    if commit:
        paths = sorted({os.path.join("docs", new) for new, _ in plan.values()} |
                       {"docs/SPECS.md", "docs/scripts", "docs/templates/spec_template.md"})
        git("add", "--", *paths)
        r = git("commit", "-q", "-m", "DOCS: Switched specs to service-prefixed IDs (<SVC>-<FEAT>-<NN>), fixed links and added the SPECS.md index.", "--", *paths)
        print(r.stdout + r.stderr if r.returncode else "Committed the ID and link changes.")
        print("\nDone. Nothing was pushed. Review with `git log -2 --stat`.")
    else:
        print("\nDone; nothing is committed. Review with `git status` and `git diff`.")
        print("Tip: commit the renamed paths on their own first, so git keeps each file's history.")


def broken_links(texts, files):
    exists = set(files) | {"SPECS.md"}
    broken = []
    for f in files:
        d = os.path.dirname(f)
        for m in LINK_RE.finditer(texts[f]):
            t = m.group(2)
            if re.match(r"^[a-z]+:", t) or t.startswith(("#", "/")):
                continue
            p = t.partition("#")[0]
            if not p:
                continue
            target = os.path.normpath(os.path.join(d, p))
            if target not in exists and not os.path.exists(os.path.join(DOCS, target)):
                broken.append((f, t))
    return broken


def report_external():
    """List files outside docs/ that mention an old spec file name (read-only)."""
    names = {os.path.basename(o) for o in MOVE_MAP}
    hits = []
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "target", ".venv", "venv", "dist", "build",
                                                ".terraform", "__pycache__", ".angular") and os.path.join(root, d) != DOCS]
        for f in files:
            if not f.endswith((".md", ".py", ".java", ".ts", ".txt", ".yml", ".yaml", ".json", ".sh")):
                continue
            p = os.path.join(root, f)
            try:
                s = open(p, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            found = sorted(n for n in names if n in s)
            if found:
                hits.append((os.path.relpath(p, ROOT), found))
    if hits:
        print("\nOutside docs/, these files mention old spec names (not changed; update them by hand):")
        for p, found in hits:
            print(f"  {p}: {', '.join(found)}")


if __name__ == "__main__":
    main()
