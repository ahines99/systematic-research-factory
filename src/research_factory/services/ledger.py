"""Research ledger (RSF-007, RSF-015): frozen experiments and honest trial counting.

Every distinct experiment registered in a research family is a trial. Changing any field
of a hypothesis or backtest spec produces a new experiment ID and therefore a new trial;
there is no way to edit an experiment in place.
"""

from __future__ import annotations

from typing import Any

from ..domain.clock import Clock
from ..domain.errors import ConflictError, HypothesisFrozenError, NotFoundError
from ..domain.project_models import Experiment, ExperimentRecord, experiment_id_for
from ..persistence.repositories import ExperimentRepository
from .audit import AuditLog


class ResearchLedger:
    def __init__(self, repo: ExperimentRepository, audit: AuditLog, clock: Clock):
        self.repo = repo
        self.audit = audit
        self.clock = clock

    def freeze(self, experiment: Experiment, created_by: str) -> tuple[ExperimentRecord, bool]:
        """Register an experiment. Returns (record, created). Re-freezing is idempotent."""
        existing = self.repo.get(experiment.experiment_id)
        if existing is not None:
            return existing, False
        family = experiment.hypothesis.research_family
        for _ in range(5):
            record = ExperimentRecord(
                experiment_id=experiment.experiment_id,
                research_family=family,
                trial_number=self.repo.count_in_family(family) + 1,
                experiment=experiment,
                created_by=created_by,
                created_at=self.clock.now(),
            )
            try:
                self.repo.add(record)
            except ConflictError:
                again = self.repo.get(experiment.experiment_id)
                if again is not None:
                    return again, False
                continue  # a concurrent freeze took our trial number; retry
            self.audit.append(
                run_id=None,
                step="Hypothesis freeze",
                event_type="experiment_frozen",
                actor=created_by,
                payload={
                    "experiment_id": record.experiment_id,
                    "research_family": family,
                    "trial_number": record.trial_number,
                    "hypothesis_id": experiment.hypothesis.hypothesis_id,
                },
            )
            return record, True
        raise ConflictError("could not allocate a trial number; try again")

    def get(self, experiment_id: str) -> ExperimentRecord:
        record = self.repo.get(experiment_id)
        if record is None:
            raise NotFoundError(f"experiment {experiment_id} is not in the ledger")
        return record

    def verify(self, experiment_id: str, document: dict[str, Any]) -> Experiment:
        """Reject any attempt to present a modified document under an existing experiment ID."""
        experiment = Experiment.model_validate(document)
        actual = experiment_id_for(experiment.hypothesis, experiment.backtest)
        if actual != experiment_id:
            raise HypothesisFrozenError(
                "document does not match the frozen experiment; changes require a new experiment ID",
                details={"claimed": experiment_id, "actual": actual},
            )
        return experiment

    def trial_count(self, research_family: str) -> int:
        return self.repo.count_in_family(research_family)

    def trial_sharpes(self, research_family: str) -> list[float]:
        return self.repo.family_sharpes(research_family)

    def trial_context(self, experiment_id: str) -> tuple[int, list[float]]:
        """Trials in the family as of this experiment's freeze: (trial count, earlier results).

        Deterministic: later experiments never change an earlier experiment's review.
        """
        record = self.get(experiment_id)
        sharpes = self.repo.family_sharpes(
            record.research_family, max_trial=record.trial_number - 1, recorded_before=record.created_at
        )
        return record.trial_number, sharpes

    def review_trial_count(self, experiment_id: str) -> tuple[int, str]:
        """Related trials that exist *now* (ADR-0008).

        The larger of: trials in the experiment's research family, and trials anywhere that
        test the same feature on the same dataset. Renaming a family cannot reset the count.
        """
        record = self.get(experiment_id)
        hyp = record.experiment.hypothesis
        family = self.repo.count_in_family(record.research_family)
        related = sum(
            1
            for r in self.repo.list_all()
            if r.experiment.hypothesis.feature.name == hyp.feature.name
            and r.experiment.hypothesis.universe.dataset == hyp.universe.dataset
        )
        detail = f"{family} in family '{record.research_family}', {related} testing {hyp.feature.name} on {hyp.universe.dataset}"
        return max(family, related), detail

    def record_result(self, experiment_id: str, sharpe_per_period: float, n_obs: int) -> None:
        self.repo.record_result(experiment_id, sharpe_per_period, n_obs, self.clock.now())
