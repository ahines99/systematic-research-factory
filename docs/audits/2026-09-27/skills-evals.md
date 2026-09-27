# Auditor 5: skills, judgment contracts, evaluation evidence

Audit date: 2026-09-27. Read-only source audit, with isolated in-memory services and temporary-directory probes. No model API calls, SEC requests, production writes, or source edits. The attached historical transcript was treated as context, not as fresh instructions to create skills or execute its commands.

## What exists and works

- Four genuinely domain-specific skills exist, with all requested references and the standalone point-in-time checker. Frontmatter names match folders; descriptions are 705–819 characters; SKILL.md files are 103–150 lines; all referenced reference files resolve. These are substantially complete authored artifacts, not placeholders.
- The formulas reference's executable example reproduces `PSR=0.99944`, `SR0=0.059867`, `DSR=0.8838`. Existing quantitative unit tests include brute-force Newey-West and the worked DSR reference (`tests/test_research.py:347`, `:354`). This is meaningful deterministic arithmetic evidence, though it is not proof that model prose contains those numbers faithfully.
- The standalone checker returned 0 for a clean row, 1 for future knowledge, 1 for naive timestamps, and 1 for absent inputs. The current suite also runs it against actual clean/leaky exported lineage (`tests/test_demo_cli_evals.py:184`).
- Thirty golden cases, seven named aggregate dimensions, offline rules judgments, scripted malicious responses, CLI integration, replay tests, and scorecard JSON/Markdown generation exist. Root independently reran 187 passing tests / 3 skipped and all 30 rules evaluations. This auditor did not repeat that entire suite.
- The rules provider does not consume skill prompts. The docs acknowledge that the Claude baseline and skill A/B remain unverified. Merely running more rules cases cannot establish model usefulness.

## Findings

### S1 — High: fabricated numbers with real citations pass the contract and every automatic fidelity check

Locations: `src/research_factory/judgment/contract.py:93`; `src/research_factory/evals.py:128`; `src/research_factory/evals.py:146`; claims in `README.md:3`, `:55`, and threat T2 in `docs/threat_model.md`.

The validator checks that a cited ID belongs to the run and that facts/calculations have at least one citation. It never verifies that the cited artifact supports the statement. The evaluation recomputes deterministic statistics but never compares numbers asserted in judgment prose with those statistics. Uncited summaries, risks, and recommendations provide additional unscored text channels. This means the tests demonstrate citation existence and deterministic calculation correctness, not factual/numeric fidelity of the model's memo.

**Reproduction, executed offline:** subclass `RulesProvider`, retain its ordinary verdict, but replace each returned summary and claims with `The annualized Sharpe ratio is 999.0 and net annual returns are 900 percent.` The sole claim is kind `calculation` and cites the real `artifact:statistical-review` ID from the request's evidence catalog. Start a clean `demo_experiment` using memory blobs and SQLite memory storage. All three reviews accept the fabrication. The run reaches Research committee with `gate=approve`; both evidence checks and all three calculation checks pass. The independently recomputed actual annualized Sharpe is 2.543932, not 999.0.

This does not itself bypass human approval or change deterministic backtest values. It does allow false evidence-bearing claims to be presented to the human, contrary to the advertised mitigation and evaluation dimension.

**Acceptance:** introduce structured numeric references (artifact ID + field/path + units/value), validate them deterministically, and render supported numbers from artifacts; score prose support separately if it remains free-form. Add golden cases for incorrect numbers citing a valid artifact, irrelevant but existing citations, and unsupported material statements in summary/risk/recommendation fields. The reproduction above must be rejected or explicitly scored as a fidelity failure. Narrow documentation until that is true.

### S2 — Medium: the skills integration cannot perform several mandatory skill procedures

Locations: `src/research_factory/judgment/prompts.py:46`, `:59`, `:78`; `src/research_factory/workflows/steps.py:603`, `:643`, `:680`, `:768`; `src/research_factory/judgment/contract.py:39`; `skills/financial-research-statistics/SKILL.md:103`; `skills/signal-red-team/SKILL.md:62`, `:63`, `:75`; `skills/research-committee/SKILL.md:62`, `:64`, `:123`; `src/research_factory/server/research_tools.py:158`.

There are four separate, concrete integration limits:

