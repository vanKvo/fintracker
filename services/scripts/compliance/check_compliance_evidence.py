"""Checks the dated-document evidence behind the compliance matrix (XS-COMP-01, -02, -14, -16).

    scripts/.venv/bin/python scripts/compliance/check_compliance_evidence.py

Exits non-zero and prints one line per problem, so it can run in CI or before a review. Stdlib only.
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_MAX_AGE_DAYS = 365  # "within 12 months"
_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


def _first_date(text: str) -> date | None:
    m = _DATE.search(text)
    try:
        return date(int(m[1]), int(m[2]), int(m[3])) if m else None
    except ValueError:
        return None


def _review_problems(label: str, line_text: str | None, today: date) -> list[str]:
    reviewed = _first_date(line_text or "")
    if reviewed is None:
        return [f"{label}: no 'Last reviewed' date"]
    if (today - reviewed).days > _MAX_AGE_DAYS:
        return [f"{label}: last reviewed {reviewed}, older than 12 months"]
    return []


def _line(text: str, prefix: str) -> str | None:
    for raw in text.splitlines():
        if raw.strip().lower().startswith(prefix.lower()):
            return raw
    return None


def _table_rows(text: str, header_start: str) -> list[list[str]]:
    """Cells of each body row of the first table whose header row starts with `header_start`."""
    lines = text.splitlines()
    for i, raw in enumerate(lines):
        if raw.strip().lower().startswith(header_start.lower()):
            rows = []
            for body in lines[i + 2 :]:
                if not body.strip().startswith("|"):
                    break
                rows.append([c.strip() for c in body.strip().strip("|").split("|")])
            return rows
    return []


def check_program(text: str, today: date) -> list[str]:
    """XS-COMP-01: names the Qualified Individual and was reviewed within 12 months."""
    problems = _review_problems("information-security-program", _line(text, "Last reviewed:"), today)
    qi = _line(text, "Qualified Individual:")
    if not qi or not qi.split(":", 1)[1].strip():
        problems.append("information-security-program: no Qualified Individual named")
    return problems


def check_incident_response(text: str, today: date) -> list[str]:
    """XS-COMP-02: each notice has a deadline and recipient; a tabletop was recorded within 12 months."""
    problems = _review_problems("incident-response", _line(text, "Last reviewed:"), today)
    notices = _table_rows(text, "| Notice")
    if not notices or any(not row[2] or not row[3] for row in notices):
        problems.append("incident-response: the notice table must list each notice with a deadline and recipient")
    dates = [d for row in _table_rows(text, "| Date | Scenario") if (d := _first_date(row[0]))]
    if not dates or (today - max(dates)).days > _MAX_AGE_DAYS:
        problems.append("incident-response: no tabletop exercise recorded within the past 12 months")
    return problems


def check_providers(text: str, today: date) -> list[str]:
    """XS-COMP-14: AWS SOC 2 Type II and PCI DSS AoC dates recorded; no provider without attestation or reason."""
    problems = _review_problems("service-providers", _line(text, "Last reviewed:"), today)
    rows = _table_rows(text, "| Provider")
    for provider, _what, attestation, *_ in rows:
        if not attestation.strip():
            problems.append(f"service-providers: {provider} has no attestation and no stated reason")
        if provider.upper().startswith("AWS"):
            has_soc2 = re.search(r"SOC 2.*\d{4}-\d{2}-\d{2}", attestation) is not None
            has_pci = re.search(r"PCI.*\d{4}-\d{2}-\d{2}", attestation) is not None
            if not (has_soc2 and has_pci):
                problems.append("service-providers: AWS needs the dated SOC 2 Type II and PCI DSS AoC reports")
    if not any(r[0].upper().startswith("AWS") for r in rows):
        problems.append("service-providers: no AWS entry")
    return problems


def check_matrix(spec_text: str, today: date) -> list[str]:
    """XS-COMP-16: Appendix B reviewed within 12 months; every Implemented row links evidence."""
    start = spec_text.find("## Appendix B")
    end = spec_text.find("## Appendix C")
    appendix = spec_text[start : end if end > start else None] if start >= 0 else ""
    m = re.search(r"Last reviewed:\s*([0-9-]+)", appendix)
    problems = _review_problems("Appendix B", m.group(0) if m else None, today)
    for raw in appendix.splitlines():
        cells = [c.strip() for c in raw.strip().strip("|").split("|")] if raw.strip().startswith("|") else []
        if len(cells) >= 4 and cells[-2].lower().startswith("implemented") and cells[-1] in ("", "—", "-"):
            problems.append(f"Appendix B: '{cells[0]}' is Implemented without evidence")
    return problems


def main() -> int:
    today = date.today()
    docs = _ROOT / "docs"
    checks = [
        (docs / "compliance" / "information-security-program.md", check_program),
        (docs / "compliance" / "incident-response.md", check_incident_response),
        (docs / "compliance" / "service-providers.md", check_providers),
        (docs / "fintracker-cross-services" / "specs" / "XS-COMP-compliance-controls-spec.md", check_matrix),
    ]
    problems: list[str] = []
    for path, check in checks:
        problems += check(path.read_text(encoding="utf-8"), today) if path.exists() else [f"{path.name}: missing"]
    for p in problems:
        print(p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
