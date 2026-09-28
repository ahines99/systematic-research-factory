# Three-minute recording script

Prepared for Alex's narration. **The video has not been recorded.** This walkthrough uses the free rules provider and scripted approval actors. Every price/return is simulated; do not call the recorded reviews live Claude output.

Use the [canonical v1 positioning](PORTFOLIO_POSITIONING.md) for the headline and claims: **Systematic Research Factory — Quantitative Research & AI Engineering**. V1 is complete and presentation-ready. This recording explains the released work; it is not a prerequisite for adding the project to a resume or a plan for more platform features.

## Prepare a fresh recording workspace

Use a new database and blob directory rather than clearing `var/`. In PowerShell:

```powershell
uv sync --locked
$env:RSF_DATABASE_URL = 'sqlite:///var/recording-01/rsf.db'
$env:RSF_BLOB_STORE = 'file://var/recording-01/blobs'
uv run --no-sync rsf --provider rules demo --out-dir var/recording-01/reports
uv run --no-sync rsf --provider rules runs
uv run --no-sync rsf eval --provider rules --out var/recording-01/scorecard.json
```

Choose a new numbered directory for another take. Open the generated reports and the research note before recording. Rehearse a replay using a run ID from this fresh database in the same source/runtime. Do not show `.env`, API keys, billing details or private browser tabs. If any command takes longer than the narration, use a clearly labeled cut; do not invent a speed measurement.

After selecting an actual run ID from the `runs` output, execute `uv run --no-sync rsf --provider rules replay <run_id>` with that placeholder replaced. Keep the recording workspace environment variables in the same terminal. If the numerical runtime is incompatible, show the explicit rejection or use a compatible recorded runtime; do not substitute regenerated expected hashes.

## Storyboard and narration

| Time | Visual | Suggested narration |
|---|---|---|
| 0:00–0:20 | Portfolio headline and simulated-data notice | “I built Systematic Research Factory to connect AI engineering with quantitative research. It tests whether a conclusion deserves approval, with frozen hypotheses, point-in-time evidence and separate review authority.” |
| 0:20–0:45 | Clean report: steps, metrics, gate | “This offline run uses deterministic reviewers. Code computes the numbers; reviews cite evidence; a separate scripted actor demonstrates the human-approval boundary. It is a workflow demonstration, not a real investment approval.” |
| 0:45–1:10 | Leakage report and cited filing timing | “This version treats EPS as available at fiscal period-end, before the filing was accepted. The audit re-derives availability from its inputs and stops the run. A better-looking backtest cannot make unavailable information valid.” |
| 1:10–1:35 | Overfit report, trial count and statistical finding | “The ledger retains the experiment history. This weak signal follows many related trials, so its statistical review accounts for selection. The model cannot override the gate or quietly erase those trials.” |
| 1:35–2:05 | Research control chart and raw CSV link | “The protocol and seeds were frozen before execution; the worlds were generated during execution. All 240 outcomes are published. All 40 constructed timing leaks were blocked; 13 of 20 clean planted worlds passed the audit/statistical gate. That is not a calibrated power estimate or empirical alpha.” |
| 2:05–2:35 | Actual current-runtime replay and CI page | “Runs retain source, inputs and numerical runtime. Current-runtime replay checks exact artifact hashes. Hosted CI revealed a last-bit BLAS difference across CPUs; that is now fingerprinted, and historical cross-host numerical comparison is labeled separately.” |
| 2:35–3:00 | Architecture, case study and current status | “Typed MCP tools expose durable workflows and spending controls. Skills-on passed 15 of 21 live observations; Skills-off passed 14. Every full-workflow observation missed an acceptance criterion. These results do not establish general uplift. The repository publishes failures, recovery evidence, and AI-assisted development attribution.” |

Add captions from the final spoken wording, not from an older script. End on the GitHub portfolio link. An unlisted draft is appropriate for review; publish a video URL only after checking that the visible revision, claims and current status agree. Desktop/mobile browser screenshots have been captured and inspected through hosted Chromium checks. Your personal recording remains unrecorded.

## Interview rehearsal: multiple-testing defect

**Prompt:** How could more experiments make the statistical evidence look stronger?

**Suggested answer:** “The original Deflated Sharpe calculation could use the observed variance of trial Sharpes. Near-duplicate trials drove that variance toward zero, weakening the multiple-testing adjustment. In the documented audit example, 99 near-identical trials moved DSR from about 0.24 to 0.965. The fix takes the larger of observed variance and an asymptotic sampling-variance floor. The committee also recomputes DSR using the current related-trial count; the original statistical artifact stays unchanged for replay.”

**Follow-up:** Does that fully solve researcher degrees of freedom?

**Suggested answer:** “No. Relatedness uses explicit family and feature/dataset rules, and experiments outside this installation remain invisible. Counting correlated near-duplicates independently can overcorrect. The benefit is that a family rename or collapsed trial variance cannot quietly remove this adjustment.”

Evidence: [ADR-0008 and its audit example](adr/0008-review-time-trial-counting.md), [near-duplicate variance regression](../tests/test_research.py), [review-time trial-count regression](../tests/test_audit_regressions.py), and [committee workflow implementation](../src/research_factory/workflows/steps.py). Explain the distinction between a preserved calculation and a current decision; do not claim a universal independent-trial estimator.

## Interview rehearsal: stale approval

**Prompt:** What happens if research changes after someone approves it?

**Suggested answer:** “An approval must refer to the evidence that was reviewed. The audit found that related trials or findings could change while an earlier approval remained usable. The corrected implementation binds the decision to a gate context covering related trials, active findings, artifacts, and recorded thresholds. It validates that context when recording and consuming approval. A mismatch requires renewed review instead of silently reusing the old decision.”

**Follow-up:** What verifies the fix?

**Suggested answer:** “The regression adds a related trial before approval and checks that stale approval is rejected. It then records a fresh approval, adds another trial before consumption, and verifies that the run returns to review. A newly recorded decision has a different context and can complete the run.”

Evidence: [historical remediation finding A02](audits/2026-09-27/remediation.md), [approval implementation](../src/research_factory/services/approvals.py), and `test_approval_is_invalidated_by_new_trials_and_can_be_recorded_again` in the [workflow regressions](../tests/test_remediation_workflow.py). The remediation document records an earlier unreleased state; [current status](PORTFOLIO_STATUS.md) records the completed release.

## Attribution and owner-only preparation

Use this attribution when discussing either story: “I built this project with AI coding assistance. These findings came through AI-assisted audits and remediation; I can explain the implementation, tradeoffs, and verification.” Do not imply an unaided discovery or a customer production incident. Practice tracing each answer into the linked source and regression before presenting it as personal technical experience.

The engineering handoff prepares the script and evidence; **Alex's rehearsal, personal narration, and human ratings remain his actions**. Rehearse each defect story in about 60 seconds, then answer its follow-up without reading. Record and review a roughly three-minute take; publish its URL only when the actual recording exists. No video is recorded by this document.

For the separate [blinded human-review packet](live-evaluation/final-study/blinded-review.md), rate usefulness, support, and clarity before opening the arm key. This script does not provide ratings or claim that they have been collected. The [hosting-cost observation](operations/cost-observation.md) also remains time-dependent; no projected budget should be narrated as a measured monthly bill. These presentation and observation tasks do not reopen v1 engineering scope. Empirical market research belongs to the separate v2 study described in the canonical positioning.
