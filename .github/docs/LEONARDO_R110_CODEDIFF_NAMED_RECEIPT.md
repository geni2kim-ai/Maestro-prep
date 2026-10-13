# R1.10 Leonardo-guided CodeDiff SHADOW named-receipt verification

Date: 2026-10-13. Non-final, candidate-only. R1.9 baseline `1614066db1a0daadf24e7215edb49c3df68c4de2`. The official CodeDiff v2.5 policy engine remains upstream-source-pinned; mandatory O-Prep and main are untouched.

## Confirmed R1.9 defect

In an isolated POSIX temp directory, intercepted the JSON report write after `O_EXCL` creation but before the final parent-directory check. Renamed the legitimate file away, created a new file at the expected basename containing synthetic `gate_conclusion=success`, `authority_effect=APPROVED`, and returned to the writer. R1.9 completed successfully with that forged report on disk. The directory's path and inode did not change. This does NOT demonstrate compromise of a real user's node, only a repeatable gap in the writer's final verification.

## R1.10 correction

- Serialize the approved SHADOW JSON exactly once and cap it at 1 MiB before opening the destination.
- Bind the `O_EXCL|O_NOFOLLOW` created file's device/inode using `fstat`.
- After flushing/fsync and closing, reopen the **named path** under the held directory descriptor with `O_NOFOLLOW|O_NONBLOCK`.
- Confirm the named file is a regular file with the exact original device/inode, single hard link, expected byte length and exact serialized payload.
- On mismatch or failed write, return a non-success status and remove only the file identified as created by the current invocation, never an attacker's replacement.
- Preserve parent directory identity checks, Linux/POSIX-only fail-closed writer, 0600 mode, no overwrite, stable pinned Leonardo candidate and CodeDiff source rules.
- Three new adversarial regressions: filename swapped after fsync, content modified in the same inode, >1MiB output rejected before creating a file.

## Residual limits

The readback closes the demonstrated replacement window before the final check, but an attacker with ongoing write access to the output directory could modify the file *after* the final readback. The output directory therefore must remain isolated and access-controlled (external OS sandbox/ACL and downstream exact-content verification). File SHA is not an independent signature or approval. Windows protected writer is still unsupported and holds; independent L1/L2/RedAgent/HUMAN and full Leonardo routing remain NOT_RUN.

## Reviewer expectations

Validate on exact candidate HEAD with Ubuntu/Windows Python 3.11-3.13 + CodeDiff v2.5 policy SHADOW, reference GitHub-native base-to-head diff, attach isolated local evidence and do not promote SHADOW output beyond `action_required`.
