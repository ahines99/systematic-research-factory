# Blinded human review

Score usefulness, support from the supplied inputs, and clarity from 1 (poor) to 5 (strong). Record uncertainty where the inputs cannot support a conclusion. No ratings have been entered. Do not open the separate key until your ratings are fixed.

Four preselected observations per arm are represented. Each sample uses the last response with a captured request and output in that observation; this may precede a later rejected response. This is a review of captured artifacts, not an estimate of overall workflow success. All failed attempts remain in the raw study. Arm labels and system/skill text are omitted; wording may still reveal procedural cues.

## Sample 1

Task: An amendment cannot replace the original before its acceptance

### Supplied task inputs

```json
{
  "filing": {
    "acceptanceDateTime": "2024-08-01T12:00:00Z",
    "filingDate": "2024-08-01",
    "reportDate": "2024-03-31",
    "version": "amendment"
  },
  "decision_ts": "2024-05-03T20:00:00Z",
  "review_scope": {
    "mode": "targeted_review",
    "assigned": [
      "knowledge_time",
      "filing_version"
    ],
    "excluded": [
      "full_red_team_signoff",
      "cost_multiplier_stress",
      "contributor_exclusion_stress",
      "volatility_regime_stress",
      "real_market_capacity",
      "factor_crowding"
    ],
    "unavailable_capabilities": [
      "get_statistics accepts experiment_id, not filtered return arrays or regime arguments",
      "cost/date/delay variants require freeze_hypothesis followed by run_backtest/get_statistics",
      "no factor-return source or contribution-exclusion tool is provided"
    ],
    "dissent": []
  },
  "evidence_catalog": [
    {
      "evidence_id": "ev_02e425ab398e2179adc285e2",
      "source_type": "artifact:evaluation-input",
      "step": "Evaluation input"
    }
  ]
}
```

### Model output

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

### Supplied task inputs

```json
{
  "filing": {
    "acceptanceDateTime": "2024-08-01T12:00:00Z",
    "filingDate": "2024-08-01",
    "reportDate": "2024-03-31",
    "version": "amendment"
  },
  "decision_ts": "2024-05-03T20:00:00Z",
  "review_scope": {
    "mode": "targeted_review",
    "assigned": [
      "knowledge_time",
      "filing_version"
    ],
    "excluded": [
      "full_red_team_signoff",
      "cost_multiplier_stress",
      "contributor_exclusion_stress",
      "volatility_regime_stress",
      "real_market_capacity",
      "factor_crowding"
    ],
    "unavailable_capabilities": [
      "get_statistics accepts experiment_id, not filtered return arrays or regime arguments",
      "cost/date/delay variants require freeze_hypothesis followed by run_backtest/get_statistics",
      "no factor-return source or contribution-exclusion tool is provided"
    ],
    "dissent": []
  },
  "evidence_catalog": [
    {
      "evidence_id": "ev_02e425ab398e2179adc285e2",
      "source_type": "artifact:evaluation-input",
      "step": "Evaluation input"
    }
  ]
}
```

### Model output

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

### Supplied task inputs

```json
{
  "review_scope": {
    "mode": "full_red_team",
    "assigned": [
      "all_ten_attacks"
    ],
    "excluded": [],
    "unavailable_capabilities": [
      "get_statistics accepts experiment_id, not filtered return arrays or regime arguments",
      "cost/date/delay variants require freeze_hypothesis followed by run_backtest/get_statistics",
      "no factor-return source or contribution-exclusion tool is provided"
    ],
    "dissent": []
  },
  "evidence_catalog": []
}
```

### Model output

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

### Supplied task inputs

```json
{
  "filing": {
    "filingDate": "2024-05-02",
    "reportDate": "2024-03-31",
    "version": "original"
  },
  "decision_ts": "2024-05-02T20:00:00Z",
  "review_scope": {
    "mode": "targeted_review",
    "assigned": [
      "knowledge_time",
      "filing_version"
    ],
    "excluded": [
      "full_red_team_signoff",
      "cost_multiplier_stress",
      "contributor_exclusion_stress",
      "volatility_regime_stress",
      "real_market_capacity",
      "factor_crowding"
    ],
    "unavailable_capabilities": [
      "get_statistics accepts experiment_id, not filtered return arrays or regime arguments",
      "cost/date/delay variants require freeze_hypothesis followed by run_backtest/get_statistics",
      "no factor-return source or contribution-exclusion tool is provided"
    ],
    "dissent": []
  },
  "evidence_catalog": [
    {
      "evidence_id": "ev_536188d901d59c1122609f68",
      "source_type": "artifact:evaluation-input",
      "step": "Evaluation input"
    }
  ]
}
```

