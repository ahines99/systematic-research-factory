"""Explicitly archive a reviewed candidate baseline; never invoked by the test suite.

Run on the pinned Linux/Python release runtime after source and Skill content are final.
Keep earlier archives and their source revision/runtime when creating a new baseline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
import tempfile
from pathlib import Path

import anyio

from research_factory.config import Settings
from research_factory.demo import DETERMINISTIC_STEPS, artifact_hashes, record_demo
from research_factory.services.container import build_services
from research_factory.workflows.execution import runtime_identity


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("refusing to replace an existing baseline; create a separately reviewed new archive")
    with tempfile.TemporaryDirectory(prefix="rsf-baseline-") as temp:
        root = Path(temp)
        services = build_services(
            Settings(
                database_url=f"sqlite:///{root / 'archive.db'}",
                blob_store=f"file://{root / 'blobs'}",
                model_provider="rules",
            )
        )
        results = anyio.run(record_demo, services)
        metadata = {
            "format": "rsf-preserved-baseline/1",
            "label": args.label,
            "source_revision": args.source_revision,
            "runtime": runtime_identity(),
            "scenarios": {
                item.scenario: {
                    "run_id": item.run_id,
                    "artifacts": artifact_hashes(services, item.run_id, DETERMINISTIC_STEPS),
                }
                for item in results
            },
        }
        services.engine.dispose()
        (root / "baseline.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(args.output, "w:gz") as archive:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    archive.add(path, arcname=path.relative_to(root), recursive=False)
        summary = metadata | {"archive_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}
        args.output.with_suffix(".json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"archived {len(results)} scenarios to {args.output}")


if __name__ == "__main__":
    main()
