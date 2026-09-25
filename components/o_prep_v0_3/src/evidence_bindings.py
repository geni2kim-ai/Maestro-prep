"""Read-only local-byte binding for O-Prep, *not* proof of provenance or authority.

Receipt indices are treated as untrusted claims. This module compares actual local
file bytes and checks narrow cross-references without exposing raw bytes or paths.
No network access, database writes, shell execution or acceptance decisions.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat

HASH = re.compile(r"^[a-f0-9]{64}$")
ALLOWED_ROLES = frozenset({
    "router_input", "router_policy", "router_output", "review_subject",
    "review_receipt", "dedup_receipt", "ack_receipt", "acceptance_receipt",
})
MAX_INDEX_BYTES = 128 * 1024
MAX_ARTIFACT_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024


class BindingError(ValueError):
    """Safe-to-display, non-path-bearing error code."""


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BindingError("duplicate_receipt_index_json_key")
        result[key] = value
    return result


def _bad_constant(_):
    raise BindingError("nonfinite_receipt_index_number")


def _json(data: bytes, what: str) -> dict:
    try:
        value = json.loads(data, object_pairs_hook=_unique_pairs, parse_constant=_bad_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise BindingError(f"invalid_{what}_json") from exc
    if not isinstance(value, dict):
        raise BindingError(f"invalid_{what}_shape")
    return value


def _time(s: str) -> datetime:
    if not isinstance(s, str) or not (s.endswith("Z") or re.search(r"[+-]\d\d:\d\d$", s)):
        raise BindingError("unbound_receipt_timestamp")
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError("no timezone")
        return dt.astimezone(timezone.utc)
    except ValueError as exc:
        raise BindingError("unbound_receipt_timestamp") from exc


def _safe_local_file(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative or "\x00" in relative:
        raise BindingError("unsafe_receipt_path")
    p = PurePosixPath(relative)
    if p.is_absolute() or relative.startswith("./") or re.match(r"^[A-Za-z]:", relative):
        raise BindingError("unsafe_receipt_path")
    if any(x in {".", "..", ""} or x.endswith((" ", ".")) for x in relative.split("/")):
        raise BindingError("unsafe_receipt_path")
    candidate = root
    for segment in p.parts:
        candidate = candidate / segment
        try:
            mode = candidate.lstat().st_mode
        except OSError as exc:
            raise BindingError("receipt_file_missing") from exc
        if stat.S_ISLNK(mode):
            raise BindingError("receipt_symlink_forbidden")
    if not candidate.is_file() or not candidate.resolve().is_relative_to(root):
        raise BindingError("receipt_not_regular_file")
    return candidate


def _read_limited(p: Path, max_bytes: int) -> bytes:
    try:
        before = p.stat()
        if before.st_size > max_bytes:
            raise BindingError("receipt_size_limit_exceeded")
        with p.open("rb") as stream:
            # Guard concurrent replacement before and after; no privileged/trusted
            # provenance is inferred even when these checks pass.
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or (before.st_ino, before.st_dev) != (opened.st_ino, opened.st_dev):
                raise BindingError("receipt_changed_during_open")
            result = stream.read(max_bytes + 1)
            after = os.fstat(stream.fileno())
            if len(result) > max_bytes or (opened.st_size, opened.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise BindingError("receipt_changed_during_read")
            return result
    except (OSError, OverflowError) as exc:
        raise BindingError("receipt_file_unreadable") from exc


def _required_roles(signal: dict) -> set[str]:
    roles = {"router_input", "router_policy", "router_output"}
    if signal["stage"] in {"PUBLISH", "CLOSE"}:
        roles |= {"review_subject", "review_receipt"}
        if signal["delivery"]["required"]:
            roles.add("dedup_receipt")
            if signal["stage"] == "CLOSE" and signal["delivery"]["disposition"] == "ACCEPTED":
                roles.add("acceptance_receipt")
        if signal["stage"] == "CLOSE" and signal["delivery"]["ack_required"]:
            roles.add("ack_receipt")
    return roles


def verify_local_bindings(index_path: str, evidence_root: str, signal: dict) -> dict:
    """Return only presence/hash/cross-reference facts, never raw content or paths.

    `LOCAL_BYTES_VERIFIED_ONLY` is *not* validation of Leonardo's status, a reviewer's
    independence, DB durability, receipt signer, remote ACK or host authorization.
    """
    root = Path(evidence_root).absolute()
    if not root.is_dir() or root.is_symlink():
        raise BindingError("invalid_evidence_root")
    # Avoid a symlink anywhere in an explicitly supplied root.
    current = root
    while current != current.parent:
        if current.is_symlink():
            raise BindingError("symlink_evidence_root_forbidden")
        current = current.parent
    index = Path(index_path).absolute()
    try:
        relative_index = index.relative_to(root).as_posix()
    except ValueError as exc:
        raise BindingError("receipt_index_outside_evidence_root") from exc
    if not relative_index.endswith(".json"):
        raise BindingError("receipt_index_must_be_json")
    data = _read_limited(_safe_local_file(root, relative_index), MAX_INDEX_BYTES)
    idx = _json(data, "receipt_index")
    if set(idx) != {"schema", "work_unit", "node_id", "stage", "captured_at_utc", "receipts"} or idx["schema"] != "O_PREP_RECEIPT_INDEX_V1":
        raise BindingError("receipt_index_contract_invalid")
    if (idx["work_unit"], idx["node_id"], idx["stage"]) != (signal["work_unit"], signal["node_id"], signal["stage"]):
        raise BindingError("receipt_index_work_binding_mismatch")
    if _time(idx["captured_at_utc"]) != _time(signal["captured_at_utc"]):
        raise BindingError("receipt_index_snapshot_mismatch")
    rows = idx["receipts"]
    if not isinstance(rows, list) or len(rows) > 16:
        raise BindingError("receipt_index_entries_invalid")
    seen_roles: set[str] = set()
    seen_paths: set[str] = set()
    checked: dict[str, bytes] = {}
    issues = []
    total = 0
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"role", "path", "sha256", "size_bytes"}:
            raise BindingError("receipt_index_entry_shape_invalid")
        role, rel, digest, size = (row[k] for k in ("role", "path", "sha256", "size_bytes"))
        if not isinstance(role, str) or role not in ALLOWED_ROLES or role in seen_roles:
            raise BindingError("duplicate_or_invalid_receipt_role")
        if not isinstance(rel, str) or rel.casefold() in seen_paths:
            raise BindingError("duplicate_or_invalid_receipt_path")
        if not isinstance(digest, str) or not HASH.fullmatch(digest):
            raise BindingError("receipt_hash_format_invalid")
        if type(size) is not int or size < 0 or size > MAX_ARTIFACT_BYTES:
            raise BindingError("receipt_declared_size_invalid")
        total += size
        if total > MAX_TOTAL_BYTES:
            raise BindingError("receipt_total_size_exceeded")
        seen_roles.add(role)
        seen_paths.add(rel.casefold())
        payload = _read_limited(_safe_local_file(root, rel), MAX_ARTIFACT_BYTES)
        if len(payload) != size or hashlib.sha256(payload).hexdigest() != digest:
            issues.append({"code": f"RECEIPT_BYTES_MISMATCH_{role.upper()}", "state": "HOLD_SOURCE"})
            continue
        checked[role] = payload

    missing = sorted(_required_roles(signal) - set(checked))
    for role in missing:
        issues.append({"code": f"BOUND_RECEIPT_MISSING_{role.upper()}", "state": "HOLD_SOURCE"})

    def mismatch(code: str) -> None:
        issues.append({"code": code, "state": "HOLD_EVIDENCE"})

    if "review_receipt" in checked and "review_subject" in checked:
        receipt = _json(checked["review_receipt"], "review_receipt")
        expected = {
            "work_unit": signal["work_unit"],
            "reviewed_sha256": hashlib.sha256(checked["review_subject"]).hexdigest(),
            "review_status": signal["review"]["status"],
            "review_evidence_class": signal["review"]["evidence_class"],
        }
        if any(receipt.get(k) != v for k, v in expected.items()):
            mismatch("REVIEW_RECEIPT_BINDING_MISMATCH")
    if "dedup_receipt" in checked and signal["delivery"]["required"]:
        receipt = _json(checked["dedup_receipt"], "dedup_receipt")
        if (receipt.get("work_unit") != signal["work_unit"] or receipt.get("idempotency_key") != signal["delivery"]["idempotency_key"]
            or type(receipt.get("record_count")) is not int or receipt.get("record_count") != 1
            or receipt.get("evidence_scope") != "HOST_DB_READBACK_PRODUCER_REPORTED"):
            mismatch("DEDUP_RECEIPT_BINDING_MISMATCH")
    if "ack_receipt" in checked and signal["delivery"]["ack_required"]:
        receipt = _json(checked["ack_receipt"], "ack_receipt")
        if (receipt.get("work_unit") != signal["work_unit"] or receipt.get("idempotency_key") != signal["delivery"]["idempotency_key"]
            or receipt.get("state") != "ACKED"):
            mismatch("ACK_RECEIPT_BINDING_MISMATCH")
    if "acceptance_receipt" in checked and signal["delivery"]["required"]:
        receipt = _json(checked["acceptance_receipt"], "acceptance_receipt")
        if (receipt.get("work_unit") != signal["work_unit"] or receipt.get("idempotency_key") != signal["delivery"]["idempotency_key"]
            or receipt.get("disposition") != signal["delivery"]["disposition"] or not isinstance(receipt.get("decision_ref"), str)
            or not receipt.get("decision_ref", "").strip()):
            mismatch("ACCEPTANCE_RECEIPT_BINDING_MISMATCH")

    return {
        "status": "LOCAL_BYTES_VERIFIED_ONLY" if not issues else "INCOMPLETE_OR_MISMATCH",
        "checked_roles": sorted(checked), "missing_roles": missing,
        "artifact_count": len(checked),
        "provenance_limit": "BYTES_ONLY_NO_AUTHORITY_ASSERTED",
        "issues": issues,
    }
