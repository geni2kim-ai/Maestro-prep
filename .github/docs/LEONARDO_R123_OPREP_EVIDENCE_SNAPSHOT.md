# R1.23 — O-Prep transported evidence snapshot and counter integrity

Date: 2026-10-13. Parent R1.22 commit `ca5e6d0ba957aaa4eb1308669dadf72597bdfc8f`. Candidate-only Draft PR #5. The public O-Prep derivative is modified; it is not an externally approved host O-Prep installation.

## Finding / threat scenario (Leonardo policy-guided, not actual Leonardo route_task)

O-Prep `audit_transport_bundle` previously computed `archive_sha256` from `Path.read_bytes()`, then separately reopened `ZipFile(path)`. If an adversarial producer swaps the archive between these reads, the SHA reported and contents audited can differ. `Path.stat().st_size` likewise did not limit actual bytes read after a race. A disposable synthetic ZIP is altered inside a mocked ZipFile constructor in a regression test to exercise this boundary.

Producer-supplied packet and test counts were compared by Python equality and arithmetic without exact integer/nonnegative validation. `True == 1` and `-1 + 2 == 1` could thus make malformed records appear arithmetically consistent, even though they are not proper count attestations. Producer-reported claims remain non-authoritative regardless.

## Remediation

- Open the ZIP once, consume at most `MAX_UNCOMPRESSED+1` compressed bytes, require a regular file, reject explicit symlink/reparse-point archive paths, hash this one immutable snapshot and inspect exactly its `io.BytesIO` content. Same snapshot used for hash and manifest/record audit; not an immutable remote provenance claim.
- Strict `type(x) is int and x >= 0` for lifetime metrics, window metrics, test baseline metrics and suite `total_tests`. Malformed claims produce `OPrepError` rather than green comparison.
- Four targeted adversarial test methods in `test_v03_hardening.py`: swap-on-ZipFile-open, bool/negative packet counters, bool/negative test arithmetic, bool/negative receipt suite counts.
- Update `SOURCE_PIN.json`, all touched entries in 40-file `MANIFEST.json`, and `SHA256SUMS.txt`. No runtime authority changes.

## Scope and gates

GitHub candidate CI across Windows/Ubuntu 3.11/3.12/3.13 plus CodeDiff v2.5 SHADOW; all require checking at exact commit. CodeDiff is non-authoritative, may emit `action_required`, and cannot approve or deploy. Windows unprivileged real junction/symlink host exercise remains HOLD; full Leonardo, independent RedAgent and HUMAN approval remain NOT_RUN. No additional Windows local node package is necessary unless a newly observed OS-specific failure requires one.
