# Blinded human review

Score each output from 1 (poor) to 5 (strong) for usefulness, support from the provided evidence, and clarity. Record uncertainty where evidence is unavailable. Do not open the separate key until ratings are fixed. No ratings have been entered by the assistant. Arm labels are hidden, although wording may reveal procedural cues; blinding is imperfect. Rate evidence support as unassessable if the supplied context is insufficient.

## Sample 1

Task: An amendment cannot replace the original before its acceptance

```json
{
  "verdict": "leakage",
  "confidence": "high",
  "summary": "The supplied filing is an amendment whose EDGAR acceptance datetime falls after the stated decision timestamp, so its value could not have been known at decision time. Using it would be both a plain look-ahead and a restatement look-ahead. This is a targeted timing/version check only; the excluded stress and red-team items were not examined.",
  "claims": [
    {
      "kind": "fact",
      "statement": "The evaluation input records the filing's EDGAR acceptance datetime as later than the supplied decision timestamp.",
      "evidence_ids": [
        "ev_02e425ab398e2179adc285e2"
      ],
      "metric_refs": []
    },
    {
      "kind": "fact",
      "statement": "The filing is flagged as an amendment rather than the original submission, and its report period end is much earlier than both its filing date and its acceptance datetime.",
      "evidence_ids": [
        "ev_02e425ab398e2179adc285e2"
      ],
      "metric_refs": []
    },
    {
      "kind": "assumption",
      "statement": "Acceptance datetime is treated as the knowledge time and is read as UTC per the EDGAR submissions API convention, while the period label and filing date are not knowledge times.",
      "evidence_ids": [
        "ev_02e425ab398e2179adc285e2"
      ],
      "metric_refs": []
    },
    {
      "kind": "risk",
      "statement": "An amendment's restated value is new information only from the amendment's own acceptance time; substituting it into earlier history replaces what the market actually knew with a later, typically worse-news revision, inflating accounting-signal performance.",
      "evidence_ids": [
        "ev_02e425ab398e2179adc285e2"
      ],
      "metric_refs": []
    },
    {
      "kind": "recommendation",
      "statement": "Reject use of this value at the supplied decision time; if a value for that period is needed, select the version whose acceptance time precedes the decision timestamp (the original submission, if one exists and was accepted in time), and route the amendment's value to the first scheduled decision at or after its own acceptance time.",
      "evidence_ids": [
        "ev_02e425ab398e2179adc285e2"
      ],
      "metric_refs": []
    }
  ],
  "open_questions": [
    "Was an original filing for the same period accepted before the decision timestamp, and what value did it report? Settle with get_filings_as_of using a timezone-aware as_of equal to the decision timestamp.",
    "Does the feature spec's timing_basis read acceptance, or does it use period_end or latest_restated? Settle by citing the frozen hypothesis evidence."
  ],
  "needs_evidence": false,
  "attacks": [
    {
      "attack": "lookahead",
      "evidence_ids": [
        "ev_02e425ab398e2179adc285e2"
      ],
      "severity": "blocking",
      "status": "unrefuted",
      "criterion": "The filing's acceptance datetime must be at or before the decision timestamp for the value to be usable at that decision.",
      "observation": "The recorded acceptance datetime is months after the decision timestamp, so the value did not exist publicly at decision time.",
      "evidence_request": "A get_filings_as_of result with as_of set to the decision timestamp showing which version of this fact, if any, was already accepted."
    },
    {
      "attack": "restatement",
      "evidence_ids": [
        "ev_02e425ab398e2179adc285e2"
      ],
      "severity": "blocking",
      "status": "unrefuted",
      "criterion": "Amended or restated values may only drive decisions at or after the amendment's own acceptance time; earlier decisions must keep the originally filed version.",
      "observation": "The version field marks this as an amendment, and its acceptance time postdates the decision, so applying it here is a latest-restated selection rather than a point-in-time one.",
      "evidence_request": "Per-version fact history keyed by accession number with each version's acceptance datetime, showing the version selected at the decision timestamp."
    }
  ],
  "dissent": []
}
```

Usefulness: ___ / 5; evidence support: ___ / 5; clarity: ___ / 5; notes: ___

## Sample 2

Task: An amendment cannot replace the original before its acceptance

