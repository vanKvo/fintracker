"""Convert an AI-assistant evaluation result JSON into an .xlsx workbook (opens in Numbers/Excel).

Usage: python3 scripts/eval_results_to_xlsx.py <result.json> [output.xlsx]

Standard library only. Sheets: Run, Fixtures, Calls, Errors, Dropped items, Error causes, Summaries.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


def col_letter(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def sheet_xml(rows: list[list]) -> str:
    out = []
    for r, row in enumerate(rows, 1):
        cells = []
        for c, v in enumerate(row):
            ref = f"{col_letter(c)}{r}"
            style = ' s="1"' if r == 1 else ' s="2"'
            if isinstance(v, bool) or v is None:
                v = "" if v is None else str(v)
            if isinstance(v, (int, float)):
                cells.append(f'<c r="{ref}"{style}><v>{v}</v></c>')
            else:
                text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(v))[:32000]
                cells.append(f'<c r="{ref}"{style} t="inlineStr"><is><t xml:space="preserve">{escape(text)}</t></is></c>')
        out.append(f'<row r="{r}">{"".join(cells)}</row>')
    width = max((len(r) for r in rows), default=1)
    cols = "".join(f'<col min="{i}" max="{i}" width="28" customWidth="1"/>' for i in range(1, width + 1))
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        f"<cols>{cols}</cols><sheetData>{''.join(out)}</sheetData></worksheet>"
    )


STYLES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
    '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>'
    '<fill><patternFill patternType="solid"><fgColor rgb="FFD9E1F2"/></patternFill></fill></fills>'
    '<borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs>'
    '<cellXfs count="3"><xf/><xf fontId="1" fillId="2" applyFont="1" applyFill="1"/>'
    '<xf applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf></cellXfs></styleSheet>'
)


def write_xlsx(path: Path, sheets: dict[str, list[list]]) -> None:
    names = list(sheets)
    with ZipFile(path, "w", ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            + "".join(
                f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                for i in range(1, len(names) + 1)
            )
            + "</Types>",
        )
        z.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        )
        z.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
            + "".join(f'<sheet name="{escape(n)}" sheetId="{i}" r:id="rId{i}"/>' for i, n in enumerate(names, 1))
            + "</sheets></workbook>",
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(
                f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
                for i in range(1, len(names) + 1)
            )
            + f'<Relationship Id="rId{len(names) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
        )
        z.writestr("xl/styles.xml", STYLES)
        for i, n in enumerate(names, 1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", sheet_xml(sheets[n]))


def classify(reason: str) -> str:
    """Group a validation error message into a short cause label."""
    if "String should match pattern '^ins_" in reason:
        return "Schema: insight id not in ins_<number> format"
    if "Input should be" in reason and ".type" in reason:
        return "Schema: invalid insight type (not in allowed list)"
    if "Input should be a valid string" in reason:
        return "Schema: field null/not a string"
    if "is a number, amount or percentage" in reason:
        return "Grounding: literal number in text instead of {{path}} token"
    if "impact_ref" in reason and "not a numeric field" in reason:
        return "Grounding: impact_ref is a {{token}} or non-numeric path"
    if "evidence" in reason and "does not exist or is null" in reason:
        return "Grounding: evidence path wrapped in {{}} or missing in FACTS"
    if "is not a numeric field in FACTS" in reason:
        return "Grounding: invented/wrong {{path}} token in text"
    if "needs FACTS" in reason:
        return "Grounding: insight for data that is absent (e.g. no budgets)"
    return "Other: " + reason[:60]


def main() -> None:
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".xlsx")
    d = json.loads(src.read_text())
    totals = d.get("totals", {})

    run = [["Field", "Value"]]
    for k in ("tier", "model_id", "prompt_template_version", "output_schema_version", "facts_schema_version",
              "version_key", "temperature", "max_tokens", "runs_per_fixture", "cap_usd", "deadline_s",
              "started_at", "finished_at", "status", "passed", "run_failures"):
        v = d.get(k)
        run.append([k, ", ".join(v) if isinstance(v, list) else v])
    for k, v in totals.items():
        if isinstance(v, dict):
            v = json.dumps(v)
        run.append([f"totals.{k}", v])

    fixtures = [["fixture", "run", "outcome", "retries", "calls", "input_tokens", "output_tokens", "cost_usd",
                 "insight_types_kept", "dropped_items", "failures", "headline", "n_insights", "n_recommendations"]]
    calls = [["fixture", "attempt", "call_outcome", "validation_outcome", "validation_reason", "latency_ms",
              "bedrock_latency_ms", "input_tokens", "output_tokens", "truncated", "validation_retry", "error_count"]]
    errors = [["fixture", "outcome", "attempt", "validation_outcome", "category", "error"]]
    dropped = [["fixture", "call", "section", "index", "item_id", "reasons", "dropped item"]]
    summaries = [["fixture", "headline", "kind", "id/metric", "type/severity", "title/action", "detail/rationale", "evidence/impact_ref"]]
    causes = Counter()
    fixtures_by_cause: dict[str, set] = {}

    for r in d["rows"]:
        s = r.get("summary") or {}
        fixtures.append([
            r["fixture"], r["run"], r["outcome"], r["retries"], len(r["calls"]), r["input_tokens"],
            r["output_tokens"], r["cost_usd"], ", ".join(r["insight_types"]), len(r["dropped"]),
            ", ".join(r["failures"]), s.get("headline", ""), len(s.get("insights", [])),
            len(s.get("recommendations", [])),
        ])
        for c in r["calls"]:
            calls.append([r["fixture"], c["attempt"], c["call_outcome"], c["validation_outcome"],
                          c["validation_reason"], c["latency_ms"], c["bedrock_latency_ms"], c["input_tokens"],
                          c["output_tokens"], c["truncated"], c["validation_retry"], len(c["validation_errors"])])
            for e in c["validation_errors"]:
                cat = classify(e)
                errors.append([r["fixture"], r["outcome"], c["attempt"], c["validation_outcome"], cat, e])
                causes[cat] += 1
                fixtures_by_cause.setdefault(cat, set()).add(r["fixture"])
        for x in r["dropped"]:
            dropped.append([r["fixture"], x.get("call"), x["section"], x["index"], x["item_id"],
                            " | ".join(x["reasons"]), json.dumps(x["item"], ensure_ascii=False)])
        if s:
            summaries.append([r["fixture"], s.get("headline", ""), "", "", "", "", "", ""])
            for h in s.get("highlights", []):
                summaries.append([r["fixture"], "", "highlight", h.get("metric_id"), "", "", h.get("commentary"), ""])
            for i in s.get("insights", []):
                summaries.append([r["fixture"], "", "insight", i.get("id"), f'{i.get("type")} / {i.get("severity")}',
                                  i.get("title"), i.get("detail"), ", ".join(i.get("evidence", []))])
            for rec in s.get("recommendations", []):
                summaries.append([r["fixture"], "", "recommendation", rec.get("related_insight_id"), "",
                                  rec.get("action"), rec.get("rationale"), rec.get("impact_ref")])

    cause_rows = [["cause", "error count", "fixtures affected", "fixtures"]]
    for cat, n in causes.most_common():
        fx = sorted(fixtures_by_cause[cat])
        cause_rows.append([cat, n, len(fx), ", ".join(fx)])

    write_xlsx(dst, {"Run": run, "Fixtures": fixtures, "Error causes": cause_rows, "Errors": errors,
                     "Calls": calls, "Dropped items": dropped, "Summaries": summaries})
    print(f"Wrote {dst}")


if __name__ == "__main__":
    main()
