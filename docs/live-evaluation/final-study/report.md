# Frozen live-provider comparison

Source: `d0dd403561a5615846852a7b1cab53e4896d6cc0`. Model: `claude-opus-5`. 42/42 planned observations completed; 21 paired case/repeats.

Three planned repeats per arm across seven cases; arm order on/off, off/on, on/off. Source, prompts and thresholds stayed fixed during this comparison. Earlier pilots informed this source, so these are development-conditioned compatibility results, not an unbiased general skills-uplift estimate.

| Arm | Cases passed | Model-exercised | Recorded cost | Median seconds |
|---|---:|---:|---:|---:|
| skills-on | 15/21 | 21 | $4.928400 | 23.845 |
| skills-off | 14/21 | 21 | $2.371960 | 18.02 |

## Every observation

| Repeat | Arm | Case | Result | Seconds | USD | Failed checks |
|---|---|---|---|---:|---:|---|
| 1 | off | 01-clean-pass | FAIL | 75.42 | 0.215425 | approval accepted: got CONFLICT; run status: needs_review (expected complete); gate recommendation: needs_more_evidence: ['Evidence needed: Reviewer needs evidence.']; final decision: None; within time budget: 75.42s |
| 1 | off | 14-edgar-real-filings | FAIL | 82.101 | 0.226425 | stopping step: Implementation review; within time budget: 82.10s |
| 1 | off | 31-pit-after-close | PASS | 14.997 | 0.046970 |  |
| 1 | off | 32-pit-amended-version | PASS | 16.944 | 0.049030 |  |
| 1 | off | 33-pit-date-only | PASS | 13.985 | 0.044515 |  |
| 1 | off | 34-pit-clean-version | PASS | 12.686 | 0.041560 |  |
| 1 | off | 37-full-red-team-missing-analyses | PASS | 36.852 | 0.081685 |  |
| 1 | on | 01-clean-pass | FAIL | 141.342 | 0.545260 | approval accepted: got CONFLICT; run status: needs_review (expected complete); gate recommendation: needs_more_evidence: ['Evidence needed: Reviewer output rejected.']; final decision: None; within time budget: 141.34s; within cost budget: $0.5453 |
| 1 | on | 14-edgar-real-filings | FAIL | 138.085 | 0.588675 | within time budget: 138.08s; within cost budget: $0.5887 |
| 1 | on | 31-pit-after-close | PASS | 18.333 | 0.100635 |  |
| 1 | on | 32-pit-amended-version | PASS | 19.413 | 0.105520 |  |
| 1 | on | 33-pit-date-only | PASS | 20.077 | 0.107330 |  |
| 1 | on | 34-pit-clean-version | PASS | 21.554 | 0.109325 |  |
| 1 | on | 37-full-red-team-missing-analyses | PASS | 41.664 | 0.230525 |  |
| 2 | off | 01-clean-pass | FAIL | 107.831 | 0.304705 | approval accepted: got CONFLICT; run status: needs_review (expected complete); gate recommendation: needs_more_evidence: ['Evidence needed: Reviewer needs evidence.']; final decision: None; within time budget: 107.83s |
| 2 | off | 14-edgar-real-filings | FAIL | 68.732 | 0.204530 | stopping step: Implementation review; within time budget: 68.73s |
| 2 | off | 31-pit-after-close | PASS | 13.703 | 0.042970 |  |
| 2 | off | 32-pit-amended-version | PASS | 15.676 | 0.047755 |  |
| 2 | off | 33-pit-date-only | PASS | 18.177 | 0.052165 |  |
| 2 | off | 34-pit-clean-version | PASS | 16.807 | 0.051310 |  |
| 2 | off | 37-full-red-team-missing-analyses | PASS | 29.568 | 0.072710 |  |
| 2 | on | 01-clean-pass | FAIL | 126.553 | 0.522210 | approval accepted: got CONFLICT; run status: needs_review (expected complete); gate recommendation: needs_more_evidence: ['Evidence needed: Reviewer needs evidence.']; final decision: None; within time budget: 126.55s; within cost budget: $0.5222 |
| 2 | on | 14-edgar-real-filings | FAIL | 141.541 | 0.558720 | stopping step: Implementation review; within time budget: 141.54s; within cost budget: $0.5587 |
| 2 | on | 31-pit-after-close | PASS | 21.544 | 0.108660 |  |
| 2 | on | 32-pit-amended-version | PASS | 23.845 | 0.107820 |  |
| 2 | on | 33-pit-date-only | PASS | 26.386 | 0.118830 |  |
| 2 | on | 34-pit-clean-version | PASS | 14.976 | 0.095700 |  |
| 2 | on | 37-full-red-team-missing-analyses | PASS | 34.945 | 0.221075 |  |
| 3 | off | 01-clean-pass | FAIL | 127.91 | 0.380115 | approval accepted: got CONFLICT; run status: needs_review (expected complete); gate recommendation: needs_more_evidence: ['Evidence needed: Reviewer needs evidence.']; final decision: None; within time budget: 127.91s |
| 3 | off | 14-edgar-real-filings | FAIL | 82.326 | 0.234830 | stopping step: Implementation review; within time budget: 82.33s |
| 3 | off | 31-pit-after-close | PASS | 14.759 | 0.045370 |  |
| 3 | off | 32-pit-amended-version | PASS | 15.374 | 0.048580 |  |
| 3 | off | 33-pit-date-only | PASS | 18.02 | 0.052290 |  |
| 3 | off | 34-pit-clean-version | PASS | 17.012 | 0.050610 |  |
| 3 | off | 37-full-red-team-missing-analyses | FAIL | 32.922 | 0.078410 | judgment contract expected rejection: claim 0 is a fact without evidence; cite evidence or mark it an assumption; targeted review verdict: expected needs_more_evidence; got claim 0 is a fact without evidence; cite evidence or mark it an assumption; targeted review uncertainty flag: missing assigned evidence must be explicit, and supported answers must not invent uncertainty |
| 3 | on | 01-clean-pass | FAIL | 88.571 | 0.375790 | approval accepted: got CONFLICT; run status: needs_review (expected complete); gate recommendation: needs_more_evidence: ['Evidence needed: Reviewer needs evidence.']; final decision: None; within time budget: 88.57s |
| 3 | on | 14-edgar-real-filings | FAIL | 90.672 | 0.378090 | stopping step: Implementation review; within time budget: 90.67s |
| 3 | on | 31-pit-after-close | PASS | 17.443 | 0.100710 |  |
| 3 | on | 32-pit-amended-version | PASS | 19.188 | 0.104845 |  |
| 3 | on | 33-pit-date-only | PASS | 22.686 | 0.116005 |  |
| 3 | on | 34-pit-clean-version | PASS | 22.851 | 0.111425 |  |
| 3 | on | 37-full-red-team-missing-analyses | PASS | 34.761 | 0.221250 |  |

