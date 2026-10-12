# Leonardo-informed R1.5: post-O task/policy tamper and contradictory guard

Date: 2026-10-13. Candidate-only. This is an execution of Maestro-prep's
synthetic threat simulations using Leonardo R3 contract source as reference.
Actual private Leonardo router executable: NOT_RUN (no independently verified
runtime receipt). No network, live host mutation, RedAgent or codediff-finder
engine executed. No merge/deploy authorized.

## Reproduction on R1.4 baseline 08328768dd5296baef9d6bbd5d4735d8e7c605e4

1. Invoke the *real pinned* O-Prep evaluator on the standard PLAN fixture; once
   it returns ADVANCE_CANDIDATE, replace `receipts/router_input.bin` and
   `receipts/router_policy.bin`. The prior raw router_output-only recheck passes,
   and Maestro incorrectly returns `BOUND_CANDIDATE_CHECKS_PASSED`.
2. Keep the route in READY, with `candidate_work_allowed=true` and `blocks=[]`,
   but set `guard.block_codes=["NETWORK_REQUESTED"]`,
   `guard.network="ALLOWED"` and contradictory next_action. R1.4 ignores those
   documented Leonardo R3 fields and incorrectly returns candidate checks PASSED.

## Fix

- Snapshot receipt index SHA-256 immediately before O-Prep; after O-Prep check
  that exact indexed bytes persisted, rejecting any missing/mismatched index.
- Re-read and validate SHA-256 plus size for all three mandatory router receipt
  roles, not only the output. Keep O-Prep's original validation authoritative.
- Require R3's three block channels to be empty, five immutable candidate
  controls exact true, forbidden network/deployment/credentials/external/
  production controls exact FORBIDDEN, and READY next_action consistent.
- No change to the pinned O-Prep source; only coordinator, tests, manifest,
  release checks and integration docs updated.

## Scope and limitations

Post-gate local file consistency does not prove trust in the receipt producer,
prevent a malicious co-resident Python interpreter, or guarantee durable
filesystem snapshots across concurrent access. Actual Leonardo CLI, independent
RedAgent, independent PR-with-codediff-finder and macOS are NOT_RUN. Validation
of changed head on Ubuntu/Windows Python 3.11/3.12/3.13 is required for CI PASS.