```json
{
  "verdict": "leakage",
  "confidence": "high",
  "summary": "The supplied filing value was not knowable at the decision time: the filing's EDGAR acceptance timestamp falls after the decision timestamp, and the value comes from an amended version whose knowledge time starts at its own acceptance. Using it at the stated decision time is a look-ahead. This is a targeted timing and version check only; the excluded stress and red-team work was not performed.",
  "claims": [
    {
      "kind": "fact",
      "statement": "The evaluation input supplies a filing with an explicit EDGAR acceptance datetime, a date-only filing date, a period end label and a version marker of amendment, evaluated against a single decision timestamp.",
      "evidence_ids": [
        "ev_02e425ab398e2179adc285e2"
      ],
      "metric_refs": []
    },
    {
      "kind": "fact",
      "statement": "The filing's acceptance datetime is later than the decision timestamp, so the value did not exist publicly when the decision was made; the earlier period-end label does not make it knowable.",
      "evidence_ids": [
        "ev_02e425ab398e2179adc285e2"
      ],
      "metric_refs": []
    },
    {
      "kind": "fact",
      "statement": "The supplied version is an amendment, which is new information from its own acceptance time and never replaces the original value in earlier history.",
      "evidence_ids": [
        "ev_02e425ab398e2179adc285e2"
      ],
      "metric_refs": []
    },
    {
      "kind": "assumption",
      "statement": "The decision timestamp and the acceptance timestamp are both timezone-aware instants expressed in UTC as supplied, and are compared as instants rather than by calendar date.",
      "evidence_ids": [
        "ev_02e425ab398e2179adc285e2"
      ],
      "metric_refs": []
    },
    {
      "kind": "risk",
      "statement": "If the pipeline selected this amended version by period label or latest-value logic, the same restatement look-ahead would affect every historical row for that period, not just this one.",
      "evidence_ids": [
        "ev_02e425ab398e2179adc285e2"
      ],
      "metric_refs": []
    },
    {
      "kind": "recommendation",
      "statement": "Treat this value as unavailable at the stated decision time; select, for that period, the version whose acceptance time precedes the decision time, and let the amendment become usable only at the first scheduled decision at or after its own acceptance.",
      "evidence_ids": [
        "ev_02e425ab398e2179adc285e2"
      ],
      "metric_refs": []
    }
  ],
  "open_questions": [
    "What is the acceptance datetime and value of the original (pre-amendment) filing for this period, so the point-in-time correct version at the decision time can be identified?",
    "Was this value selected by acceptance-time version logic or by period label, that is, what timing basis does the frozen hypothesis declare?"
  ],
  "needs_evidence": false,
  "attacks": [
    {
      "attack": "lookahead",
      "evidence_ids": [
        "ev_02e425ab398e2179adc285e2"
      ],
      "severity": "blocking",
      "status": "unrefuted",
      "criterion": "The value's knowledge time, taken as the EDGAR acceptance datetime, must be at or before the decision timestamp.",
      "observation": "The supplied acceptance datetime is after the supplied decision timestamp, so the value was used before it existed.",
      "evidence_request": "A submissions-API record showing an acceptance datetime at or before the decision timestamp for the accession that actually supplied this value."
    },
    {
      "attack": "restatement",
      "evidence_ids": [
        "ev_02e425ab398e2179adc285e2"
      ],
      "severity": "blocking",
      "status": "unrefuted",
      "criterion": "For a given period, the version used must be the one accepted by the decision time, not a later amendment.",
      "observation": "The supplied version is marked as an amendment and no originally filed version accepted before the decision time was supplied.",
      "evidence_request": "The full version history for this concept and period, each version keyed by accession number with its acceptance datetime, so the version knowable at the decision time can be chosen."
    }
  ],
  "dissent": []
}
```

Usefulness: ___ / 5; evidence support: ___ / 5; clarity: ___ / 5; notes: ___

## Sample 3

Task: An explicitly requested full red team cannot certify missing analyses

