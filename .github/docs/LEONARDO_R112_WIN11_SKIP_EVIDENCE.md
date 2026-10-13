# R1.12 Windows skip-attribution evidence hardening

Date: 2026-10-13. **CANDIDATE_ONLY / HUMAN review required.** Supersedes R1.11 accounting wording, not its product security gate.

## Fresh producer receipt observed

A single ordinary-permission Windows 11 retest supplied for R1.11 reports `HOLD_WINDOWS_PLATFORM_COVERAGE`, offline checks **7/9**, 79 coordinator tests with **2 skipped**, and 21 CodeDiff tests with **7 skipped**, exit code 0. Package manifest entries were byte checked (8/8); inner receipt checksum and duplicate copy also matched. The full Leonardo router, independent adversarial review, and trusted TextDiff were NOT_RUN. Neither PASS nor independent verification is claimed.

## Reproduced accounting error

R1.11 `main_ci.py` returned `UNEXECUTED_SYMLINK_TESTS` on Windows whenever *any* coordinator tests were skipped. A crafted synthetic result `Ran 79 tests; OK (skipped=2)` with two **unrelated** skipped tests was therefore incorrectly attributed to symlink coverage. The final FAIL/HOLD remained but this could mask the true reason.

## R1.12 remediation

- Run Windows coordinator tests with `unittest -v` to capture **test identities and skip reasons**, without relaxing the zero-skip approval floor.
- Attribute skips to symlink coverage only when every verbose skip entry matches one of the two closed expected test method names, the exact reason `Symlinks restricted`, and the summary count.
- Otherwise report `COORDINATOR_SKIP_CAUSE_UNVERIFIED` and preserve failure. Missing, duplicated, unrelated or wrong-reason skip records cannot become a named coverage exception or a PASS.
- Add adversarial accounting regressions for unknown skips, no verbose records, wrong reasons, and actual verbose invocation. Product O-Prep authority unchanged.

## Evidence limitation: raw log hashes not independently bound

The separately supplied text log index contains abbreviated SHA-256 prefixes that do not match exact stdout/stderr digest fields in the machine-readable producer receipt. Corresponding original log streams were **not included**, so their identities cannot be reconciled. The outer package and receipt bytes are internally intact; that is not authentication of unprovided logs.

Full Leonardo `route_task`, actual signal extraction, trusted TextDiff, independent L1/L2/RedAgent/HUMAN: **NOT_RUN**. CodeDiff SHADOW remains non-authoritative; `authority_effect=NONE`. Draft only, no merge/deployment.