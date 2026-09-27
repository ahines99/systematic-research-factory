# Preserved candidate archives

These archives are immutable pre-release evidence, not published releases. `registry.json` selects the original source commit; sidecar manifests contain checksums and expected artifact hashes. Tests never regenerate those expectations.

For exact replay, use the original Python container, locked dependencies and numerical CPU backend. The historical CI jobs perform an explicitly labeled cross-host comparison because OpenBLAS Haswell and SkylakeX reductions differ by two ULPs in the overfit case's HAC statistic. Only the documented fields allow at most four ULPs; thresholds, decisions and all other fields stay exact. See [the investigation](../../../docs/audits/2026-09-27/ci-followup.md).

`scripts/check_replay_archive.py` defaults to strict exact comparison. `--cross-host` never reports a numerical difference as identical. New source/runtime identities require a separately reviewed baseline at final release freeze, while retaining these archives.
