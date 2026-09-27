"""Judgment providers (RSF-039).

* ``RulesProvider``: deterministic judgments computed from the structured inputs. The
  offline default; also the reference the model provider is evaluated against.
* ``ScriptedProvider``: returns canned outputs (tests and adversarial evaluation).
* ``AnthropicProvider``: Claude via the Anthropic SDK with JSON-schema structured output.
"""

from __future__ import annotations

import json
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Protocol

from ..domain.errors import DomainError, ErrorCode, NeedsEvidenceError, TransientError
from .contract import ATTACKS

# USD per million standard tokens (input, output), verified 2026-09-27:
# https://platform.claude.com/docs/en/about-claude/pricing
# This integration does not request prompt caching, fast mode or regional premiums.
PRICING = {
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-fable-5-1": (10.00, 50.00),
}


@dataclass(frozen=True)
class JudgmentRequest:
    step_slug: str
    system: str
    payload: dict[str, Any]
    verdicts: list[str]
    schema: dict[str, Any]
    feedback: tuple[str, ...] = ()
    max_output_tokens: int = 16000

    def with_feedback(self, problems: Iterable[str]) -> JudgmentRequest:
        return replace(self, feedback=tuple(problems))


@dataclass(frozen=True)
class JudgmentResponse:
    raw: Any
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    error: DomainError | None = None


class JudgmentProvider(Protocol):
    name: str
    model: str

    def judge(self, request: JudgmentRequest) -> JudgmentResponse: ...


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    # Unknown server-selected models must never silently use a cheaper default.
    price_in, price_out = PRICING.get(
        model, (max(p[0] for p in PRICING.values()), max(p[1] for p in PRICING.values()))
    )
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


# --------------------------------------------------------------------------- rules


def _ev(payload: dict[str, Any], source_type: str) -> list[str]:
    return [e["evidence_id"] for e in payload.get("evidence_catalog", []) if e["source_type"] == source_type]