```json
{
  "verdict": "needs_more_evidence",
  "confidence": "high",
  "summary": "The evidence catalog supplied for this full red-team review is empty: no backtest artifact, statistics output, holdings, cost or delay variants, or regime splits were provided. None of the ten required attacks can be evaluated, so all are recorded as not_tested and the review returns insufficient evidence rather than a no-objection.",
  "claims": [
    {
      "kind": "fact",
      "statement": "The review scope assigns the full ten-attack red-team procedure with no excluded work.",
      "evidence_ids": [],
      "metric_refs": []
    },
    {
      "kind": "assumption",
      "statement": "With an empty evidence catalog, no strategy artifact exists on which any attack criterion could be exercised.",
      "evidence_ids": [],
      "metric_refs": []
    },
    {
      "kind": "risk",
      "statement": "Declaring a strategy red-teamed on the basis of a review with no artifacts would create a false assurance of robustness; the absence of evidence must not be read as absence of flaws.",
      "evidence_ids": [],
      "metric_refs": []
    },
    {
      "kind": "risk",
      "statement": "The declared unavailable capabilities mean cost, delay, date-shift and regime variants cannot be produced without first freezing a hypothesis and re-running backtests, and no factor-return or contribution-exclusion source exists, so several attacks remain structurally untestable with current tooling.",
      "evidence_ids": [],
      "metric_refs": []
    },
    {
      "kind": "recommendation",
      "statement": "Supply a frozen hypothesis with a baseline backtest and statistics artifact, plus point-in-time data provenance, universe construction records, holdings/turnover detail, and cost, execution-delay and sub-period variant runs, then resubmit for the full ten-attack procedure.",
      "evidence_ids": [],
      "metric_refs": []
    }
  ],
  "open_questions": [
    "Which experiment identifier and frozen hypothesis is this review meant to cover?",
    "Is point-in-time data with vintage timestamps available to distinguish original from restated fundamentals?",
    "How was the tradable universe constructed, and does it include delisted or deregistered names?",
    "How many hypothesis variants were tried before the submitted configuration?",
    "Can baseline, higher-cost and delayed-execution runs be produced so sensitivity can be measured?",
    "Are per-position weights and per-period contributions retrievable to assess concentration and capacity?"
  ],
  "needs_evidence": true,
  "attacks": [
    {
      "attack": "lookahead",
      "evidence_ids": [],
      "severity": "high",
      "status": "not_tested",
      "criterion": "Every input field used in signal construction must be available at or before the simulated decision timestamp, verified against data vintage timestamps.",
      "observation": "No backtest configuration, feature specification, or data-vintage artifact was supplied, so timestamp alignment could not be inspected.",
      "evidence_request": "Signal definition with each input field's availability timestamp, and the decision-time convention used by the backtest engine."
    },
    {
      "attack": "restatement",
      "evidence_ids": [],
      "severity": "high",
      "status": "not_tested",
      "criterion": "Fundamental or accounting inputs must be sourced as originally reported rather than as later restated values.",
      "observation": "No data-source description or point-in-time versus restated comparison was provided.",
      "evidence_request": "Provenance record showing whether the fundamentals source is point-in-time, plus a rerun on as-originally-reported vintages."
    },
    {
      "attack": "survivorship",
      "evidence_ids": [],
      "severity": "high",
      "status": "not_tested",
      "criterion": "The backtest universe must include securities that were delisted, acquired or deregistered during the sample window.",
      "observation": "No universe construction record or delisted-name count was supplied.",
      "evidence_request": "Universe membership history including dead tickers, and a rerun comparing surviving-only versus full-history universes."
    },
    {
      "attack": "data_snooping",
      "evidence_ids": [],
      "severity": "high",
      "status": "not_tested",
      "criterion": "Reported significance must be adjusted for the number of hypotheses and parameter settings examined before selection.",
      "observation": "No trial log, parameter sweep record, or multiple-comparison adjustment was supplied.",
      "evidence_request": "Complete record of hypotheses and parameter variants tested, with an out-of-sample or holdout result for the selected configuration."
    },
    {
      "attack": "execution_delay",
      "evidence_ids": [],
      "severity": "high",
      "status": "not_tested",
      "criterion": "Performance must survive a realistic lag between signal observation and trade execution.",
      "observation": "No baseline or delayed-execution backtest variant exists to compare.",
      "evidence_request": "Baseline and lagged-execution runs of the frozen hypothesis with comparable statistics outputs."
    },
    {
      "attack": "cost_sensitivity",
      "evidence_ids": [],
      "severity": "high",
      "status": "not_tested",
      "criterion": "Net performance must remain positive under conservative commission, spread and slippage assumptions.",
      "observation": "No cost assumption disclosure and no higher-cost variant run were provided.",
      "evidence_request": "Cost model used in the baseline plus at least one stressed-cost rerun with turnover figures."
    },
    {
      "attack": "concentration",
      "evidence_ids": [],
      "severity": "medium",
      "status": "not_tested",
      "criterion": "Aggregate results must not depend on a small number of positions, dates or contribution outliers.",
      "observation": "No holdings, weights, or per-position contribution breakdown was supplied.",
      "evidence_request": "Position-level weights and contributions over time, plus results excluding top contributors."
    },
    {
      "attack": "regime_dependence",
      "evidence_ids": [],
      "severity": "medium",
      "status": "not_tested",
      "criterion": "Performance should be reasonably stable across distinct market sub-periods rather than concentrated in one regime.",
      "observation": "No sub-period or regime-split statistics were provided, and the tooling notes state regime arguments are not accepted directly.",
      "evidence_request": "Sub-period backtests over separately defined date ranges covering distinct volatility and trend regimes."
    },
    {
      "attack": "capacity",
      "evidence_ids": [],
      "severity": "medium",
      "status": "not_tested",
      "criterion": "Target position sizes must be small relative to traded liquidity at the intended deployment size.",
      "observation": "No liquidity, volume, or assets-under-management assumptions were supplied.",
      "evidence_request": "Per-name participation rates against average traded volume at the intended capital base."
    },
    {
      "attack": "crowding",
      "evidence_ids": [],
      "severity": "medium",
      "status": "not_tested",
      "criterion": "Returns should not be fully explained by exposure to widely harvested common factors.",
      "observation": "No factor-return source or contribution-exclusion tool is available, and no factor attribution artifact was supplied.",
      "evidence_request": "Factor exposure attribution of the return stream, or a documented rationale for why the signal is not a repackaged common factor."
    }
  ],
  "dissent": []
}
```

