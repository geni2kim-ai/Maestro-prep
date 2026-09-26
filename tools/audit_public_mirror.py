#!/usr/bin/env python3
"""Read-only, non-authorizing provenance audit for an Astra-Prep PUBLIC MIRROR.

The historical CANDIDATE_HASHES.json is never modified. Even a byte-for-byte
matching published mirror does not authenticate a node owner's approved install.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_MAX_MANIFEST_BYTES = 512_000
_MAX_LISTED_FILES = 250
_MAX_FILE_BYTES = 5_000_000


class AuditError(ValueError):
    pass


def is_reparse_or_link(path: Path) -> bool:
    """Reject POSIX symlinks and Windows junction/reparse points (Leonardo threat model)."""
    try:
        mode = os.lstat(path)
    except FileNotFoundError:
        return False  # The ordinary missing-file check remains responsible.
    except OSError as exc:
        raise AuditError("PATH_LSTAT_FAILED") from exc
    if stat.S_ISLNK(mode.st_mode):
        return True
    return bool(getattr(mode, "st_file_attributes", 0) &
                getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def checked_root(path: Path) -> Path:
    """Reject links on the audit-root chain *before* resolve can erase evidence."""
    absolute = Path(os.path.abspath(path))
    for ancestor in (absolute, *absolute.parents):
        if is_reparse_or_link(ancestor):
            raise AuditError("AUDIT_ROOT_LINK_OR_REPARSE")
    if not absolute.is_dir():
        raise AuditError("AUDIT_ROOT_MISSING")
    return absolute.resolve(strict=True)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def unique_json(payload: bytes) -> dict:
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise AuditError("DUPLICATE_MANIFEST_KEY")
            obj[key] = value
        return obj
    try:
        decoded = payload.decode("utf-8", errors="strict")
        if decoded.startswith("\ufeff"):
            raise AuditError("UTF8_BOM_NOT_ALLOWED")
        doc = json.loads(decoded, object_pairs_hook=unique)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AuditError("INVALID_MANIFEST_ENCODING_OR_JSON") from exc
    if not isinstance(doc, dict):
        raise AuditError("MANIFEST_NOT_OBJECT")
    return doc


def safe_member(root: Path, rel: str) -> Path:
    if (not isinstance(rel, str) or not rel or rel.startswith("/") or
        "\\" in rel or "\x00" in rel or any(
            seg in ("", ".", "..") or ":" in seg for seg in rel.split("/")
        )):
        raise AuditError("UNSAFE_MANIFEST_PATH")
    p = root
    for part in rel.split("/"):
        p = p / part
        if is_reparse_or_link(p):
            raise AuditError("MANIFEST_LINK_OR_REPARSE_PATH")
    if not p.resolve(strict=False).is_relative_to(root.resolve(strict=True)):
        raise AuditError("MANIFEST_PATH_ESCAPES_ROOT")
    return p


def load_manifest(root: Path) -> tuple[dict, bytes]:
    p = safe_member(root, "CANDIDATE_HASHES.json")
    if not p.is_file() or p.stat().st_size > _MAX_MANIFEST_BYTES:
        raise AuditError("MANIFEST_MISSING_OR_OVERSIZE")
    raw = p.read_bytes()
    doc = unique_json(raw)
    files = doc.get("files")
    if not isinstance(files, dict) or not (1 <= len(files) <= _MAX_LISTED_FILES):
        raise AuditError("INVALID_MANIFEST_INVENTORY")
    if type(doc.get("file_count")) is not int or doc["file_count"] != len(files):
        raise AuditError("MANIFEST_COUNT_MISMATCH")
    for rel, h in files.items():
        safe_member(root, rel)
        if not isinstance(h, str) or not _SHA256.fullmatch(h):
            raise AuditError("INVALID_DECLARED_SHA256")
    if not isinstance(doc.get("bundle_aggregate_sha256"), str) or not _SHA256.fullmatch(doc["bundle_aggregate_sha256"]):
        raise AuditError("INVALID_DECLARED_AGGREGATE")
    return doc, raw


def aggregate(pairs: dict[str, str]) -> str:
    return sha256("".join(f"{path}  {pairs[path]}\n" for path in sorted(pairs)).encode("utf-8"))


def audit(root: Path) -> dict:
    root = checked_root(root)
    doc, manifest_bytes = load_manifest(root)
    declared = doc["files"]
    expected_aggregate = aggregate(declared)
    observed = {}
    discrepancies = []
    for rel in sorted(declared):
        p = safe_member(root, rel)
        if not p.is_file():
            actual = None
        elif p.stat().st_size > _MAX_FILE_BYTES:
            raise AuditError("LISTED_SOURCE_TOO_LARGE")
        else:
            actual = sha256(p.read_bytes())
        if actual is not None:
            observed[rel] = actual
        if actual != declared[rel]:
            discrepancies.append({"path": rel, "declared_sha256": declared[rel], "observed_sha256": actual})
    internally_consistent = expected_aggregate == doc["bundle_aggregate_sha256"]
    match = internally_consistent and not discrepancies
    return {
        "schema": "ASTRA_PUBLIC_MIRROR_PROVENANCE_AUDIT_V1",
        "scope": "PUBLIC_MIRROR_OBSERVED_BYTES_ONLY",
        "authority": "none", "node_approved_astra": "NOT_RUN",
        "historical_manifest_preserved": True,
        "status": "MATCH_NOT_AUTHORIZATION" if match else "HOLD_UNRECONCILED",
        "manifest_sha256": sha256(manifest_bytes),
        "manifest_listed_files": len(declared),
        "declared_aggregate": doc["bundle_aggregate_sha256"],
        "declared_aggregate_recomputed": expected_aggregate,
        "declared_aggregate_internally_consistent": internally_consistent,
        "observed_aggregate": aggregate(observed) if len(observed) == len(declared) else None,
        "observed_sha256": observed,
        "mismatches": discrepancies,
        "mismatch_count": len(discrepancies),
    }


def assess_known_drift(report: dict, root: Path, policy_path: Path) -> dict:
    """V2 known drift: fixed *bytes*, exact commit, clean tree, stable snapshot.

    An immutable commit hash alone is not enough: v0.2.6 accidentally accepted a
    dirty worktree changing the same ten paths. A hash/policy mismatch ALWAYS holds.
    """
    policy = unique_json(policy_path.read_bytes())
    if set(policy) != {"baseline_commit", "known_mismatch_sha256", "manifest_sha256",
                       "declared_aggregate_sha256", "observed_aggregate_sha256", "schema"}:
        raise AuditError("UNKNOWN_KNOWN_DRIFT_POLICY_SHAPE")
    expected = policy["known_mismatch_sha256"]
    if (policy["schema"] != "ASTRA_PUBLIC_MIRROR_KNOWN_DRIFT_V2" or
        not isinstance(expected, dict) or not expected or
        not all(isinstance(x, str) and x in report["observed_sha256"] and
                isinstance(h, str) and _SHA256.fullmatch(h) for x, h in expected.items()) or
        any(not isinstance(policy[key], str) or not _SHA256.fullmatch(policy[key])
            for key in ("manifest_sha256", "declared_aggregate_sha256", "observed_aggregate_sha256")) or
        not isinstance(policy["baseline_commit"], str) or
        not re.fullmatch(r"[0-9a-f]{40}", policy["baseline_commit"])):
        raise AuditError("INVALID_KNOWN_DRIFT_POLICY")

    root = checked_root(root)
    def git(*args: str) -> bytes:
        cmd = subprocess.run(["git", "-C", str(root), *args], check=False,
                             capture_output=True, timeout=12)
        if cmd.returncode != 0:
            raise AuditError("GIT_BASELINE_OR_STATUS_UNAVAILABLE")
        return cmd.stdout
    repo_root = Path(os.fsdecode(git("rev-parse", "--show-toplevel").strip())).resolve(strict=True)
    root_matches = repo_root == root
    head = git("rev-parse", "--verify", "HEAD").strip().decode("ascii")
    head_matches = head == policy["baseline_commit"]
    # Commit-to-commit diff cannot see dirty index/worktree files. Require a clean
    # source tree as a whole, including untracked files not ignored by Git.
    dirty = bool(git("status", "--porcelain=v1", "-z", "--untracked-files=all"))
    changed = git("diff", "--name-only", policy["baseline_commit"], "HEAD", "--",
                  "CANDIDATE_HASHES.json", *report["observed_sha256"]).decode("utf-8").splitlines()
    # Detect changes after the first audit but before this source classification.
    again = audit(root)
    stable = (report["manifest_sha256"] == again["manifest_sha256"] and
              report["observed_sha256"] == again["observed_sha256"] and
              report["declared_aggregate"] == again["declared_aggregate"])
    mismatches = {x["path"]: x["observed_sha256"] for x in report["mismatches"]}
    exact = (root_matches and head_matches and not dirty and not changed and stable and
             mismatches == expected and
             report["manifest_sha256"] == policy["manifest_sha256"] and
             report["declared_aggregate"] == policy["declared_aggregate_sha256"] and
             report["observed_aggregate"] == policy["observed_aggregate_sha256"] and
             report["declared_aggregate_internally_consistent"] and
             report["status"] == "HOLD_UNRECONCILED")
    return {
        "schema": "ASTRA_PUBLIC_MIRROR_KNOWN_DRIFT_RECEIPT_V2",
        "expected_public_commit": policy["baseline_commit"],
        "observed_public_commit": head,
        "checkout_bound_to_commit": bool(root_matches and head_matches),
        "source_worktree_clean": not dirty,
        "audit_snapshot_stable": stable,
        "exact_mismatch_bytes": mismatches == expected,
        "historic_payload_changed_since_commit": changed,
        "exact_known_drift": exact,
        "status": "EXPECTED_DRIFT_STILL_HOLD" if exact else "UNEXPECTED_DELTA_HOLD",
        "node_authority": False,
    }


def exclusive_report(path: Path, obj: dict, root: Path) -> None:
    resolved = path.resolve(strict=False)
    if resolved.is_relative_to(root.resolve(strict=True)):
        raise AuditError("REPORT_MUST_BE_OUTSIDE_PUBLIC_SOURCE_TREE")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as out:
        out.write(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--report", type=Path)
    ap.add_argument("--known-drift-policy", type=Path,
                    help="diagnostic only: exit 0 for exactly documented HOLD, never approved")
    args = ap.parse_args()
    try:
        result = audit(args.root)
        if args.known_drift_policy:
            result["known_drift"] = assess_known_drift(result, args.root, args.known_drift_policy)
        if args.report:
            exclusive_report(args.report, result, args.root)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        # A supplied known-drift policy must always be honored: a now-matching
        # mirror is a new provenance state, not the same historical exception.
        if args.known_drift_policy:
            return 0 if result["known_drift"]["exact_known_drift"] else 2
        return 0 if result["status"] == "MATCH_NOT_AUTHORIZATION" else 2
    except (AuditError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({"schema": "ASTRA_PUBLIC_MIRROR_PROVENANCE_AUDIT_V1", "status": "HOLD_ERROR",
                          "code": str(exc) if isinstance(exc, AuditError) else type(exc).__name__,
                          "authority": "none"}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
