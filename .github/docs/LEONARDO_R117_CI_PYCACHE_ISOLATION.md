# R1.17 Leonardo-informed CI child-process bytecode cache isolation (NON-FINAL)

Date: 2026-10-13. R1.16 baseline `b5a5e69a5c13c1ca283a214825747c430c834a11`. Changes limited to CI test execution and regression checks; candidate-only, no operating-system host approval, no merge/deployment.

## Actual attack reproduced against R1.16

1. Restored exact GitHub Actions Run #95 source (HEAD `b5a5e69a5c13c1ca283a214825747c430c834a11`, nested source ZIP SHA256 `e0610955df1c70d503ec1908a571292fc4efef59b215ab0a9a43fb891ae7f5b9`). Original `python -B .github/scripts/main_ci.py` was **9/9 PASS**, source-pin `CI_GUARD_SOURCE_BYTES_VERIFIED`, test-identity `CI_GUARD_TEST_IDENTITIES_VERIFIED`.
2. Placed a harmless yet **different, syntactically valid timestamp/size-matching CPython .pyc** at `.github/scripts/__pycache__/test_main_ci_contract.cpython-313.pyc`. The bytecode substituted one security-accounting test method body with a marker write; the `.py` file bytes and SHA256 `ed68940d05d2599e2fc5b4e0052ec278c9fba3d0ce22eca106a3b6044e568043` remained unchanged.
3. Real CPython 3.13 execution of R1.16 `python -B .github/scripts/main_ci.py` generated the **attack marker** and still returned **9/9 PASS**, including valid source SHA and 31 required test identities. Thus `-B` and `PYTHONDONTWRITEBYTECODE=1` blocked bytecode *writes*, not *reads*. No real user machine, production data or secrets were touched.

## R1.17 fix

- All nine offline CI child checks are launched with `-B -X pycache_prefix=<fresh-temp-dir>` and `PYTHONDONTWRITEBYTECODE=1`. The supplied prefix is unique per subprocess and empty when execution starts. Because CPython resolves import cache locations using the explicit prefix, stale repository `__pycache__` contents cannot shadow checked source imports.
- `-X` explicitly overrides an inherited `PYTHONPYCACHEPREFIX`; the temp directory is removed when the subprocess ends. This does **not** override a compromised Python binary, malicious `sitecustomize`, or imports from unchecked source and is **not** sandbox isolation.
- Three new regressions: verify cache-prefix flag and freshness; two sequential child calls use distinct prefixes; actual CPython import uses an untrusted valid `.pyc` without the prefix but source text **with** the prefix.
- CI accounting methods increase **31→34**, closed identity allowlist and required floor both updated; reviewed test source SHA256 literal pinned to `1e021d2028189689f04f6b2c59e12d16e026f0234ebb21d185668df0d689f7a2`. The pinned source hash is candidate-controlled, not independent attestation.

## Reproduction and verification

Local Python 3.13 original candidate: offline **9/9 PASS**, accounting unit **34 PASS**, coordinator **79**, public O-Prep **70**, official CodeDiff integration regressions **21 PASS**, public privacy PASS. Replayed the same valid malicious bytecode in the same exact relative `__pycache__` location on patched candidate, without editing source: offline **9/9 PASS** and **attack marker ABSENT**. The success count alone does not demonstrate cache safety: the absent marker plus deliberate cached-bytecode control are the meaningful paired observations. The isolated three-module Python import probe also showed original `-B` -> `POISON`, and `-B -X pycache_prefix=empty` -> `SOURCE`.

GitHub blob identity of exact locally executed candidate: `main_ci.py` Git blob `3196bb90b094ca2c05cb353d06e88e5e97d2935e`; `test_main_ci_contract.py` Git blob `e4bf13f3136fce5058e90de1e464a3920bec55c7`.

## Leonardo original-source policy execution, strictly bounded

Four Leonardo R2.30 original modules were checked by SHA-1 Git object IDs and copied into fresh isolated Python source directory, using fresh bytecode prefix:
- `leonardo_use_policy.py` `2dedbc58ba968da3d10fd783f54f43e762c52763`
- `signals.py` `34c8d412ad376ed21a5ca94a5cfc65c173a09be5`
- `contract.py` `4665c26f9be9e52b4bba1bb968660bb654bd7f67`
- `util.py` `36b526f73692609d1b230b2ef7760f64f2d435ec`.

With **hand-assigned synthetic flags**, frozen-evidence review -> `FORBIDDEN_INSIDE_REVIEW`; security-sensitive multi-agent change -> `MANDATORY`; checksum-only -> `BYPASS`. Frozen synthetic contract SHA matched; modifying its authority-relevant flag invalidated digest. **Actual `route_task`, signal inference, model execution and independent RedAgent/HUMAN NOT_RUN.** This is non-authoritative policy-function execution, not a full Leonardo verdict.

## Review and remaining limitations

Re-run native GitHub PR diff and pinned official CodeDiff v2.5 policy-engine SHADOW on exact HEAD; CodeDiff remains sensor-only, `required_level=HUMAN`, `authority_effect=NONE`. Candidate-owned test source hash is not a signature. The same-host general-user Windows symlink restriction remains unresolved/HOLD; test cache isolation is verifiable in GitHub CI and requires no new end-user sandbox run to preserve fail-closed status, so **no new local operator package is necessary**. Existing Draft PR remains non-final.

**Do not merge, approve or deploy from these self-tests.**