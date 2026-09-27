# Security, APIs, approval and judgment audit — 2026-09-27

Read-only audit of auth.py, http_app.py, server/, judgment/, approvals/budget services, related workflow integration, tests and threat model. No production credentials, real model calls or external writes. Probes used `.venv312/Scripts/python.exe` with scripts piped over stdin, SQLite in memory and memory blobs; no probe source files were persisted. Root owns full suite verification.

## Existing work verified by inspection

- API keys use random 256-bit secrets, hashed storage, revocation and server-side roles. Reserved public-demo owners cannot be issued keys.
- MCP tools share policy enforcement and typed errors; private run reads fail closed for guests. HTTP context propagation also protects resources. Viewer/researcher/approver access is intentionally shared-read, not tenant isolation.
- Resume/cancel require requester ownership or approver role. Approvals require approver role, separate requester, appropriate workflow pause and a deterministic gate. Database uniqueness prevents duplicate committee decisions.
- Guests use free RulesProvider for live runs. Guest data reads omit stored evidence. IP rate limits are bounded and only trust proxy headers when configured.
- `/mcp` applies host/origin allowlists and a 4 MiB body limit. The oversize-body probe returned 413 as intended.
- Judgment schema validation rejects unknown evidence identifiers, uncited fact/calculation claims, unknown verdicts and extra fields. Committee memos cannot be more permissive than the gate at initial drafting. HTML output is escaped.

## Verified findings and remaining work

### SEC-01 — P1: approvals can finalize against a newly rejecting gate

Evidence: `src/research_factory/services/approvals.py:69` computes the gate from stored findings; `:88` validates that stale gate. `src/research_factory/workflows/steps.py:790` recomputes review-time trial-count findings on resume; `:824` consumes the already-recorded approval; `:851` completes with its decision without checking the newly computed gate.

Reproduction: freeze `demo_experiment('weak-first', dataset='synthetic:v1:weak', family='later-search')`; start its primary workflow and let it pause for approval. Then freeze 99 related variants using `demo_experiment(f'later-{k:03d}', dataset='synthetic:v1:weak', family=f'renamed-{k}', delay=31+k)` for k in range(99). Record an approve decision as bob and advance. All operations use real services and free rules judgments.

Observed output:
```
INITIAL needs_review gate=approve
BEFORE_APPROVE gate=approve
FINAL complete decision=approve gate=reject
reason: Statistical threshold failed: Failed: deflated sharpe at today's trial count.
```

Impact: a normal sequence of freezing additional trials while an approver considers a run defeats the stated non-overridable statistical gate; the final report contradicts itself. This does not require concurrency or malicious database access. Current regression `test_q5_trials_frozen_after_an_experiment_count_at_review` freezes variants before the workflow starts, missing this ordering.

Fix/acceptance: recompute and bind approval to a fresh, versioned committee evaluation; atomically validate the applicable gate at decision/consumption time. Never finalize approve when current gate rejects or needs more evidence. Add the exact pause → freeze variants → approve regression, plus gate changes between decision record and resume. Handle stale immutable approvals without trapping the run behind its one-decision unique index.

### SEC-02 — P1: advertised hard spend caps are retrospective checks

Evidence: `src/research_factory/services/budget.py:31-47` reads previously recorded totals; `src/research_factory/workflows/steps.py:542-550` checks, calls, then records. Provider uses fixed `max_tokens=16000` at `src/research_factory/judgment/providers.py:305`. There is no reservation or adjustment to the remaining token/cost allowance.

Reproduction: configure both run and daily caps to $0.01. Use an offline RulesProvider subclass returning its normal valid result with input_tokens=1000, output_tokens=200 and cost_usd=0.10. Start a normal clean demo workflow.

Observed: first judgment is admitted and records `(1200, 0.1)`; only the following step pauses with `BUDGET_EXCEEDED: run cost budget reached ($0.10 >= $0.01)`. Concurrent independent runs can all pass before any records arrive (verified code path; concurrency overrun not separately stress-tested). Thus the $3/day production setting is a stop-after threshold, not a hard cap.

Fix/acceptance: reserve conservative call cost/tokens transactionally across workers before dispatch, constrain output tokens to the remaining budget, and settle actual usage. Include near-cap, simultaneous-run and retry tests. If deliberate soft limits are retained, explicitly document maximum overshoot and remove hard-cap claims. Unknown provider model pricing falls back to one model's rate (`providers.py:60`); fail closed or conservatively price unknown fallback models when promising a spend ceiling.

### SEC-03 — P1/P2: paid refusal and empty responses disappear from usage accounting

Evidence: `src/research_factory/judgment/providers.py:321-328` obtains usage and estimates cost, then raises NeedsEvidenceError on refusal or no text. The caller records only returned JudgmentResponse objects at `src/research_factory/workflows/steps.py:544`. A second unaccounted path is cancellation: `steps.py:36` abandons worker threads on cancellation before caller-side accounting.

Reproduction: use AnthropicProvider with an injected fake client returning usage(input_tokens=1000, output_tokens=200), model='claude-opus-5', stop_reason='refusal', content=[]. Run the real workflow; no network call occurs.

Observed: run pauses with `NEEDS_EVIDENCE: the model declined to review this input; a human must review it`; usage is `(0, 0.0)`. Empty responses follow the same verified code path. The workflow auditor independently reproduced timeout loss: a fake provider returning $1 after 0.1 seconds, with step timeout 0.02 seconds and max_attempts=2, completed two provider calls while recorded usage remained zero (reported to root; see workflow audit for its probe).

