"""Independent hand checks for the new study summaries; core models have their own tests."""

from __future__ import annotations

import runpy
from pathlib import Path

import numpy as np
import pytest

STUDY = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/research_study.py"))


def test_drawdown_includes_initial_capital_and_compounds() -> None:
    result = STUDY["return_metrics"](np.array([-0.1, 0.1]))
    assert result["cumulative_return"] == pytest.approx(-0.01)
    assert result["max_drawdown"] == pytest.approx(-0.1)
    assert result["annualized_mean"] == pytest.approx(0)


def test_study_rejects_invalid_returns() -> None:
    for returns in ([], [np.nan], [-1.0], [np.inf]):
        with pytest.raises(ValueError, match="finite, nonempty"):
            STUDY["return_metrics"](np.array(returns))


def test_wilson_interval_retains_uncertainty_at_boundaries() -> None:
    assert STUDY["wilson"](0, 20) == pytest.approx([0, 0.161125158])
    assert STUDY["wilson"](20, 20) == pytest.approx([0.838874842, 1])
    assert len(STUDY["VARIANTS"]) == 10
