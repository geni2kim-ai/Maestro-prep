# Maestro-Prep — public candidate

This repository contains an **offline, non-authorizing** coordinator for external routing captures, owner-approved planning, and a mandatory evidence gate. It does not include proprietary routing binaries, local policies, operational node data or approved planning installations.

## Functional interfaces

- `python -m maestro_prep.cli decide`: assess an owner-pinned local work/lock and already captured normalized routing result; no router execution.
- `python -m maestro_prep.cli component-check`: check the bundled **redacted public O-Prep compatibility derivative** against `SOURCE_PIN.json`. This is **not** the original private/vendored component pin and cannot substitute for a separately approved installation.
- `python tools/audit_external_archive.py <archive.zip> --owner-bundle-sha256 <SHA> --owner-manifest-sha256 <SHA>`: generic byte-only archive check. Specific routing semantics require a separately authorized local-only profile.
- `python tools/local_node_preflight.py --help`: read-only source and installed-component byte preflight; no installation or approval.
- `python tools/ci_check.py`: reproducible synthetic and unit tests.

`LEONARDO_ROUTE_DECISION_V1` is the **coordinator-defined adapter**, not a vendor's original output format. The indispensable O-Prep gate cannot be bypassed by routing output. External planning and routing installations are never auto-updated.

## Public-source boundary

The public archive intentionally omits any historical internal node IDs, real evidence archive shapes, installation paths, private repository references, historical operator tickets, private skill names, real routing captures and detailed internal workflow history. Synthetic fixture files are invented and do not identify a real deployment. The generic archive checker replaces the former private-export-specific checker; it does not attempt to verify private router semantics.

**Published public O-Prep compatibility code has changed:** its optional transported-archive example is genericized. Its core decision and receipt-binding functions remain subject to synthetic regression tests; any existing approved original O-Prep must be verified locally against its own independent owner pin. Do not use this public source's `SOURCE_PIN.json` to attest to the original vendor installation.

Public CI may intentionally show a separate reference-source integrity HOLD: published historical reference hashes are not re-signed by Maestro. An offline test PASS is never live node, rollout or reviewer approval.

See `SKILL.md` and `README_KO.md` for workflow-independent operation. Privacy regression checks run in CI and against the distributable file inventory. Old public Git commits, PR discussions, CI logs and downloaded copies are separate historical records: a new clean working tree does not delete them.
