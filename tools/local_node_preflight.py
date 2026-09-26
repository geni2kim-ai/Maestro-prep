#!/usr/bin/env python3
"""Read-only, fail-closed candidate-to-node *byte* preflight.

No deployment, promotion, network, Leonardo execution, Astra validator execution,
or NTFS access-control attestation. Expected digests must come from an independent
owner channel; this command only checks local byte equality.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from maestro_prep.coordinator import (  # noqa: E402
    ContractError, _verify_astra_manifest, check_lock, read_json_owner_pinned,
    vendor_module,
)
from tools.verify_package import verify  # noqa: E402

SHA = re.compile(r"[a-f0-9]{64}\Z")
NOT_RUN = [
    "LEONARDO_EXECUTION", "ASTRA_VALIDATOR_ON_APPROVED_NODE",
    "WINDOWS_NTFS_ACL_ATTESTATION", "INDEPENDENT_REVIEW", "LIVE_NODE_INSTALL",
    "OWNER_APPROVAL", "ROLLBACK_REHEARSAL",
]


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_path(path: Path, expect_dir: bool, max_bytes: int = 1024 * 1024) -> bool:
    """Conservative lstat path walk. Not a race-free openat/reparse defense."""
    try:
        p = Path(os.path.abspath(path))
        for n in (p, *p.parents):
            st = os.lstat(n)
            if stat.S_ISLNK(st.st_mode) or (
                getattr(st, "st_file_attributes", 0) &
                getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            ):
                return False
        st = os.lstat(p)
        return stat.S_ISDIR(st.st_mode) if expect_dir else (
            stat.S_ISREG(st.st_mode) and st.st_size <= max_bytes
        )
    except (OSError, ValueError):
        return False


def _safe_zip_member(name: str) -> bool:
    if not name or "\\" in name or "\x00" in name or name.endswith("/"):
        return False
    posix, win = PurePosixPath(name), PureWindowsPath(name)
    return (not posix.is_absolute() and not win.is_absolute() and
            not win.drive and not win.root and all(
                part not in ("", ".", "..") and not part.endswith((" ", ".")) and ":" not in part
                for part in name.split("/")
            ))


def _check_source(candidate_root: Path, candidate_zip: Path, expected_zip_sha: str) -> None:
    if not isinstance(expected_zip_sha, str) or not SHA.fullmatch(expected_zip_sha):
        raise ValueError("CANDIDATE_OWNER_ZIP_PIN_REQUIRED")
    if not _safe_path(candidate_root, True) or not _safe_path(candidate_zip, False, 8 * 1024 * 1024):
        raise ValueError("CANDIDATE_PATH_UNSAFE_OR_MISSING")
    if _digest(candidate_zip.read_bytes()) != expected_zip_sha:
        raise ValueError("CANDIDATE_ZIP_PIN_MISMATCH")
    verified = verify(candidate_root)
    listed = {entry["path"]: entry for entry in json.loads((candidate_root / "MANIFEST.json").read_text(encoding="utf-8"))["files"]}
    expected = set(listed) | {"MANIFEST.json", "SHA256SUMS.txt"}
    with zipfile.ZipFile(candidate_zip) as z:
        info = z.infolist()
        names = [item.filename for item in info]
        if len(names) != len(set(names)) or set(names) != expected or not all(_safe_zip_member(x) for x in names):
            raise ValueError("CANDIDATE_ZIP_INVENTORY_UNSAFE")
        for member in info:
            filetype = (member.external_attr >> 16) & 0o170000
            if filetype not in (0, stat.S_IFREG):
                raise ValueError("CANDIDATE_ZIP_NONREGULAR_ENTRY")
            if member.file_size > 1024 * 1024:
                raise ValueError("CANDIDATE_ZIP_MEMBER_TOO_LARGE")
            raw = z.read(member)
            if _digest(raw) != _digest((candidate_root / member.filename).read_bytes()):
                raise ValueError("CANDIDATE_ZIP_EXTRACTED_BYTES_DIFFER")
            if member.filename in listed and (
                len(raw) != listed[member.filename]["bytes"] or _digest(raw) != listed[member.filename]["sha256"]
            ):
                raise ValueError("CANDIDATE_ZIP_MANIFEST_MISMATCH")
        if z.testzip() is not None:
            raise ValueError("CANDIDATE_ZIP_CRC_INVALID")
    if verified.get("verified") is not True:
        raise ValueError("CANDIDATE_MANIFEST_FAILED")


def _check_astra(astra_root: Path, lock: dict) -> None:
    if not _safe_path(astra_root, True):
        raise ValueError("APPROVED_ASTRA_ROOT_UNSAFE_OR_MISSING")
    pins = lock["astra"].get("official_v71")
    if not isinstance(pins, dict):
        raise ValueError("APPROVED_ASTRA_V71_PINS_REQUIRED")
    files = _verify_astra_manifest(astra_root, pins["manifest_sha256"])
    required = {
        "SKILL.md": lock["astra"]["skill_sha256"],
        "scripts/validate_prework.py": pins["validator_sha256"],
        "schemas/prework-plan.schema.json": pins["schema_sha256"],
        "profiles/ai-maestro.md": pins["profile_sha256"],
    }
    if any(files.get(rel) != h for rel, h in required.items()):
        raise ValueError("ASTRA_MANIFEST_ENTRY_OWNER_PIN_MISMATCH")
    if not _safe_path(astra_root / "CANDIDATE_HASHES.json", False):
        raise ValueError("ASTRA_MANIFEST_PATH_UNSAFE")
    for rel in required:
        if not _safe_path(astra_root / rel, False):
            raise ValueError("ASTRA_ESSENTIAL_PATH_UNSAFE")


def _check_leonardo(router: Path, router_sha: str, policy: Path, lock: dict) -> None:
    if not isinstance(router_sha, str) or not SHA.fullmatch(router_sha):
        raise ValueError("LEONARDO_OWNER_ROUTER_PIN_REQUIRED")
    if not _safe_path(router, False, 8 * 1024 * 1024):
        raise ValueError("LEONARDO_ROUTER_PATH_UNSAFE_OR_MISSING")
    if not _safe_path(policy, False):
        raise ValueError("LEONARDO_POLICY_PATH_UNSAFE_OR_MISSING")
    if _digest(router.read_bytes()) != router_sha:
        raise ValueError("LEONARDO_ROUTER_PIN_MISMATCH")
    if _digest(policy.read_bytes()) != lock["leonardo"]["policy_sha256"]:
        raise ValueError("LEONARDO_POLICY_PIN_MISMATCH")


def run(*, source_root: Path, candidate_zip: Path, candidate_zip_sha256: str,
        lock_path: Path | None = None, lock_sha256: str | None = None,
        astra_root: Path | None = None, leonardo_router: Path | None = None,
        leonardo_router_sha256: str | None = None, leonardo_policy: Path | None = None,
        evidence_root: Path | None = None) -> dict:
    checks = {}
    def gate(name: str, fn):
        try:
            fn()
            checks[name] = {"status": "PASS", "scope": "LOCAL_BYTES_ONLY"}
        except (ContractError, OSError, KeyError, TypeError, ValueError, zipfile.BadZipFile) as exc:
            code = str(exc).split(":")[0] if isinstance(exc, (ContractError, ValueError)) else type(exc).__name__.upper()
            checks[name] = {"status": "HOLD", "code": code}

    gate("source_archive_and_extraction", lambda: _check_source(source_root, candidate_zip, candidate_zip_sha256))
    gate("o_prep_source_pin", lambda: vendor_module())
    lock = None
    if lock_path is not None and lock_sha256 is not None:
        try:
            lock = read_json_owner_pinned(lock_path, lock_sha256)
            check_lock(lock)
            checks["owner_lock_bytes"] = {"status": "PASS", "scope": "OWNER_DIGEST_BYTE_EQUALITY_ONLY"}
        except (ContractError, ValueError, OSError) as exc:
            checks["owner_lock_bytes"] = {"status": "HOLD", "code": str(exc).split(":")[0]}
    else:
        checks["owner_lock_bytes"] = {"status": "HOLD", "code": "OWNER_LOCK_REQUIRED"}
    if lock is not None and astra_root is not None:
        gate("approved_astra_full_manifest", lambda: _check_astra(astra_root, lock))
    else:
        checks["approved_astra_full_manifest"] = {"status": "HOLD", "code": "APPROVED_ASTRA_PIN_AND_ROOT_REQUIRED"}
    if lock is not None and leonardo_router is not None and leonardo_policy is not None:
        gate("leonardo_local_bytes", lambda: _check_leonardo(leonardo_router, leonardo_router_sha256, leonardo_policy, lock))
    else:
        checks["leonardo_local_bytes"] = {"status": "HOLD", "code": "LEONARDO_OWNER_PINS_AND_PATHS_REQUIRED"}
    if evidence_root is None:
        checks["evidence_root"] = {"status": "HOLD", "code": "LOCAL_EVIDENCE_ROOT_REQUIRED"}
    else:
        def check_evidence():
            if not _safe_path(evidence_root, True):
                raise ValueError("EVIDENCE_ROOT_UNSAFE_OR_MISSING")
            evidence = evidence_root.resolve()
            forbidden = [source_root, astra_root, leonardo_router, leonardo_policy, lock_path]
            for other in forbidden:
                if other is None:
                    continue
                other = Path(other).resolve()
                if other.is_dir() and (evidence == other or evidence.is_relative_to(other)):
                    raise ValueError("EVIDENCE_ROOT_COLOCATED_WITH_SOURCE_OR_PINS")
                # For evidence, avoid co-locating with a policy or binary file,
                # but allow a sibling directory elsewhere on an isolated volume.
                if other.is_file() and evidence == other.parent:
                    raise ValueError("EVIDENCE_ROOT_COLOCATED_WITH_SOURCE_OR_PINS")
        gate("evidence_root", check_evidence)

    ok = all(v["status"] == "PASS" for v in checks.values())
    return {
        "schema": "MAESTRO_LOCAL_NODE_BYTE_PREFLIGHT_V1",
        "status": "BYTES_VERIFIED_OWNER_PILOT_REVIEW_REQUIRED" if ok else "HOLD",
        "checks": checks,
        "not_run": NOT_RUN,
        "candidate_only": True, "finality": "non_final", "decision_authority": "none",
        "node_mutation_performed": False, "source_mirror_is_node_authority": False,
        "note": "No executor, no attestation, no deployment. Owner-provided hashes prove byte equality only.",
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root", required=True, type=Path)
    p.add_argument("--candidate-zip", required=True, type=Path)
    p.add_argument("--candidate-zip-sha256", required=True)
    p.add_argument("--owner-lock", type=Path)
    p.add_argument("--owner-lock-sha256")
    p.add_argument("--approved-astra-root", type=Path)
    p.add_argument("--leonardo-router", type=Path)
    p.add_argument("--leonardo-router-sha256")
    p.add_argument("--leonardo-policy", type=Path)
    p.add_argument("--evidence-root", type=Path)
    args = p.parse_args(argv)
    result = run(source_root=args.source_root, candidate_zip=args.candidate_zip,
                 candidate_zip_sha256=args.candidate_zip_sha256, lock_path=args.owner_lock,
                 lock_sha256=args.owner_lock_sha256, astra_root=args.approved_astra_root,
                 leonardo_router=args.leonardo_router,
                 leonardo_router_sha256=args.leonardo_router_sha256,
                 leonardo_policy=args.leonardo_policy, evidence_root=args.evidence_root)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "BYTES_VERIFIED_OWNER_PILOT_REVIEW_REQUIRED" else 2

if __name__ == "__main__":
    raise SystemExit(main())