Usefulness: ___ / 5; evidence support: ___ / 5; clarity: ___ / 5; notes: ___

## Sample 4

Task: A filed date without acceptance time is insufficient evidence

```json
{
  "verdict": "needs_evidence",
  "confidence": "high",
  "summary": "The filing's stated filing date falls on the same calendar day as the decision timestamp, and no acceptance timestamp is supplied, so availability at the decision moment cannot be established. The version is original, so no amendment-restatement issue arises, but knowledge time remains unresolved.",
  "claims": [
    {
      "kind": "fact",
      "statement": "The supplied filing record is marked as an original version, not an amendment, for a quarter-end report period preceding the filing date.",
      "evidence_ids": [
        "ev_536188d901d59c1122609f68"
      ],
      "metric_refs": []
    },
    {
      "kind": "fact",
      "statement": "The filing date and the decision date fall on the same calendar day, and the evidence contains only a date-level filing field with no acceptance or dissemination timestamp.",
      "evidence_ids": [
        "ev_536188d901d59c1122609f68"
      ],
      "metric_refs": []
    },
    {
      "kind": "assumption",
      "statement": "A date-only filing field cannot be assumed to precede an intraday decision timestamp; issuers commonly transmit filings after the late-afternoon market close, which can fall at or after the decision moment in the decision timezone.",
      "evidence_ids": [
        "ev_536188d901d59c1122609f68"
      ],
      "metric_refs": []
    },
    {
      "kind": "risk",
      "statement": "If the filing was accepted after the decision timestamp, any signal built on this value would embed same-day lookahead; the current evidence cannot exclude that case.",
      "evidence_ids": [
        "ev_536188d901d59c1122609f68"
      ],
      "metric_refs": []
    },
    {
      "kind": "recommendation",
      "statement": "Supply the source acceptance/dissemination timestamp with timezone semantics for this filing, and re-run the knowledge-time check before any human sign-off; the filing_version check raises no concern on the evidence provided.",
      "evidence_ids": [
        "ev_536188d901d59c1122609f68"
      ],
      "metric_refs": []
    }
  ],
  "open_questions": [
    "What is the exact acceptance timestamp (with timezone) recorded by the filing source for this original filing?",
    "Does the data pipeline key observations on acceptance time or on the date-level filing field?"
  ],
  "needs_evidence": true,
  "attacks": [
    {
      "attack": "lookahead",
      "evidence_ids": [
        "ev_536188d901d59c1122609f68"
      ],
      "severity": "high",
      "status": "not_tested",
      "criterion": "Refuted only if the source acceptance timestamp is strictly earlier than the decision timestamp in a common timezone.",
      "observation": "Only a date-level filing field is available, coinciding with the decision date; same-day availability can be neither confirmed nor refuted.",
      "evidence_request": "Acceptance/dissemination timestamp from the filing source for this accession, with timezone."
    }
  ],
  "dissent": []
}
```

