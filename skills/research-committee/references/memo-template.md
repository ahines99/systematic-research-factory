# Committee memo template and worked example

This file supports the `research-committee` Skill. Part A is the blank template. Part B is a
filled example for a **fictional** run. Every ID, name and number in Part B is invented for
illustration: evidence IDs use the `ev_f1c7…` ("fict") prefix, and none of them resolve in any
real ledger. The statistics in Part B match the worked example in
`financial-research-statistics/references/formulas.md`, so a reader can check them.

---

## Part A: blank template

```markdown
# Research committee memo — run <run_id>

| Field | Value |
|---|---|
| Experiment / family | <experiment_id> / <research_family> |
| Requested by | <requester> |
| Trial count (N) in family | <n> [ev_…] |
| Gate recommendation (deterministic) | approve | reject | needs_more_evidence [ev_…] |
| Memo recommendation | approve | reject | needs_more_evidence |
| Data label | Prices are simulated (ADR-0003); no claim about real-world performance |

## 1. Facts
- <observation> [ev_…]

## 2. Calculations (tool outputs only)
| Quantity | Value | Threshold | Tool | Evidence |
|---|---|---|---|---|

## 3. Assumptions
- A1: <assumption> — basis: <evidence, or "none: stated assumption">

## 4. Risks and counterarguments
- <strongest case against the recommendation> [ev_…]
- Red-team table: <paste the table from signal-red-team>

## 5. Recommendation
<decision> — <reasons, each cited>. Relation to gate: same | more conservative (why).
Path forward: <new experiment / specific evidence requests>.

## 6. Open questions
- Q1: <question> — resolve by: <tool call with arguments> | owner: <role>

## 7. Dissent
<D1..Dn in the standard structure, or "None recorded">

## 8. Decision record (human approver only; left blank by the model)
Decision: ____  Approver: ____  Timestamp: ____  Reason: ____
Override of gate: yes/no
```

---

## Part B: filled example (fictional run)

# Research committee memo — run 00000000-0000-4000-8000-00000000f1c7 (FICTIONAL)

| Field | Value |
|---|---|
| Experiment / family | `exp_f1c7e01` / `accruals-quality` (fictional) |
| Requested by | `researcher.alpha` (fictional) |
| Trial count (N) in family | 20 [ev_f1c70001] |
| Gate recommendation (deterministic) | **reject**: 1 blocking statistical finding [ev_f1c70002] |
| Memo recommendation | **reject** |
| Data label | Prices are simulated (ADR-0003); no claim about real-world performance |

## 1. Facts
- The frozen hypothesis says that low balance-sheet accruals predict higher returns over a 21-day
  hold. Feature `timing_basis` = `acceptance`, universe mode = `point_in_time`, execution delay
  = 1 session, costs = 10 bps [ev_f1c70003].
- The leakage audit passed with no findings. The lineage check exited 0 over all feature rows
  [ev_f1c70004, ev_f1c70005].
- The universe includes 37 names that later delisted. Each exits with a delisting return in the
  backtest artifact [ev_f1c70006].
- The ledger lists 20 experiments in `accruals-quality`. Nine share the same economic spec and
  differ only in pipeline version [ev_f1c70001].
- The economic rationale review is schema-valid, and every claim cites evidence [ev_f1c70007].
- The implementation review raises no unrealistic-cost flag [ev_f1c70008].

## 2. Calculations (tool outputs only)
| Quantity | Value | Threshold | Tool | Evidence |
|---|---|---|---|---|
| Observations (daily) | 1260 | ≥ 252 `min_observations` | `get_statistics` | ev_f1c70010 |
| Annualized Sharpe (net) | 1.50 | — | `get_statistics` | ev_f1c70010 |
| Skewness / kurtosis (non-excess) | −0.50 / 6.0 | — | `get_statistics` | ev_f1c70010 |
| Newey-West t (L = 3) | 3.05 | ≥ 3.0 `min_newey_west_t` | `get_statistics` | ev_f1c70010 |
| Newey-West t (L = 7, red-team check) | 2.97 | ≥ 3.0 | `get_statistics` | ev_f1c70011 |
| Bootstrap 95% CI, annualized Sharpe (stationary, b = 21, B = 10,000) | [0.55, 2.43] | lower > 0 | `get_statistics` | ev_f1c70010 |
| PSR(0) | 0.9994 | — | `get_statistics` | ev_f1c70010 |
| SR0 (expected max of N = 20, annualized) | 0.95 | — | `get_statistics` | ev_f1c70010 |
| **Deflated Sharpe ratio** | **0.884** | ≥ 0.95 `min_deflated_sharpe` | `get_statistics` | ev_f1c70010 |
| Mean IC / IC-IR (monthly) | 0.031 / 0.26 | — | `get_statistics` | ev_f1c70012 |
| Break-even cost | 34 bps | ≥ 2× assumed | `run_backtest` artifact | ev_f1c70013 |