Impact: reports and caps undercount successfully billed provider responses. Repeated resume can spend without depleting the app budget. Priority P1 for enabling paid production traffic, P2 for the current offline-only workflow.

Fix/acceptance: account for provider usage independently of interpretation success, preserve usage on error objects/results, and reconcile calls that outlive timeout/cancellation. Test refusal, empty content, invalid JSON (currently accounted), timeout with late success and retries. Keep uncertain-call reservations until reconciliation.

### SEC-04 — P2: explicit needs_evidence output is ignored

Evidence: `src/research_factory/judgment/contract.py:47` defines needs_evidence; validation checks schema/verdict/citations only. Economic and implementation execution use only verdict at `src/research_factory/workflows/steps.py:661` and `:705`; no consumer reads the boolean. Implementation verdicts do not even include a needs_evidence alternative.

Reproduction: use a RulesProvider subclass preserving the valid feasible implementation verdict but setting `response.raw['needs_evidence']=True` and `open_questions=['Missing capacity and liquidity evidence.']`. Start a clean workflow.

Observed: reaches `APPROVAL_REQUIRED: awaiting a committee decision; the gate recommends approve`. The explicit uncertainty produces no needs_evidence finding and no approval restriction.

Fix/acceptance: map needs_evidence=true to a deterministic finding/pause or reject inconsistent outputs; provide an implementation-review insufficient-evidence verdict. Test every judgment step and inconsistent flag/verdict combinations. A valid model declaration of missing evidence must not silently yield an approving gate.

### SEC-05 — P2: public custom POST route bypasses the transport body limit

Evidence: `src/research_factory/http_app.py:175-180` reads all request JSON in `/demo/live-run`; transport middleware is applied to `/mcp`, not this custom route. `docs/threat_model.md:29` broadly claims requests are capped at 4 MB.

Reproduction: TestClient with memory services; POST `/demo/live-run` JSON `{"scenario":"not-a-scenario","padding":"x"*(4*1024*1024+1)}`. Separately POST an equivalently padded MCP healthcheck.

Observed: custom route returns 400 scenario validation after consuming the >4 MiB body; MCP returns 413. This proves missing application-level protection, not measured production memory exhaustion. No load test was run.

Fix/acceptance: apply a streaming body-size limit to the entire ASGI app or this route before reading/decoding, including chunked requests; assert 413 for over-limit payloads on both paths. Byte limits should apply before budget checks since those currently occur after parsing.

### SEC-06 — P2/P3: malformed scenario shapes cause HTTP 500

Evidence: `src/research_factory/http_app.py:181` performs set membership on user-controlled scenario without checking string type.

Reproduction: POST `/demo/live-run` JSON `{"scenario":[]}` or `{"scenario":{}}` with TestClient(raise_server_exceptions=False).

Observed: both return 500 Internal Server Error, from unhashable input. A null scenario correctly returns 400. This causes no verified data breach; it is a public-input robustness/API-contract defect.

Fix/acceptance: validate body with a typed request model or check type before membership; invalid object/array/string/null/number cases must consistently return a typed 4xx, with no workflow creation.

## Additional bounded hardening / documentation work (inspection-confirmed)

1. **Citation membership is not factual correctness.** `src/research_factory/judgment/contract.py:85-104` does not check whether cited evidence supports the statement or whether any number occurs in the cited artifact. Only fact/calculation kinds require a citation (`:28`); summary, risks and recommendations can be uncited. README.md:3 says a model ?can't compute numbers?; docs/architecture.md:3 says every number is reproducible and every claim traceable. Actual guarantee: authoritative quantitative artifacts are deterministic, but model prose can invent a number while citing an existing evidence ID. Clarify this boundary. If stronger assurances are needed, use structured metric references resolved by code, require citations for designated material claims, and evaluate wrong-number/wrong-evidence entailment cases. Do not claim arbitrary prose entailment is solved by schema validation.
2. **Untrusted input wrapping is incomplete.** `src/research_factory/workflows/steps.py:646` duplicates raw researcher rationale in rationale_raw, while _hypothesis_brief wraps it. `steps.py:76-77` wraps without escaping closing tags. No prompt exploit was demonstrated; model has no tools and the human/statistical controls remain separate. Remove unused raw field (RulesProvider currently reads rationale, not rationale_raw), use an unambiguous data encoding, and describe wrappers as guidance rather than a security boundary.
3. **Unbounded call-name retention.** `src/research_factory/server/common.py:41,77` appends every governed tool/resource invocation to an in-memory list that has no consumer anywhere in source/tests. Remove it or use a bounded diagnostic buffer/metric. Durable audit already exists. This is a small-per-request leak, not a demonstrated near-term outage.
4. **Prompt fingerprints omit effective prompt text.** `src/research_factory/judgment/prompts.py:94-95` hashes COMMON_RULES+STEP_PROMPTS; actual system_prompt also contains NO_TOOLS_PREFACE (`:46`, `:90`). Skill hash covers skill content but not this preface. Hash full effective system prompt, or version all components, to uphold traceability when the preface changes.

## Not claimed / limits

- No new API-key authentication bypass was found. Owner aliases are operator-issued; identity canonicalization alone is not an attacker-controlled key issuance exploit.
- Rate limiter per-process scope is documented and intentional at planned scale; not a newly discovered defect.
- Guest budget check and creation are separate transactions, but a single event-loop path creates the run before its first await. Multi-process races deserve an eventual concurrency test, not a claimed reproduced exploit here.
- Live model compatibility, current provider model availability/prices and fallback API support were not externally checked. No live provider calls made.
- Existing tests cover prior audit issues, but did not cover the temporal approval ordering, refusal accounting or contradictory needs_evidence flag above.
