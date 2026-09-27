"""Historic CPU drift is narrowly classified, never reported as exact replay."""

import copy
import math
import runpy
from pathlib import Path

from research_factory.workflows.execution import runtime_identity


def test_historical_comparison_rejects_material_or_unrelated_changes() -> None:
    compare = runpy.run_path(str(Path(__file__).parents[1] / "scripts/check_replay_archive.py"))[
        "historical_difference_allowed"
    ]
    before = {
        "newey_west_t": 3.206359668491078,
        "checks": [
            {"name": "min_observations"},
            {"name": "newey_west_t", "value": 3.206359668491078, "passed": True},
        ],
        "passed": False,
    }
    after = copy.deepcopy(before)
    after["newey_west_t"] = 3.206359668491077
    after["checks"][1]["value"] = 3.206359668491077
    assert compare("Statistical review", before, after)
    assert not compare("Backtest", before, after)
    assert before["newey_west_t"] == 3.206359668491078
    after["passed"] = True
    assert not compare("Statistical review", before, after)
    after["passed"] = False
    after["newey_west_t"] = before["newey_west_t"] + 5 * math.ulp(before["newey_west_t"])
    assert not compare("Statistical review", before, after)
    after["newey_west_t"] = float("nan")
    assert not compare("Statistical review", before, after)


def test_runtime_records_patch_and_numerical_backend_without_host_paths() -> None:
    import platform

    runtime = runtime_identity()
    assert runtime["python"] == platform.python_version()
    assert runtime["libc"] == list(platform.libc_ver())
    assert runtime["numpy_simd"]["baseline"]
    assert runtime["numerical_libraries"]
    for library in runtime["numerical_libraries"]:
        assert "filepath" not in library
        assert library["version"]
        assert library["num_threads"] > 0
