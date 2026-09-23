"""Documentation stays true: generated docs are current, links resolve, cited tests exist."""

from __future__ import annotations

import re
from pathlib import Path

from research_factory.contracts_doc import render

ROOT = Path(__file__).resolve().parents[1]
DOCS = [ROOT / "README.md", ROOT / "IMPLEMENTATION_HANDOFF.md", *(ROOT / "docs").rglob("*.md")]


def test_data_contracts_doc_is_current() -> None:
    committed = (ROOT / "docs" / "data_contracts.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert committed == render(), "run: python -m research_factory.contracts_doc"


def test_relative_links_resolve() -> None:
    broken = []
    for doc in DOCS:
        for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", doc.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if not (doc.parent / target).exists():
                broken.append(f"{doc.relative_to(ROOT)} -> {target}")
    assert not broken, broken


def test_threat_model_cites_real_tests() -> None:
    text = (ROOT / "docs" / "threat_model.md").read_text(encoding="utf-8")
    missing = []
    for file, name in re.findall(r"`(?:tests/)?(test_\w+\.py)::(\w+)`", text):
        source = (ROOT / "tests" / file).read_text(encoding="utf-8")
        if f"def {name}(" not in source:
            missing.append(f"{file}::{name}")
    for name in re.findall(r"`::(\w+)`", text):
        if not any(
            f"def {name}(" in p.read_text(encoding="utf-8") for p in (ROOT / "tests").glob("test_*.py")
        ):
            missing.append(name)
    for case in re.findall(r"golden case `?(\d\d)-", text):
        assert list((ROOT / "evals" / "golden").glob(f"{case}-*.yaml")), case
    assert not missing, missing