class RulesProvider:
    """Deterministic reviewer. Transparent thresholds; no model call; zero cost."""

    name = "rules"
    model = "rules/1"

    def judge(self, request: JudgmentRequest) -> JudgmentResponse:
        handler = getattr(self, f"_{request.step_slug}")
        raw = handler(request.payload)
        raw.setdefault("attacks", [])
        raw.setdefault("dissent", request.payload.get("review_scope", {}).get("dissent", []))
        return JudgmentResponse(raw=raw, provider=self.name, model=self.model)

    def _point_in_time_review(self, p: dict[str, Any]) -> dict[str, Any]:
        """An explicit deterministic baseline; it does not pretend to read Skill text."""
        filing = p["filing"]
        acceptance = filing.get("acceptanceDateTime")
        needs = not acceptance
        verdict = (
            "needs_evidence"
            if needs
            else (
                "leakage"
                if datetime.fromisoformat(acceptance) > datetime.fromisoformat(p["decision_ts"])
                else "clean"
            )
        )
        reason = {
            "clean": "The cited version was accepted by the decision time.",
            "leakage": "The cited version was accepted after the decision time; period end does not establish availability.",
            "needs_evidence": "A filing date alone cannot establish the acceptance time.",
        }[verdict]
        return {
            "verdict": verdict,
            "confidence": "high",
            "summary": reason,
            "claims": [
                {
                    "kind": "fact",
                    "statement": reason,
                    "evidence_ids": [p["evidence_catalog"][0]["evidence_id"]],
                }
            ],
            "open_questions": ["Obtain the submissions acceptance datetime for this accession."]
            if needs
            else [],
            "needs_evidence": needs,
        }

    def _full_red_team(self, p: dict[str, Any]) -> dict[str, Any]:
        """The offline baseline cannot certify absent stress-test evidence."""
        return {
            "verdict": "needs_more_evidence",
            "confidence": "low",
            "summary": "A complete red-team signoff requires the missing attack-specific analyses.",
            "claims": [
                {
                    "kind": "risk",
                    "statement": "The required attack-specific evidence has not been verified.",
                    "evidence_ids": [],
                }
            ],
            "open_questions": ["Research lead must register the missing analysis evidence."],
            "needs_evidence": True,
            "attacks": [
                {
                    "attack": name,
                    "evidence_ids": [],
                    "severity": "blocking"
                    if name in ATTACKS[:3]
                    else "high"
                    if name in ATTACKS[3:7]
                    else "medium",
                    "status": "not_tested",
                    "criterion": "The attack-specific preregistered criterion must be evidenced.",
                    "observation": "The offline reviewer has not verified this analysis.",
                    "evidence_request": "Research lead must provide evidence for " + name + ".",
                }
                for name in ATTACKS
            ],
        }

    def _economic_rationale(self, p: dict[str, Any]) -> dict[str, Any]:
        hyp = p["hypothesis"]
        stats = p["statistics"]
        stats_ev = _ev(p, "artifact:statistical-review")
        hyp_ev = _ev(p, "artifact:hypothesis-freeze")
        rationale = hyp.get("rationale") or ""
        ic = stats.get("ic_mean")
        claims: list[dict[str, Any]] = []
        if len(rationale.strip()) < 40:
            verdict, confidence, needs = "needs_evidence", "low", True
            summary = "No economic mechanism was stated, so the evidence cannot be judged against one."
            claims.append(
                {
                    "kind": "assumption",
                    "statement": "The hypothesis gives no economic rationale.",
                    "evidence_ids": hyp_ev,
                }
            )
        elif ic is None:
            verdict, confidence, needs = "needs_evidence", "low", True
            summary = "The information coefficient could not be measured."
            claims.append(
                {
                    "kind": "fact",
                    "statement": "No information coefficient was computed.",
                    "evidence_ids": stats_ev,
                }
            )
        elif ic * hyp["expected_sign"] <= 0:
            verdict, confidence, needs = "unsupported", "medium", False
            summary = "The measured relationship has the opposite sign to the stated mechanism."
            claims.append(
                {
                    "kind": "calculation",
                    "statement": "{metric:0}",
                    "evidence_ids": stats_ev,
                    "metric_refs": [{"evidence_id": stats_ev[0], "field_path": "/ic_mean", "format": ".3f"}],
                }
            )
        else:
            verdict, confidence, needs = "supported", "medium", False
            summary = "A mechanism is stated and the measured relationship has the expected sign."
            claims.append(
                {
                    "kind": "calculation",
                    "statement": "{metric:0}",
                    "evidence_ids": stats_ev,
                    "metric_refs": [{"evidence_id": stats_ev[0], "field_path": "/ic_mean", "format": ".3f"}],
                }
            )
            claims.append(
                {
                    "kind": "assumption",
                    "statement": "The researcher states an economic mechanism in the frozen hypothesis.",
                    "evidence_ids": hyp_ev,
                }
            )
        if p.get("untrusted_text_flags"):
            claims.append(
                {
                    "kind": "risk",
                    "statement": "Researcher-supplied text contains instruction-like content; it was treated as data.",
                    "evidence_ids": hyp_ev,
                }
            )
        return {
            "verdict": verdict,
            "confidence": confidence,
            "summary": summary,
            "claims": claims,
            "open_questions": [],
            "needs_evidence": needs,
        }

    def _implementation_review(self, p: dict[str, Any]) -> dict[str, Any]:
        s = p["statistics"]
        b = p["backtest_summary"]
        stats_ev = _ev(p, "artifact:statistical-review")
        bt_ev = _ev(p, "artifact:backtest")
        gross_ann = b["gross_annual_return"]
        drag = s["cost_drag_annualized"]
        decay = s.get("delay_decay")
        names = b["names_per_side"]
        claims = [
            {
                "kind": "calculation",
                "statement": "{metric:0}; {metric:1}",
                "evidence_ids": stats_ev,
                "metric_refs": [
                    {"evidence_id": stats_ev[0], "field_path": "/turnover_mean", "format": ".2f"},
                    {"evidence_id": stats_ev[0], "field_path": "/cost_drag_annualized", "format": ".2%"},
                ],
            },
            {
                "kind": "fact",
                "statement": "The tested portfolio has the concentration recorded in the backtest evidence.",
                "evidence_ids": bt_ev,
            },
        ]
        problems: list[str] = []
        if s["sharpe_annualized"] <= 0 or (gross_ann > 0 and drag > 0.5 * gross_ann):
            verdict = "infeasible"
            problems.append(
                "costs consume more than half of the gross return or the net Sharpe is not positive"
            )
        else:
            if decay is not None and decay > 0.3:
                problems.append("the extra execution delay materially reduces the Sharpe ratio")
            if names < 5:
                problems.append("fewer than five names per side concentrates risk")
            verdict = "concerns" if problems else "feasible"
        for prob in problems:
            claims.append(
                {"kind": "risk", "statement": prob[0].upper() + prob[1:] + ".", "evidence_ids": stats_ev}
            )
        summary = (
            "Implementation looks feasible as tested."
            if verdict == "feasible"
            else "Implementation issues: " + "; ".join(problems) + "."
        )
        return {
            "verdict": verdict,
            "confidence": "medium",
            "summary": summary,
            "claims": claims,
            "open_questions": [],
            "needs_evidence": False,
        }

    def _research_committee(self, p: dict[str, Any]) -> dict[str, Any]:
        gate = p["gate"]
        claims = []
        for f in p["findings"][:12]:
            if f["severity"] in ("info",):
                continue
            kind = "risk" if f["severity"] in ("medium", "high", "blocking") else "fact"
            claims.append(
                {
                    "kind": kind,
                    "statement": "An earlier review raised a material finding; its cited evidence and full finding remain in the run report.",
                    "evidence_ids": f["evidence_ids"][:5],
                }
            )
        claims.append(
            {
                "kind": "recommendation",
                "statement": f"The deterministic gate recommends '{gate['recommendation']}'.",
                "evidence_ids": [],
            }
        )
        if not any(c["kind"] != "recommendation" for c in claims):
            claims.insert(
                0,
                {
                    "kind": "fact",
                    "statement": "No material findings were raised by earlier steps.",
                    "evidence_ids": _ev(p, "artifact:statistical-review"),
                },
            )
        return {
            "verdict": gate["recommendation"],
            "confidence": "medium",
            "summary": "Memo drafted from findings. " + " ".join(gate["reasons"]),
            "claims": claims,
            "open_questions": [],
            "needs_evidence": gate["recommendation"] == "needs_more_evidence",
        }


