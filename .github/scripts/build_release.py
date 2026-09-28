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

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(build(ROOT, args.output_dir), sort_keys=True, indent=2))
        return 0
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "FAIL", "error_type": type(exc).__name__}))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
