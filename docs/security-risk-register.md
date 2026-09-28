# Candidate security risk register

Reviewed 2026-09-27. Owner: Alex Hines. Recheck by **2026-10-04**, at dependency/base-image updates, and before any hosted release. These are candidate dispositions, not an owner acceptance of a final scanned release image.

The local remediation scan used Grype 0.119.0 and passed the **fixed High/Critical** gate, with the four Python matches below. CI now scans each candidate image and uploads the JSON; the release independently scans its built image before publication. The gate does not certify absence of lower-severity or unfixed vulnerabilities. Preserve scanner version, database time and image identity in the scan output. Do not suppress a finding merely because direct application usage was not found.

| Advisory / recorded severity | Application exposure reviewed | Treatment and residual uncertainty |
|---|---|---|
| [CVE-2026-17084](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/17xxx/CVE-2026-17084.json), Medium | Python `stringprep`/IDNA Unicode handling; EDGAR URLs require exact allowed HTTPS hosts and reject credentials, nonstandard ports and fragments. Configured model/storage destinations are operator-controlled. | Retain host allowlists; no blanket claim about every transitive hostname operation. Adopt a suitable stable runtime fix and regenerate a separately reviewed candidate baseline. |
| [CVE-2026-15806](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/15xxx/CVE-2026-15806.json), Medium | Python urllib password-manager scheme matching; app data client uses httpx, with no direct `HTTPPasswordMgr` use. Healthchecks use urllib without authentication. | No demonstrated credential-manager path in application code; keep HTTPS and scoped service credentials. This is a source review, not proof that all dependencies are unreachable. |
| [CVE-2025-15367](https://github.com/python/cpython/issues/143923), Medium | POP3 command injection; no POP client or mailbox feature in the application. | Avoid adding POP functionality without reassessment; review stable Python fixes and scanner CPE accuracy. Do not suppress an apparent match without verifying actual installed code. |
| [CVE-2026-15310](https://github.com/python/cpython/issues/156002), Low | Malicious compressed ZIP memory consumption; no user ZIP-upload/extraction endpoint. Replay utilities use trusted checksummed tar archives; release bundle creation writes ZIPs. | Do not accept untrusted archives into administrative tools. Patch with a suitable stable Python update; re-evaluate if archive ingestion becomes a feature. |

## Operational residuals

- Actual R2 overwrite/delete denial, viewer-key rotation and isolated restore with exact replay passed on 2026-09-28; see [hosted evidence](operations/2026-09-28/README.md). Owner accepted six-hour Neon recovery and ninety-day R2 retention. An administrator can change a retention policy; evidence is not unconditionally tamper-proof.
- Model prose can be misleading despite a valid citation. Structured numeric binding and scoped review contracts reduce specific failure modes, not general semantic risk. Public guest demos use rules and never paid calls.
- Numerical replay depends on CPU/backend settings as well as source and versions. See the [measured CI finding](audits/2026-09-27/ci-followup.md); historical numerical comparison must not be labeled exact replay.
- The project has no production on-call commitment. Keep public reports as an offline fallback, cap spending, restrict keyed access, and shut down dynamic service if ownership or monitoring lapses.

Before release, attach the actual scan/digest, reassess any changed advisories, complete the hosted controls, and have Alex explicitly accept remaining risk or defer publication. No `v1.0.0` tag has been created by this preparation.

The deployed candidate scan on 2026-09-28 matched the same three Medium and one Low advisories, with no High/Critical matches. Its immutable digest and full JSON are preserved in the hosted evidence directory.
