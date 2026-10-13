# R1.25 — bounded external JSON and O-Prep read-at-open path checks

Date 2026-10-13. Parent `d3383518e89eba50094645dc7a88ee6f0a04ef56`, candidate Draft PR #5 only.

## Leonardo policy-guided adversarial simulation and observed gap

O-Prep's `evidence_bindings._safe_local_file` checks that each receipt path component is not a symlink/junction, but the later `_read_limited` previously started with `p.stat()` and `p.open()`, both following symlinks. In a bounded CPython sandbox reproduction, swap the final leaf for a symlink to an outside file after path validation: stat and fstat agree about the *outside target*, and external bytes pass the old open-time check. **No real protected node or active Leonardo router was touched.** This issue does not imply robust protection against all ancestor directory swap races.

Separately, O-Prep CLI `evaluate` and `evaluate-bound` used unbounded `Path.read_bytes()` on producer-controlled signal JSON, as did `audit_transport_bundle` on optional peer audit JSON. This exposes a memory exhaustion risk even though transported ZIP bytes and indexed artifacts are bounded. Peer audit root/nested shape did not have stable contract checking.

## Corrective candidate scope

- At `_read_limited` recheck final component by `lstat()` before open, use `O_NOFOLLOW` where available, compare inode/device and reparse/symlink state at opening and after reading. Reject changed files with existing `receipt_changed_during_open/read` and `receipt_symlink_forbidden` codes. This strengthens file-leaf handling; does **not** guarantee safe ancestor paths across all OS rename races, and is not a sandbox.
- For CLI signal and optional peer JSON, read at most 1 MiB + 1 byte and reject oversized documents before JSON parsing or evaluation. Reject explicit symlink input paths and non-regular opened files.
- Reject malformed optional peer audit root/nested document with fixed `peer_audit_shape_invalid` rather than leaking a traceback from an `AttributeError`.
- Add four tests: post-validation symlink swap (real on POSIX; synthetic NTFS reparse flag on Windows), oversized signal both CLI commands, oversized peer archive, invalid peer document shape. No new Windows-specific skip added.
- Maintain public derivative v0.3, update `SOURCE_PIN.json`, all touched entries of the 40-file manifest and `SHA256SUMS.txt`. SHA256 pins are candidate-owned consistency checks, not external authenticity signatures.

## Remaining security gates

The full Leonardo R2.30 route_task/model was not invoked; the Leonardo use-policy informs the synthetic adversarial test prioritization only. Independent RedAgent and HUMAN review NOT_RUN. Real unprivileged Windows symlink privilege and ancestor directory swap handling remain HOLD. CodeDiff v2.5 is SHADOW, nonauthoritative and may require human review. Do not merge or deploy based on successful CI.
