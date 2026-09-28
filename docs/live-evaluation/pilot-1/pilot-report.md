# Live Anthropic pilot ? stopped pending reconciliation

Two preregistered pilot cases were attempted using the frozen source and skills. Neither passed the complete evaluation. This is not a successful live-provider baseline.

| Case | Outcome | Recorded cost |
|---|---|---:|
| Point-in-time after-close review | Model returned `leakage`, correctly identifying the timing issue, but evidence-contract validation rejected the response | $0.13495 |
| Clean workflow | Ended `needs_review`; approval was refused; no final decision | Unknown for the unresolved call |

The confirmed response used `claude-opus-5`, with 12,735 input and 2,851 output tokens. The ledger retains one uncertain reservation of $0.99998 for the clean workflow's economic-rationale review. This is an upper-bound hold, not a confirmed charge. Recorded usage plus the unresolved hold totals $1.13493.

Further paid calls are stopped until provider usage is reconciled. The owner must check Anthropic usage around September 28, 2026, 00:13?00:16 UTC (September 27, 8:13?8:16 p.m. Eastern). Do not reset the ledger or guess a zero refund.

The point-in-time response also exposes a contract mismatch to investigate: the validator requires `reject` for an unrefuted blocking attack, but the point-in-time task permits only `clean`, `leakage`, and `needs_evidence`. Other failures include numeric form identifiers in prose and a calculation claim without structured metric references. Preserve these results; any corrected implementation or prompt must be evaluated as a separately labeled revision.

Raw scorecards: [point-in-time](pilot-pit.json), [clean workflow](pilot-clean.json). Hashes, usage, and outstanding reservation: [pilot summary](pilot-summary.json). Inputs: [frozen manifest](input-manifest.json). The SQLite accounting database remains local and is not a publication artifact.
