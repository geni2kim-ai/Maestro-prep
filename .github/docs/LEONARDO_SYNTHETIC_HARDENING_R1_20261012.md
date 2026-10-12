# Leonardo-oriented synthetic hardening — Maestro-prep R1 (2026-10-12)

## Immutable source scope
- Upstream: `geni2kim-ai/Maestro-prep`, baseline `eb9fa7a39e02d9c4853fe7ecc58c45b3543fdbf1` (`main` at inspection).
- Referenced Leonardo repository: `geni2kim-ai/Leonardo`, main `a4e0bc631d1033e8ba25a0a3e7b1457ca3d6a0d7`.
- **Leonardo binary/runtime was NOT executed here.** This is a Leonardo-policy-oriented hostile-input simulation and coordinator regression hardening, not evidence of a real external route invocation, live host authorization, independent RedAgent result, or deployment readiness.
- Default public profile is not an approved external vendor integration. No changes to vendored O-Prep source/pins or local node configuration.

## Findings and source-bound reproduction
1. **F1 / Input-shape fail-closed gap** — in `check_work`, non-string JSON list/dict `stage` or `intent` reaches set membership, causing unhandled `TypeError`. Expected: `ContractError(WORK_SCHEMA_OR_STAGE_INVALID)` / `WORK_INTENT_INVALID`.
2. **F2 / Nested-lock shape gap** — `_fields` calls `set(obj)` on untrusted `astra` / `leonardo` JSON; null and numeric entries raise `TypeError`. Expected: stable `ASTRA_LOCK_INVALID` / `LEONARDO_LOCK_INVALID`.
3. **F3 / JSON nesting gap** — `json.loads` accepts/rejects deeply nested JSON at different thresholds on Python 3.11 and 3.13. The candidate now imposes a cross-version explicit depth cap of 256 containers, returning `JSON_NESTING_LIMIT`; quoted brackets are excluded. The parser still converts unexpected recursion failures into `INVALID_JSON_SOURCE`.
4. **F4 / External gate exception gap** — `decide` catches expected O-Prep failures but not malformed-input `TypeError`, `KeyError` or `RecursionError`. Expected: `HOLD_O_BINDING_FAILED`, never advance candidate or grant authority.
5. **F5 / CLI recovery boundary** — malformed nested JSON/runtime failures should return sanitized `MALFORMED_INPUT` and exit 2 rather than traceback, without ever identifying private filesystem locations.

## Mitigation
- Validate dictionaries and string discriminants before set membership.
- Normalize deeply nested JSON rejection to a stable contract failure.
- Treat malformed-input exceptions from the **existing mandatory** O gate as HOLD, not a success or bypass.
- Extend CLI safe error envelope to avoid traceback for these malformed cases.
- Add table-driven adversarial regression tests and refresh distribution manifest/SHA256SUMS for exactly 40 existing inventory files. No new release-payload file introduced.

## Check matrix
| Check | Expected | Verification source |
| --- | --- | --- |
| Existing synthetic coordinator/replay | 20 cases match; no gate skips | `python tools/replay_simulation.py` |
| Adversarial input regression | HOLD or contract error, no crash/advancement | `python -m unittest discover -s tests -q` |
| O-Prep source pin | unchanged, valid | `python -m maestro_prep.cli component-check` |
| 40-file public inventory | exact hashes and file count | `python tools/verify_package.py .` |
| Full offline CI | all cases PASS | `python .github/scripts/main_ci.py` |
| Strict typing | mypy --strict on three W1 components | GitHub candidate-ci workflow |
| Leonardo executable / independent reviewer | NOT_RUN | Requires separate owner-approved local node |

**Execution note:** Tests must be run on a checked-out PR branch or CI runner. A GitHub source review alone does not establish PASS. Record run URL, commit SHA, and failures without substituting assertions for observed CI output.

## Operator reproduction (read-only)
```sh
git fetch origin
git checkout fix/leonardo-synthetic-input-failclosed-20261012
python -m unittest discover -s tests -q
python .github/scripts/main_ci.py
python tools/verify_package.py .
python -m maestro_prep.cli component-check
```
No packet execution, secrets, networking by coordinator, autonomous retries or upstream merges are authorized.

## PR/code-diff sensor usage log
- Baseline and candidate must be compared separately. Treat any PR diff tool including `PR-with-codediff-finder` as a non-authoritative change sensor only.
- Available validation: GitHub compare/PR diff and CI run after candidate commit. External PR-with-codediff-finder runtime: NOT_RUN in this session.
- Document unresolved integration: actual Leonardo local router, independent RedAgent/host receipts, and external package signature verification all NOT_RUN.

## R1.1 CI recheck record
- GitHub workflow run 61 (38252912758), initial candidate d44f2a049742d96eb5d11547d2b8757932c4ce57: Ubuntu 3.11 PASS, Windows 3.11 PASS, Ubuntu 3.13 FAIL, Windows 3.13 FAIL.
- Failure isolated to test `test_deeply_nested_json_returns_stable_hold_error`: Python 3.13 accepted 1,200 nested containers while Python 3.11 rejected it. Other checks passed (8/9 main CI cases on failing jobs).
- R1.1 resolution: version-independent parser depth cap (256) plus quoted-brackets regression. This record is historical; new commit CI still needs observation.

## R1.2 reviewer feedback response (pending fresh CI)
- Historical Run #62 for R1.1 only: success in its four original jobs. The old "new commit CI still needs observation" sentence is historical and is superseded by that run, not by any later commit.
- Broad Exception fail-closed boundary is isolated to vendored O-Prep invocation/shape handling and the CLI; never catch BaseException.
- Handle 5,000 digit integer ValueError as INVALID_JSON_SOURCE while preserving ContractError duplicate-key codes.
- Reject unhashable receipt roles before constructing dictionary; CLI emits only safe vocabulary and ASCII-escaped JSON for surrogate inputs.
- Synthetic tests: malicious vendor exception matrix, broken responses, route index roles, nested locks, 256/257 depth, escaped markers, giant ints, CLI exit/status and surrogate.
- Matrix updated to Ubuntu/Windows Python 3.11/3.12/3.13, strict mypy includes CLI; macOS NOT_TESTED.
- On fully successful PR CI, a GitHub Actions artifact contains git archive HEAD full tracked source plus SHA-256 and commit metadata. Artifact does not grant authority.
- Actual Leonardo local executable, independent review, PR-with-codediff-finder engine and deployment: NOT_RUN.
