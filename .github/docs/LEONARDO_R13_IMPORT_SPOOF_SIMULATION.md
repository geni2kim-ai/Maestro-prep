# Leonardo-policy-guided R1.3: poisoned module cache simulation

**Authority:** non-final candidate; *actual Leonardo router NOT_RUN*. Read the private Leonardo R3 local router SKILL at main a4e0bc631d1033e8ba25a0a3e7b1457ca3d6a0d7. Its local-only, byte-pinned, adversarial and no-deploy guidelines informed this regression. This is not an actual Leonardo execution receipt.

**R1.2 baseline:** f28bc564b1349ef55f2ce80dca123768ad426915.
**Observed pre-fix:** A real O-Prep evaluation of synthetic PLAN with manifest_verified=false returns HOLD_SOURCE. Overriding sys.modules['o_prep'] with fake __file__ pointing to the real file, but forged evaluate_bound_signal claiming ADVANCE_CANDIDATE and LOCAL_BYTES_VERIFIED_ONLY caused BOUND_CANDIDATE_CHECKS_PASSED. This bypasses the mandatory O gate as a candidate check (does NOT grant host mutation authority).

**Fix:** Hash-check exact vendored o_prep.py and evidence_bindings.py source snapshots and execute the authenticated in-memory bytes independently. Resolve only the pinned evidence_bindings dependency with a scoped __import__ override rather than trusting preloaded named entries. Do not mutate sys.path or sys.modules. This also closes the check-to-import filesystem reread window. This is not a sandbox and cannot defeat an attacker who already controls arbitrary Python interpreter code.

**Regression:** Three added coordinator methods challenge cached o_prep, cached evidence_bindings, and process-global import side effects. Coordinator minimum raises 59 to 62. Vendor source bytes and SOURCE_PIN.json remain unchanged; 40-file distribution hashes only update for coordinator and its tests.

**Required proofs:** run python .github/scripts/main_ci.py (9/9), python -m unittest discover -s tests -q (62), tools/replay_simulation.py (20/20), tools/verify_package.py . (40), mypy --strict and GitHub CI for Ubuntu/Windows Python 3.11/3.12/3.13 before any promotion. PR/native Git diff is advisory; external PR-with-codediff-finder NOT_RUN.

**External gates:** actual Leonardo router, independent RedAgent, authenticated original private vendor installation, and production hosts: NOT_RUN. No deploy, auto-merge, or host authority.
