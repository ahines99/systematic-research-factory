# Live model evaluation protocol

Prepared before any paid calls. The first pilot was executed and failed complete acceptance; its [frozen report](live-evaluation/pilot-1/pilot-report.md) preserves both attempts. The offline 37-case scorecard is not a live Anthropic baseline.

## Revision two, declared before further generation

The first pilot exposed an incompatible negative-verdict check and a long-response transport failure. Revision two fixes task-specific negative verdicts, consumes provider streaming internally, and clarifies concise qualitative output versus numeric metric references. These changes were informed by the pilot: subsequent results are a separate revised experiment, not an untouched replication of the initial protocol. Original artifacts and accounting are retained.

The owner explicitly instructed continuation without dashboard reconciliation. The uncertain first-pilot call retains its full $0.99998 reservation in the same ledger; it is never refunded, represented as confirmed spend, or excluded from the $3 daily/pilot and $20 lifetime admission checks. Continue only while confirmed usage plus all unresolved holds plus the next bounded run fits the allowance. Dashboard reconciliation remains an unverified limitation. No retry of the uncertain original step is permitted.

Run the same two-case pilot under the revised source, then the same seven-case paired comparison if compatible and affordable. Use distinct revision-two output paths. Preserve failed checks; neither prompt tuning nor case replacement is allowed during this revision. If the daily allowance prevents completion, publish the completed observations and remaining schedule instead of increasing caps.

## Frozen comparison

The fourth clean-workflow pilot returned a valid grounded economic review, then paused after 45,548 recorded tokens across two responses ($0.403820; 110.941 seconds). Its subsequent retry could not fit the remaining 60,000-token ceiling. Before further testing, the default token ceiling is raised to 150,000 to accommodate three skill-backed steps and bounded validation retries; financial caps are unchanged. Completed paid responses are now audited immediately, and scorecards include run state/reason so a later budget stop cannot hide the diagnostic record. The fourth pilot's implementation response was billed and recorded in usage, but its raw body was not retained in that old scorecard; do not imply otherwise.

The third clean-workflow pilot again failed (76.625 seconds, $0.384835); canonical metric references resolved, but the blanket numeric-prose check misclassified the repository identifier `ADR-0003` as a measurement. A fourth corrective revision explicitly exempts only the repository's ADR identifiers and standard SEC form names from this lexical check. Actual quantitative claims still require validated metric references; arbitrary numbers and invented ADR identifiers remain rejected in regression tests. The final corrective pilot may lower its per-run cap to the remaining original $3 allowance; this is operational compatibility testing, not a skills-effect estimate. All prior failures remain published.

Revision two results: the targeted PIT review passed (29.337 seconds, $0.122790). The clean workflow failed output grounding after two responses (110.353 seconds, $0.446470), with complete recorded usage and no new uncertain reservation. [Raw outputs](live-evaluation/revision-2/pilot-clean.json) are retained. The original uncertain call remains held.

Before a third corrective pilot, add a code-generated metric catalog containing only resolvable evidence references and their canonical formats. The second pilot showed the model guessing formatting and field paths absent from its inputs. The validator remains strict; no invalid output is promoted. This is a further development revision, not a treatment/control result. Repeat the clean-workflow pilot once under this revision while charging every earlier attempt and unresolved hold to the original allowance. Do not start a paired claim until the source is frozen and enough budget remains. Preserve latency failures as failures; do not raise the frozen case's latency threshold.

Keep the accepted `claude-opus-5` default, structured-output contract, frozen case files and statistical thresholds. Verify current availability and price again before the pilot; never substitute another model silently. Compare Skills enabled versus `--no-skills` with identical case/input hashes, three planned repeats per arm. Alternate arm order by repeat (on/off, off/on, on/off). Use distinct output directories and one durable accounting database for the whole experiment.

Primary live subset: cases 01 (clean workflow), 14 (SEC-timed workflow), 31–34 (four point-in-time judgments) and 37 (missing full-red-team evidence). These exercise the actual provider without injected reviewer output. Preserve the complete offline suite separately: injected-output cases such as fabricated metrics test contract enforcement, not model quality. Report requested provider, actual provider, `model_exercised`, returned model IDs, case/skill/source hashes and the number of paid calls. A requested Anthropic suite must not be described as 37 model-tested cases.

Primary outcomes: case pass fraction by arm and paired case/repeat differences. Also report dimension failures, invalid schemas, refusals, missing-evidence behavior, tokens, latency, cost, and unresolved reservations. Provide all raw redacted outputs; three repeats on seven cases are a small compatibility/behavior study, not a powered causal estimate of general skill usefulness. No tuning against these reported outputs. New prompt revisions require a separately labeled experiment.

## Pilot and stopping rules

The accepted total allowance is **$20**, including pilot and repeats; pilot allowance **$3**. Keep existing per-run **$1** and per-UTC-day **$3** caps. Use a provider-side project spend limit where available. The application daily cap is not a lifetime experiment cap: before each batch, sum settled costs plus all outstanding reservations across this accounting database, and stop if the remaining allowance cannot cover the next bounded reservation. Never reset the database, rotate accounting identities or raise limits to get a preferred result.

Start with one point-in-time judgment and a clean workflow. Verify schema behavior, requested versus returned model, tokens, recorded cost and billed usage. Stop on a price mismatch, unexpected model/fallback, unexplained pending reservation, or incompatible API behavior. Reconcile uncertain calls from provider evidence before retrying; do not erase them. Freeze the pilot report before scaling up. If the budget permits fewer than three complete repeats, publish a budget-limited partial study with missing observations; do not silently add spending.

The owner confirms dashboard usage and reviews a blinded sample: four outputs per arm, with arm labels hidden until review. Score usefulness, evidence support and clarity separately from automated pass/fail. The owner need not claim domain conclusions beyond the supplied evidence.

## Execution setup

Set `ANTHROPIC_API_KEY` in a local ignored `.env` or platform secret store, never chat or a committed file. A Claude chat subscription is not API billing. Use a dedicated durable SQLite path (or dedicated PostgreSQL database), not `:memory:`. Copy the exact seven case files to an isolated `var/live-eval/cases` directory, recording their SHA-256 hashes before running. Retain the same case directory and accounting URL for both arms.

```bash
# Repeat/arm labels are deliberate. Never overwrite previous outputs.
uv run --no-sync rsf --database-url sqlite:///var/live-eval/accounting.db eval \
  --provider anthropic --cases var/live-eval/cases --out var/live-eval/repeat-1/on.json
uv run --no-sync rsf --database-url sqlite:///var/live-eval/accounting.db eval \
  --provider anthropic --cases var/live-eval/cases --no-skills --out var/live-eval/repeat-1/off.json
```

These are batch commands for after the pilot and allowance checks, not instructions to start spending immediately. Three-day/monthly hosting spend is a separate ledger. A real supported MCP-client interaction must also demonstrate authenticated research/read and approval-role boundaries; HTTP smoke tests alone are not a human client walkthrough.

## Required report

Publish protocol revision, exact inputs, pilot compatibility/accounting evidence, all attempted repeats, paired results, cost including failures, missing observations, manually sampled ratings, and limitations. A neutral or negative result is acceptable. No skill-uplift or live-provider-readiness claim is authorized before this evidence exists.