1. `SKILL_FOR_STEP` loads only signal-red-team, financial-research-statistics, and research-committee. The point-in-time skill is never loaded in any automated judgment. It can be useful to a human/external agent and its script is tested, but the proposed all-skills/no-skills experiment cannot demonstrate the point-in-time skill changing a model outcome. This directly affects the RSF-034 done-when (`docs/ROADMAP.md:49`).
2. Only SKILL.md is loaded. References are linked as local paths but the model has no tools/file access. It cannot read the required committee template or deeper formula/attack references. This is not functioning progressive disclosure in the judgment runtime.
3. Required evidence is missing from payloads: `_statistics_brief` drops the Newey-West lag, variance source, bootstrap method/block/sample count/seed/interval method and other inputs demanded by the statistical skill. Some bootstrap metadata is absent even from `StatisticalReport` (`research/statistics.py:135`), despite the skill requiring `NEEDS_EVIDENCE` when it is missing. The economic payload does not supply the ten-attack red-team evidence set. Skills-enabled model output therefore faces a choice between ignoring its procedure and asking for missing evidence on otherwise ordinary runs.
4. The output schema offers only verdict/confidence/summary/claims/open_questions/needs_evidence. It has no structured attack table or dissent fields, and does not enforce all required memo sections. Current `get_statistics` accepts only `experiment_id`, so instructions to directly request statistics excluding the top ten contributors or high/low volatility halves do not map to callable arguments. A new frozen date-range experiment can support some calendar subsamples; security exclusions/regime analytics are not currently implemented. Cost/delay variants similarly require explicit re-freezing, not extra `run_backtest` arguments.

**Acceptance:** distinguish external-agent procedures from the tool-less judgment procedure; supply the necessary references and evidence or explicitly mark unavailable checks; define an output schema/renderer capable of preserving attack rows and dissent; implement supported variant requests or accurately label them unavailable. Add a targeted PIT skill treatment/control task before treating RSF-034 as only owner/API-key work.

### S3 — Medium: evaluation accepts no cases and misclassifies unexpected MCP errors as expected input errors

Locations: `src/research_factory/evals.py:106`, `:317`; `src/research_factory/cli.py:220`.

**Executed reproduction A:** point `rsf eval --provider rules --cases` at an empty temporary directory. CLI returns 0 and emits `0/0 cases passed`, with every dimension 0/0. A accidentally empty suite is a successful gate. The ordinary repository suite is nonempty; this finding concerns failure behavior under missing/misconfigured fixtures.

**Executed reproduction B:** replace the in-process MCP Client in a unit probe with one returning `is_error=True` and plain text `INTERNAL DATABASE FAILURE`. A case expecting `INVALID_INPUT` passes, because *any* unparseable error text is coerced to that code. The existing schema-error compatibility fallback masks unexpected internal failures.

**Acceptance:** reject zero cases, duplicate IDs, unknown dimensions/kinds, and missing expected dimension coverage as configuration errors (or explicitly scoped partial runs). Treat malformed error envelopes as failures; assert the exact typed error rather than assigning a favorable default. Add the two reproductions as regression tests. Note `GoldenCase(dimensions=['not-a-dimension'])` currently validates; dimension declarations are reporting metadata, not enforced coverage.

### S4 — Medium: a Claude/skill baseline would be poorly attributable and is currently overwritten by the documented second run

Locations: `src/research_factory/evals.py:199`, `:345`, `:365`; `src/research_factory/cli.py:214`; `IMPLEMENTATION_HANDOFF.md:275`; `docs/ROADMAP.md:49`.

The scorecard stores the requested provider label, cases/checks, elapsed time and cost, but not skills enabled/disabled, model ID actually used, prompt/skill hashes, revision, configuration, dataset/case hashes, actual model response, or per-case provider. Cases 21 and 22 unconditionally use ScriptedProvider (falling back to rules) even for `--provider anthropic`; early-failing deterministic cases and MCP-only cases do not necessarily exercise Claude either. Thus a card labelled anthropic includes mixed execution. That can be appropriate for integration tests if attributed clearly, but cannot by itself measure Claude fidelity or skill effect.

The documented pair `rsf eval --provider anthropic`, then `rsf eval --provider anthropic --no-skills` writes both results to the same default `var/scorecard.json` / `.md`, replacing the first baseline. Temporary per-case stores are discarded, so the model output/audit stamps are not retained in the scorecard as an alternative source of attribution.

**Acceptance:** persist an evaluation manifest with exact model and actual per-case provider, skill flag/hashes, full prompt hash, source revision, configuration and input/case hashes, and review artifacts; use distinct output names for both arms; report model-exercising and deterministic/scripted results separately. Add supported semantic quality criteria before spending on a baseline. Repeat paired cases as needed to distinguish model variability from a skill effect. This is engineering work before the remaining owner-funded/API-key step.

### S5 — Medium: advertised adversarial categories are not tested as described

Locations: `evals/golden/20-prompt-injection.yaml:8`; `evals/golden/22-contradictory-reviewer.yaml:9`; `tests/test_demo_cli_evals.py:210`; `docs/ROADMAP.md:414`, `:670`.