Usefulness: ___ / 5; evidence support: ___ / 5; clarity: ___ / 5; notes: ___

## Sample 5

Task: An after-close acceptance was unavailable at the earlier decision

```json
{
  "verdict": "leakage",
  "confidence": "high",
  "summary": "The filing's EDGAR acceptance instant falls after the supplied decision instant, so the value was not public knowledge at decision time; using it at that decision is a look-ahead leak. This is a targeted timing/version check only.",
  "claims": [
    {
      "kind": "fact",
      "statement": "The evaluation input supplies an EDGAR acceptance datetime for the filing that is later in the same session than the supplied decision timestamp; the decision timestamp corresponds to the Eastern close and the acceptance falls after that close.",
      "evidence_ids": [
        "ev_114e0257699bedb0d33b5562"
      ],
      "metric_refs": []
    },
    {
      "kind": "fact",
      "statement": "The supplied filing is flagged as the original submission, not an amendment or restated version, so no earlier-accepted version of this value exists to substitute and no later amendment is being back-applied.",
      "evidence_ids": [
        "ev_114e0257699bedb0d33b5562"
      ],
      "metric_refs": []
    },
    {
      "kind": "fact",
      "statement": "The filing date supplied is date-only and equals the decision session's date, while the period-end label is an earlier fiscal period end; neither field establishes knowledge time under the acceptance-based rule.",
      "evidence_ids": [
        "ev_114e0257699bedb0d33b5562"
      ],
      "metric_refs": []
    },
    {
      "kind": "assumption",
      "statement": "The acceptance datetime is interpreted as UTC per the EDGAR submissions API convention and converted to Eastern only for session comparison; no timezone reinterpretation was applied to either timestamp.",
      "evidence_ids": [
        "ev_114e0257699bedb0d33b5562"
      ],
      "metric_refs": []
    },
    {
      "kind": "risk",
      "statement": "Relying on the date-only filing date rather than acceptance would make this after-close acceptance appear same-day-usable, silently hiding a sub-session look-ahead across all similarly timed filings.",
      "evidence_ids": [
        "ev_114e0257699bedb0d33b5562"
      ],
      "metric_refs": []
    },
    {
      "kind": "recommendation",
      "statement": "Treat this value as first usable at the next scheduled session decision after acceptance, with the execution delay applied from that decision, and re-run the leakage audit under a new experiment ID if the frozen spec used a filing-date or period-end basis.",
      "evidence_ids": [
        "ev_114e0257699bedb0d33b5562"
      ],
      "metric_refs": []
    }
  ],
  "open_questions": [
    "Which timing_basis and universe mode does the frozen hypothesis declare for the feature consuming this filing value? The frozen hypothesis artifact would settle it.",
    "Does the lineage export record this filing's knowledge time as the acceptance instant, and does the leakage audit already flag the affected rows?"
  ],
  "needs_evidence": false,
  "attacks": [
    {
      "attack": "lookahead",
      "evidence_ids": [
        "ev_114e0257699bedb0d33b5562"
      ],
      "severity": "blocking",
      "status": "unrefuted",
      "criterion": "The value may drive the decision only if its acceptance instant is at or before the decision instant.",
      "observation": "The acceptance instant is after the decision instant in the same session, so the value did not exist publicly when the decision was taken.",
      "evidence_request": "Lineage export plus audit_leakage output for the affected rows showing knowledge_ts set to the acceptance instant and the first use rolled to the next session."
    }
  ],
  "dissent": []
}
```

Usefulness: ___ / 5; evidence support: ___ / 5; clarity: ___ / 5; notes: ___

## Sample 6

Task: Real EDGAR filings reach the committee with a clean audit