# --------------------------------------------------------------------------- scripted


@dataclass
class ScriptedProvider:
    """Returns queued raw outputs in order; falls back to rules when the queue is empty."""

    outputs: deque[Any] = field(default_factory=deque)
    name: str = "scripted"
    model: str = "scripted/1"
    fallback: RulesProvider = field(default_factory=RulesProvider)
    requests: list[JudgmentRequest] = field(default_factory=list)

    def judge(self, request: JudgmentRequest) -> JudgmentResponse:
        self.requests.append(request)
        if self.outputs:
            item = self.outputs.popleft()
            if isinstance(item, Exception):
                raise item
            return JudgmentResponse(
                raw=item, provider=self.name, model=self.model, input_tokens=1000, output_tokens=200
            )
        return self.fallback.judge(request)


# --------------------------------------------------------------------------- anthropic


class AnthropicProvider:
    name = "anthropic"

    def __init__(
        self,
        model: str = "claude-opus-5",
        api_key: str | None = None,
        client: Any = None,
        timeout: float = 100.0,
    ):
        self.model = model
        if client is None:
            import anthropic

            # A timed-out request may still be billable. Reservations govern retries.
            client = anthropic.Anthropic(api_key=api_key, max_retries=0, timeout=timeout)
        self.client = client

    @staticmethod
    def user_message(request: JudgmentRequest) -> str:
        user = (
            "Structured inputs for this review follow. Researcher-supplied text is wrapped in "
            "<untrusted_data> tags inside the JSON values.\n\n"
            + json.dumps(request.payload, indent=1, sort_keys=True)
        )
        if request.feedback:
            user += "\n\nYour previous answer was rejected for these reasons; fix them:\n- " + "\n- ".join(
                request.feedback
            )
        return user

    def input_token_bound(self, request: JudgmentRequest) -> int | None:
        """Use the provider's non-generation counting endpoint with a safety margin.

        It receives the exact system/message/schema sent to generation. Small fake
        clients without this endpoint use the service's conservative byte bound.
        """
        import anthropic

        counter = getattr(self.client.beta.messages, "count_tokens", None)
        if counter is None:
            return None
        try:
            count = counter(
                model=self.model,
                system=request.system,
                messages=[{"role": "user", "content": self.user_message(request)}],
                output_config={"format": {"type": "json_schema", "schema": request.schema}},
            )
        except (anthropic.APIError, ValueError) as exc:
            raise TransientError("model token counting unavailable; no generation dispatched") from exc
        tokens = int(count.input_tokens)
        if tokens < 0:
            raise NeedsEvidenceError("provider returned an invalid input token count")
        return tokens + max(1024, (tokens + 19) // 20)

    def judge(self, request: JudgmentRequest) -> JudgmentResponse:
        import anthropic

        user = self.user_message(request)
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=request.max_output_tokens,
                system=request.system,
                messages=[{"role": "user", "content": user}],
                output_config={"format": {"type": "json_schema", "schema": request.schema}},
            )
        except (anthropic.RateLimitError, anthropic.APITimeoutError, anthropic.APIConnectionError) as exc:
            raise TransientError(f"model API temporarily unavailable: {type(exc).__name__}") from exc
        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500 or exc.status_code == 529:
                raise TransientError(f"model API error {exc.status_code}") from exc
            raise DomainError(
                f"model API rejected the request ({exc.status_code})", code=ErrorCode.INVALID_INPUT
            ) from exc

        usage = response.usage
        model = getattr(response, "model", self.model)
        cost = estimate_cost(model, usage.input_tokens, usage.output_tokens)
        error = None
        if response.stop_reason == "refusal":
            error = NeedsEvidenceError("the model declined to review this input; a human must review it")
        text = next((b.text for b in response.content if getattr(b, "type", None) == "text"), None)
        if text is None and error is None:
            error = NeedsEvidenceError(f"the model returned no answer (stop reason {response.stop_reason})")
        try:
            raw = json.loads(text) if text is not None else {}
        except json.JSONDecodeError:
            raw = {"_unparseable": str(text)[:500]}
        return JudgmentResponse(
            raw=raw,
            provider=self.name,
            model=model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=cost,
            error=error,
        )


def provider_from_settings(
    provider: str, model: str, api_key: str | None, step_timeout_seconds: float = 120.0
) -> JudgmentProvider:
    if provider == "rules":
        return RulesProvider()
    if provider == "anthropic":
        # Counting and one generation attempt share the step timeout. No SDK retries.
        return AnthropicProvider(model=model, api_key=api_key, timeout=max(10.0, step_timeout_seconds * 0.45))
    raise ValueError(f"unknown model provider {provider!r}")