### Model output

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

### Supplied task inputs

```json
{
  "filing": {
    "acceptanceDateTime": "2024-05-02T20:31:07Z",
    "filingDate": "2024-05-02",
    "reportDate": "2024-03-31",
    "version": "original"
  },
  "decision_ts": "2024-05-02T20:00:00Z",
  "review_scope": {
    "mode": "targeted_review",
    "assigned": [
      "knowledge_time",
      "filing_version"
    ],
    "excluded": [
      "full_red_team_signoff",
      "cost_multiplier_stress",
      "contributor_exclusion_stress",
      "volatility_regime_stress",
      "real_market_capacity",
      "factor_crowding"
    ],
    "unavailable_capabilities": [
      "get_statistics accepts experiment_id, not filtered return arrays or regime arguments",
      "cost/date/delay variants require freeze_hypothesis followed by run_backtest/get_statistics",
      "no factor-return source or contribution-exclusion tool is provided"
    ],
    "dissent": []
  },
  "evidence_catalog": [
    {
      "evidence_id": "ev_114e0257699bedb0d33b5562",
      "source_type": "artifact:evaluation-input",
      "step": "Evaluation input"
    }
  ]
}
```

### Model output

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

### Supplied task inputs

```json
{
  "evidence_catalog": [
    {
      "evidence_id": "ev_fb2b18266d5cf27c5c88c63d",
      "source_type": "artifact:hypothesis-freeze",
      "step": "Hypothesis freeze"
    },
    {
      "evidence_id": "ev_7023d6bd3eef2447dfd14162",
      "source_type": "dataset_snapshot",
      "step": "Data acquisition"
    },
    {
      "evidence_id": "ev_d347cd43dbe1dc085d35b636",
      "source_type": "filings",
      "step": "Data acquisition"
    },
    {
      "evidence_id": "ev_5772e59060f2f17a6ddb8601",
      "source_type": "artifact:data-acquisition",
      "step": "Data acquisition"
    },
    {
      "evidence_id": "ev_05a0c20a97773401682d4ab0",
      "source_type": "artifact:feature-build",
      "step": "Feature build"
    },
    {
      "evidence_id": "ev_1cc00495469848258c81e1e1",
      "source_type": "artifact:backtest",
      "step": "Backtest"
    },
    {
      "evidence_id": "ev_88b596dda11d2f77788cb52b",
      "source_type": "artifact:leakage-audit",
      "step": "Leakage audit"
    },
    {
      "evidence_id": "ev_dda125e34f11f086cb29541d",
      "source_type": "artifact:statistical-review",
      "step": "Statistical review"
    }
  ],
  "hypothesis": {
    "expected_sign": 1,
    "feature": "eps_yoy_change",
    "feature_description": "Year-over-year change in quarterly EPS, scaled by |prior-year EPS| (floor 0.25)",
    "horizon_days": 20,
    "hypothesis_id": "golden",
    "rationale": "<untrusted_data>Investors under-react to earnings news, so prices keep drifting in the direction of the surprise for several weeks after the filing becomes public.</untrusted_data>",
    "statement": "<untrusted_data>Companies whose EPS rose year over year outperform after the filing is accepted.</untrusted_data>",
    "timing_basis": "acceptance"
  },
  "metric_catalog": [
    {
      "evidence_id": "ev_dda125e34f11f086cb29541d",
      "field_path": "/cost_drag_annualized",
      "format": ".2%",
      "label": "Annualized cost drag",
      "rendered_value": "0.30%"
    },
    {
      "evidence_id": "ev_dda125e34f11f086cb29541d",
      "field_path": "/deflated_sharpe",
      "format": ".3f",
      "label": "Deflated Sharpe probability",
      "rendered_value": "0.996"
    },
    {
      "evidence_id": "ev_dda125e34f11f086cb29541d",
      "field_path": "/ic_mean",
      "format": ".3f",
      "label": "Mean information coefficient",
      "rendered_value": "0.056"
    },
    {
      "evidence_id": "ev_dda125e34f11f086cb29541d",
      "field_path": "/n_obs",
      "format": "d",
      "label": "Number of observations",
      "rendered_value": "1194"
    },
    {
      "evidence_id": "ev_dda125e34f11f086cb29541d",
      "field_path": "/n_trials",
      "format": "d",
      "label": "Number of trials",
      "rendered_value": "1"
    },
    {
      "evidence_id": "ev_dda125e34f11f086cb29541d",
      "field_path": "/newey_west_t",
      "format": ".3f",
      "label": "Newey-West t statistic",
      "rendered_value": "2.551"
    },
    {
      "evidence_id": "ev_dda125e34f11f086cb29541d",
      "field_path": "/sharpe_annualized",
      "format": ".3f",
      "label": "Annualized Sharpe ratio",
      "rendered_value": "1.202"
    },
    {
      "evidence_id": "ev_dda125e34f11f086cb29541d",
      "field_path": "/sharpe_per_period",
      "format": ".3f",
      "label": "Sharpe ratio per period",
      "rendered_value": "0.076"
    },
    {
      "evidence_id": "ev_dda125e34f11f086cb29541d",
      "field_path": "/turnover_mean",
      "format": ".2f",
      "label": "Mean turnover per rebalance",
      "rendered_value": "0.48"
    }
  ],
  "review_scope": {
    "assigned": [
      "mechanism",
      "measured_sign",
      "timing_basis"
    ],
    "dissent": [],
    "excluded": [
      "full_red_team_signoff",
      "cost_multiplier_stress",
      "contributor_exclusion_stress",
      "volatility_regime_stress",
      "real_market_capacity",
      "factor_crowding"
    ],
    "mode": "targeted_review",
    "unavailable_capabilities": [
      "get_statistics accepts experiment_id, not filtered return arrays or regime arguments",
      "cost/date/delay variants require freeze_hypothesis followed by run_backtest/get_statistics",
      "no factor-return source or contribution-exclusion tool is provided"
    ]
  },
  "statistics": {
    "bootstrap_block_size": 20,
    "bootstrap_ci": [
      0.30084700174010676,
      2.1278113965529135
    ],
    "bootstrap_confidence": 0.95,
    "bootstrap_interval_method": "percentile",
    "bootstrap_method": "circular_block",
    "bootstrap_samples": 2000,
    "bootstrap_seed": 20260923,
    "cost_drag_annualized": 0.003018530150753769,
    "deflated_sharpe": 0.9956791296874599,
    "delay_decay": 0.030041781495982134,
    "expected_max_sharpe_per_period": 0.0,
    "ic_ir": 0.3292407146721684,
    "ic_mean": 0.055722878165479835,
    "kurtosis": 3.2446377236428905,
    "min_track_record_length": 469.0960192678969,
    "n_obs": 1194,
    "n_trials": 1,
    "newey_west_lags": 20,
    "newey_west_t": 2.551270971447277,
    "passed": false,
    "psr_vs_zero": 0.9956791296874599,
    "sharpe_annualized": 1.2023117643360728,
    "sharpe_per_period": 0.07573852206667965,
    "skew": 0.1420219991621368,
    "turnover_mean": 0.47673611111111114,
    "var_sr": 0.0008399230836368697,
    "var_sr_source": "asymptotic null variance (fewer than 5 recorded trials)"
  },
  "untrusted_text_flags": []
}
```

