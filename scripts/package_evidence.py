"""Create an explicit release evidence bundle; never include databases, credentials or scratch logs."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def package(
    root: Path, out: Path, revision: str, distributions: Path, scorecard: Path, reports: Path
) -> None:
    if out.exists():
        raise ValueError("refusing to overwrite an evidence bundle")
    inputs = [(path, Path(path.name)) for path in sorted(distributions.glob("*.whl"))]
    inputs += [(path, Path(path.name)) for path in sorted(distributions.glob("*.tar.gz"))]
    if len(inputs) != 2:
        raise ValueError("exactly one wheel and one source distribution are required")
    inputs.append((scorecard, Path("evaluation/scorecard.json")))
    inputs.append((reports / "manifest.json", Path("demo/manifest.json")))
    for name in (
        "clean-approved",
        "leak-caught",
        "survivorship-caught",
        "overfit-rejected",
        "real-filings",
        "fault-survived",
    ):
        inputs.append((reports / f"{name}.html", Path(f"demo/{name}.html")))
    for relative in (
        "docs/research/protocol.md",
        "docs/research/note.md",
        "docs/research/data-sheet.md",
        "docs/research/results/study.json",
        "docs/research/results/metrics.csv",
        "docs/research/results/controls.svg",
        "docs/research/results/sensitivity.svg",
        "docs/CASE_STUDY.md",
        "docs/PORTFOLIO_STATUS.md",
        "docs/security-risk-register.md",
    ):
        inputs.append((root / relative, Path(relative)))
    # Only reviewed public evidence trees; never collect var/, databases or env files.
    for directory in ("docs/live-evaluation", "docs/operations"):
        for source in sorted((root / directory).rglob("*")):
            if source.is_file() and source.suffix in {".json", ".md", ".png", ".txt"}:
                inputs.append((source, source.relative_to(root)))
    inputs.append((root / "docs/live-evaluation-protocol.md", Path("docs/live-evaluation-protocol.md")))
    for source, _ in inputs:
        if not source.is_file() or source.is_symlink():
            raise ValueError(f"required regular evidence file missing: {source}")
    result = json.loads(scorecard.read_text(encoding="utf-8"))
    if result["passed"] != result["total"] or result["provider"] != "rules":
        raise ValueError("bundle requires a passing rules scorecard; live results are separate evidence")
    out.mkdir(parents=True)
    files = []
    for source, relative in inputs:
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        files.append(
            {
                "path": relative.as_posix(),
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "bytes": target.stat().st_size,
            }
        )
    manifest = {
        "format": "rsf-release-evidence/1",
        "source_revision": revision,
        "live_model_evidence": any("docs/live-evaluation/" in relative.as_posix() for _, relative in inputs),
        "files": files,
    }
    (out / "evidence-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    entries = [f"{item['sha256']}  {item['path']}" for item in files]
    entries.append(
        f"{hashlib.sha256((out / 'evidence-manifest.json').read_bytes()).hexdigest()}  evidence-manifest.json"
    )
    (out / "SHA256SUMS").write_text("\n".join(entries) + "\n", encoding="utf-8")
    shutil.make_archive(str(out), "zip", root_dir=out)
    print(f"created {out}.zip with {len(files)} checksummed evidence files")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--distributions", type=Path, required=True)
    parser.add_argument("--scorecard", type=Path, required=True)
    parser.add_argument("--reports", type=Path, required=True)
    args = parser.parse_args()
    package(
        Path(__file__).resolve().parents[1],
        args.out,
        args.source_revision,
        args.distributions,
        args.scorecard,
        args.reports,
    )
