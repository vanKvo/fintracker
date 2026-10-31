#!/usr/bin/env python3
"""Build docs/SPECS.md, the index of every spec, its tests and its requirement IDs.

Usage (from anywhere):
    python3 docs/scripts/build_spec_index.py           # rewrite docs/SPECS.md
    python3 docs/scripts/build_spec_index.py --check   # exit 1 if SPECS.md is stale or a spec breaks the naming or status rules

A spec is any file named <SVC>-<FEAT>-<feature-name>-spec[-NN].md inside a <service-folder>/specs/ folder.
Its tests file is <SVC>-<FEAT>-<feature-name>-tests[-NN][-vN].md in the same folder.
Standard library only.
"""
import os
import re
import sys

DOCS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(DOCS, "SPECS.md")

SERVICES = {
    "LG": ("Ledger", "fintracker-ledger-doc"),
    "AN": ("Analytics", "fintracker-analytics"),
    "DP": ("Data pipeline", "fintracker-data-pipelines"),
    "UP": ("User profile", "fintracker-user-profile-doc"),
    "AI": ("AI assistant", "fintracker-ai-assistant"),
    "KN": ("Knowledge", "fintracker-knowledge"),
    "DS": ("Document service", "fintracker-document-service"),
    "UI": ("Frontend", "fintracker-ui-doc"),
    "XS": ("Cross-service", "fintracker-cross-services"),
    "LB": ("Libraries", "fintracker-libraries"),
}

STATUSES = ("Proposed", "In progress", "Implemented", "Superseded", "Removed", "Unverified")
STATUS_RE = re.compile(r"^(?P<value>" + "|".join(STATUSES) + r")\b\s*(?P<note>.*)$")
REF_RE = re.compile(r"[A-Z]{2}-[A-Z]{2,6}(?:-\d+)?")
ID_CELL_RE = re.compile(r"^[`~*\s]*(?P<id>[A-Z]{2}-[A-Z]{2,6}-\d+(?:\.\d+)?)[`~*\s]*$")

FILE_RE = re.compile(
    r"^(?P<svc>[A-Z]{2})-(?P<feat>[A-Z]{2,6})-(?P<name>[a-z0-9]+(?:-[a-z0-9]+)*?)"
    r"-(?P<kind>spec|tests)(?P<part>-\d{2})?(?P<ver>-v\d+)?\.md$"
)


def find_files():
    found = []
    for root, dirs, files in os.walk(DOCS):
        dirs[:] = [d for d in dirs if d not in (".git", "git", "node_modules")]
        if os.path.basename(root) != "specs":
            continue
        for f in sorted(files):
            if f.endswith(".md"):
                found.append(os.path.join(root, f))
    return found


