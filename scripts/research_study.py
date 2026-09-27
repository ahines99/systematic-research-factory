"""Reproduce the frozen simulation protocol without model calls or live data."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

from research_factory.config import StatisticalThresholds
from research_factory.data.price_sim import PriceSimParams
from research_factory.data.synthetic import generate_synthetic_world
from research_factory.data.world import filing_to_dict
from research_factory.demo import demo_experiment
from research_factory.domain.project_models import TimingBasis, UniverseMode
from research_factory.research.backtest import run_backtest
from research_factory.research.features import build_features, get_feature, rebalance_sessions
from research_factory.research.leakage import audit_leakage
from research_factory.research.statistics import deflated_sharpe_at, statistical_review
from research_factory.workflows.execution import runtime_identity

ROOT = Path(__file__).resolve().parents[1]
VARIANTS: dict[str, dict[str, Any]] = {
    "clean": {},
    "period_end_leak": {"timing": "period_end"},
    "cost_0": {"cost": 0},
    "cost_10": {"cost": 10},
    "cost_25": {"cost": 25},
    "extra_day": {"extra_lag": 1},
    "quantile_10": {"quantile": 0.1},
    "quantile_30": {"quantile": 0.3},
    "hold_10": {"hold": 10},
    "hold_40": {"hold": 40},
}


def return_metrics(net: np.ndarray) -> dict[str, float]:
    """Compounded wealth includes initial capital when calculating drawdown."""
    if not len(net) or not np.isfinite(net).all() or np.any(net <= -1):
        raise ValueError("study requires finite, nonempty simple returns above -100%")
    wealth = np.r_[1.0, np.cumprod(1.0 + net)]
    drawdown = wealth / np.maximum.accumulate(wealth) - 1.0
    return {
        "cumulative_return": float(wealth[-1] - 1.0),
        "max_drawdown": float(drawdown.min()),
        "annualized_mean": float(net.mean() * 252),
        "annualized_volatility": float(net.std() * math.sqrt(252)),
    }


def wilson(successes: int, total: int) -> list[float]:
    """Wilson score interval; fixed 95% normal quantile, no asymptotic zero-width endpoints."""
    if total <= 0 or not 0 <= successes <= total:
        raise ValueError("invalid binomial counts")
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total**2)) / denominator
    return [max(0.0, center - radius), min(1.0, center + radius)]


def run_study(development: bool) -> dict[str, Any]:
    seeds = range(101, 103) if development else range(200, 220)
    start = "2019-06-03" if development else "2022-01-03"
    end = "2021-12-31" if development else "2023-12-29"
    records: list[dict[str, Any]] = []
    for seed in seeds:
        for control in ("null", "planted"):
            params = PriceSimParams(seed=seed)
            if control == "null":
                params = replace(params, jump_beta=0.0, drift_gamma=0.0)
            dataset = generate_synthetic_world(seed=seed, sim=params)
            variants = (
                VARIANTS if control == "planted" and not development else dict(list(VARIANTS.items())[:2])
            )
            for name, variant in variants.items():
                experiment = demo_experiment(
                    f"study-{control}-{seed}-{name}",
                    start=start,
                    end=end,
                    timing=variant.get("timing", "acceptance"),
                    cost=variant.get("cost", 5),
                    hold=variant.get("hold", 20),
                )
                spec = experiment.backtest.model_copy(update={"quantile": variant.get("quantile", 0.2)})
                table = build_features(
                    dataset,
                    feature="eps_yoy_change",
                    timing_basis=TimingBasis(variant.get("timing", "acceptance")),
                    universe_mode=UniverseMode.POINT_IN_TIME,
                    sessions=rebalance_sessions(dataset, spec.start, spec.end, spec.hold_days),
                    filings_evidence_id="study-filings:" + dataset.content_hash,
                    prices_evidence_id="study-prices:" + dataset.content_hash,
                )
                result = run_backtest(dataset, table, spec, extra_lag_sessions=variant.get("extra_lag", 0))
                delayed = run_backtest(
                    dataset, table, spec, extra_lag_sessions=variant.get("extra_lag", 0) + 1
                )
                audit = audit_leakage(
                    feature_doc=table.to_document(dataset),
                    backtest_doc=result.to_document(dataset),
                    filings_doc=[filing_to_dict(f) for f in dataset.filings],
                    dataset=dataset,
                    input_sources=get_feature("eps_yoy_change").input_sources,
                )
                statistics = statistical_review(
                    result.net,
                    result.gross,
                    hold_days=spec.hold_days,
                    ic_values=[r["ic"] for r in result.ic_by_decision],
                    turnover=[r["turnover"] for r in result.turnover],
                    trial_sharpes=[],
                    n_trials=10,
                    thresholds=StatisticalThresholds(),
                    delay_net=delayed.net,
                ).to_document()
                eligible = np.sum(table.universe & np.isfinite(table.values), axis=1)
                k = np.floor(eligible * spec.quantile)
                intended_weights = 0.5 / k[k > 0]
                record = {
                    "seed": seed,
                    "control": control,
                    "variant": name,
                    "dataset_sha256": dataset.content_hash,
                    "spec": spec.model_dump(mode="json"),
                    "extra_lag_sessions": variant.get("extra_lag", 0),
                    "metrics": {
                        **return_metrics(result.net),
                        "sharpe": statistics["sharpe_annualized"],
                        "mean_turnover": statistics["turnover_mean"],
                        "annualized_cost_drag": statistics["cost_drag_annualized"],
                        "mean_intended_max_abs_weight": float(intended_weights.mean()),
                        "max_intended_abs_weight": float(intended_weights.max()),
                        "unfilled_orders": len(result.unfilled_orders),
                    },
                    "statistics": statistics,
                    "dsr_trial_sensitivity": {
                        str(n): deflated_sharpe_at(statistics, n) for n in (1, 10, 100)
                    },
                    "leakage_blocking": audit.blocking,
                    "audit": audit.to_document(),
                    "sessions": [dataset.day(t).isoformat() for t in result.sessions],
                    "net": result.net.tolist(),
                }
                records.append(record)
        print(f"completed seed {seed}", flush=True)
    summaries = []
    for control, variant in sorted({(r["control"], r["variant"]) for r in records}):
        rows = [r for r in records if (r["control"], r["variant"]) == (control, variant)]
        sharpes = [r["metrics"]["sharpe"] for r in rows]
        blocked = sum(r["leakage_blocking"] for r in rows)
        passes = sum(r["statistics"]["passed"] and not r["leakage_blocking"] for r in rows)
        summaries.append(
            {
                "control": control,
                "variant": variant,
                "worlds": len(rows),
                "median_sharpe": float(np.median(sharpes)),
                "min_sharpe": min(sharpes),
                "max_sharpe": max(sharpes),
                "median_return": float(np.median([r["metrics"]["cumulative_return"] for r in rows])),
                "median_max_drawdown": float(np.median([r["metrics"]["max_drawdown"] for r in rows])),
                "audit_blocks": blocked,
                "audit_block_wilson_95": wilson(blocked, len(rows)),
                "combined_gate_passes": passes,
                "gate_pass_wilson_95": wilson(passes, len(rows)),
            }
        )
    return {
        "format": "rsf-simulation-study/1",
        "phase": "development" if development else "evaluation",
        "prices_simulated": True,
        "protocol_sha256": hashlib.sha256(
            (ROOT / "docs/research/protocol.md").read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
        "runtime": runtime_identity(),
        "seeds": list(seeds),
        "records": records,
        "summary": summaries,
        "deviations": [],
    }


def charts(study: dict[str, Any], out: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "svg.hashsalt": "rsf-study-v1"})
    records = study["records"]
    groups = [("null", "clean"), ("planted", "clean"), ("planted", "period_end_leak")]
    labels = ["No planted signal", "Clean timing", "Invalid period-end timing"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout="constrained")
    for j, (group, label) in enumerate(zip(groups, labels, strict=True)):
        rows = [r for r in records if (r["control"], r["variant"]) == group]
        values = [r["metrics"]["sharpe"] for r in rows]
        axes[0].scatter(np.full(len(values), j), values, alpha=0.65, s=24)
        axes[0].plot([j - 0.2, j + 0.2], [np.median(values)] * 2, color="#162d45", linewidth=3)
        equity = np.array([np.cumprod(1 + np.array(r["net"])) for r in rows])
        axes[1].plot(np.median(equity, axis=0), label=label)
    axes[0].set(
        xticks=range(3),
        xticklabels=["Null", "Clean", "Leaky (invalid)"],
        ylabel="Annualized net Sharpe",
        title="Every evaluation seed; line = median",
    )
    axes[0].axhline(0, color="#777777", linewidth=0.8)
    axes[1].set(
        xlabel="Session from first execution",
        ylabel="Median simulated wealth (initial 1)",
        title="Pointwise median paths, not one investable portfolio",
    )
    axes[1].legend(fontsize=8)
    fig.suptitle("SIMULATED PRICES · Frozen evaluation worlds · No real-return claim", fontsize=12)
    for extension in ("svg", "png"):
        fig.savefig(
            out / f"controls.{extension}", dpi=160, metadata={"Date": None} if extension == "svg" else None
        )
    plt.close(fig)
    summaries = [
        r for r in study["summary"] if r["control"] == "planted" and r["variant"] != "period_end_leak"
    ]
    fig, ax = plt.subplots(figsize=(9, 5), layout="constrained")
    medians = [r["median_sharpe"] for r in summaries]
    ax.errorbar(
        medians,
        range(len(medians)),
        xerr=[
            [m - r["min_sharpe"] for m, r in zip(medians, summaries, strict=True)],
            [r["max_sharpe"] - m for m, r in zip(medians, summaries, strict=True)],
        ],
        fmt="o",
        color="#24586d",
        capsize=4,
    )
    ax.set(
        yticks=range(len(summaries)),
        yticklabels=[r["variant"] for r in summaries],
        xlabel="Net Sharpe: median and observed min–max across worlds",
        title="SIMULATED PRICES · Prespecified sensitivity; ranges are not confidence intervals",
    )
    ax.axvline(0, color="#777777", linewidth=0.8)
    for extension in ("svg", "png"):
        fig.savefig(
            out / f"sensitivity.{extension}", dpi=160, metadata={"Date": None} if extension == "svg" else None
        )
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("var/study"))
    parser.add_argument("--development", action="store_true")
    args = parser.parse_args()
    if (args.out / "study.json").exists():
        parser.error("choose a new output directory; preserved results are never overwritten")
    study = run_study(args.development)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "study.json").write_text(
        json.dumps(study, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    with (args.out / "metrics.csv").open("w", encoding="utf-8", newline="") as stream:
        rows = [
            {
                "seed": r["seed"],
                "control": r["control"],
                "variant": r["variant"],
                **r["metrics"],
                "leakage_blocking": r["leakage_blocking"],
                "statistics_pass": r["statistics"]["passed"],
            }
            for r in study["records"]
        ]
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    charts(study, args.out)
    print(json.dumps(study["summary"], indent=2))


if __name__ == "__main__":
    main()
