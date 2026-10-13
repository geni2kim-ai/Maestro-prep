# R1.14 Leonardo policy-guided offline CI evidence guard review

2026-10-13. Candidate-only, non-authoritative. Based on R1.13 commit `16990124c625a66a0a7ccf12db15277e78891f04`. This is an evidence/reporting code change, **not** a host security feature, approval, merge or deployment.

## Reproduced R1.13 failures (actual `main_ci.run_case`, mocked subprocess outputs)
1. The self-accounting test suite included 20 methods, but the CI self-check required a stale minimum of just **7**. A synthetic `Ran 7 tests / OK` with exit 0 was incorrectly accepted as `passed=true`. Thus up to 13 accounting regressions could be absent and the wrapper would not notice by count.
2. A synthetic coordinator output `Ran 79 tests / Ran 2 tests / OK`, exit 0, also returned `passed=true`, because CI used the first unanchored run-count match despite contradictory evidence. Neither test proves a real operator-node compromise.

## R1.14 correction
- Require **one and only one complete unittest `Ran N tests` line**, with optional wall-time suffix, and one consistent `OK` summary. Two run-count lines reject even if the larger value meets the floor and exit status is zero.
- Increase the CI-accounting self-test floor to **23** (R1.13 retained 20 methods plus three new targeted regressions). Other test floors remain unchanged. Preserve fail-closed handling for all missing/unknown Windows symlink cases, unexpected component skips and the mandatory O-Prep guard.
- New unit cases cover seven-only regression suppression (BLOCK), conflicting run counts (BLOCK), and an honest 23-test self-check (PASS).
- Hardcoded floors are a bounded safeguard, **not proof of stable test identity**: a compromised test publisher could replace cases while retaining the same count. GitHub diff review, independent evidence and a real reviewer remain required. Future additions to the accounting suite must update this count.

## Measured local before/after on the exact-source R1.13 archive
Official Run #92 full tracked-source ZIP SHA256 `902f5f64292797ae8743cf5e90ffd8910fa2e14369f6e6050f7fc50d1e1a4522` (84 regular tracked files); source HEAD matches `16990124c625a66a0a7ccf12db15277e78891f04`.
- BEFORE: `7 tests / OK` -> `passed=true`, and `Ran 79 / Ran 2 / OK` -> `passed=true`.
- AFTER: both -> `passed=false`; all local offline CI checks **9/9 PASS**, coordinator **79**, component **70**, accounting suite **23 PASS**.
- CodeDiff tool: official pinned upstream v2.5 policy-engine SHA `69a49faa35b56d48e9e3067e5f484b443735df67` retained, candidate-only SHADOW; run on exact new GitHub head after push. SHADOW is never an independent approval.

## Original Leonardo unit execution (limited)
Verified original upstream R2.30 candidate module Git blob IDs prior to isolated local execution: policy-use `2dedbc58ba968da3d10fd783f54f43e762c52763`, contract `4665c26f9be9e52b4bba1bb968660bb654bd7f67`, JSON utility `36b526f73692609d1b230b2ef7760f64f2d435ec`. Hand-constructed frozen review -> `FORBIDDEN_INSIDE_REVIEW`; high-impact multi-agent security -> `MANDATORY`; checksum-only -> `BYPASS`; tampered synthetic contract hash rejected. The original signal detector, complete `route_task`, model/agent orchestration, independent RedAgent and HUMAN review remain **NOT_RUN**. No original private code was copied to this public repository.

## Residual Windows local evidence
Prior ordinary-user Windows sandbox symlink privilege coverage remains **HOLD**, even when hosted CI is green. None of these changes require another operator-side test to keep that coverage blocked; no new local test package should be created. No production permissions changed.
