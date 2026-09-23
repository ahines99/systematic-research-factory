#!/usr/bin/env python3
"""Check a feature-lineage export for point-in-time (knowledge-time) violations.

Standalone, standard library only, Python 3.12+.

Input: the feature lineage export produced by the Systematic Research Factory
(``build_features`` lineage), as a file path or on stdin::

    {
      "feature": "accruals_ratio",
      "rows": [
        {
          "security_id": "cik:0000000001",
          "decision_ts": "2024-05-03T16:00:00-04:00",
          "value": 0.042,
          "inputs": [
            {"evidence_id": "ev_1a2b3c", "knowledge_ts": "2024-05-02T16:31:07-04:00"}
          ]
        }
      ]
    }

Checks, per row:

* ``lookahead``        an input's ``knowledge_ts`` is strictly later than the row's
                       ``decision_ts`` (the value could not have been known when
                       the decision was made). Equal timestamps are allowed.
* ``naive_timestamp``  ``decision_ts`` or an input ``knowledge_ts`` has no UTC
                       offset. Naive timestamps cannot be compared safely, so the
                       affected comparison is skipped and the row is flagged.
* ``no_inputs``        the row has no inputs, so its knowledge time is unknown.
                       ``--allow-empty-null`` exempts rows whose ``value`` is null.
* ``malformed_row``    a row or input is structurally invalid (missing field,
                       wrong type, unparseable timestamp). Fails closed.

Exit codes:
    0  no violations
    1  one or more violations
    2  bad input (unreadable file, invalid JSON, wrong top-level shape, bad args)

Usage::

    python check_pit_timestamps.py lineage.json
    python check_pit_timestamps.py --json lineage.json
    some_command | python check_pit_timestamps.py -
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

EXIT_CLEAN = 0
EXIT_VIOLATIONS = 1
EXIT_BAD_INPUT = 2

KINDS = ("lookahead", "naive_timestamp", "no_inputs", "malformed_row")


class BadInput(Exception):
    """Input cannot be interpreted as a lineage export at all."""


@dataclass
class Violation:
    kind: str
    row_index: int
    security_id: str | None
    decision_ts: str | None
    detail: str
    evidence_id: str | None = None
    knowledge_ts: str | None = None
    lead_seconds: float | None = None  # knowledge_ts - decision_ts, for lookahead


@dataclass
class Report:
    feature: str
    rows_checked: int = 0
    violating_rows: int = 0
    counts: dict[str, int] = field(default_factory=lambda: {k: 0 for k in KINDS})
    violations: list[Violation] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.violations


def _parse_ts(raw: Any) -> tuple[datetime | None, str | None]:
    """Return (datetime, error). Accepts ISO-8601 incl. a trailing 'Z'."""
    if not isinstance(raw, str) or not raw.strip():
        return None, f"expected ISO-8601 string, got {type(raw).__name__}"
    try:
        return datetime.fromisoformat(raw.strip()), None
    except ValueError as exc:
        return None, f"unparseable timestamp {raw!r}: {exc}"


def _is_naive(ts: datetime) -> bool:
    return ts.tzinfo is None or ts.utcoffset() is None


def _is_valid_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return False
    return isinstance(value, (int, float))


def load(source: str) -> Any:
    try:
        if source == "-":
            text = sys.stdin.read()
        else:
            # utf-8-sig tolerates a BOM (e.g. files written by Windows PowerShell).
            with open(source, encoding="utf-8-sig") as fh:
                text = fh.read()
    except OSError as exc:
        raise BadInput(f"cannot read {source!r}: {exc}") from exc
    text = text.lstrip("﻿")
    if not text.strip():
        raise BadInput("input is empty")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise BadInput(f"invalid JSON: {exc}") from exc


def check(doc: Any, *, allow_empty_null: bool = False) -> Report:
    if not isinstance(doc, dict):
        raise BadInput("top level must be a JSON object with 'feature' and 'rows'")
    feature = doc.get("feature")
    if not isinstance(feature, str) or not feature:
        raise BadInput("'feature' must be a non-empty string")
    rows = doc.get("rows")
    if not isinstance(rows, list):
        raise BadInput("'rows' must be a list")

    report = Report(feature=feature)
    for idx, row in enumerate(rows):
        report.rows_checked += 1
        found = _check_row(idx, row, allow_empty_null=allow_empty_null)
        if found:
            report.violating_rows += 1
            for v in found:
                report.counts[v.kind] += 1
            report.violations.extend(found)
    return report


def _check_row(idx: int, row: Any, *, allow_empty_null: bool) -> list[Violation]:
    if not isinstance(row, dict):
        return [Violation("malformed_row", idx, None, None,
                          f"row is {type(row).__name__}, expected object")]

    sec = row.get("security_id")
    sec_id = sec if isinstance(sec, str) else None
    raw_dec = row.get("decision_ts")
    dec_str = raw_dec if isinstance(raw_dec, str) else None
    out: list[Violation] = []

    def add(kind: str, detail: str, **kw: Any) -> None:
        out.append(Violation(kind, idx, sec_id, dec_str, detail, **kw))

    if not isinstance(sec, str) or not sec:
        add("malformed_row", "missing or non-string 'security_id'")
    if "value" not in row:
        add("malformed_row", "missing 'value' (use null for a missing value)")
    elif not _is_valid_value(row["value"]):
        add("malformed_row", f"'value' must be a number or null, got {row['value']!r}")

    decision, err = _parse_ts(raw_dec)
    if err:
        add("malformed_row", f"decision_ts: {err}")
    elif decision is not None and _is_naive(decision):
        add("naive_timestamp", "decision_ts has no UTC offset")
        decision = None  # cannot compare safely

    inputs = row.get("inputs")
    if inputs is None or inputs == []:
        value_is_null = row.get("value") is None
        if not (allow_empty_null and value_is_null):
            add("no_inputs", "row has no inputs; knowledge time is unknown")
        return out
    if not isinstance(inputs, list):
        add("malformed_row", f"'inputs' must be a list, got {type(inputs).__name__}")
        return out

    for j, inp in enumerate(inputs):
        if not isinstance(inp, dict):
            add("malformed_row", f"inputs[{j}] is {type(inp).__name__}, expected object")
            continue
        ev = inp.get("evidence_id")
        ev_id = ev if isinstance(ev, str) and ev else None
        if ev_id is None:
            add("malformed_row", f"inputs[{j}] missing or non-string 'evidence_id'")
        raw_k = inp.get("knowledge_ts")
        k_str = raw_k if isinstance(raw_k, str) else None
        known, kerr = _parse_ts(raw_k)
        if kerr:
            add("malformed_row", f"inputs[{j}].knowledge_ts: {kerr}",
                evidence_id=ev_id, knowledge_ts=k_str)
            continue
        assert known is not None
        if _is_naive(known):
            add("naive_timestamp", f"inputs[{j}].knowledge_ts has no UTC offset",
                evidence_id=ev_id, knowledge_ts=k_str)
            continue
        if decision is not None and known > decision:
            lead = (known - decision).total_seconds()
            add("lookahead",
                f"inputs[{j}] known {_fmt_duration(lead)} after decision",
                evidence_id=ev_id, knowledge_ts=k_str, lead_seconds=lead)
    return out


def _fmt_duration(seconds: float) -> str:
    if not math.isfinite(seconds):
        return str(seconds)
    s = int(round(seconds))
    days, rem = divmod(s, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts = [f"{days}d"] if days else []
    parts.append(f"{hours:02d}:{minutes:02d}:{secs:02d}")
    return " ".join(parts)


def render_text(report: Report) -> str:
    lines = [
        f"Feature:        {report.feature}",
        f"Rows checked:   {report.rows_checked}",
        f"Violating rows: {report.violating_rows}",
    ]
    lines += [f"  {kind:<16}{report.counts[kind]}" for kind in KINDS]
    if report.clean:
        lines.append("RESULT: CLEAN - every input knowledge_ts <= decision_ts")
        return "\n".join(lines)
    lines.append("RESULT: VIOLATIONS FOUND")
    lines.append("")
    for v in report.violations:
        where = f"row {v.row_index} security={v.security_id} decision_ts={v.decision_ts}"
        extra = ""
        if v.evidence_id or v.knowledge_ts:
            extra = f" evidence_id={v.evidence_id} knowledge_ts={v.knowledge_ts}"
        lines.append(f"[{v.kind}] {where}{extra}: {v.detail}")
    return "\n".join(lines)


def render_json(report: Report) -> str:
    payload = {
        "feature": report.feature,
        "clean": report.clean,
        "rows_checked": report.rows_checked,
        "violating_rows": report.violating_rows,
        "counts": report.counts,
        "violations": [asdict(v) for v in report.violations],
    }
    return json.dumps(payload, indent=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report point-in-time violations in a feature lineage export.")
    parser.add_argument("path", nargs="?", default="-",
                        help="lineage JSON file, or '-' / omitted for stdin")
    parser.add_argument("--json", action="store_true",
                        help="print machine-readable JSON instead of text")
    parser.add_argument("--allow-empty-null", action="store_true",
                        help="do not flag rows that have no inputs and a null value")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse exits 2 on bad args, 0 on --help
        return int(exc.code) if isinstance(exc.code, int) else EXIT_BAD_INPUT

    if args.path == "-" and sys.stdin.isatty():
        print("error: no input file given and stdin is a terminal", file=sys.stderr)
        return EXIT_BAD_INPUT
    try:
        report = check(load(args.path), allow_empty_null=args.allow_empty_null)
    except BadInput as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}))
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_BAD_INPUT

    print(render_json(report) if args.json else render_text(report))
    return EXIT_CLEAN if report.clean else EXIT_VIOLATIONS


if __name__ == "__main__":
    sys.exit(main())
