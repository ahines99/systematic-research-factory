# Hosted CI follow-up

The first public CI run exposed two portability assumptions missed by the local audit. This supplements the original verification record; it does not rewrite it.

## Interpreter and optional dependencies

`uv sync --python 3.14 --all-extras` selected the requested interpreter and installed PostgreSQL support. Subsequent `uv run` commands honored the repository's Python 3.12 preference and synchronized again without the optional extras. Named matrix jobs could therefore execute a different Python and the PostgreSQL job lost `psycopg`.

CI now sets `UV_PYTHON` explicitly for each matrix job and uses `uv run --no-sync` after the locked installation. The PostgreSQL suite subsequently passed. Release smoke commands use the same rule.

## Historical replay across CPUs

Preserving source, dependency versions and a container digest was insufficient for byte-identical numerical output on a different host CPU. Both candidate archives remain unchanged, including their reviewed checksums. Re-execution under source commit `2300404a749fb46ab435ec76007cea43a3c36e23` reproduced the first five stages exactly, but the overfit scenario's HAC t-statistic changed from `3.206359668491078` to `3.206359668491077`.

A controlled diagnostic on the same archived returns, Python 3.14.7 and NumPy 2.5.3 produced:

| OpenBLAS 0.3.34.106.0 backend | Newey–West t |
|---|---:|
| Haswell | 3.206359668491077 |
| SkylakeX | 3.206359668491078 |

Only `OPENBLAS_CORETYPE` changed. OpenBLAS dynamically selects a CPU kernel; a container does not virtualize away the host instruction set. See [NumPy's runtime troubleshooting documentation](https://numpy.org/devdocs/user/troubleshooting-importerror.html).

New runtime identities include the complete Python version/build, libc, NumPy SIMD configuration and numerical library versions, CPU backend and thread count, without recording host file paths. Replay rejects incompatible identities before executing. Matching-runtime replay tests still require exact artifact hashes.

The separate **historical artifact comparison** jobs select the immutable old implementation and pinned Python containers. They verify the stored archive and artifact hashes exactly, then compare re-executed results. The explicit `--cross-host` mode allows at most four ULPs only in the statistical artifact's `newey_west_t` and its corresponding check value. Every other field, including thresholds and decisions, remains exact. It logs changed hashes and reports `identical: false` when drift occurs. Strict mode remains the default. Regression tests reject unrelated changes, larger drift, altered decisions and NaN.

This is numerical cross-host compatibility evidence, **not byte-identical historical replay on GitHub's CPU**. The earlier same-host replay evidence remains dated local evidence. Do not claim portable byte equality from matching OS/architecture and package versions alone. A new release baseline must retain this richer runtime identity and its independent expected artifacts.

## Validation

The authoritative hosted result is the [CI run history](https://github.com/ahines99/systematic-research-factory/actions/workflows/ci.yml). Failed diagnostic runs remain visible. Final candidate status is recorded in the portfolio execution status after the checks complete.