def parse_spec(path, prefix):
    text = open(path, encoding="utf-8").read()
    title = ""
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break
    if title.startswith(prefix + ":"):
        title = title[len(prefix) + 1:].strip()
    formerly = ""
    m = re.search(r"\*\*Formerly:\*\*\s*(.+?)\s*(?:\(renamed[^)]*\)\)?)?\s*$", text, re.M)
    if m:
        formerly = m.group(1).strip().rstrip(",")
    reqs, problems = [], []
    seen = set()
    head_re = re.compile(r"^#{2,4}\s+(~~)?(?P<id>[A-Z]{2}-[A-Z]{2,6}-\d+(?:\.\d+)?)(~~)?:?\s*(?P<title>.*)$")
    for line in text.splitlines():
        hm = head_re.match(line)
        if not hm:
            continue
        rid = hm.group("id")
        if not rid.startswith(prefix + "-"):
            problems.append(f"{os.path.relpath(path, DOCS)}: heading {rid} does not use the spec's prefix {prefix}")
            continue
        if rid in seen:
            problems.append(f"{os.path.relpath(path, DOCS)}: requirement {rid} appears twice")
        seen.add(rid)
        rtitle = re.sub(r"`Priority:[^`]*`", "", hm.group("title")).strip()
        wm = re.search(r"\*\(was ([^)]+)\)\*", rtitle)
        old_id = wm.group(1) if wm else ""
        rtitle = re.sub(r"\s*\*\(was [^)]+\)\*", "", rtitle).strip()
        removed = bool(hm.group(1)) or "Priority: Removed" in line or rtitle.lower().startswith("removed")
        reqs.append((rid, rtitle, removed, old_id))

    # Status lives in the spec: the Requirements Index (template specs) or the short
    # Status table at the top (older specs). Any table whose header starts with "ID"
    # and has a "Status" column counts.
    rel = os.path.relpath(path, DOCS)
    statuses = {}
    status_col = None
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.lstrip().startswith("|") else None
        if cells is None:
            status_col = None
            continue
        if cells and cells[0] == "ID" and "Status" in cells:
            status_col = cells.index("Status")
            continue
        if status_col is None or set("".join(cells)) <= set("-: "):
            continue
        im = ID_CELL_RE.match(cells[0])
        if im and status_col < len(cells):
            statuses[im.group("id")] = cells[status_col]

    req_ids = {r[0] for r in reqs}
    for sid in statuses:
        if sid not in req_ids:
            problems.append(f"{rel}: status given for {sid}, which has no requirement heading")
    out = []
    for rid, rtitle, removed, old_id in reqs:
        raw = statuses.get(rid, "")
        sm = STATUS_RE.match(raw)
        if not raw:
            problems.append(f"{rel}: {rid} has no status")
        elif not sm:
            problems.append(f"{rel}: {rid} status '{raw}' is not one of {', '.join(STATUSES)}")
        elif sm.group("value") == "Superseded" and not REF_RE.search(sm.group("note")):
            problems.append(f"{rel}: {rid} is Superseded but doesn't name what replaces it")
        if sm and (sm.group("value") == "Removed") != removed:
            problems.append(f"{rel}: {rid} status and heading disagree about removal "
                            "(a removed requirement needs status Removed and a ~~struck~~ heading)")
        out.append((rid, rtitle, removed, old_id, raw or "—"))
    return title, formerly, out, problems


def _summary(counts):
    return " · ".join(f"{counts[v]} {v}" for v in (*STATUSES, "—") if counts.get(v)) or "—"


