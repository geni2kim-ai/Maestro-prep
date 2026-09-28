#!/usr/bin/env python3
"""Owner-only external reference candidate conformance *gate*, never reviewer authority.

Source bytes, schemas, contract and harness must exist on an OWNER-PROVISIONED,
isolated local runner. No network fetch, auto-install, pin inference or mutation
of approved source is performed by this gate.
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
import zipfile
from pathlib import Path

CHECKOUT = Path(__file__).resolve().parents[2]
FILENAMES = {
    "reference_archive": "reference_archive.zip",
    "profile": "profile.json",
    "schema": "schema.json",
    "validator": "validator.py",
    "skill_contract": "SKILL.md",
    "bundle_manifest": "bundle_manifest.json",
}
PIN_KEYS = {
    "schema", "owner_approval_id", "approval_scope",
    "maestro_source_commit", "reference_files", "trusted_harness_sha256",
}
SHA = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")

class GateError(ValueError):
    pass

def strict_json(path: Path, limit: int = 8 * 1024 * 1024) -> dict:
    """Read bounded UTF-8 JSON, rejecting duplicate keys and non-finite values."""
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise GateError("JSON_SIZE_LIMIT")
    def no_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise GateError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    def no_constant(_value):
        raise GateError("NONFINITE_JSON_VALUE")
    return json.loads(data.decode("utf-8"), object_pairs_hook=no_duplicates,
                      parse_constant=no_constant)

def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def valid_sha(value: object) -> bool:
    return isinstance(value, str) and SHA.fullmatch(value) is not None and value != "0" * 64

def ordinary_private_file(path: Path, root: Path) -> Path:
    if path.is_symlink() or not path.is_file():
        raise GateError("PINNED_FILE_MISSING_OR_LINK")
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise GateError("PINNED_FILE_OUTSIDE_ROOT")
    return resolved

def check_archive(archive: Path, manifest_file: Path) -> int:
    manifest = strict_json(manifest_file, limit=256 * 1024)
    if not isinstance(manifest, dict) or set(manifest) != {"schema", "files"} or manifest["schema"] != "OWNER_APPROVED_REFERENCE_BUNDLE_V1":
        raise GateError("REFERENCE_BUNDLE_MANIFEST_INVALID")
    files = manifest["files"]
    if not isinstance(files, list) or not 1 <= len(files) <= 512:
        raise GateError("REFERENCE_FILE_COUNT_INVALID")
    expected = {}
    for row in files:
        if not isinstance(row, dict) or set(row) != {"path", "bytes", "sha256"}:
            raise GateError("REFERENCE_ENTRY_INVALID")
        path, size, digest = row["path"], row["bytes"], row["sha256"]
        if (not isinstance(path, str) or not path or path.startswith("/")
                or "\\" in path or any(x in {"", ".", ".."} for x in path.split("/"))
                or path in expected or type(size) is not int or not 0 <= size <= 32 * 1024 * 1024
                or not valid_sha(digest)):
            raise GateError("REFERENCE_ENTRY_UNSAFE")
        expected[path] = row
    if sum(x["bytes"] for x in files) > 256 * 1024 * 1024:
        raise GateError("REFERENCE_ARCHIVE_TOO_LARGE")
    if archive.stat().st_size > 512 * 1024 * 1024:
        raise GateError("REFERENCE_ARCHIVE_COMPRESSED_LIMIT")
    with zipfile.ZipFile(archive) as zf:
        info = zf.infolist()
        if len(info) != len(expected) or sorted(x.filename for x in info) != sorted(expected):
            raise GateError("REFERENCE_ARCHIVE_MEMBER_MISMATCH")
        for member in info:
            filetype = stat.S_IFMT(member.external_attr >> 16)
            if (member.is_dir() or filetype not in {0, stat.S_IFREG}
                    or member.file_size != expected[member.filename]["bytes"]
                    or member.flag_bits & 1):
                raise GateError("REFERENCE_ARCHIVE_UNSAFE")
            h = hashlib.sha256()
            with zf.open(member, "r") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    h.update(block)
            if h.hexdigest() != expected[member.filename]["sha256"]:
                raise GateError("REFERENCE_ARCHIVE_BYTES_MISMATCH")
    return len(expected)

def verify_pins(pin_path: Path, source_root: Path, harness: Path, commit: str) -> dict:
    if not COMMIT.fullmatch(commit):
        raise GateError("INVALID_SOURCE_COMMIT")
    root = source_root.resolve(strict=True)
    if root.is_relative_to(CHECKOUT) or CHECKOUT.is_relative_to(root):
        raise GateError("REFERENCE_ROOT_MUST_BE_EXTERNAL")
    if pin_path.is_symlink() or not pin_path.is_file() or pin_path.resolve().is_relative_to(CHECKOUT):
        raise GateError("PIN_FILE_MUST_BE_OWNER_CONTROLLED")
    pin = strict_json(pin_path, limit=128 * 1024)
    if not isinstance(pin, dict) or set(pin) != PIN_KEYS or pin["schema"] != "MAESTRO_EXTERNAL_REFERENCE_PIN_V1":
        raise GateError("PIN_CONTRACT_INVALID")
    if (pin["approval_scope"] != "OFFLINE_REFERENCE_CONFORMANCE_ONLY"
            or not isinstance(pin["owner_approval_id"], str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", pin["owner_approval_id"])
            or pin["owner_approval_id"] == "OWNER_APPROVAL_REQUIRED"):
        raise GateError("OWNER_APPROVAL_NOT_SUPPLIED")
    if pin["maestro_source_commit"] != commit:
        raise GateError("CHECKOUT_COMMIT_NOT_OWNER_PINNED")
    entries = pin["reference_files"]
    if not isinstance(entries, dict) or set(entries) != set(FILENAMES):
        raise GateError("REFERENCE_PINS_INCOMPLETE")
    paths = {}
    for role, name in FILENAMES.items():
        entry = entries[role]
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256"} or entry["path"] != name or not valid_sha(entry["sha256"]):
            raise GateError("REFERENCE_PIN_INVALID")
        path = ordinary_private_file(root / name, root)
        if digest_file(path) != entry["sha256"]:
            raise GateError("REFERENCE_HASH_MISMATCH")
        paths[role] = path
    if (not valid_sha(pin["trusted_harness_sha256"]) or harness.is_symlink()
            or not harness.is_file() or harness.resolve().is_relative_to(CHECKOUT)
            or harness.resolve().is_relative_to(root)
            or digest_file(harness) != pin["trusted_harness_sha256"]):
        raise GateError("HARNESS_NOT_SEPARATELY_PINNED")
    for role in ("profile", "schema", "bundle_manifest"):
        parsed = strict_json(paths[role])
        if not isinstance(parsed, dict):
            raise GateError("INVALID_REFERENCE_JSON")
    members = check_archive(paths["reference_archive"], paths["bundle_manifest"])
    return {
        "schema": "MAESTRO_EXTERNAL_REFERENCE_GATE_V1",
        "gate": "PINNED_OWNER_BYTES_VALIDATED",
        "source_commit": commit,
        "reference_archive_sha256": entries["reference_archive"]["sha256"],
        "pin_sha256": digest_file(pin_path),
        "reference_members": members,
        "candidate_only": True,
        "actual_conformance": "NOT_RUN",
        "independent_review": "NOT_RUN",
        "deployment_authorized": False,
    }

def run_owner_harness(pin_path: Path, root: Path, harness: Path, commit: str, output: Path) -> dict:
    gate = verify_pins(pin_path, root, harness, commit)
    target = output.resolve()
    if (target.exists() or target.is_relative_to(CHECKOUT)
            or target.is_relative_to(root.resolve(strict=True))):
        raise GateError("RECEIPT_OUTPUT_NOT_ISOLATED")
    target.parent.mkdir(parents=True, exist_ok=True)
    raw_receipt = target.with_name(target.name + ".owner-tmp")
    if raw_receipt.exists():
        raise GateError("RECEIPT_OUTPUT_ALREADY_EXISTS")
    # The separately approved harness owns *semantic* checks and negative tests.
    # A distinct independent review is still required; harness stdout is not published.
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        call = subprocess.run(
            [sys.executable, "-I", str(harness.resolve()), "--reference-root", str(root.resolve()),
             "--pin", str(pin_path.resolve()), "--receipt-output", str(raw_receipt)],
            cwd=str(harness.resolve().parent), env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120, check=False)
        if call.returncode != 0 or not raw_receipt.is_file() or raw_receipt.is_symlink():
            raise GateError("OWNER_HARNESS_FAILED")
        # Exact owner-approved inputs must remain pinned after the separate
        # harness returns; this is not a claim of immutable host custody.
        post = verify_pins(pin_path, root, harness, commit)
        if (post["pin_sha256"] != gate["pin_sha256"]
                or post["reference_archive_sha256"] != gate["reference_archive_sha256"]):
            raise GateError("APPROVED_INPUTS_CHANGED_DURING_RUN")
        result = strict_json(raw_receipt, limit=32 * 1024)
        counts = result.get("cases") if isinstance(result, dict) else None
        if (not isinstance(result, dict)
                or set(result) != {"schema", "status", "source_commit", "pin_sha256",
                                   "reference_archive_sha256", "cases", "scope", "authority"}
                or result["schema"] != "MAESTRO_OWNER_HARNESS_RECEIPT_V1"
                or result["status"] != "PASS" or result["source_commit"] != commit
                or result["pin_sha256"] != gate["pin_sha256"]
                or result["reference_archive_sha256"] != gate["reference_archive_sha256"]
                or result["scope"] != "OFFLINE_APPROVED_REFERENCE_ONLY"
                or result["authority"] != "none"
                or not isinstance(counts, dict)
                or set(counts) != {"positive", "negative", "failed", "skipped"}
                or any(type(x) is not int for x in counts.values())
                or counts["positive"] < 1 or counts["negative"] < 2
                or counts["failed"] != 0 or counts["skipped"] != 0):
            raise GateError("OWNER_HARNESS_RECEIPT_INVALID")
        gate.update(actual_conformance="OWNER_HARNESS_REPORTED_PASS",
                    positive_cases=counts["positive"], negative_cases=counts["negative"])
        with target.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(json.dumps(gate, indent=2, sort_keys=True) + "\n")
        return gate
    finally:
        raw_receipt.unlink(missing_ok=True)

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pin", required=True, type=Path)
    p.add_argument("--reference-root", required=True, type=Path)
    p.add_argument("--harness", required=True, type=Path)
    p.add_argument("--expected-commit", required=True)
    p.add_argument("--receipt-output", type=Path)
    p.add_argument("--mode", choices=("validate-only", "owner-run"), default="validate-only")
    a = p.parse_args()
    try:
        if a.mode == "owner-run":
            if a.receipt_output is None:
                raise GateError("RECEIPT_OUTPUT_REQUIRED")
            result = run_owner_harness(a.pin, a.reference_root, a.harness, a.expected_commit, a.receipt_output)
        else:
            result = verify_pins(a.pin, a.reference_root, a.harness, a.expected_commit)
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (ValueError, KeyError, OSError, TimeoutError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        print(json.dumps({"schema": "MAESTRO_EXTERNAL_REFERENCE_GATE_V1",
                          "status": "BLOCKED", "code": type(exc).__name__,
                          "actual_conformance": "NOT_RUN"}))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
