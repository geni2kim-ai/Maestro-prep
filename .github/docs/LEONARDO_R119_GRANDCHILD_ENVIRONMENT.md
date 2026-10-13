# R1.19 — inherited PYTHONPATH in Python grandchildren (NON-FINAL)

2026-10-13. Base R1.18 `81efdcced3e869e398bed75e35be6659a05892f9`. Draft PR #5; candidate only. No merge, deployment, operating host authority, or HUMAN/RedAgent approval.

## Reproduced gap

R1.18's `-E -s` protects each directly spawned offline CI Python child from ambient `PYTHONPATH` during that interpreter's own imports. It does not remove the variable from the environment forwarded to that process. A Python grandchild started without `-E` can still inherit that path and import an unreviewed module.

An isolated CPython 3.13 demonstration with a harmless synthetic module showed the first protected interpreter spawning a grandchild that printed `GRANDCHILD_IMPORTED` (return code 0). With Python-specific ambient variables stripped before the protected child started, the identical grandchild import returned 1. This is an interpreter-level reproduction, not a claim that a production Maestro or local Leonardo node was compromised.

## Narrow correction

- All nine offline CI checks receive a sanitized child environment with every case-insensitive `PYTHON*` variable removed, then `PYTHONDONTWRITEBYTECODE=1` explicitly added. `-E -s -B -X pycache_prefix` remains unchanged.
- Add a standalone two-case `test_child_env_isolation.py` suite: (1) mock-verified env forwarding, (2) actual CPython child/grandchild import experiment. A separate mandatory CI workflow step runs it across Windows/Linux and Python 3.11/3.12/3.13.
- The existing 36-method accounting source, its SHA256 pin and closed-name allowlist remain unchanged. Offline CI keeps its nine gate count, coordinator 79, component 70, replay 20 and manifest 40. O-Prep and Leonardo component sources remain untouched.
- The top-level GitHub runner continues to invoke `main_ci.py` as `python -I -B` as in R1.18.

## Residual boundaries

This regression is separately run by GitHub CI but is not independently attested. A child can **intentionally create a new** hostile `PYTHONPATH`; this fix blocks unintended ambient inheritance, not malicious source, interpreter or system packages. Independently verified Leonardo full `route_task`, model routing, RedAgent and HUMAN remain NOT_RUN. Ordinary-user Windows real-symlink coverage is still HOLD. CodeDiff v2.5 remains a non-authoritative SHADOW sensor, and independent source/diff review is required. No new Windows local-node bundle is warranted for this portable CI-only change.
