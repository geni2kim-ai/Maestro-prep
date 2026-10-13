# R1.20 — R1.19 regression coverage bound into pinned CI accounting

Date: 2026-10-13. Baseline R1.19 `33143f4f0c5632a996ff3e01cd0df34ddbaa9e44`. Candidate-only, Draft PR #5.

## Reproduced evidence-accounting gap

The R1.19 standalone test step was `python -I -B -m unittest discover -s .github/scripts -p test_child_env_isolation.py -v`, with no fixed identities or source-byte check. A controlled CPython 3.13 local simulation of unittest discovery with **two passing methods vs. one passing method** produced exit code 0 in both cases. Removing one of the mandatory two new tests therefore would not turn this standalone CI step red, even though security regression coverage decreased. This is a validation-inventory weakness, NOT a confirmed bypass of the product's environment isolation.

## Smallest safe corrective action

- Copy the exact two R1.19 test method implementations into `CIAccountingTests` in `.github/scripts/test_main_ci_contract.py` in addition to keeping the R1.19 standalone test and workflow step.
- Extend the reviewed per-method identity allowlist and required test floor from 36 to 38 and regenerate the candidate-owned whole-file SHA256 pin for the expanded CI accounting implementation: `8acb8276f9fc255e98d4ff90611b3c8be494284c268a8a2a07d2436d5586cdf3`.
- This reuses R1.15's exact unittest trace and R1.16's before-and-after implementation byte gate and R1.17's fresh Python cache prefix, without broadening runtime or deployment permissions.
- Each of the two checks now runs both as supplementary standalone evidence and in the pinned CI accounting suite; deliberately removing or renaming one in the pinned suite triggers a fail-closed gate. **This is redundant test execution, not two independent reviewers**.
- No O-Prep, Leonardo route-adapter, manifest inventory, coordinator product decision, or release code is changed. No new local-node package is needed for this CI-only regression.

## Leonardo provenance and human-review gate

Inspected original pinned Leonardo R2.30 `leonardo_use_policy.py` Git blob `2dedbc58ba968da3d10fd783f54f43e762c52763`: a multi-agent authority-sensitive change implies mandatory deeper consideration, while deterministic checks should prefer direct tools. The analysis here is a **policy-guided simulation**, not a live full `route_task` run, model execution, or independent Leonardo/RedAgent verdict.

CI acceptance: GitHub Actions 6 OS/Python matrix PASS, exact 38/38 accounting PASS, offline profile 9/9, CodeDiff v2.5 SHADOW and source-bundle jobs PASS on the exact PR HEAD. Independently signed provenance, trusted host integrity, Windows ordinary-user real symlink tests and HUMAN approval remain NOT_RUN / HOLD. SHADOW has no authority to approve, merge, or deploy.
