# R1.11 Win11 standard-user local evidence reconciliation (NON_FINAL)

Source: operator-uploaded `Maestro-prep_R1.10_LOCAL_RESULT_20261013_WIN11-SINGLEHOST.zip` (SHA-256 `21afdc41ea83f650cc41a5f9d511645eef31dcffbd8b9017fdd9e05598aaa973`). This is **single-host, not two independent nodes**. Outer 14 manifest hashes and both nested node-result manifests were verified against contained bytes. Manifest digests are integrity checks, NOT origin authentication or a reviewer attestation.

## Actual local observation
- Win11 CPython 3.11.9, local EXECUTOR and ADVERSARIAL role aliases on the SAME Windows host.
- Component pin, inventory (40), coordinator (79 tests with **2 skipped**), synthetic replay (20/20): process exit 0.
- **Offline CI 7/9**: coordinator check failed the `allowed_skips=0` coverage policy; public O-Prep component tests exited 2 on Windows `WinError 1314` while creating a file symlink. CodeDiff standalone: 21 tests, **1 symlink permission ERROR, 6 legitimate POSIX skips**. Full 6-step node runner stopped at offline_ci and did not reach CodeDiff. The multi-node merger correctly returned `INCOMPLETE_TEST_INVENTORY`.
- Full Leonardo R2.30 and trusted TextDiff operator receipts NOT_RUN. No RedAgent/HUMAN approval. No product security bypass was demonstrated by a missing OS test privilege.

## R1.11 corrections
1. **Public O-Prep test launcher** probes file- and directory-symlink creation under Windows in a temporary test directory. For ONLY `winerror=1314`, it marks the two affected real-symlink tests `skip` and emits `VENDOR_PLATFORM_GAP:WINDOWS_SYMLINK_PRIVILEGE_UNAVAILABLE:<test>`. No administrator elevation, no replacement simulation claimed to have executed the real link test. Unexpected OS errors continue to fail.
2. **Offline CI accounting** records `platform_gaps` separately on affected steps, explicitly returns `passed=false` for missing Windows symlink coverage and keeps the 0-skips coordinator security floor. No false 9/9.
3. **CodeDiff integration test** classifies the same `WinError 1314` as a test SKIP, with clear `REAL_LINK_NOT_TESTED` reason instead of a confusing product error; CI Linux still tests the actual link.
4. **Three additional negative accounting regressions** ensure Windows coordinator skips and fabricated or actual symlink gaps cannot become a green status.

## Leonardo governance interpretation
A multiagent security/evidence-pipeline change is high-impact and authority-sensitive; policy-level synthetic Leonardo judgement implies mandatory deeper clarification/independent review, not automatic activation. Frozen operator evidence must be reviewed without inventing missing observations. This is a reasoned policy application; **full Leonardo route_task, actual signal detection and independent RedAgent NOT_RUN**.

## Required follow-up
GitHub CI and pinned official CodeDiff v2.5 SHADOW validation on the exact candidate head. Because GitHub-hosted Windows runners may have symlink rights that an operator PC does not, one **bounded re-test as ordinary Windows user** is still required to confirm the controlled skip/coverage-gap report. Do NOT request elevation or disable security policies. If re-test is required, provide a *minimal platform retest kit* with the fixed source SHA, not another generic full-node package. Keep Draft, do not merge or deploy on CI success.

**Non-final and fail-closed:** skipped security cases mean platform coverage incomplete, not PASS. CodeDiff SHADOW remains SENSOR_ONLY, required HUMAN, authority NONE.