```json
{
  "verdict": "concerns",
  "confidence": "medium",
  "summary": "Costs look implementable as tested: mean turnover per rebalance is moderate for a month-long hold, the modelled cost drag is a small fraction of gross annual return, and the reported Sharpe decay from one extra session of execution delay sits well inside the fragility threshold. The blocking implementability doubt is portfolio concentration: the book holds only a single-digit number of names per side, and no per-name or per-date contribution evidence was supplied, while contributor-exclusion and cost-multiplier stress runs are outside this targeted scope and remain unverified. Verdict is concerns pending that evidence.",
  "claims": [
    {
      "kind": "fact",
      "statement": "{metric:0}; {metric:1}",
      "evidence_ids": [
        "ev_dda125e34f11f086cb29541d"
      ],
      "metric_refs": [
        {
          "evidence_id": "ev_dda125e34f11f086cb29541d",
          "field_path": "/cost_drag_annualized",
          "format": ".2%"
        },
        {
          "evidence_id": "ev_dda125e34f11f086cb29541d",
          "field_path": "/turnover_mean",
          "format": ".2f"
        }
      ]
    },
    {
      "kind": "fact",
      "statement": "The modelled annualized cost drag is a small fraction of the backtest's gross annual return, so net and gross performance are close.",
      "evidence_ids": [
        "ev_1cc00495469848258c81e1e1",
        "ev_dda125e34f11f086cb29541d"
      ],
      "metric_refs": []
    },
    {
      "kind": "fact",
      "statement": "The backtest applies a low per-trade transaction cost in basis points and an intraday execution delay after the filing acceptance timestamp, with a month-long holding period and a rebalance count consistent with that hold.",
      "evidence_ids": [
        "ev_1cc00495469848258c81e1e1"
      ],
      "metric_refs": []
    },
    {
      "kind": "fact",
      "statement": "The reported Sharpe decay from additional execution delay is well below the maximum delay-decay fragility threshold used by the statistical gate.",
      "evidence_ids": [
        "ev_dda125e34f11f086cb29541d"
      ],
      "metric_refs": []
    },
    {
      "kind": "fact",
      "statement": "The backtest holds only a single-digit number of names per side, driven by the quantile cut on a narrow universe.",
      "evidence_ids": [
        "ev_1cc00495469848258c81e1e1"
      ],
      "metric_refs": []
    },
    {
      "kind": "assumption",
      "statement": "Turnover, cost drag and delay decay are taken as computed by the backtest and statistics tools on the frozen rebalance schedule; I recomputed nothing.",
      "evidence_ids": [
        "ev_1cc00495469848258c81e1e1",
        "ev_dda125e34f11f086cb29541d"
      ],
      "metric_refs": []
    },
    {
      "kind": "risk",
      "statement": "With so few names per side, a handful of positions can carry most of the profit and loss, and idiosyncratic single-name risk plus borrow availability on the short side could dominate live results; no contribution-concentration artifact was supplied and contributor-exclusion stress is excluded from this scope.",
      "evidence_ids": [
        "ev_1cc00495469848258c81e1e1"
      ],
      "metric_refs": []
    },
    {
      "kind": "risk",
      "statement": "The cost assumption is optimistic for a concentrated small-name book; because cost-multiplier stress is outside this scope, the break-even cost level at which net returns vanish is unknown.",
      "evidence_ids": [
        "ev_1cc00495469848258c81e1e1"
      ],
      "metric_refs": []
    },
    {
      "kind": "risk",
      "statement": "Only one execution-delay configuration and one extra-session decay figure are available, so sensitivity to a full-session or open-auction fill is not characterized.",
      "evidence_ids": [
        "ev_dda125e34f11f086cb29541d"
      ],
      "metric_refs": []
    },
    {
      "kind": "recommendation",
      "statement": "Before treating the strategy as implementable as tested, request a per-name and per-date contribution breakdown, an exclusion run dropping the largest contributors, and a cost-multiplier sweep with a break-even cost estimate; also request a delay variant at a full session.",
      "evidence_ids": [
        "ev_1cc00495469848258c81e1e1",
        "ev_dda125e34f11f086cb29541d"
      ],
      "metric_refs": []
    }
  ],
  "open_questions": [
    "What share of profit and loss comes from the top contributing names and the most profitable rebalance dates?",
    "At what cost level in basis points does the net return fall to zero, and how does that compare with realistic costs for the traded universe?",
    "Does the Sharpe survive a full-session execution delay rather than the intraday delay tested?",
    "Is short borrow available and affordable for the short-side names at the tested position sizes?"
  ],
  "needs_evidence": true,
  "attacks": [
    {
      "attack": "concentration",
      "evidence_ids": [
        "ev_1cc00495469848258c81e1e1"
      ],
      "severity": "high",
      "status": "not_tested",
      "criterion": "No single name or small set of rebalance dates accounts for a dominant share of cumulative profit and loss.",
      "observation": "The portfolio holds only a single-digit number of names per side and no contribution breakdown or exclusion run was provided; contributor-exclusion stress is listed as excluded from this review.",
      "evidence_request": "Per-name and per-date profit-and-loss contribution table from the backtest artifact, plus a re-run excluding the largest contributors."
    },
    {
      "attack": "cost_sensitivity",
      "evidence_ids": [
        "ev_1cc00495469848258c81e1e1",
        "ev_dda125e34f11f086cb29541d"
      ],
      "severity": "medium",
      "status": "not_tested",
      "criterion": "Net performance remains positive and the Sharpe stays above the gate when transaction costs are multiplied to realistic levels for the universe.",
      "observation": "Only the single frozen cost assumption is available; cost-multiplier stress requires a new freeze and backtest, which is outside this scope.",
      "evidence_request": "Backtest and statistics runs at multiple cost multipliers with a break-even cost estimate."
    },
    {
      "attack": "execution_delay",
      "evidence_ids": [
        "ev_dda125e34f11f086cb29541d"
      ],
      "severity": "low",
      "status": "refuted",
      "criterion": "Sharpe lost with one additional session of execution delay stays within the maximum delay-decay threshold.",
      "observation": "The reported delay decay is well inside the threshold at the tested intraday delay, so same-session timing fragility is not indicated; longer delays were not evaluated.",
      "evidence_request": "Delay variants at a full session and at the next open to confirm the decay profile."
    }
  ],
  "dissent": []
}
```

