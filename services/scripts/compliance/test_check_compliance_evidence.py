"""XS-COMP-01, -02, -14, -16: the dated-document evidence behind the compliance matrix.

Run from the repo root: scripts/.venv/bin/python -m pytest scripts/compliance
"""
from __future__ import annotations

from datetime import date

from compliance.check_compliance_evidence import (
    check_incident_response,
    check_matrix,
    check_program,
    check_providers,
)

TODAY = date(2026, 10, 29)

PROGRAM = """# Program
Qualified Individual: Van Vo (owner)
Last reviewed: 2026-06-01
"""

INCIDENT = """# Incident response
Last reviewed: 2026-06-01
## 3. Notices
| Notice | When | Deadline | Recipient | Template |
|---|---|---|---|---|
| FTC | x | Within 30 days | FTC | t |
## 5. Tabletop exercises
| Date | Scenario | Outcome |
|---|---|---|
| 2026-03-15 | Leaked access token | ok |
"""

PROVIDERS = """# Register
Last reviewed: 2026-06-01
| Provider | What it does | Attestation | Checked | Stays with FinTracker |
|---|---|---|---|---|
| AWS | hosting | SOC 2 Type II (report 2026-04-30); PCI DSS AoC (2026-05-12) | 2026-06-01 | config |
"""

MATRIX = """## Appendix B
Status: **Implemented** ... *Last reviewed: 2026-10-29.*
| Element | FinTracker control | Status | Evidence / tracking |
|---|---|---|---|
| A | c | Implemented | ADR-002 |
| B | c | Designed | XS-COMP-01 |
"""


class TestProgram:
    def test_a_named_qualified_individual_and_a_recent_review_pass(self) -> None:
        """XS-COMP-01 [Happy]: names the Qualified Individual, reviewed within the past 12 months."""
        assert check_program(PROGRAM, TODAY) == []

    def test_a_review_older_than_12_months_fails(self) -> None:
        """XS-COMP-01 [Fail]: the review date is older than 12 months."""
        problems = check_program(PROGRAM.replace("2026-06-01", "2025-10-28"), TODAY)

        assert any("older than 12 months" in p for p in problems)

    def test_no_review_date_or_no_qualified_individual_fails(self) -> None:
        """XS-COMP-01 [Happy]: both the name and the date must be present."""
        assert len(check_program("# Program\n", TODAY)) == 2


class TestIncidentResponse:
    def test_notices_and_a_recent_tabletop_pass(self) -> None:
        """XS-COMP-02 [Happy]/[Fail]: notices are listed and a tabletop was recorded within the year."""
        assert check_incident_response(INCIDENT, TODAY) == []

    def test_a_missed_tabletop_year_fails(self) -> None:
        """XS-COMP-02 [Fail]: a tabletop exercise at least once a year, recorded with its date."""
        stale = INCIDENT.replace("2026-03-15", "2025-10-01")

        assert any("tabletop" in p for p in check_incident_response(stale, TODAY))

    def test_no_notice_table_fails(self) -> None:
        """XS-COMP-02 [Happy]: the runbook lists each notice with its deadline and recipient."""
        assert any("notice" in p for p in check_incident_response("Last reviewed: 2026-06-01\n", TODAY))


class TestProviders:
    def test_aws_with_dated_soc2_and_pci_reports_passes(self) -> None:
        """XS-COMP-14 [Happy]: AWS SOC 2 Type II and PCI DSS AoC dates are recorded."""
        assert check_providers(PROVIDERS, TODAY) == []

    def test_aws_without_report_dates_fails(self) -> None:
        """XS-COMP-14 [Happy]: not downloaded yet means not done."""
        missing = PROVIDERS.replace("SOC 2 Type II (report 2026-04-30); PCI DSS AoC (2026-05-12)", "not yet downloaded")

        assert any("AWS" in p for p in check_providers(missing, TODAY))

    def test_a_provider_without_attestation_or_reason_fails(self) -> None:
        """XS-COMP-14 [Alt]: a provider without an independent attestation lists why it is accepted."""
        row = "| Teller | bank sync | | 2026-06-01 | tokens |\n"

        assert any("Teller" in p for p in check_providers(PROVIDERS + row, TODAY))


class TestMatrix:
    def test_a_recent_review_and_evidence_on_every_implemented_row_pass(self) -> None:
        """XS-COMP-16 [Happy]: Appendix B reviewed within 12 months and every Implemented row links evidence."""
        assert check_matrix(MATRIX, TODAY) == []

    def test_an_implemented_row_without_evidence_fails(self) -> None:
        """XS-COMP-16 [Fail]: a row marked Implemented without evidence goes back to Designed."""
        bare = MATRIX.replace("| Implemented | ADR-002 |", "| Implemented |  |")

        assert any("Implemented" in p for p in check_matrix(bare, TODAY))

    def test_a_review_older_than_12_months_fails(self) -> None:
        """XS-COMP-16 [Happy]: the Last reviewed date is within 12 months."""
        old = MATRIX.replace("2026-10-29", "2025-10-01")

        assert any("older than 12 months" in p for p in check_matrix(old, TODAY))
