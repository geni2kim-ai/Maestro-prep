# R1.8 CodeDiff SHA-to-execution consistency hardening

Candidate-only non-final hardening of CodeDiff v2.5 SHADOW review. Actual Leonardo route_task and independent reviewers remain NOT_RUN.

## Confirmed on R1.7

A forged CPython timestamp .pyc file under `.github/review_tools/codediff_v25/__pycache__/` with an original source mtime and size caused the importlib file loader to execute a distinct compiled object while official SHA-pinned policy_engine.py source verification still PASSED. A local marker `SIMULATED_TAMPER_PYC` was present on the returned module. Python `-B` avoids writing bytecode but does not prevent reading an already-present valid pyc.

## R1.8 fix

- Exactly four official upstream Git source/policy blobs remain pinned.
- Compile and execute the source bytes **returned by successful Git blob hash verification**, not via `spec.loader.exec_module`; no importlib bytecode-cache source can replace the pinned engine.
- Preserve the three policy YAML bodies in immutable in-memory byte snapshots; parse these bytes through the official v2.5 PyYAML policy parser, never reopen the path after pin verification.
- Three new regression cases cover forged executable pyc, immutable YAML snapshots and actual source blob identity. Previous fail-closed and CodeDiff HUMAN-floor semantics unchanged.

## Limits

The R1.8 runner still executes within the Python interpreter; a compromised interpreter, Python dependency, Git executable or privileged filesystem adversary is not an OS sandbox. The CodeDiff SHADOW policy remains non-authoritative (`trusted_for_gate=false`, `action_required`, HUMAN needed). The Leonardo R2.30 candidate is pinned but quarantined; no full Leonardo router/model execution or independent Adversarial/RedAgent approval occurred. No main merge or production deployment is authorized.