## 3. Assumptions
- A1: The ledger's N = 20 counts genuinely distinct trials. Basis: ledger policy counts every
  frozen experiment [ev_f1c70001]. Disputed in D1.
- A2: V[SR] is the cross-trial variance of the family's Sharpe ratios as reported by the tool
  [ev_f1c70010]. No fallback was used.
- A3: Prices, volumes and delistings are simulated (ADR-0003). Statistics describe how well the
  pipeline recovers the planted effect, not market alpha.

## 4. Risks and counterarguments
- **Against rejecting:** the signal clears the Newey-West t at the frozen lag (3.05), the bootstrap
  interval excludes zero, and PSR(0) is 0.9994 [ev_f1c70010]. Taken alone, it looks significant.
- **Why that doesn't carry the decision:** DSR 0.884 is below 0.95 given N = 20 [ev_f1c70010]. The
  Newey-West result is also lag-fragile: 2.97 at L = 7 [ev_f1c70011]. Both point to a result that
  doesn't survive the family's search.
- **Unmodelled risk:** the result depends on 2020 (see regime row below).

Red team (from `signal-red-team`, experiment `exp_f1c7e01`):

| # | Attack | Evidence IDs | Severity | Status | Criterion → observed |
|---|---|---|---|---|---|
| 1 | Look-ahead leakage | ev_f1c70004, ev_f1c70005 | blocking | refuted | audit clean + lineage exit 0 → met |
| 2 | Restatement look-ahead | ev_f1c70003, ev_f1c70014 | blocking | refuted | original value before the 10-K/A acceptance → met |
| 3 | Survivorship | ev_f1c70006 | blocking | refuted | delisted names held and exited with delisting returns → met |
| 4 | Data snooping | ev_f1c70001, ev_f1c70010 | blocking | unrefuted | DSR ≥ 0.95 → 0.884 |
| 5 | Execution delay | ev_f1c70015 | high | refuted | same sign at +1 session → IC 0.031 → 0.027 |
| 6 | Cost sensitivity | ev_f1c70013 | high | refuted | break-even ≥ 20 bps → 34 bps |
| 7 | Concentration | ev_f1c70016 | high | refuted | top 10 names < 30% of P&L → 18% |
| 8 | Regime dependence | ev_f1c70017 | medium | unrefuted | no year > 40% of P&L → 2020 = 45% |
| 9 | Capacity | — | medium | not_tested | simulated volume only (ADR-0003) |
| 10 | Crowding | — | medium | not_tested | no factor-return evidence → NEEDS_EVIDENCE |

## 5. Recommendation
**Reject.** Same as the gate. The deflated Sharpe ratio of 0.884 is below the 0.95 threshold given
the ledger's 20 trials [ev_f1c70010, ev_f1c70001]. That is a blocking statistical finding
[ev_f1c70002]. No leakage finding is involved: attacks 1–3 are refuted with evidence.
**Path forward:** freeze a new hypothesis (a new experiment in `accruals-quality`, so N becomes 21)
that tests the unchanged rule only on filings accepted **after** this memo's date, with thresholds
set before that data exists.

## 6. Open questions
- Q1: Should reruns caused by pipeline bugs, with the same economic spec, count as separate trials?
  This is a ledger-policy question, not a question for this run. Resolve by: review of
  `ledger://accruals-quality` and the ledger policy in `project://policies`. Owner: research lead
  (fictional).
- Q2: Crowding against known accruals factors. Resolve by: factor-return evidence, which no current
  tool provides (NEEDS_EVIDENCE).

## 7. Dissent
```
Dissent D1
- Author / role: implementation reviewer (fictional: reviewer.beta)
- Position: needs_more_evidence (disputes "reject")
- Argument: 9 of the 20 ledger entries are pipeline-bug reruns of one economic spec
  [ev_f1c70001]; the effective number of independent trials is lower, so the DSR is too harsh.
- What would change the author's mind: a ledger-policy ruling that the reruns count as
  separate trials (Q1).
- Response from the memo author: the gate uses the ledger's N as recorded, and the committee
  can't change N for one run. The reruns also produced close variants that were each looked at,
  which is exactly the selection the DSR corrects for. The question goes to Q1 as a policy matter.
  Separately, the lag fragility (2.97 at L = 7, ev_f1c70011) points to rejection on its own.
- Status: noted, not adopted
```

## 8. Decision record (human approver only; the model leaves this blank)
Decision: reject  ·  Approver: `approver.gamma` (fictional, not the requester)  ·
Timestamp: 2026-01-15T14:02:00-05:00 (fictional)  ·
Reason: "DSR 0.884 < 0.95 with N = 20 [ev_f1c70010]; D1 noted, and the trial-counting policy is
referred to Q1. New out-of-sample experiment encouraged."  ·  Override of gate: no

*(Filled in here only to show the finished record. In a real run the model leaves section 8 blank,
and it is completed by `approve_run`.)*