## Accounting and interpretation

All development pilots and study calls share one durable ledger: **$9.479900 confirmed usage** and **$0.999980 unresolved reserve**. The latter is a conservative budget hold, not a confirmed bill. These remain below the owner's $20 lifetime allowance. No reservation was refunded or ledger reset. Provider-dashboard reconciliation was explicitly waived by the owner; actual billing for the original lost response remains unknown.

The exact executed runner is archived as `runner.py.txt`; the prospective manifest records its UTF-8/LF source SHA-256, and `runner-identity.json` also records the executed Windows file bytes. The original pre-pilot input manifest preserves the unchanged case and skill-file hashes. Runtime case provenance records the explicitly authorized daily-cap override. Raw JSON includes checks, source/runtime/input/skill provenance, validated artifacts, rejected response audits, token usage and run state. The old revision-four pilot lost one billed raw response before the immediate-audit fix; its cost remains included. Longer audit strings may be summarized by the audit redactor. Repeated cases share fixed inputs and are not independent research worlds.

Failure of output grounding, model semantic expectations, $0.50 case-level cost targets or 60-second workflow latency remains a failure. Per-case evaluation thresholds are distinct from the $1 safety cap. No threshold was relaxed to improve pass rates. The Skills-off arm retains the same core prompt, schema, evidence payload and hard validation; it omits the procedural skill assets. This is not a comparison with an unguarded chatbot. These results do not demonstrate investment performance or reliable unsupervised research. Public demos remain deterministic rules-based.

The earlier [one-case diagnostic](../component-pair/prospective-manifest.json) passed in both arms but was selected after a successful pilot and is excluded here. Human usefulness/evidence/clarity ratings remain uncollected; use the blinded packet before looking at its key.