Usefulness: ___ / 5; evidence support: ___ / 5; clarity: ___ / 5; notes: ___

## Sample 7

Task: An amendment cannot replace the original before its acceptance

```json
{
  "verdict": "leakage",
  "confidence": "high",
  "summary": "The filing value could not have been known at the decision time: the acceptance timestamp of the supplied filing falls after the decision timestamp, and the artifact is an amended version rather than the original. Using the period-end label would overstate availability. This is a targeted review of knowledge time and filing version only; the listed excluded checks were not performed.",
  "claims": [
    {
      "kind": "fact",
      "statement": "The supplied filing record carries an acceptance timestamp that is later than the supplied decision timestamp, so the value was not public or accessible at decision time.",
      "evidence_ids": [
        "ev_02e425ab398e2179adc285e2"
      ],
      "metric_refs": []
    },
    {
      "kind": "fact",
      "statement": "The filing version field identifies the artifact as an amendment, not the original submission.",
      "evidence_ids": [
        "ev_02e425ab398e2179adc285e2"
      ],
      "metric_refs": []
    },
    {
      "kind": "fact",
      "statement": "The report period end date precedes the decision timestamp, but period labels do not establish knowledge time; the acceptance timestamp governs availability.",
      "evidence_ids": [
        "ev_02e425ab398e2179adc285e2"
      ],
      "metric_refs": []
    },
    {
      "kind": "risk",
      "statement": "Amended filings restate values that differ from whatever was originally disclosed; even if an original submission had been accepted before the decision time, the restated figures in this amendment would be forward-looking information relative to the decision.",
      "evidence_ids": [
        "ev_02e425ab398e2179adc285e2"
      ],
      "metric_refs": []
    },
    {
      "kind": "recommendation",
      "statement": "Do not use this value at the stated decision time. If the underlying metric is required, supply the original filing's acceptance timestamp and its as-originally-reported value, and re-run this knowledge-time check against that record.",
      "evidence_ids": [
        "ev_02e425ab398e2179adc285e2"
      ],
      "metric_refs": []
    }
  ],
  "open_questions": [
    "Was an original (pre-amendment) filing for the same report period accepted before the decision timestamp, and what value did it carry?",
    "Does the research pipeline key filings on period label or on acceptance timestamp for point-in-time construction?"
  ],
  "needs_evidence": false,
  "attacks": [
    {
      "attack": "lookahead",
      "evidence_ids": [
        "ev_02e425ab398e2179adc285e2"
      ],
      "severity": "blocking",
      "status": "unrefuted",
      "criterion": "The filing's acceptance timestamp must be at or before the decision timestamp for the value to be usable.",
      "observation": "The acceptance timestamp of the supplied amended filing is after the decision timestamp, so the value was unavailable when the decision was made.",
      "evidence_request": "Acceptance timestamp and as-originally-reported value for the original filing of the same report period, to test whether any version was available before the decision time."
    },
    {
      "attack": "restatement",
      "evidence_ids": [
        "ev_02e425ab398e2179adc285e2"
      ],
      "severity": "high",
      "status": "unrefuted",
      "criterion": "Point-in-time values must come from the version available at decision time, not a later restatement.",
      "observation": "The supplied record is flagged as an amendment, so its figures reflect a later revision of the period's reporting.",
      "evidence_request": "Original-version filing record with its own acceptance timestamp and reported value for comparison against the amended figures."
    }
  ],
  "dissent": []
}
```