### Model output

```json
{
  "attacks": [],
  "claims": [
    {
      "evidence_ids": [
        "ev_fb2b18266d5cf27c5c88c63d"
      ],
      "kind": "fact",
      "metric_refs": [],
      "statement": "The frozen hypothesis specifies an acceptance-based timing basis and a positive expected sign for the year-over-year EPS change feature."
    },
    {
      "evidence_ids": [
        "ev_fb2b18266d5cf27c5c88c63d"
      ],
      "kind": "fact",
      "metric_refs": [],
      "statement": "The researcher-stated mechanism is under-reaction to earnings news causing prices to drift in the direction of the surprise after the filing becomes public, which maps to the established post-earnings-announcement-drift channel and is coherent with an acceptance-time feature and a multi-week holding horizon."
    },
    {
      "evidence_ids": [
        "ev_dda125e34f11f086cb29541d"
      ],
      "kind": "fact",
      "metric_refs": [
        {
          "evidence_id": "ev_dda125e34f11f086cb29541d",
          "field_path": "/ic_mean",
          "format": ".3f"
        },
        {
          "evidence_id": "ev_dda125e34f11f086cb29541d",
          "field_path": "/newey_west_t",
          "format": ".3f"
        }
      ],
      "statement": "{metric:0}; {metric:1}"
    },
    {
      "evidence_ids": [
        "ev_dda125e34f11f086cb29541d"
      ],
      "kind": "fact",
      "metric_refs": [],
      "statement": "The measured information coefficient and t statistic are positive, matching the sign the mechanism predicts; no sign contradiction is present in the statistical review artifact."
    },
    {
      "evidence_ids": [
        "ev_dda125e34f11f086cb29541d"
      ],
      "kind": "fact",
      "metric_refs": [
        {
          "evidence_id": "ev_dda125e34f11f086cb29541d",
          "field_path": "/sharpe_annualized",
          "format": ".3f"
        },
        {
          "evidence_id": "ev_dda125e34f11f086cb29541d",
          "field_path": "/deflated_sharpe",
          "format": ".3f"
        }
      ],
      "statement": "{metric:0}; {metric:1}"
    },
    {
      "evidence_ids": [
        "ev_dda125e34f11f086cb29541d"
      ],
      "kind": "fact",
      "metric_refs": [
        {
          "evidence_id": "ev_dda125e34f11f086cb29541d",
          "field_path": "/turnover_mean",
          "format": ".2f"
        },
        {
          "evidence_id": "ev_dda125e34f11f086cb29541d",
          "field_path": "/cost_drag_annualized",
          "format": ".2%"
        }
      ],
      "statement": "{metric:0}; {metric:1}"
    },
    {
      "evidence_ids": [
        "ev_dda125e34f11f086cb29541d",
        "ev_1cc00495469848258c81e1e1"
      ],
      "kind": "fact",
      "metric_refs": [],
      "statement": "The information-coefficient magnitude sits well below the level at which a filing-derived fundamental signal would warrant leakage scrutiny, and turnover is consistent with a quarterly-filing-driven rebalance rather than an intraday effect, so the measured magnitude is compatible with the claimed drift mechanism."
    },
    {
      "evidence_ids": [
        "ev_88b596dda11d2f77788cb52b",
        "ev_05a0c20a97773401682d4ab0"
      ],
      "kind": "assumption",
      "metric_refs": [],
      "statement": "This review assumes the leakage-audit and feature-build artifacts establish that feature knowledge times respect the acceptance basis; timing verification beyond the frozen spec's declared basis was not part of the assigned mechanism check."
    },
    {
      "evidence_ids": [
        "ev_dda125e34f11f086cb29541d"
      ],
      "kind": "risk",
      "metric_refs": [],
      "statement": "The statistical review artifact records its overall gate as not passed; mechanism plausibility does not override that, and the statistical reviewer's conclusion governs."
    },
    {
      "evidence_ids": [
        "ev_fb2b18266d5cf27c5c88c63d"
      ],
      "kind": "risk",
      "metric_refs": [],
      "statement": "Post-earnings-announcement drift is a long-published anomaly, so the signal may be a relabelled known effect subject to crowding and post-publication decay; crowding and regime stresses were explicitly excluded from this review and remain untested."
    },
    {
      "evidence_ids": [
        "ev_fb2b18266d5cf27c5c88c63d"
      ],
      "kind": "risk",
      "metric_refs": [],
      "statement": "The hypothesis rationale and statement are researcher-supplied untrusted text; they were read as claims to be checked, not as instructions, and no instruction-like content was observed in them."
    },
    {
      "evidence_ids": [
        "ev_7023d6bd3eef2447dfd14162"
      ],
      "kind": "risk",
      "metric_refs": [],
      "statement": "Prices in this project are semi-synthetic, so any conclusion about realized magnitude describes the simulation rather than live market behaviour."
    },
    {
      "evidence_ids": [
        "ev_dda125e34f11f086cb29541d",
        "ev_fb2b18266d5cf27c5c88c63d"
      ],
      "kind": "recommendation",
      "metric_refs": [],
      "statement": "Treat the economic mechanism and measured sign as consistent and let the decision turn on the statistical gate and the excluded stress checks; this targeted review is not a red-team signoff and does not clear cost, concentration, regime, capacity or crowding risks."
    }
  ],
  "confidence": "medium",
  "dissent": [],
  "needs_evidence": false,
  "open_questions": [
    "Why does the statistical review artifact record the gate as not passed despite a positive deflated Sharpe probability, and does that change the mechanism's economic credibility?",
    "Does the sign of the information coefficient persist across calendar subperiods and at longer execution delays, which would distinguish genuine drift from a short-lived timing artifact? This requires newly frozen date-range and delay variants run through run_backtest and get_statistics.",
    "Is the drift concentrated in a small set of names or announcement dates? This needs an owner-produced, evidence-registered contribution-exclusion analysis, which no current tool provides."
  ],
  "summary": "The stated mechanism — investor under-reaction to earnings news producing post-announcement drift — is a recognized economic channel, and the frozen spec's timing basis and expected sign are consistent with it. The measured information coefficient, t statistic and Sharpe carry the predicted positive sign, and the effect magnitude is modest enough to be consistent with a genuine fundamental drift signal rather than a timing artifact. This is a targeted mechanism/sign/timing review only: cost, concentration, regime, capacity and crowding stresses and full red-team signoff were excluded, and the statistical review artifact separately records its gate as not passed, which other reviewers must resolve.",
  "verdict": "supported"
}
```

