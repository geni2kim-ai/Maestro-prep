#!/usr/bin/env python3
"""Build byte-reproducible owner-gated *candidate* ZIP, never authenticity proof."""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.verify_package import verify

VERSION = "0.1.0-public-redacted-hotfix"
ZIP_NAME = "maestro-prep-" + VERSION + ".zip"
FIXED_TIME = (1980, 1, 1, 0, 0, 0)

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def build(root: Path, dest: Path) -> dict:
    root = root.resolve(strict=True)
    dest = dest.resolve()
    if dest == root or root in dest.parents or dest in root.parents:
        raise ValueError("OUTPUT_MUST_BE_SEPARATE_FROM_CHECKOUT")
    receipt = verify(root)
    if receipt["verified"] is not True or receipt["files"] != 40:
        raise ValueError("EXPECTED_40_FILES")
    manifest = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
    if manifest["version"] != VERSION or manifest["file_count"] != 40:
        raise ValueError("UNEXPECTED_PROFILE")
    expected = {f["path"]: f for f in manifest["files"]}
    names = sorted([*expected, "MANIFEST.json", "SHA256SUMS.txt"])
    if any(name.startswith("/") or ".." in Path(name).parts or "\\" in name for name in names):
        raise ValueError("UNSAFE_MEMBER_NAME")
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest / ZIP_NAME
    sums = dest / "SHA256SUMS.txt"
    archive_sum = dest / (ZIP_NAME + ".sha256")
    if any(x.exists() or x.is_symlink() for x in (archive, sums, archive_sum)):
        raise FileExistsError("REFUSE_OVERWRITE")
    with zipfile.ZipFile(archive, mode="x", compression=zipfile.ZIP_STORED, allowZip64=False) as zf:
        for name in names:
            data = (root / name).read_bytes()
            if name in expected:
                entry = expected[name]
                if len(data) != entry["bytes"] or digest(data) != entry["sha256"]:
                    raise ValueError("SOURCE_CHANGED_DURING_ASSEMBLY")
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            zf.writestr(info, data)
    with zipfile.ZipFile(archive, mode="r") as zf:
        if zf.namelist() != names:
            raise ValueError("ARCHIVE_MEMBER_SET_MISMATCH")
        for name in names:
            if zf.read(name) != (root / name).read_bytes():
                raise ValueError("ARCHIVE_BYTE_MISMATCH")
    archive_sha = digest(archive.read_bytes())
    sums.write_bytes((root / "SHA256SUMS.txt").read_bytes())
    archive_sum.write_text(archive_sha + "  " + ZIP_NAME + "\n", encoding="utf-8", newline="\n")
    return {"schema": "MAESTRO_CANDIDATE_RELEASE_ASSEMBLY_V1",
            "archive": ZIP_NAME, "archive_sha256": archive_sha,
            "payload_files": 40, "archive_entries": 42, "candidate_only": True,
            "owner_out_of_band_digest_comparison": "NOT_RUN",
            "independent_archive_authenticity": "NOT_VERIFIED",
            "deployment_authorized": False}

def verify_candidate_archive(root: Path, archive: Path, expected_sha256: str) -> dict:
    """Inspect downloaded ZIP without extraction, using a separately supplied digest.

    This tool cannot establish whether the supplied digest arrived through an
    independent channel; the owner must retain evidence of that comparison.
    """
    import re
    import stat
    if not isinstance(expected_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None:
        raise ValueError("OWNER_DIGEST_REQUIRED")
    root = root.resolve(strict=True)
    archive = archive.resolve(strict=True)
    if not archive.is_file() or not archive.name.endswith(".zip"):
        raise ValueError("CANDIDATE_ZIP_REQUIRED")
    if verify(root)["files"] != 40:
        raise ValueError("EXPECTED_40_FILES")
    manifest = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
    expected = {f["path"]: f for f in manifest["files"]}
    expected_bytes = sum(f["bytes"] for f in manifest["files"])
    meta = ("MANIFEST.json", "SHA256SUMS.txt")
    expected_bytes += sum((root / name).stat().st_size for name in meta)
    names = sorted([*expected, *meta])
    if len(names) != 42 or len(set(names)) != 42:
        raise ValueError("ARCHIVE_MEMBER_COUNT_INVALID")
    if archive.stat().st_size > expected_bytes + 1024 * 1024:
        raise ValueError("CANDIDATE_ZIP_SIZE_LIMIT")
    archive_hash = digest(archive.read_bytes())
    if archive_hash != expected_sha256:
        raise ValueError("OWNER_DIGEST_MISMATCH")
    with zipfile.ZipFile(archive, mode="r") as zf:
        info = zf.infolist()
        if len(info) != 42 or [i.filename for i in info] != names:
            raise ValueError("ARCHIVE_MEMBER_SET_MISMATCH")
        for entry in info:
            if (entry.is_dir() or entry.flag_bits & 1 or entry.compress_type != zipfile.ZIP_STORED
                    or entry.date_time != FIXED_TIME or entry.create_system != 3
                    or entry.external_attr != 0o100644 << 16
                    or stat.S_IFMT(entry.external_attr >> 16) != stat.S_IFREG):
                raise ValueError("ARCHIVE_MEMBER_METADATA_INVALID")
            original = (root / entry.filename).read_bytes()
            if entry.file_size != len(original) or zf.read(entry) != original:
                raise ValueError("ARCHIVE_MEMBER_BYTES_MISMATCH")
            if entry.filename in expected:
                pinned = expected[entry.filename]
                if len(original) != pinned["bytes"] or digest(original) != pinned["sha256"]:
                    raise ValueError("ARCHIVE_CHECKOUT_PIN_MISMATCH")
    return {
        "schema": "MAESTRO_CANDIDATE_ZIP_LOCAL_VERIFICATION_V1",
        "source": "CURRENT_CHECKOUT_AND_SUPPLIED_DIGEST",
        "archive_sha256": archive_hash,
        "payload_files": 40,
        "archive_entries": 42,
        "local_byte_integrity": "PASS",
        "digest_channel_independence": "NOT_VERIFIED",
        "independent_archive_authenticity": "NOT_VERIFIED_BY_THIS_TOOL",
        "deployment_authorized": False,
    }

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--output-dir", type=Path)
    choice.add_argument("--verify-archive", type=Path)
    parser.add_argument("--expected-sha256", help="Digest separately supplied by owner; origin is not attested here")
    args = parser.parse_args()
    try:
        if args.verify_archive is not None:
            if not args.expected_sha256:
                raise ValueError("OWNER_DIGEST_REQUIRED")
            result = verify_candidate_archive(ROOT, args.verify_archive, args.expected_sha256)
        else:
            if args.expected_sha256 is not None:
                raise ValueError("DIGEST_ONLY_FOR_VERIFICATION")
            result = build(ROOT, args.output_dir)
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "FAIL", "error_type": type(exc).__name__}))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
