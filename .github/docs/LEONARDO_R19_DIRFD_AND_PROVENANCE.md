# R1.9 Leonardo-informed CodeDiff SHADOW adversarial simulation and fix

Date: 2026-10-13. **Candidate only / no external authority.** Baseline R1.8 `6caa6d49caee1ba1bbfbc08aceee6d183fb9d98b`.

## Observed and reproduced before changes

1. **Post-validation directory symlink swap**: the SHADOW CLI verified output was outside the source tree. The injected `analyze()` hook then replaced the output directory with a link into the source root; R1.8 successfully wrote a JSON receipt **inside the checkout** (`exit 0`, 155 bytes in the local minimal reproduction). A pre-write `Path.resolve` is inadequate if directories can change between test and open.
2. **Leonardo candidate provenance substitution**: modifying `EXTERNAL_SOURCE_PINS.json` so `latest_examined_candidate_sha` was 40 zeroes was accepted by `trusted_source_snapshot()`; CodeDiff original file hashes remained valid. This allowed an unverified Leonardo candidate identifier to enter the SHADOW report.

## R1.9 corrections and residual risk

- On POSIX platforms only, open the already-approved output parent with `O_DIRECTORY|O_NOFOLLOW`, hold a directory descriptor, compare inode/device/path containment, create the output with `O_CREAT|O_EXCL|O_NOFOLLOW` relative to that FD, use mode `0600`, and check directory identity again before declaring success. Remove a partial report from the held FD when a post-write check fails. No fallback to path-based writing when the fd primitive is unavailable (`OUTPUT_DIRFD_UNSUPPORTED`), including current Windows path. On Windows use a separate approved, OS-attested launcher rather than relaxing this guard.
- This mitigates the **simulated symlink-parent exchange** but is *not* a general guarantee against a privileged attacker that can move the held directory into the checkout after the final check. Enforce OS sandbox/ACL and an isolated output mount for production-grade integrity. No sandbox was configured by this software.
- Bind the Leonardo upstream repository, stable/main SHA, pinned R2.30 candidate SHA, candidate branch, version and `live_execution=NOT_RUN` to reviewed constants before a report can be created. Source-pinning is not proof of running the full Leonardo router.
- Five new unit tests cover an attack during analysis, an exchange after the directory FD is opened, Leonardo SHA/branch/repo substitution, and protected report create/no-overwrite.

## Leonardo exact-source limited execution and CodeDiff boundary

A **separately isolated** local probe executed the exact Git blob-pinned R2.30 modules `leonardo_use_policy.py`, `contract.py`, and `util.py` from `80bb6891e772feb506a79dfe2c3beac2b5ae1dcc`. Explicit high-impact multiagent authority/security signals led to `MANDATORY`, frozen evidence led to `FORBIDDEN_INSIDE_REVIEW`; a synthetic `BLOCKED_BY_LOCAL_POLICY` contract's SHA was valid and a tampered candidate flag failed recomputation. These synthetic signals were **hand-assigned**; real signal detection, full `route_task`, model providers, and independent RedAgent were **NOT_RUN**. No upstream private module is checked into Maestro-prep.

The official pinned PR-with-codediff-finder v2.5 policy-engine remains SHADOW, `DEGRADED_GIT_INVENTORY`, `trusted_for_gate=false`, `required_level=HUMAN`, `gate_conclusion=action_required`. No L1/L2/Adversarial/HUMAN review was executed. This change is not a merge, deployment or approval decision. Freeze exact CI head, CI log, native GitHub diff and the local portable reproduction separately.