Usefulness: ___ / 5; evidence support: ___ / 5; clarity: ___ / 5; notes: ___

## Sample 7

Task: An amendment cannot replace the original before its acceptance

### Supplied task inputs

```json
{
  "filing": {
    "acceptanceDateTime": "2024-08-01T12:00:00Z",
    "filingDate": "2024-08-01",
    "reportDate": "2024-03-31",
    "version": "amendment"
  },
  "decision_ts": "2024-05-03T20:00:00Z",
  "review_scope": {
    "mode": "targeted_review",
    "assigned": [
      "knowledge_time",
      "filing_version"
    ],
    "excluded": [
      "full_red_team_signoff",
      "cost_multiplier_stress",
      "contributor_exclusion_stress",
      "volatility_regime_stress",
      "real_market_capacity",
      "factor_crowding"
    ],
    "unavailable_capabilities": [
      "get_statistics accepts experiment_id, not filtered return arrays or regime arguments",
      "cost/date/delay variants require freeze_hypothesis followed by run_backtest/get_statistics",
      "no factor-return source or contribution-exclusion tool is provided"
    ],
    "dissent": []
  },
  "evidence_catalog": [
    {
      "evidence_id": "ev_02e425ab398e2179adc285e2",
      "source_type": "artifact:evaluation-input",
      "step": "Evaluation input"
    }
  ]
}
```

### Model output

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

### Supplied task inputs

```json
{
  "filing": {
    "filingDate": "2024-05-02",
    "reportDate": "2024-03-31",
    "version": "original"
  },
  "decision_ts": "2024-05-02T20:00:00Z",
  "review_scope": {
    "mode": "targeted_review",
    "assigned": [
      "knowledge_time",
      "filing_version"
    ],
    "excluded": [
      "full_red_team_signoff",
      "cost_multiplier_stress",
      "contributor_exclusion_stress",
      "volatility_regime_stress",
      "real_market_capacity",
      "factor_crowding"
    ],
    "unavailable_capabilities": [
      "get_statistics accepts experiment_id, not filtered return arrays or regime arguments",
      "cost/date/delay variants require freeze_hypothesis followed by run_backtest/get_statistics",
      "no factor-return source or contribution-exclusion tool is provided"
    ],
    "dissent": []
  },
  "evidence_catalog": [
    {
      "evidence_id": "ev_536188d901d59c1122609f68",
      "source_type": "artifact:evaluation-input",
      "step": "Evaluation input"
    }
  ]
}
```

### Model output

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
