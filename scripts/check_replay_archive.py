"""Replay a trusted stored archive in its preserved, explicitly selected runtime.

Run this script with the archive's locked environment, not the current checkout's
environment. It never downloads/executes code selected by archive contents.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import tarfile
import tempfile
from pathlib import Path
from typing import Any

import anyio

from research_factory.config import Settings
from research_factory.demo import artifact_hashes, replay_run
from research_factory.services.container import build_services
from research_factory.workflows.execution import runtime_identity


def historical_difference_allowed(step: str, before: dict[str, Any], after: dict[str, Any]) -> bool:
    """Only the observed BLAS reduction drift, never a changed decision or arbitrary tolerance.

    This is a numerical comparison, NOT a byte-identical replay. Archive checksums and
    all other fields remain exact. New or larger differences require investigation.
    """
    if step != "Statistical review":
        return False
    old, new = dict(before), dict(after)
    for document in (old, new):
        document["checks"] = [dict(check) for check in document["checks"]]
    for old_values, new_values, key in (
        (old, new, "newey_west_t"),
        (old["checks"][1], new["checks"][1], "value"),
    ):
        a, b = old_values[key], new_values[key]
        if not isinstance(a, float) or not isinstance(b, float):
            return False
        if not math.isfinite(a) or not math.isfinite(b) or abs(a - b) > 4 * math.ulp(a):
            return False
        new_values[key] = a
    return old == new


async def check(path: Path, cross_host: bool = False) -> None:
    summary = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    if hashlib.sha256(path.read_bytes()).hexdigest() != summary["archive_sha256"]:
        raise ValueError("archive checksum does not match reviewed manifest")
    with tempfile.TemporaryDirectory(prefix="rsf-replay-") as directory:
        root = Path(directory)
        with tarfile.open(path) as archive:
            archive.extractall(root, filter="data")
        baseline = json.loads((root / "baseline.json").read_text(encoding="utf-8"))
        if baseline["runtime"] != runtime_identity():
            raise ValueError("select the preserved source, dependencies, Python and platform before replay")
        services = build_services(
            Settings(database_url=f"sqlite:///{root / 'archive.db'}", blob_store=f"file://{root / 'blobs'}")
        )

        def forbidden(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("archived replay must not call live data or a judgment provider")

        services.dataset = forbidden  # type: ignore[method-assign]
        services.provider.judge = forbidden  # type: ignore[method-assign]
        differences = []
        try:
            assert len(baseline["scenarios"]) == 6
            for name, scenario in baseline["scenarios"].items():
                run_id = scenario["run_id"]
                assert artifact_hashes(services, run_id, 6) == scenario["artifacts"]
                result = await replay_run(services, run_id)
                if not result.identical:
                    for step, (before, after) in result.compared.items():
                        if before != after:
                            old = services.repos.steps.get(run_id, step)
                            new = services.repos.steps.get(result.replay_run_id, step)
                            assert old is not None
                            assert new is not None
                            assert old.artifact_evidence_id is not None
                            assert new.artifact_evidence_id is not None
                            old_doc = services.evidence.load_json(old.artifact_evidence_id)
                            new_doc = services.evidence.load_json(new.artifact_evidence_id)
                            assert cross_host
                            assert historical_difference_allowed(step, old_doc, new_doc)
                            differences.append(
                                {"scenario": name, "step": step, "before": before, "after": after}
                            )
                            print(
                                json.dumps(
                                    {
                                        "scenario": name,
                                        "step": step,
                                        "differences": {
                                            key: [old_doc.get(key), new_doc.get(key)]
                                            for key in old_doc.keys() | new_doc.keys()
                                            if old_doc.get(key) != new_doc.get(key)
                                        },
                                    },
                                    sort_keys=True,
                                )
                            )
                if not cross_host:
                    assert result.identical, (name, result.compared)
                    assert {key: after for key, (_, after) in result.compared.items()} == scenario[
                        "artifacts"
                    ]
            print(
                json.dumps(
                    {
                        "archive": path.name,
                        "scenarios": 6,
                        "identical": not differences,
                        "comparison": "cross-host" if cross_host else "exact",
                        "differences": differences,
                    }
                )
            )
        finally:
            services.engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument(
        "--cross-host",
        action="store_true",
        help="Allow only documented <=4 ULP HAC reduction drift; never claim exact replay",
    )
    args = parser.parse_args()
    anyio.run(check, args.archive.resolve(), args.cross_host)