def build():
    specs, tests, problems = {}, {}, []
    for path in find_files():
        rel = os.path.relpath(path, DOCS)
        m = FILE_RE.match(os.path.basename(path))
        if not m:
            problems.append(f"{rel}: name doesn't follow <SVC>-<FEAT>-<feature-name>-spec.md or -tests.md")
            continue
        svc, feat = m.group("svc"), m.group("feat")
        if svc not in SERVICES:
            problems.append(f"{rel}: unknown service code {svc}")
            continue
        prefix = f"{svc}-{feat}"
        key = (prefix, m.group("name"))
        if m.group("kind") == "spec":
            specs.setdefault(key, []).append(path)
        else:
            tests.setdefault(key, []).append(path)
    owners = {}
    for (prefix, name) in specs:
        if prefix in owners and owners[prefix] != name:
            problems.append(f"prefix {prefix} is used by two features: {owners[prefix]} and {name}")
        owners[prefix] = name
    for (prefix, name), paths in tests.items():
        if (prefix, name) not in specs:
            problems.append(f"{os.path.relpath(paths[0], DOCS)}: tests file has no matching spec")

    rows, req_rows = [], []
    counts = {}
    for (prefix, name) in sorted(specs):
        svc = prefix.split("-")[0]
        title, formerly, all_reqs = "", [], []
        spec_counts = {}
        links = []
        for p in sorted(specs[(prefix, name)]):
            t, f, reqs, probs = parse_spec(p, prefix)
            problems.extend(probs)
            title = title or re.sub(r",?\s*Part \d+\b.*$", "", t)
            if f and f not in formerly:
                formerly.append(f)
            rel = os.path.relpath(p, DOCS)
            links.append(f"[{os.path.basename(p)}]({rel})")
            for rid, rt, removed, old_id, status in reqs:
                all_reqs.append(rid)
                value = STATUS_RE.match(status).group("value") if STATUS_RE.match(status) else "—"
                counts[value] = counts.get(value, 0) + 1
                spec_counts[value] = spec_counts.get(value, 0) + 1
                req_rows.append(f"| {rid} | {old_id or '—'} | {'~~' + rt + '~~ (removed)' if removed else rt} | {status} | [{os.path.basename(p)}]({rel}) |")
        test_links = [f"[{os.path.basename(p)}]({os.path.relpath(p, DOCS)})" for p in sorted(tests.get((prefix, name), []))]
        span = "—" if not all_reqs else all_reqs[0] if len(all_reqs) == 1 else f"{all_reqs[0]} … {all_reqs[-1]} ({len(all_reqs)})"
        rows.append(f"| `{prefix}` | {title} | {SERVICES[svc][0]} | {'<br>'.join(links)} | "
                    f"{'<br>'.join(test_links) or '—'} | {span} | {_summary(spec_counts)} | {'<br>'.join(formerly) or '—'} |")

    lines = [
        "# Spec Index",
        "",
        "Generated by `python3 docs/scripts/build_spec_index.py`. Do not edit by hand; edit the specs and re-run it.",
        "",
        "Search this page for any requirement ID or spec path, old or new, to find the current spec. "
        "Code and old commits may keep old IDs and paths; the **Old ID** and **Formerly** columns map them to the new ones.",
        "",
        "## Naming",
        "",
        "- **Prefix** = service code + feature code, e.g. `LG-TXT`. The feature code is 2–6 letters and unique within its service.",
        "- **Spec file:** `<service-folder>/specs/<PREFIX>-<feature-name>-spec.md`. A spec in parts adds `-01`, `-02`.",
        "- **Tests file:** `<PREFIX>-<feature-name>-tests.md`, next to the spec.",
        "- **Requirement ID:** `<PREFIX>-<NN>`, e.g. `LG-TXT-02`. Never renumbered; removed IDs stay as placeholders.",
        "- **Commit message:** `<PREFIX>-<NN>: <summary>`, e.g. `LG-TXT-02: Applied refund offsets to budget spend`.",
        "- **Status:** each requirement's status lives in its own spec (the Requirements Index, or the Status table at the top of an older spec). "
        "This page only collects it. Values: " + ", ".join(f"`{v}`" for v in STATUSES) + ".",
        "- Full rules: [templates/spec_template.md](templates/spec_template.md).",
        "",
        "| Code | Service | Folder |",
        "|---|---|---|",
    ]
    lines += [f"| `{c}` | {s} | `{f}/specs/` |" for c, (s, f) in SERVICES.items()]
    lines += [
        "",
        "## Status summary",
        "",
        "| Status | Requirements |",
        "|---|---|",
        *[f"| {v} | {counts[v]} |" for v in (*STATUSES, "—") if counts.get(v)],
        "",
        "## Specs",
        "",
        "| Prefix | Feature | Service | Spec | Tests | Requirements | Status | Formerly (old path and IDs) |",
        "|---|---|---|---|---|---|---|---|",
        *rows,
        "",
        "## Requirements",
        "",
        "| ID | Old ID | Title | Status | Spec |",
        "|---|---|---|---|---|",
        *req_rows,
        "",
    ]
    return "\n".join(lines), problems


def main():
    content, problems = build()
    check = "--check" in sys.argv
    if check:
        current = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        if current != content:
            problems.append("SPECS.md is out of date; run python3 docs/scripts/build_spec_index.py")
    else:
        with open(OUT, "w", encoding="utf-8") as fh:
            fh.write(content)
        print(f"Wrote {os.path.relpath(OUT, os.path.dirname(DOCS))}")
    for p in problems:
        print("PROBLEM:", p)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
