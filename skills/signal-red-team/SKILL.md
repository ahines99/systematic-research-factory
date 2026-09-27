---
name: signal-red-team
description: Adversarially attacks a systematic equity signal before it reaches the research committee in the Systematic Research Factory. Works through leakage, restatement look-ahead, survivorship, data snooping, regime dependence, crowding, capacity, cost sensitivity, concentration in a few names, and sensitivity to execution delay. For each attack it names which MCP tool to ask for evidence and what would refute the attack, and it produces the required red-team table (attack, evidence IDs, severity low|medium|high|blocking, status refuted|unrefuted|not_tested). Use when the red_team_signal(experiment_id) prompt is invoked, when asked to "stress-test", "poke holes in" or "red-team" a signal or backtest, before the Implementation review or Research committee steps, or when a result looks too good.
---

# Signal red team

## Execution modes and available capabilities

The complete procedure below applies to an explicitly assigned **full red-team review**.
Automated economic-rationale/implementation steps are targeted reviews: `review_scope` states
their assigned checks and excludes full red-team signoff. They cannot claim that all attacks
were refuted. A missing material input within the assigned scope requires `needs_evidence=true`.
In `full_red_team` JSON output, populate `attacks` with all ten named attacks, including
`not_tested` rows and actionable `evidence_request` values. Untested high/blocking attacks
require `needs_evidence=true`; unrefuted blocking attacks require `reject`. Numbers are rendered
through calculation `metric_refs`, not invented in criterion/observation prose.

`run_backtest` and `get_statistics` accept **only `experiment_id`**. For supported cost, delay
or date variants, first `freeze_hypothesis` with a modified spec, then pass its new ID to those
tools. Contributor-exclusion and volatility-regime analysis are not current tool capabilities;
request an owner-produced, evidence-registered analysis and mark these `not_tested` meanwhile.
No tool supplies real capacity or factor-return evidence. The playbook describes what would
refute those attacks, not a claim that the current runtime can run every test.

Your job is to **try to break the signal**, not to explain why it works. Assume every good backtest
is wrong until the evidence says otherwise. Every conclusion cites `ev_<hex>` evidence IDs. The
model never computes a statistic: variants and numbers come from `run_backtest`,
`get_statistics`, `audit_leakage` and the other tools.

## Setup
1. Start from `red_team_signal(experiment_id)`, or collect the same context yourself: read
   `project://policies`, then `get_run_report` (or `run://{run_id}`) for the run and its frozen
   hypothesis and backtest spec.
2. Call `get_ledger` (or read `ledger://{research_family}`) for the trial count and history.
3. **Write each refutation criterion down before you look at the result.** For example: "refuted
   if net Sharpe at 2× costs is still > 0 and the break-even cost is ≥ 2× assumed". Changing a
   criterion after seeing the result is data snooping by the red team.
4. Robustness variants (a different delay, costs or subsample) run through `run_backtest`, and each
   one becomes its **own experiment in the ledger**. Label them as red-team checks. A variant is
   never offered as the new result. If a variant looks better, that is a finding about fragility,
   not an improvement.

## Severity and status

**Severity is the impact *if the attack is right*.** Status says whether the evidence refutes it.

| Severity | Meaning |
|---|---|
| `blocking` | If true, the result is invalid: any look-ahead, restatement look-ahead, survivorship, target leakage, or a failed statistical gate |
| `high` | Could plausibly erase the edge. Must be refuted before approval |
| `medium` | Changes sizing, capacity or expected net return. Approval can proceed with a stated condition |
| `low` | Worth recording. Doesn't change the decision |

| Status | Rule |
|---|---|
| `refuted` | The pre-registered criterion is met, **with evidence IDs**. No evidence means not refuted |
| `unrefuted` | Tested, and the evidence supports the attack or fails to rule it out |
| `not_tested` | Could not be tested. Say why, and give the exact tool call that would test it |

What happens next:
- An unrefuted `blocking` attack means the red team recommends **reject**. A confirmed leakage
  finding can't be overridden later.
- A `high` or `blocking` attack that is `not_tested` becomes `NEEDS_EVIDENCE` for the committee.
- An unrefuted `high` attack means **reject or needs_more_evidence**. The reasoning has to be given.

## Attack checklist

Deeper procedures, thresholds and failure signatures are in
[references/attack-playbook.md](references/attack-playbook.md).

