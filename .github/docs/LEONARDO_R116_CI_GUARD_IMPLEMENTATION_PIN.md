# R1.16 Leonardo-informed CI-guard implementation byte binding (NON-FINAL)

Date: 2026-10-13. Draft PR candidate only. Baseline 1f9dae80a8386e9e803203f168c5d6c741f8a30d (R1.15). Mandatory O-Prep/runtime unchanged. No merge/deploy/HUMAN signoff.

## Reproduced real local test-body neutralization

Using the exact GitHub Run #94 tracked-source ZIP SHA-256 `eb4d13c921561d29780f37f33700f075e986a4cdabe07eec047d06974bbfa958`, Python 3.11, in an isolated checkout copy:
- Original baseline `python -B .github/scripts/main_ci.py` -> **9/9 PASS**, CI accounting **27 methods PASS**.
- Replaced the body of exactly one `test_contradictory_coordinator_summary_is_not_green` method with a harmless no-op, **preserving its name, test count and invocation**. R1.15 still exited zero, **9/9 PASS**, `CI_GUARD_TEST_IDENTITIES_VERIFIED`, even though a required security-accounting assertion was missing. No production host or secret was touched.

## R1.16 fix

- Define a SHA-256 pin for **the entire UTF-8 bytes of `.github/scripts/test_main_ci_contract.py`**, not just its method names. Pinned reviewed candidate test bytes: `ed68940d05d2599e2fc5b4e0052ec278c9fba3d0ce22eca106a3b6044e568043`.
- Verify candidate test source bytes before and after the subprocess run; reject missing, symlink, oversized (>1 MiB), unreadable and hash-mismatched code. Record `CI_GUARD_SOURCE_BYTES_VERIFIED` or `CI_GUARD_SOURCE_PIN_MISMATCH` separately from name/count matching.
- Four new unit tests cover matching source, changed method source, missing file, and simulated symlink source. Maintained closed 31-method list and minimum of 31; existing coordinator (79), component (70), O-Prep and CodeDiff SHADOW rules unchanged.
- Exact patched source Git blob IDs were independently matched before pushing: `main_ci.py` `c461e6511bf0d68dc63f849c80962bf3d4669359` and `test_main_ci_contract.py` `41401f370deaa3610a1523d76374d94e1c36c327`.

### Executed local verification and attack replay

- Real modified candidate source: 31 accounting tests PASS, all 9 offline gates PASS, coordinator 79 PASS, component 70 PASS, Python syntax compile PASS.
- After same benign test body neutralization on R1.16: `main_ci.py` exit **2**, offline checks **8/9**, specific guard `CI_GUARD_SOURCE_PIN_MISMATCH`. Other gates unaffected.
- This validates fixed bytes in a stable checkout; **not** a signed/independently attested test suite. Candidate can change both the pinned source file and its local hash constant, or a malicious execution environment could substitute imported bytecode or files after the readback. A trusted host/signed release, independent diff review, filesystem ACL and CodeDiff-only sensor distinction remain necessary. Do not claim full TOCTOU coverage.

## Leonardo exact upstream code, limited policy/contract execution

From isolated source-only copy after verifying the four original R2.30 Git blob IDs: `leonardo_use_policy.py` `2dedbc58ba968da3d10fd783f54f43e762c52763`; `signals.py` `34c8d412ad376ed21a5ca94a5cfc65c173a09be5`; `contract.py` `4665c26f9be9e52b4bba1bb968660bb654bd7f67`; `util.py` `36b526f73692609d1b230b2ef7760f64f2d435ec`. **Hand-assigned** synthetic inputs: frozen evidence `FORBIDDEN_INSIDE_REVIEW`, high-impact multi-agent security `MANDATORY`, deterministic digest `BYPASS`; synthetic contract digest valid; mutated `candidate_only` invalidates digest. Actual detector, full Leonardo `route_task`, model orchestration, independent RedAgent **NOT_RUN**.

## Required CodeDiff/GitHub validation

Use native R1.15→R1.16 compare, 6 OS/Python jobs and official pinned CodeDiff v2.5 policy-engine SHADOW on exact head. SHADOW `trusted_for_gate=false`, `authority_effect=NONE`, `required_level=HUMAN`; no L1/L2/RedAgent/HUMAN. Operator's Windows ordinary-user symlink security test coverage still HOLD, no new environment-specific need; per user preference **no new local-node package**.

**Nonfinal result.** The local SHA pin helps detect *unreviewed changes to an individual test body*. Only an independent trusted reviewer can bind both the pin and its owning source to an approved baseline.
