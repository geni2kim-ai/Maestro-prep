# R1.7 Leonardo-guided CodeDiff SHADOW negative simulations

**Source comparison date:** 2026-10-13. Candidate-only. R1.6 baseline e78c33027153dd30da991a3d4e4007484b8e1e08. No human signoff, merge, or deployment permission.

## Exact-source Leonardo limited execution (locally, NOT in public GitHub source)
Three upstream Leonardo R2.30 private Python modules (policy-use, contract, JSON hash utility) from commit 80bb6891e772feb506a79dfe2c3beac2b5ae1dcc were executed in an isolated temporary test location and compared to the exact upstream Git blob SHA identifiers. Synthetic, explicitly supplied signal shapes produced MANDATORY clarification for multi-agent high-impact security changes; FORBIDDEN_INSIDE_REVIEW for frozen evidence; BYPASS for deterministic-only inspection. A synthetic blocked contract's event hash matched and tampering was rejected. **The actual complete Leonardo routing pipeline and input signal detector were NOT_RUN**. The private original source was NOT checked into this public repo. This is a manually constructed policy/unit probe, not a Leonardo-issued route_task receipt.

## Confirmed R1.6 failure cases
1. Relative external output path beneath a symlinked parent resolving into the repository allowed an on-disk write inside the source root (exit 0); verified with an actual filesystem link.
2. An actual Git HEAD matching the requested SHA but with modified tracked and untracked files was accepted for SHADOW analysis; change inventory represented clean Git commit content rather than what the runner could execute.
3. A modified upstream descriptor inside EXTERNAL_SOURCE_PINS.json naming an unrelated reviewer repository was accepted by the R1.6 source snapshot check. Duplicate expected sources could also satisfy the length check.

## R1.7 corrections
- Canonicalize output parent and destination, rejecting paths that resolve into the source checkout. Preserve no-overwrite creation and existing non-authoritative review output.
- Require clean Git worktree (tracked, untracked, renamed) at analysis start; disable external diffs/textconv and Git fsmonitor for deterministic inventory.
- Pin expected upstream commit/repository, exactly one copy of each of four expected source files, and check known upstream Git blob identities; reject symlinked vendor source/path.
- Five new negative unit methods; all tests remain shadow-only. CI reports the historical failures separately and does not classify CodeDiff output as authority.

**Limitations:** As long as scripts/workflow are supplied by the untrusted candidate branch, local self-validation cannot be an independent approval. Symlink parent replacement after checks is not protected by a filesystem sandbox. Real TextDiff and L1/L2/RedAgent/HUMAN authority: NOT_RUN. GitHub CI on exact candidate commit is mandatory before handoff.