Usefulness: ___ / 5; evidence support: ___ / 5; clarity: ___ / 5; notes: ___

## Sample 8

Task: A filed date without acceptance time is insufficient evidence

```json
{
  "verdict": "needs_evidence",
  "confidence": "high",
  "summary": "The filing's calendar filing date is the same day as the decision timestamp, and no acceptance timestamp is supplied, so availability at the decision moment cannot be established. The version field indicates an original rather than an amended filing, which addresses the restatement half of the scope but not knowledge time.",
  "claims": [
    {
      "kind": "fact",
      "statement": "The evaluation input records the filing's filing date as falling on the same calendar day as the decision timestamp, with the report period ending earlier in the quarter.",
      "evidence_ids": [
        "ev_536188d901d59c1122609f68"
      ],
      "metric_refs": []
    },
    {
      "kind": "fact",
      "statement": "The evaluation input labels the filing version as original, so no amended-version restatement issue is indicated for this record.",
      "evidence_ids": [
        "ev_536188d901d59c1122609f68"
      ],
      "metric_refs": []
    },
    {
      "kind": "fact",
      "statement": "No acceptance or dissemination timestamp is present anywhere in the supplied evidence; only a calendar filing date is provided.",
      "evidence_ids": [
        "ev_536188d901d59c1122609f68"
      ],
      "metric_refs": []
    },
    {
      "kind": "assumption",
      "statement": "Treating a same-day calendar filing date as proof of pre-decision availability would assume an acceptance time earlier in the day, which the inputs do not support; acceptance can occur after a late-afternoon decision cutoff.",
      "evidence_ids": [
        "ev_536188d901d59c1122609f68"
      ],
      "metric_refs": []
    },
    {
      "kind": "risk",
      "statement": "If the filing was accepted and disseminated after the decision moment, any signal built on this value is forward-looking and would inflate backtested performance.",
      "evidence_ids": [
        "ev_536188d901d59c1122609f68"
      ],
      "metric_refs": []
    },
    {
      "kind": "recommendation",
      "statement": "Supply the source acceptance timestamp with time zone for this filing, and re-run the knowledge-time check before any human decision on use; if acceptance cannot be sourced, apply a conservative availability lag rather than the calendar filing date.",
      "evidence_ids": [
        "ev_536188d901d59c1122609f68"
      ],
      "metric_refs": []
    }
  ],
  "open_questions": [
    "What is the exact acceptance or dissemination timestamp, with time zone, for this original filing?",
    "Does the data pipeline key availability on acceptance time or on the calendar filing date field?"
  ],
  "needs_evidence": true,
  "attacks": [
    {
      "attack": "lookahead",
      "evidence_ids": [
        "ev_536188d901d59c1122609f68"
      ],
      "severity": "high",
      "status": "unrefuted",
      "criterion": "Refuted only if a sourced acceptance timestamp precedes the decision timestamp.",
      "observation": "Filing date and decision fall on the same calendar day and no acceptance time is supplied, so same-day lookahead cannot be excluded.",
      "evidence_request": "Acceptance timestamp with time zone from the filing source feed for this document."
    },
    {
      "attack": "restatement",
      "evidence_ids": [
        "ev_536188d901d59c1122609f68"
      ],
      "severity": "low",
      "status": "refuted",
      "criterion": "Refuted if the record is the original version rather than a later amendment.",
      "observation": "The supplied version field states the filing is original, so the value is not sourced from a later amended version.",
      "evidence_request": "None; version field is sufficient for this check."
    }
  ],
  "dissent": []
}
```

Usefulness: ___ / 5; evidence support: ___ / 5; clarity: ___ / 5; notes: ___
