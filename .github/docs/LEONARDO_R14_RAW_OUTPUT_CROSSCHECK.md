# R1.4 Leonardo-policy-guided raw route/capture discrepancy simulation

Date: 2026-10-13. Candidate-only, non-final. Actual external Leonardo executable: NOT_RUN. Input model aligned with the Leonardo R3 router contract (execution_state, candidate_work_allowed, request.request_sha256, input_bindings.policy_sha256, guard.blocks) after source review, but the regression values are synthetic and no external router receipt is asserted.

## Reproduced on R1.3

1. A genuine locally byte-bound router_output artifact contains execution_state=BLOCKED_BY_LOCAL_POLICY and candidate_work_allowed=false.
2. The separate producer-authored LEONARDO_ROUTE_CAPTURE_V1 claims READY/exit 0. The O-Prep index and capture SHA256 both match those raw bytes.
3. The R1.3 coordinator returns BOUND_CANDIDATE_CHECKS_PASSED, despite contradictory route semantics. The physical host-mutation authority remains false.

This is a false-positive candidate verification, not evidence of actual Leonardo running or a deployment.

## Code fix / evidence classes

- Resolve router_output from the existing verified receipt index, re-read its bytes under the bounded local root, and rehash after the O-Prep gate (TOCTOU hardening).
- Parse the actual output JSON and require an exact READY_FOR_LOCAL_CANDIDATE_WORK state, exact boolean true, matching request/policy digests, and well-formed empty guard blocks.
- Hold on disagreement, missing/malformed fields, invalid raw JSON, path changes and post-gate modifications. Issue codes remain stable and path-free.
- Keep original vendored O-Prep sources and no-host-authority boundary unchanged. Prevent claims of independent sign-off from producer-authored captures.

## Proof requirement

Coordinator 71 tests, including nine new R1.4 regressions (malformed guard and non-object route included); synthetic replay 20/20, offline CI 9/9, public inventory 40/40. Require Ubuntu/Windows Python 3.11/3.12/3.13 GitHub Actions CI after the exact head SHA. Strict mypy local may be unavailable and must not be claimed PASS without CI evidence.

Independent RedAgent, real Leonardo router, external codediff-finder binary, macOS and live deployment remain NOT_RUN. Never merge or deploy on this evidence alone.
