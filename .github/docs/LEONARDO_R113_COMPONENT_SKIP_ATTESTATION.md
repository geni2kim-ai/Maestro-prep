# R1.13 Component test SKIP identity binding and contradictory summary rejection

Date: 2026-10-13. **Draft candidate / non-final review.** Base 813b0e01a665657b78cd2c5d66da2976a044a784 (R1.12). No operational or deployment authorization.

## Local R1.12 adversarial reproductions (synthetic process output)
1. With an explicitly mocked success exit status and `Ran 70 tests / OK (skipped=5)`, `main_ci.run_case(kind='component')` returned `passed=true` while providing **no identities or reasons** for the five omitted tests. This makes the numerical skip exemption indistinguishable from five unrelated unexecuted tests.
2. With an explicitly mocked success exit and a contradictory `Ran 79 tests / OK / FAILED (failures=1)` summary, `main_ci.run_case(kind='coordinator')` returned `passed=true`, because it searched for any successful OK line, not the unique final summary. These are controlled test doubles, **not actual product security bypasses on a user node**.

## R1.13 corrections
- Public component test wrapper emits `MAESTRO_COMPONENT_TEST_RESULT_V1` as one JSON stdout receipt containing `tests_run`, success flag, failures/errors, plus every skipped test's **method ID and skip reason** from `unittest.TestResult.skipped`.
- Offline main CI checks exact numeric agreement between unittest stderr and the machine-readable receipt; only a closed allowlist of four optional schema tests, one optional schema receipt test, and (on Windows) the POSIX mode-bit test is permitted as a baseline SKIP. Unrecognized, duplicated, or substituted skips remain **BLOCKED** even if the total SKIP count is unchanged.
- Explicit Windows `WinError 1314` symlink test skips are not included in the allowed baseline, still flagged `VENDOR_PLATFORM_GAP` and remain HOLD. This does not require elevation and does not establish any new Windows test coverage.
- Reject contradictory or multiple unittest success/failure summary lines even if an external wrapper improperly returns exit code 0.
- Six new CI accounting unit tests (20 total), including missing inventory, substituted identity, duplicate identity, wrong run count, contradictory summary and valid optional dependency coverage.

## Observed local evidence
The exact GitHub Run #90 tracked-source archive at `813b0e0...` was the working baseline (83 tracked files, full source SHA-256 `3eb3028a5dcf0e52ec0477ac50ee7e79194d655650c1f3ea5ce4e4d4e5733087`). Modified candidate on Linux Python environment: main offline CI **9/9**, component **70 tests with 0 SKIP**, coordinator **79 with 0 SKIP**, CI accounting **20 PASS**, synthetic replay **20/20**, CodeDiff regression **21 PASS**, public privacy PASS. The negative samples were directly run and originally produced false `passed=true`; they now produce `passed=false`. Windows local operator after R1.13 is **NOT_RUN**.

## Leonardo use and review boundary
Actual Git-blob verified original R2.30 policy/contract/util function modules were executed in an isolated test package against **hand-supplied synthetic** frozen-evidence, high-impact multi-agent security, and deterministic-checksum inputs. Results: `FORBIDDEN_INSIDE_REVIEW`, `MANDATORY`, `BYPASS` respectively; synthetic contract hash mutation rejected. Full Leonardo `route_task`, natural-language signal extractor, model operation and independent RedAgent **NOT_RUN**; do not treat policy function outputs as independent approval.

Official CodeDiff v2.5 policy engine on the GitHub PR diff remains a non-authoritative SHADOW sensor (`HUMAN` approval necessary, `trusted_for_gate=false`, `authority_effect=NONE`), to be rerun on the exact R1.13 commit. No trusted TextDiff, merge, activation or deployment.

## Local-node test kit decision
Only evidence bookkeeping and SHADOW instrumentation changed. Missing unprivileged Windows symlink coverage is already correctly blocked. Additional local Windows deployment is **not necessary to keep the gate fail-closed**, so no new local node package is requested. If someone wants to claim complete Windows symlink coverage, independently capture it later; ordinary-user node result remains HOLD.
