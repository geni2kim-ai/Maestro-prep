# R1.15 Leonardo-guided exact CI guard-test identity verification

Date 2026-10-13. Candidate-only, Draft PR #5. No product runtime authority or deployment authorized.

## Confirmed R1.14 accounting defects

R1.14 `.github/scripts/main_ci.py` accepted both of the following **controlled** mocked `subprocess.CompletedProcess` reports as `passed=true`:
- `ci_guard_tests` returned exit 0, `Ran 23 tests / OK`, but the 23 displayed test names were all replaced by arbitrary dummy test methods.
- `ci_guard_tests` returned exit 0, `Ran 23 tests / OK`, with **no per-test method identities whatsoever**.

The issue was not the numeric R1.14 floor (23), but the absence of a test identity cross-check for the security-sensitive CI accounting suite. The injected output was synthetic; this does not demonstrate real local node compromise or an independent malicious runtime.

## R1.15 remediation

- Run the CI accounting unittest suite in verbose mode (`-v`) to expose the executed per-test identities and their outcomes in stderr.
- Maintain an explicitly reviewed **27-method exact-name list** (R1.14 23 tests + 4 focused regressions) inside `main_ci.py`. Require one unique `test_method (test_main_ci_contract.CIAccountingTests.test_method) ... ok` trace for every required method, with no missing, duplicate or unexpected entries. The total trace count must equal the unambiguous standard unittest run count and the pinned 27-method list.
- Increase the `ci_guard_tests` minimum count to 27; do not change coordinator, public component, privacy, replay or external gate acceptance policies. The Windows standard-user symlink privilege coverage remains HOLD when unexecuted.
- Four new focused tests cover same-count test ID substitution (BLOCK), missing per-test trace with unchanged count (BLOCK), duplicate ID (BLOCK), and complete exact identity inventory (PASS).
- The test names and reporting logic are maintained together in the candidate. A malicious actor who can arbitrarily modify both could retain the names but replace implementation bodies. This is *bounded CI evidence*, not independent code integrity attestation. GitHub-native diff inspection and HUMAN reviewer are required.

## Verified local preflight and Leonardo scope

Exact GitHub Run #93 R1.14 source archive SHA256 `cdfc1903c35b6a227f00f5ca2f387ed0249f8fd8fa8d87ab89389bf88d5bef01` at `5964d6b393ee5944face9ba4407ff3e701867811` was extracted and reverified before modification. R1.14 offline CI **9/9 PASS** and original accounting suite **23 PASS**. Baseline synthetic probes above both returned `passed=true`.

R1.15 local Linux result: accounting tests **27 PASS**, source inventory and offline CI **9/9 PASS**, coordinator **79**, public compatibility component **70**, pinned CodeDiff regression **21 PASS**. Both altered/missing-list probes now return `passed=false`, and exact executed identity set matches all 27 pinned names.

Verified Git blob source IDs for the four separately isolated original Leonardo R2.30 modules `leonardo_use_policy.py` `2dedbc58ba968da3d10fd783f54f43e762c52763`, `signals.py` `34c8d412ad376ed21a5ca94a5cfc65c173a09be5`, `contract.py` `4665c26f9be9e52b4bba1bb968660bb654bd7f67`, and `util.py` `36b526f73692609d1b230b2ef7760f64f2d435ec`. Ran original policy function with **hand-assigned** signals: frozen evidence -> `FORBIDDEN_INSIDE_REVIEW`; authority-sensitive multiagent change -> `MANDATORY`; deterministic checksum-only -> `BYPASS`. Verified synthetic frozen contract hash and rejection on mutation. **Real Leonardo natural-language signal detector, full `route_task` pipeline, agent/model execution, and independent RedAgent NOT_RUN.**

## Governance boundary

Pinned CodeDiff v2.5 SHADOW policy-engine and GitHub CI must run against the eventual exact commit. `DEGRADED_GIT_INVENTORY` remains non-final, `trusted_for_gate=false`, `gate_conclusion=action_required`, HUMAN required. Do not merge or deploy. No new local operator sandbox package: no host-specific runtime behavior changed, and ordinary-user Windows missing symlink coverage remains a known blocked gap.
