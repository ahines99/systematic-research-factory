# Three-minute demo script (RSF-052)

For a screen recording. Everything below runs locally with no API key.

**Setup (before recording):** `uv sync --locked`, then clear `var/`.

| Time | Show | Say |
|---|---|---|
| 0:00 | README "Why this is not just a chatbot" | "A backtest that looks good is usually wrong in a predictable way: look-ahead, survivorship, or trying fifty variants. This system makes those mistakes impossible to hide." |
| 0:20 | `uv run rsf demo --out-dir var/reports` | "Six recorded scenarios run end to end in about two seconds: the same idea done right, done with a leak, done on survivors only, and found after 99 other tries." |
| 0:45 | `var/reports/leak-caught.html` | "Here EPS is treated as known at quarter-end. The backtest looks *better*, and the leakage audit fails the run. It re-derives every input's SEC acceptance time from evidence and finds inputs up to 75 days in the future." |
| 1:15 | `var/reports/overfit-rejected.html` | "A weak signal. Alone it passes, but it's the 100th variant in its family, so the deflated Sharpe ratio rejects it. The ledger counted every trial." |
| 1:40 | `var/reports/clean-approved.html`: findings and audit trail | "Every finding cites evidence IDs. The model-drafted reviews had to cite them too. The gate is deterministic, and a human who isn't the requester made the decision." |
| 2:10 | `uv run rsf replay <run_id>` | "Replaying from the archived snapshot gives byte-identical artifacts." |
| 2:30 | `uv run rsf eval` | "28 golden cases, including prompt injection and invented evidence, scored on seven dimensions. They run in CI." |
| 2:50 | `docs/architecture.md` diagram | "Real SEC filings, simulated prices, a typed MCP interface, and no trading tools. Research you can audit." |

The recording itself is an owner action.
