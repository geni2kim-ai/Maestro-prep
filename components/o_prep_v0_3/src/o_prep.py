#!/usr/bin/env python3
"""O-Prep v0.3 candidate: offline evidence audit and non-authoritative node gate replay.

Zero remote calls, zero node mutations, no Leonardo emulation or authorization.
Imported or CLI-run locally against explicitly supplied evidence only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import zipfile
from datetime import datetime, timezone
from typing import Any
from evidence_bindings import verify_local_bindings, BindingError

VERSION = "0.3.0-prep"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MAX_ZIP_MEMBERS = 128
MAX_UNCOMPRESSED = 25 * 1024 * 1024
MAX_MEMBER_BYTES = 10 * 1024 * 1024
ALLOWED_STAGES = ("PLAN", "EXECUTE", "PUBLISH", "CLOSE")
PRIORITY = [
    "STOP_DISCLOSURE", "STOP_ROUTER_WRITE", "STOP_MUTATION", "HOLD_SOURCE",
    "HOLD_EVIDENCE", "HOLD_ROUTING", "HOLD_REVIEW", "REWORK", "HOLD_DELIVERY",
    "PROVISIONAL", "ADVANCE_CANDIDATE",
]


class OPrepError(ValueError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_json(payload: bytes, label: str) -> Any:
    def no_duplicates(pairs):
        d = {}
        for key, value in pairs:
            if key in d:
                raise OPrepError(f"duplicate_json_key:{label}")
            d[key] = value
        return d
    def no_constants(_):
        raise OPrepError(f"nonfinite_json_number:{label}")
    try:
        return json.loads(payload, object_pairs_hook=no_duplicates, parse_constant=no_constants)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise OPrepError(f"invalid_json:{label}:{type(exc).__name__}") from exc


def _utc(value: str) -> datetime:
    if not isinstance(value, str) or not (value.endswith("Z") or re.search(r"[+-]\d\d:\d\d$", value)):
        raise OPrepError("timestamp_requires_timezone")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError("naive time")
        return dt.astimezone(timezone.utc)
    except ValueError as exc:
        raise OPrepError("invalid_timestamp") from exc


def _is_safe_member(info: zipfile.ZipInfo) -> bool:
    name = info.filename
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        return False
    path = PurePosixPath(name)
    if path.is_absolute() or name.startswith(("/", "./")) or any(p in {"..", "."} for p in name.split("/")):
        return False
    if re.match(r"^[a-zA-Z]:", name):
        return False
    mode = (info.external_attr >> 16) & 0xFFFF
    if stat.S_IFMT(mode) == stat.S_IFLNK:
        return False
    return True


def audit_transport_bundle(zip_path: str, peer_audit_path: str | None = None) -> dict:
    """Audit transported SUBJECT evidence bytes. Report local evidence discrepancies only.

    No original SUBJECT router, host SQLite DB, or raw runner is present in this bundle;
    the reported router/test/host assertions remain PRODUCER_REPORTED.
    """
    path = Path(zip_path)
    if not path.is_file():
        raise OPrepError("evidence_file_missing")
    if path.stat().st_size > MAX_UNCOMPRESSED:
        raise OPrepError("zip_file_too_large")
    archive_hash = _sha256(path.read_bytes())
    with zipfile.ZipFile(path) as z:
        members = z.infolist()
        if len(members) > MAX_ZIP_MEMBERS or len(members) < 2:
            raise OPrepError("archive_member_count_invalid")
        if any(not _is_safe_member(m) for m in members):
            raise OPrepError("unsafe_archive_member")
        names = [m.filename for m in members]
        if len(names) != len(set(n.casefold() for n in names)):
            raise OPrepError("duplicate_archive_member")
        if sum(m.file_size for m in members) > MAX_UNCOMPRESSED or any(m.file_size > MAX_MEMBER_BYTES for m in members):
            raise OPrepError("archive_expansion_limit")
        if "manifest.json" not in names:
            raise OPrepError("manifest_missing")
        content = {}
        try:
            for m in members:
                if m.is_dir():
                    raise OPrepError("unexpected_archive_directory")
                content[m.filename] = z.read(m)
        except (zipfile.BadZipFile, RuntimeError, EOFError) as exc:
            raise OPrepError("archive_crc_or_read_failure") from exc

    manifest = _read_json(content["manifest.json"], "manifest")
    if not isinstance(manifest, dict) or not isinstance(manifest.get("entries"), list):
        raise OPrepError("manifest_shape_invalid")
    entries = manifest["entries"]
    if (len(entries) + 1 != len(content) or manifest.get("total_entries") != len(content)):
        raise OPrepError("manifest_entry_count_mismatch")
    listed = set()
    for item in entries:
        if not isinstance(item, dict) or not isinstance(item.get("relative_path"), str):
            raise OPrepError("manifest_entry_shape_invalid")
        name = item["relative_path"]
        if name in listed or name not in content or name == "manifest.json":
            raise OPrepError("manifest_path_mismatch")
        listed.add(name)
        if not isinstance(item.get("size_bytes"), int) or isinstance(item["size_bytes"], bool):
            raise OPrepError("manifest_size_invalid")
        if item["size_bytes"] != len(content[name]) or item.get("sha256") != _sha256(content[name]):
            raise OPrepError("manifest_byte_hash_mismatch")
    if listed != set(content) - {"manifest.json"}:
        raise OPrepError("manifest_unlisted_content")
    required = {
        "node_snapshot.json", "router_policy_manifest.json", "episodes.json",
        "branch_probes.json", "packet_reconciliation.json", "test_receipts.json",
        "open_gates.json", "evidence_ledger.json", "handoff.md",
    }
    if required - set(content):
        raise OPrepError("required_evidence_missing")
    snapshot = _read_json(content["node_snapshot.json"], "node_snapshot")
    router = _read_json(content["router_policy_manifest.json"], "router_policy_manifest")
    ledger = _read_json(content["packet_reconciliation.json"], "packet_reconciliation")
    receipts = _read_json(content["test_receipts.json"], "test_receipts")
    gates = _read_json(content["open_gates.json"], "open_gates")
    branch_probes = _read_json(content["branch_probes.json"], "branch_probes")
    episodes = _read_json(content["episodes.json"], "episodes")
    evidence_ledger = _read_json(content["evidence_ledger.json"], "evidence_ledger")
    if any(not isinstance(item, list) for item in (branch_probes, episodes)) or not isinstance(ledger, dict):
        raise OPrepError("evidence_shape_invalid")

    findings: list[dict] = []
    def flag(code: str, severity: str, detail: str) -> None:
        findings.append({"code": code, "severity": severity, "detail": detail})

    rows_a = ledger.get("peer_packet_ledger", [])
    rows_b = ledger.get("secondary_packet_ledger", [])
    if not isinstance(rows_a, list) or not isinstance(rows_b, list):
        raise OPrepError("packet_ledger_shape_invalid")
    rows = rows_a + rows_b
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("delivery_id"), str) or not row["delivery_id"].strip():
            raise OPrepError("invalid_delivery_row_identity")
        if not isinstance(row.get("sender_node_id"), str) or not isinstance(row.get("receiver_node_id"), str):
            raise OPrepError("invalid_delivery_row_nodes")
        if (row["sender_node_id"] == "SUBJECT") == (row["receiver_node_id"] == "SUBJECT"):
            raise OPrepError("invalid_subject_ledger_direction")
    ids = [row.get("delivery_id") for row in rows]
    if len(ids) != len(set(ids)):
        flag("DUPLICATE_DELIVERY_ID", "hold_evidence", "Repeated delivery identity in supplied ledger")
    sent = sum(row.get("sender_node_id") == "SUBJECT" for row in rows)
    received = sum(row.get("receiver_node_id") == "SUBJECT" for row in rows)
    observed_lifetime = {"sent": sent, "received": received, "deliveries": len(rows)}
    reported = snapshot["packet_metrics_lifetime"]
    if ((sent, received, len(rows)) !=
       (reported["packets_sent_by_subject"], reported["packets_received_by_subject"], reported["packet_deliveries_involving_subject"])):
        flag("LIFETIME_METRIC_MISMATCH", "hold_evidence", "Reported totals differ from supplied ledger")

    window = snapshot["packet_metrics_72h_window"]
    start = _utc(window["window_start_utc"])
    end = _utc(window["window_end_utc"])
    if end <= start:
        raise OPrepError("invalid_window_bounds")
    counted: list[dict] = []
    for row in rows:
        try:
            created = _utc(row["created_at"])
        except (KeyError, OPrepError):
            flag("LEDGER_TIMESTAMP_INVALID", "hold_evidence", "Packet row lacks parseable offset-aware time")
            continue
        if start <= created <= end:
            counted.append(row)
    window_observed = {
        "sent": sum(row.get("sender_node_id") == "SUBJECT" for row in counted),
        "received": sum(row.get("receiver_node_id") == "SUBJECT" for row in counted),
        "total": len(counted),
    }
    if (window_observed["sent"], window_observed["received"], window_observed["total"]) != (
       window["packets_sent_by_subject"], window["packets_received_by_subject"], window["total_packets_in_window"]):
        flag("WINDOW_LEDGER_MISMATCH", "hold_evidence",
             "Reported window totals differ from raw recorded timestamps; historically malformed timestamps are not silently corrected")

    test_baseline = snapshot["regression_test_baseline"]
    count_ok = (test_baseline["passed"] + test_baseline["skipped"] +
                test_baseline["failures"] + test_baseline["errors"] == test_baseline["total_tests"])
    if not count_ok:
        flag("TEST_COUNT_INCONSISTENT", "hold_evidence", "Reported test arithmetic inconsistent")
    test_suites = receipts["test_suites"]
    if not any(s.get("total_tests") == test_baseline["total_tests"] for s in test_suites):
        flag("MISSING_CANONICAL_RECEIPT", "hold_evidence", "Canonical reported test count lacks matching suite summary")
    # A delivered receipt is a producer assertion, not a raw runner transcript.
    flag("RAW_HOST_VALIDATION_NOT_TRANSPORTED", "info", "Unit-test and router pass counts are SUBJECT reported; host executable and runner output not transported")
    flag("DEDUP_RECORD_NOT_PROVEN", "hold_closeout", "Envelope idempotency fields do not prove canonical dedup-table persistence; F3 remains unresolved")
    if snapshot.get("queue_status_disk", {}).get("incoming", {}).get("count", 0) > 0:
        flag("INCOMING_NOT_EQ_PROCESSED", "info", "Zero pending does not establish that every incoming item is substantively processed")

    if peer_audit_path:
        peer = _read_json(Path(peer_audit_path).read_bytes(), "peer_archive_audit")
        prior = peer["peer"]["observed_snapshot"]
        if peer.get('explicit_reversed_direction_proven') is True and isinstance(prior,dict):
            flag('PEER_DIRECTION_REVERSED','hold_evidence','Independent peer evidence reports a direction reversal')

    return {
        "schema": "O_PREP_AUDIT_V1", "o_prep_version": VERSION,
        "archive_sha256": archive_hash,
        "manifest_verified": True,
        "manifest_entry_count_excluding_self": len(entries),
        "zip_entry_count_including_manifest": len(content),
        "source_provenance": "SUBJECT_TRANSPORTED_EVIDENCE_ONLY",
        "router_status": "NOT_RUN", "host_runtime_status": "NOT_RUN",
        "reported_router_version": router.get("installed_router", {}).get("package_version"),
        "reported_test_total": test_baseline.get("total_tests"),
        "episode_count": len(episodes), "branch_probe_count": len(branch_probes),
        "evidence_claim_count": len(evidence_ledger.get("claims", [])),
        "open_gate_statuses": [g.get("status") for g in gates.get("gates", [])],
        "observed_from_transported_ledger": {
            "lifetime": observed_lifetime, "reported_window": {
                "sent": window["packets_sent_by_subject"], "received": window["packets_received_by_subject"],
                "total": window["total_packets_in_window"]},
            "window_using_literal_recorded_timestamps": window_observed,
        },
        "findings": findings,
        "candidate_only": True, "finality": "non_final", "decision_authority": "none",
    }


def _require_type(obj: dict, key: str, kind: type, label: str) -> Any:
    if key not in obj or not isinstance(obj[key], kind) or (kind is int and isinstance(obj[key], bool)):
        raise OPrepError(f"invalid_{label}.{key}")
    return obj[key]


def validate_signal(signal: dict) -> None:
    if not isinstance(signal, dict) or signal.get("schema") != "O_PREP_SIGNAL_V1":
        raise OPrepError("invalid_signal_schema")
    allowed_top = {"schema", "work_unit", "node_id", "captured_at_utc", "stage", "router", "evidence", "execution", "review", "delivery", "assertions", "metrics", "open_gates"}
    if set(signal) - allowed_top:
        raise OPrepError("unknown_signal_fields")
    for key in ("work_unit", "node_id", "captured_at_utc"):
        if not isinstance(signal.get(key), str) or not signal[key].strip():
            raise OPrepError(f"missing_or_invalid:{key}")
    _utc(signal["captured_at_utc"])
    if signal.get("stage") not in ALLOWED_STAGES:
        raise OPrepError("invalid_stage")
    for key in ("router", "evidence", "execution", "review", "delivery", "assertions"):
        _require_type(signal, key, dict, "signal")
    if not isinstance(signal.get("metrics"), list) or not isinstance(signal.get("open_gates"), list):
        raise OPrepError("invalid_metrics_or_gates")
    if not all(isinstance(x, str) and x.strip() for x in signal["open_gates"]):
        raise OPrepError("invalid_open_gate_value")
    if signal["router"].get("status") not in {"READY", "BLOCKED", "CLARIFICATION_REQUIRED", "ERROR", "NOT_RUN"}:
        raise OPrepError("invalid_router_status")
    expected_exits = {"READY": 0, "BLOCKED": 1, "CLARIFICATION_REQUIRED": 2, "ERROR": 3, "NOT_RUN": None}
    if signal["router"].get("exit_code", "MISSING") != expected_exits[signal["router"]["status"]]:
        raise OPrepError("router_status_exit_code_conflict")
    if signal["review"].get("status") not in {"PASS", "FINDINGS", "NOT_RUN"}:
        raise OPrepError("invalid_review_status")
    if signal["review"].get("evidence_class") not in {"NOT_RUN", "SAME_LINEAGE", "FRESH_CONTEXT", "VERIFIED_INDEPENDENT"}:
        raise OPrepError("invalid_review_class")
    if signal["delivery"].get("state") not in {"NOT_RUN", "PENDING", "DELIVERED", "PROCESSED"}:
        raise OPrepError("invalid_delivery_state")
    if signal["delivery"].get("disposition") not in {"NOT_RUN", "HELD", "FINDINGS", "ACCEPTED", "REJECTED"}:
        raise OPrepError("invalid_delivery_disposition")
    mandatory_bools = {
        "router": ("local_router_executed", "policy_hash_verified", "input_hash_verified", "output_hash_verified", "evidence_root_isolated"),
        "evidence": ("manifest_verified", "summary_raw_consistent", "timestamp_provenance_verified", "backfill_disclosed"),
        "execution": ("secret_exposure", "mutation_requested", "authority_verified", "live_action_requested", "shared_router_tree_write", "reviewed_bytes_changed", "blocked_node_contact"),
        "review": ("verified_independent", "harness_separately_verified", "fresh_context_policy_verified", "adjudicator_separate", "review_hash_matches", "blocking_findings"),
        "delivery": ("required", "ack_required", "ack_verified", "dedup_persistence_verified", "disposition_evidence_verified", "claims_accepted"),
        "assertions": ("metrics_simultaneous_claim", "claims_backfill_proves_history", "claims_full_closeout"),
    }
    for group, keys in mandatory_bools.items():
        for key in keys:
            if type(signal[group].get(key)) is not bool:
                raise OPrepError(f"invalid_{group}.{key}")
    for m in signal["metrics"]:
        if not isinstance(m, dict):
            raise OPrepError("invalid_metric_shape")
        for key in ("name", "captured_at_utc", "source_sha256"):
            if not isinstance(m.get(key), str) or not m[key].strip():
                raise OPrepError(f"invalid_metric.{key}")
        _utc(m["captured_at_utc"])
        if not SHA256.fullmatch(m["source_sha256"]):
            raise OPrepError("invalid_metric_hash")
    required_shape = {
        "router": {"status", "exit_code", *mandatory_bools["router"]},
        "evidence": set(mandatory_bools["evidence"]),
        "execution": set(mandatory_bools["execution"]),
        "review": {"status", "evidence_class", *mandatory_bools["review"]},
        "delivery": {"state", "disposition", "idempotency_key", *mandatory_bools["delivery"]},
        "assertions": set(mandatory_bools["assertions"]),
    }
    for group, fields in required_shape.items():
        if set(signal[group]) != fields:
            raise OPrepError(f"invalid_{group}_field_set")
    if len(set(signal["open_gates"])) != len(signal["open_gates"]):
        raise OPrepError("duplicate_open_gate")
    idempotency = signal["delivery"].get("idempotency_key")
    if idempotency is not None and (not isinstance(idempotency, str) or not idempotency.strip()):
        raise OPrepError("invalid_idempotency_key")


def evaluate_signal(signal: dict) -> dict:
    """Deterministic candidate-only decision. No host authority can be returned."""
    validate_signal(signal)
    stage = signal["stage"]
    router = signal["router"]
    ev = signal["evidence"]
    action = signal["execution"]
    review = signal["review"]
    delivery = signal["delivery"]
    assertions = signal["assertions"]
    issues = []
    def issue(code: str, state: str) -> None:
        issues.append({"code": code, "state": state})

    if action["secret_exposure"]:
        issue("SECRET_EXPOSURE", "STOP_DISCLOSURE")
    if action["shared_router_tree_write"]:
        issue("SHARED_ROUTER_OUTPUT_FORBIDDEN", "STOP_ROUTER_WRITE")
    if action["live_action_requested"]:
        issue("NO_LIVE_AUTHORITY_IN_O_PREP", "STOP_MUTATION")
    if action["blocked_node_contact"]:
        issue("NODE_COMMUNICATION_FREEZE", "STOP_MUTATION")
    if action["mutation_requested"] and not action["authority_verified"]:
        issue("MUTATION_AUTHORITY_MISSING", "STOP_MUTATION")
    if not ev["manifest_verified"]:
        issue("MANIFEST_UNVERIFIED", "HOLD_SOURCE")
    if not ev["summary_raw_consistent"]:
        issue("RAW_SUMMARY_MISMATCH", "HOLD_EVIDENCE")
    if not ev["timestamp_provenance_verified"]:
        issue("TIMESTAMP_PROVENANCE_UNVERIFIED", "HOLD_EVIDENCE")
    if assertions["claims_backfill_proves_history"]:
        issue("BACKFILL_IS_NOT_HISTORICAL_PROOF", "HOLD_EVIDENCE")
    if not ev["backfill_disclosed"]:
        issue("RECONSTRUCTED_HISTORY_UNDISCLOSED", "HOLD_EVIDENCE")
    if assertions["metrics_simultaneous_claim"]:
        stamps = {(_utc(m["captured_at_utc"]), m["source_sha256"]) for m in signal["metrics"]}
        if not stamps:
            issue("SIMULTANEOUS_METRICS_WITHOUT_EVIDENCE", "HOLD_EVIDENCE")
        elif len(stamps) > 1:
            issue("NON_SIMULTANEOUS_METRICS", "HOLD_EVIDENCE")
    if assertions["claims_full_closeout"] and stage != "CLOSE":
        issue("PREMATURE_FULL_CLOSEOUT_CLAIM", "HOLD_EVIDENCE")
    if (router["status"] != "READY" or not router["local_router_executed"] or
        not all(router[k] for k in ("policy_hash_verified", "input_hash_verified", "output_hash_verified", "evidence_root_isolated"))):
        issue("ROUTER_NOT_VERIFIED_READY", "HOLD_ROUTING")
    if action["reviewed_bytes_changed"]:
        issue("REVIEW_BOUND_ARTIFACT_CHANGED", "REWORK")
    if stage in ("PUBLISH", "CLOSE"):
        if review["status"] == "PASS" and review["blocking_findings"]:
            issue("PASS_CONTRADICTS_BLOCKING_FINDINGS", "REWORK")
        if review["evidence_class"] == "SAME_LINEAGE":
            issue("SAME_LINEAGE_CANNOT_CLOSE_REVIEW_GATE", "HOLD_REVIEW")
        if review["evidence_class"] == "NOT_RUN" and review["status"] == "PASS":
            issue("REVIEW_NOT_RUN_CONTRADICTS_PASS", "HOLD_REVIEW")
        if review["evidence_class"] != "VERIFIED_INDEPENDENT" and review["verified_independent"]:
            issue("FRESH_CONTEXT_NOT_INDEPENDENT", "HOLD_REVIEW")
        if review["evidence_class"] == "VERIFIED_INDEPENDENT" and not (review["harness_separately_verified"] and review["verified_independent"]):
            issue("INDEPENDENT_NOT_VERIFIED", "HOLD_REVIEW")
        if review["evidence_class"] == "FRESH_CONTEXT" and not (
            review["fresh_context_policy_verified"] and review["adjudicator_separate"]):
            issue("FRESH_CONTEXT_POLICY_OR_ADJUDICATOR_MISSING", "HOLD_REVIEW")
        if review["status"] != "PASS":
            issue("REVIEW_UNRESOLVED", "REWORK" if review["blocking_findings"] else "HOLD_REVIEW")
        if not review["review_hash_matches"]:
            issue("REVIEW_BYTE_BINDING_UNVERIFIED", "HOLD_REVIEW")
    if delivery["disposition"] == "ACCEPTED" and not delivery["disposition_evidence_verified"]:
        if stage in ("PUBLISH", "CLOSE"):
            issue("ACCEPTED_WITHOUT_RECEIPT", "HOLD_DELIVERY")
    if delivery["ack_verified"] and delivery["state"] == "NOT_RUN":
        issue("ACK_WITHOUT_DELIVERY", "HOLD_DELIVERY")
    if stage in ("PUBLISH", "CLOSE") and delivery["required"]:
        if not delivery["idempotency_key"]:
            issue("IDEMPOTENCY_KEY_MISSING", "HOLD_DELIVERY")
        if not delivery["dedup_persistence_verified"]:
            issue("DURABLE_DEDUP_NOT_VERIFIED", "HOLD_DELIVERY")
    if stage == "CLOSE":
        if delivery["required"] and (delivery["disposition"] != "ACCEPTED" or not delivery["disposition_evidence_verified"]):
            issue("SUBSTANTIVE_ACCEPTANCE_MISSING", "HOLD_DELIVERY")
        if delivery["required"] and delivery["claims_accepted"] and delivery["state"] == "PROCESSED" and delivery["disposition"] != "ACCEPTED":
            issue("TRANSPORT_IS_NOT_ACCEPTANCE", "HOLD_DELIVERY")
        if delivery["ack_required"] and not delivery["ack_verified"]:
            issue("ACK_NOT_VERIFIED", "HOLD_DELIVERY")
        if signal["open_gates"]:
            issue("UNRESOLVED_EXTERNAL_GATES", "HOLD_DELIVERY")
    if assertions["claims_full_closeout"] and stage == "CLOSE" and issues:
        issue("FULL_CLOSEOUT_CLAIM_HAS_OPEN_ISSUES", "HOLD_DELIVERY")
    next_action = min([r["state"] for r in issues], key=PRIORITY.index) if issues else "ADVANCE_CANDIDATE"
    return {
        "schema": "O_PREP_DECISION_V1", "o_prep_version": VERSION,
        "work_unit": signal["work_unit"], "node_id": signal["node_id"],
        "source_captured_at_utc": signal["captured_at_utc"], "stage": stage,
        "next_action": next_action, "issues": issues,
        "evaluation_mode": "UNBOUND_SIMULATION",
        "host_mutation_authorized": False, "live_effect": "NOT_RUN",
        "candidate_only": True, "finality": "non_final", "decision_authority": "none",
    }


def evaluate_bound_signal(signal: dict, receipt_index_path: str, evidence_root: str) -> dict:
    """Candidate evaluation with independently re-hashed *local bytes*.

    Receipt content can still be producer-provided or spoofed. This method cannot
    attest actual router execution, reviewer independence or persistent host state.
    """
    result = evaluate_signal(signal)
    binding = verify_local_bindings(receipt_index_path, evidence_root, signal)
    result["evaluation_mode"] = "LOCAL_BYTES_BOUND_CANDIDATE"
    result["evidence_binding"] = {k: v for k, v in binding.items() if k != "issues"}
    result["issues"].extend(binding["issues"])
    result["next_action"] = (min((x["state"] for x in result["issues"]), key=PRIORITY.index)
                             if result["issues"] else "ADVANCE_CANDIDATE")
    return result


def _secure_out_file(target: Path, output_root: Path, text: str) -> None:
    """Create a new 0600 file only inside a pre-existing isolated output root.

    Never follow a path-component symlink or overwrite a prior receipt.
    """
    root = output_root.absolute()
    if not root.is_dir():
        raise OPrepError("output_root_not_existing_directory")
    current = root
    while current != current.parent:
        if current.is_symlink():
            raise OPrepError("symlink_output_root_forbidden")
        current = current.parent
    try:
        relative = target.absolute().relative_to(root)
    except ValueError as exc:
        raise OPrepError("output_target_outside_private_root") from exc
    if relative in (Path("."), Path("")):
        raise OPrepError("output_target_invalid")
    p = root
    for component in relative.parts[:-1]:
        if component in {".", ".."}:
            raise OPrepError("output_path_component_invalid")
        p = p / component
        if not p.is_dir() or p.is_symlink():
            raise OPrepError("output_parent_not_private_directory")
    p = p / relative.name
    _check_out_path(p)
    if p.is_symlink():
        raise OPrepError("output_symlink_forbidden")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(p, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
    except BaseException:
        p.unlink(missing_ok=True)
        raise


def _check_out_path(path: Path) -> None:
    parts = [p.lower() for p in path.resolve().parts]
    if "skills" in parts and "active_shared" in parts:
        raise OPrepError("shared_skill_tree_is_not_an_output_root")
    if path.exists() and path.is_symlink():
        raise OPrepError("symlink_output_not_allowed")


def _main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Offline candidate-only O-Prep (no host effects)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_audit = sub.add_parser("audit-transport", help="read-only transported archive verification")
    p_audit.add_argument("--zip", required=True)
    p_audit.add_argument("--peer-audit", help="optional earlier independent minimal archive audit JSON")
    p_audit.add_argument("--out", help="explicit output path outside active shared skill tree")
    p_eval = sub.add_parser("evaluate", help="unbound simulation of a provided O_PREP_SIGNAL_V1 JSON")
    p_eval.add_argument("--signal", required=True)
    p_eval.add_argument("--out", help="explicit new output file inside --output-root")
    p_bound = sub.add_parser("evaluate-bound", help="offline check of local receipt bytes, still candidate only")
    p_bound.add_argument("--signal", required=True)
    p_bound.add_argument("--receipt-index", required=True)
    p_bound.add_argument("--evidence-root", required=True)
    p_bound.add_argument("--out", help="explicit new output file inside --output-root")
    for item in (p_audit, p_eval, p_bound):
        item.add_argument("--output-root", help="required with --out; must be pre-existing isolated directory")
    args = parser.parse_args(argv)
    try:
        if args.cmd == "audit-transport":
            result = audit_transport_bundle(args.zip, args.peer_audit)
        elif args.cmd == "evaluate-bound":
            result = evaluate_bound_signal(_read_json(Path(args.signal).read_bytes(), "signal"),
                                           args.receipt_index, args.evidence_root)
        else:
            result = evaluate_signal(_read_json(Path(args.signal).read_bytes(), "signal"))
        output = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.out:
            if not args.output_root:
                raise OPrepError("explicit_output_root_required")
            _secure_out_file(Path(args.out), Path(args.output_root), output)
        else:
            sys.stdout.write(output)
    except (OSError, zipfile.BadZipFile, OPrepError, BindingError, KeyError, TypeError) as exc:
        print(json.dumps({"error": type(exc).__name__, "reason": str(exc)[:200],
                          "candidate_only": True, "decision_authority": "none"}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