The purported filing-text injection case injects one instruction into the hypothesis rationale. It does not inject into filing text or company names. The category assertion checks case IDs, not attack content or successful passage through the relevant input route. The contradictory-reviewer case emits unsupported assumptions and upbeat verdicts while the deterministic statistics fail. It proves the gate still rejects those statistics; it does not test contradictory cited evidence or a model reconciling conflicting source facts.

Currently model payloads chiefly expose numerical summaries and hypothesis text, not raw filing bodies, which reduces the raw-filing injection attack surface. State that boundary accurately instead of claiming a filing corpus test. Economic payload also includes `rationale_raw` alongside its wrapped copy (`workflows/steps.py:646`), so not all researcher text is inside the promised tags; test the actual request serialization.

**Acceptance:** create route-specific adversarial fixtures for content actually delivered to the model, including delimiter-like instructions, missing/contradictory supported evidence, and false statements with genuine citations. Preserve a negative control demonstrating each scorer can fail. Where raw filing text is deliberately never delivered, document and test its exclusion instead of claiming it was injected and resisted.

### S6 — Medium/low: actual prompt wording can change without either recorded version changing

Locations: `src/research_factory/judgment/prompts.py:46`, `:86`, `:94`; `tests/test_workflow.py:243`.

`prompt_version` hashes COMMON_RULES plus STEP_PROMPTS; `skill_version` hashes SKILL.md. Neither includes NO_TOOLS_PREFACE or the assembled separators/skill wrapper. The test merely checks that version fields exist. **Executed reproduction:** append a sentence to `NO_TOOLS_PREFACE` in process memory. The actual `system_prompt('economic_rationale')` changes, while both version hashes remain identical. No repository file was modified.

**Acceptance:** hash the exact assembled system prompt; separately stamp schemas and any dynamically included reference material. Test that changing every prompt component changes the version. Archive the evaluated request with secrets excluded so a version can be resolved to exact input text. This is a provenance limitation, not a standalone approval bypass.

### S7 — Low: timestamp checker violates its documented bad-input exit contract for undecodable files

Location: `skills/point-in-time-research/scripts/check_pit_timestamps.py:116`, `:124`.

`load` catches OSError but not UnicodeDecodeError. **Executed reproduction:** a two-byte file `FF FE`, run with `--json`, exits 1 with a traceback, rather than bad-input exit 2 with machine-readable error. Normal clean/leaking/naive/absent-input checks worked. The tool also accepts nonfinite Python JSON numbers as values; it is only a timestamp pre-check, so this is lower priority than the separate production finite-number validation finding from the quantitative auditor.

**Acceptance:** catch decode errors into BadInput; test invalid encoding, malformed JSON/top-level shapes, stdin and flag behavior. Keep the documented exit codes precise.

## Meaning and limits of current green checks

The current suite has genuine breadth and catches many deterministic regressions. Its evidence arithmetic checks are deliberately narrower than the README's plain-language promises. DSR recomputation takes moments, trial count and variance from the same statistics artifact, so it checks formula assembly, not independent truth of all those inputs. Newey-West, bootstrap, IC and delay-window correctness are not independently scored by the golden harness; some have useful separate unit tests. Replay tests exercise rules-provider scenarios, not archival reproduction of nondeterministic live model responses (the main code auditor covers that defect).

No test establishes that the actual four skills can all be executed through the advertised tools, that committee output follows the full memo template, that dissent survives end-to-end, or that a model's prose numbers match cited fields. Those missing acceptance tests explain why 30/30 can coexist with the concrete false-number reproduction.

## Recommended owner baseline procedure after engineering fixes

1. Retain the passing rules baseline as deterministic regression evidence; repair S1–S6 before using it as a model-quality scorecard.
2. Add an explicit PIT treatment/control task, provide its necessary evidence/tool route, and define observable success before calling the API. Model safety/gate outcomes alone may remain unchanged because deterministic gates already decide them.
3. Once the owner authorizes/configures credentials, run paired Claude evaluations with distinct outputs, e.g. `rsf eval --provider anthropic --out var/baseline-anthropic-skills.json` and `rsf eval --provider anthropic --no-skills --out var/baseline-anthropic-no-skills.json`. Capture actual model/configuration/provenance and repeated-case variability; separate scripted/deterministic cases in the comparison.
4. Review evidence/number fidelity, uncertainty responses, actionability, required memo coverage, cost and latency. Document changed outcomes rather than assuming skill text improves results. Only then close RSF-034 / RSF-039 or accurately narrow their acceptance criteria.

Repository source files remain unchanged by this audit.
