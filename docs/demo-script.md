# Three-minute recording script

Prepared for Alex's narration. **The video has not been recorded.** This walkthrough uses the free rules provider and scripted approval actors. Every price/return is simulated; do not call the recorded reviews live Claude output.

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

## Storyboard and narration

| Time | Visual | Suggested narration |
|---|---|---|
| 0:00–0:20 | Portfolio headline and simulated-data notice | “I built Systematic Research Factory to connect AI engineering with quantitative research. It tests whether a conclusion deserves approval, with frozen hypotheses, point-in-time evidence and separate review authority.” |
| 0:20–0:45 | Clean report: steps, metrics, gate | “This offline run uses deterministic reviewers. Code computes the numbers; reviews cite evidence; a separate scripted actor demonstrates the human-approval boundary. It is a workflow demonstration, not a real investment approval.” |
| 0:45–1:10 | Leakage report and cited filing timing | “This version treats EPS as available at fiscal period-end, before the filing was accepted. The audit re-derives availability from its inputs and stops the run. A better-looking backtest cannot make unavailable information valid.” |
| 1:10–1:35 | Overfit report, trial count and statistical finding | “The ledger retains the experiment history. This weak signal follows many related trials, so its statistical review accounts for selection. The model cannot override the gate or quietly erase those trials.” |
| 1:35–2:05 | Research control chart and raw CSV link | “I froze a separate simulation protocol and published all 240 combinations. The timing leak was blocked throughout these controls, while only 13 of 20 clean planted worlds passed the combined gate. Twenty worlds leave wide uncertainty. These are simulated returns, not empirical alpha.” |
| 2:05–2:35 | Actual current-runtime replay and CI page | “Runs retain source, inputs and numerical runtime. Current-runtime replay checks exact artifact hashes. Hosted CI revealed a last-bit BLAS difference across CPUs; that is now fingerprinted, and historical cross-host numerical comparison is labeled separately.” |
| 2:35–3:00 | Architecture, case study and current status | “The system exposes typed MCP tools and persists state and cost reservations. Thirty-seven offline cases test governance behavior. The live model comparison reports its failures separately. An isolated hosted restore replayed all six deterministic artifacts exactly; public demos still use free rules. The repository includes the evidence and reproduction commands.” |

Add captions from the final spoken wording, not from an older script. End on the GitHub portfolio link. An unlisted draft is appropriate for review; publish a video URL only after checking that the visible revision, claims and current status agree. Desktop/mobile browser screenshots have been captured and inspected through hosted Chromium checks. Your personal recording remains unrecorded.