| # | Attack | Ask for (tool) | Refuted when | Default severity |
|---|---|---|---|---|
| 1 | **Look-ahead leakage** (knowledge time after decision time; target among the features; no execution delay) | `audit_leakage`; lineage from `build_features`, checked with `point-in-time-research/scripts/check_pit_timestamps.py`; spot checks with `get_filings_as_of` | Audit clean, lineage checker exit 0, and at least 5 spot-checked filings have acceptance time ≤ decision time | blocking |
| 2 | **Restatement look-ahead** | Frozen spec `timing_basis` (`run://{run_id}`); `get_filings_as_of` for an amended filer at an `as_of` before and after the amendment's acceptance | `timing_basis = acceptance`, and the value before the amendment is the original one | blocking |
| 3 | **Survivorship** | Universe mode in the spec; `get_universe_as_of` at an early and a late date; delisted positions and delisting returns in the backtest artifact | `point_in_time` universe; delisted names were held and exited with a delisting return | blocking |
| 4 | **Data snooping** | `get_ledger` (N, variant history, freeze times); DSR and N from `get_statistics` | DSR ≥ `min_deflated_sharpe` with the ledger's N, and no sign of unledgered search (see playbook) | high (blocking if the DSR gate fails) |
| 5 | **Execution delay sensitivity** | `run_backtest` variants at the frozen delay +1 and +5 sessions; IC by lag from `get_statistics` | Edge decays gradually and stays the same sign at +1 session; no cliff at the first lag | high |
| 6 | **Cost sensitivity** | `run_backtest` at 2× and 3× `transaction_cost_bps`; turnover and gross vs net from the artifact | Break-even cost ≥ 2× assumed, and net Sharpe at 2× costs is still > 0 | high |
| 7 | **Concentration in a few names** | P&L contribution by security from the backtest artifact; `get_statistics` on returns excluding the top 10 contributors | Top 10 names < ~30% of gross P&L, and the sign survives excluding them | high |
| 8 | **Regime dependence** | `get_statistics` by calendar year and by high/low-volatility halves | Same sign in most subperiods; no single year > ~40% of total P&L | medium |
| 9 | **Capacity** | Position sizes vs average daily volume from `get_prices_as_of` and the backtest artifact | Participation at the stated capital ≤ ~5% of ADV for ~95% of trades | medium |
| 10 | **Crowding** | Correlation with known anomalies or factors (needs factor returns); overlap with published signals from the economic rationale | Low correlation to known factors, or a rationale that isn't a relabelled known anomaly | medium (often `not_tested`) |

The thresholds marked "~" are red-team defaults. Pre-register the exact numbers in step 3 of Setup.

**Project caveat (ADR-0003):** prices are semi-synthetic. Crowding and capacity can't be
established from simulated volume and returns. Mark them `not_tested` (with a reason) unless
evidence other than prices exists, and never report simulated capacity as real.

## Required output format

Give **exactly** this table, one row per attack, with no attacks skipped, followed by the summary
block.

```
Red team — experiment <experiment_id> (run <run_id>) — prices simulated (ADR-0003)

| # | Attack | Evidence IDs | Severity | Status | Criterion → observed |
|---|--------|--------------|----------|--------|----------------------|
| 1 | Look-ahead leakage | ev_… , ev_… | blocking | refuted | audit clean + lineage exit 0 → met |
| … | … | … | low|medium|high|blocking | refuted|unrefuted|not_tested | … |

Unrefuted blocking: <list or "none">
Unrefuted high: <list or "none">
Not tested (high/blocking) → NEEDS_EVIDENCE: <attack: exact tool call>
Red-team recommendation: reject | needs_more_evidence | no objection
Variants run (ledger experiment IDs): <list>
```

Rules for the table:
- The "Evidence IDs" cell is empty only when the status is `not_tested`.
- "Criterion → observed" quotes tool numbers with their evidence IDs. It never contains model arithmetic.
- "No objection" is the strongest the red team says. It is not an approval.

## Worked row examples (fictional IDs)
| # | Attack | Evidence IDs | Severity | Status | Criterion → observed |
|---|---|---|---|---|---|
| 5 | Execution delay | ev_f1c7a501, ev_f1c7a502 | high | unrefuted | same sign at +1 session → IC falls from 0.041 to 0.003 at +1 session (ev_f1c7a502). A cliff at the first lag suggests same-day information: route to attack 1 |
| 6 | Cost sensitivity | ev_f1c7a601 | high | refuted | break-even ≥ 2× assumed 10 bps → break-even 34 bps; net Sharpe at 20 bps is 0.9 (ev_f1c7a601) |
| 10 | Crowding | — | medium | not_tested | no factor-return source available → NEEDS_EVIDENCE: factor-return evidence, which no current tool provides |
