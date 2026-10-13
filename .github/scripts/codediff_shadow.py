#!/usr/bin/env python3
"""Non-authoritative PR-with-codediff-finder v2.5 policy SHADOW.

Authentic upstream policy engine is vendored with source blob pins. This script
uses degraded Git change inventory; it does NOT run trusted TextDiff, L1/L2,
Adversarial workers, Leonardo models, or a human approval step.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from types import MappingProxyType, ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
VENDOR = ROOT / ".github" / "review_tools" / "codediff_v25"
PIN_PATH = ROOT / ".github" / "review_tools" / "EXTERNAL_SOURCE_PINS.json"
OVERLAY = {
    "governance_paths": [".github/review_tools/**", ".github/scripts/**"],
    "human_floor_paths": [
        "/maestro_prep/coordinator.py", "/maestro_prep/cli.py",
        "/components/o_prep_v0_3/**", "/.github/review_tools/**",
        "/.github/workflows/**", "/.github/scripts/**", "/tools/verify_package.py",
        "/MANIFEST.json", "/SHA256SUMS.txt", "/adapters/**",
    ],
    "adversarial_floor_paths": [
        "/maestro_prep/**", "/components/o_prep_v0_3/**",
        "/.github/review_tools/**", "/tests/test_maestro.py",
    ],
    "supply_chain_files": [],
}
SHA = re.compile(r"^[0-9a-f]{40}$")
# Byte-level provenance locked to the inspected v2.5 upstream reference.
# The candidate (including this file) is not a trusted reviewer; this detects
# accidental/partial pin tampering, not malicious redefinition of the checker.
CODEDIFF_UPSTREAM_REF = "69a49faa35b56d48e9e3067e5f484b443735df67"
CODEDIFF_UPSTREAM_REPO = "geni2kim-ai/PR-with-codediff-finder"
LEONARDO_UPSTREAM_REPO = "geni2kim-ai/Leonardo"
LEONARDO_MAIN_REF = "a4e0bc631d1033e8ba25a0a3e7b1457ca3d6a0d7"
LEONARDO_CANDIDATE_REF = "80bb6891e772feb506a79dfe2c3beac2b5ae1dcc"
LEONARDO_CANDIDATE_BRANCH = "candidate/leonardo-r230-excluded-import-guard-20261012"
TRUSTED_VENDOR_BLOBS = {
    ".github/review_tools/codediff_v25/policy_engine.py": "b1466919d765d0b905ba1ba4447efddf87099efb",
    ".github/review_tools/codediff_v25/protected-paths.yml": "9abc44dd8d390fc6cb9f6c11d0224e779d6362bb",
    ".github/review_tools/codediff_v25/escalation-policy.yml": "85f6026a41d83490dc267ead5bfc8a170f881377",
    ".github/review_tools/codediff_v25/sensor-policy.yml": "6f79fd4ec7e5b9f0947cb4cf086ab26c7f4c3640",
}


def git(repo: Path, *args: str) -> str:
    env = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "WINDIR", "HOME",
        "USERPROFILE", "TEMP", "TMP", "TMPDIR") if k in os.environ}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_TERMINAL_PROMPT="0")
    result = subprocess.run(["git", "-c", "core.fsmonitor=false",
                             "-c", "diff.external=", "-C", str(repo), *args], cwd=repo,
                            env=env, capture_output=True, check=False,
                            timeout=40)
    if result.returncode:
        raise ValueError("GIT_DATA_UNAVAILABLE")
    return result.stdout.decode("utf-8", "surrogateescape")


def git_status(repo: Path, base: str, head: str) -> list[str]:
    # Git's NUL format is safe for renames and filenames with whitespace.
    raw = git(repo, "diff", "--no-ext-diff", "--no-textconv",
              "--name-status", "-z", "-M", base, head)
    tokens = raw.split("\0")
    if tokens[-1] == "":
        tokens.pop()
    changed: set[str] = set()
    i = 0
    while i < len(tokens):
        action = tokens[i]
        i += 1
        if not action or action[0] not in "ACDMRTUX":
            raise ValueError("UNKNOWN_DIFF_STATUS")
        if action[0] in "RC":
            if i + 1 >= len(tokens):
                raise ValueError("INVALID_RENAME_RECORD")
            changed.add(tokens[i])
            changed.add(tokens[i + 1])
            i += 2
        else:
            if i >= len(tokens):
                raise ValueError("INVALID_DIFF_RECORD")
            changed.add(tokens[i])
            i += 1
    return sorted(changed)


def object_id(data: bytes) -> str:
    # Git SHA-1 source-object identity, not an authentication signature.
    prefix = ("blob " + str(len(data)) + "\0").encode("ascii")
    return hashlib.sha1(prefix + data).hexdigest()


def trusted_source_snapshot() -> tuple[dict[str, Any], Any]:
    pins = json.loads(PIN_PATH.read_text(encoding="utf-8"))
    if (pins["codediff"]["version"] != "2.5"
            or pins["codediff"]["mode"] != "SHADOW"
            or pins["codediff"]["trusted_textdiff_sensor"] is not False
            or pins["leonardo"]["promoted_to_mandatory_runtime"] is not False):
        raise ValueError("UNAUTHORIZED_REVIEW_OR_LEONARDO_PROMOTION")
    # The SHADOW receipt emits the Leonardo candidate ref as provenance.
    # Previously an altered descriptor was accepted while retaining a valid
    # CodeDiff upstream SHA. Lock these refs separately; this is NOT proof of
    # a Leonardo runtime or an endorsement of the candidate's failed CI.
    leo = pins["leonardo"]
    if (leo.get("repo") != LEONARDO_UPSTREAM_REPO
            or leo.get("stable_main_sha") != LEONARDO_MAIN_REF
            or leo.get("latest_examined_candidate_sha") != LEONARDO_CANDIDATE_REF
            or leo.get("candidate_branch") != LEONARDO_CANDIDATE_BRANCH
            or leo.get("version") != "R2.30 candidate"
            or leo.get("live_execution") != "NOT_RUN"):
        raise ValueError("LEONARDO_PROVENANCE_PIN_MISMATCH")
    if (pins["codediff"].get("repo") != CODEDIFF_UPSTREAM_REPO
            or pins["codediff"].get("source_commit") != CODEDIFF_UPSTREAM_REF
            or pins["codediff"].get("independent_review") != "NOT_RUN"
            or pins.get("authority") != "NONE"
            or pins.get("candidate_only") is not True):
        raise ValueError("UNTRUSTED_UPSTREAM_SOURCE_DESCRIPTOR")
    paths = pins["codediff"]["upstream_files"]
    if (not isinstance(paths, list) or len(paths) != len(TRUSTED_VENDOR_BLOBS)
            or any(not isinstance(x, dict) for x in paths)):
        raise ValueError("UPSTREAM_PINSET_INVALID")
    seen: set[str] = set()
    verified: dict[str, bytes] = {}
    for item in paths:
        dest = item.get("dest")
        if (not isinstance(dest, str) or dest in seen
                or item.get("source_git_blob") != TRUSTED_VENDOR_BLOBS.get(dest)):
            raise ValueError("UNTRUSTED_UPSTREAM_SOURCE_DESCRIPTOR")
        seen.add(dest)
        target = ROOT / dest
        # Reject a symlink in any parent directory, not only a linked file.
        if (not target.is_file() or target.is_symlink()
                or target.resolve() != target.absolute()):
            raise ValueError("REVIEW_VENDOR_SOURCE_MISSING")
        data = target.read_bytes()
        if object_id(data) != TRUSTED_VENDOR_BLOBS[dest]:
            raise ValueError("UPSTREAM_SOURCE_PIN_MISMATCH")
        verified[dest] = data
    if seen != set(TRUSTED_VENDOR_BLOBS):
        raise ValueError("UPSTREAM_PINSET_INVALID")
    # Importlib's SourceFileLoader can execute a valid-looking __pycache__ .pyc
    # even when the corresponding source bytes were SHA checked above. Compile
    # exactly the *verified* source snapshot and bypass importlib cache lookup.
    path = VENDOR / "policy_engine.py"
    payload = verified[".github/review_tools/codediff_v25/policy_engine.py"]
    module = ModuleType("_pinned_pr_codediff_policy_engine_v25")
    module.__file__ = str(path)
    exec(compile(payload, str(path), "exec", dont_inherit=True), module.__dict__)
    # Keep policy YAML in immutable byte snapshots: no second disk read after
    # verifying its object ID, even if files are concurrently replaced.
    module._maestro_verified_policy_yaml = MappingProxyType({
        Path(name).name: content for name, content in verified.items()
        if name.endswith(".yml")
    })
    return pins, module


def analyze(repo: Path, base: str, head: str) -> dict[str, Any]:
    if not SHA.fullmatch(base) or not SHA.fullmatch(head):
        raise ValueError("UNPINNED_GIT_REFERENCE")
    if git(repo, "rev-parse", "HEAD").strip() != head:
        raise ValueError("STALE_HEAD")
    if git(repo, "merge-base", base, head).strip() != base:
        raise ValueError("BASE_NOT_ANCESTOR")
    # A clean HEAD hash alone says nothing about modified or untracked files
    # loaded by the current runner. Refuse to review a nonreproducible workspace.
    if git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all"):
        raise ValueError("DIRTY_REVIEW_WORKTREE")
    pins, engine = trusted_source_snapshot()
    paths = git_status(repo, base, head)
    if not paths:
        raise ValueError("EMPTY_DIFF")
    # Real upstream policy_engine.run: classify paths + derive escalation.
    # Parsing the verified in-memory bytes closes the post-pin read race.
    # Use the original upstream policy decoder (PyYAML) and unchanged rules.
    verified_yaml = engine._maestro_verified_policy_yaml
    protected = engine.yaml.safe_load(verified_yaml["protected-paths.yml"].decode("utf-8"))
    escalation = engine.yaml.safe_load(verified_yaml["escalation-policy.yml"].decode("utf-8"))
    sensor = engine.yaml.safe_load(verified_yaml["sensor-policy.yml"].decode("utf-8"))
    merged = {k: list(protected.get(k, [])) + OVERLAY.get(k, [])
              for k in OVERLAY}
    path_hits = engine.classify_paths(paths, merged)
    model = {
        "reversibility": "MODERATE", "blast_radius": "MULTI_SERVICE",
        "data_sensitivity": "NONE", "security_surface": "HIGH",
        "availability_criticality": "HIGH",
    }
    signals = {
        "sensor_runtime_untrusted": True, "sensor_approximate": True,
        "reviewer_confidence": "low", "novel_failure_family": True,
        "reviewer_policy_tampering": bool(path_hits["governance"]),
    }
    risk = engine.derive_risk(model, path_hits)
    required, reasons = engine.derive_required_level(
        model, path_hits, signals, escalation_cfg=escalation, sensor_cfg=sensor)
    # Official required-level function is the risk policy; missing reviewer
    # executions are never rewritten as PASS (regardless of required level).
    return {
        "schema": "MAESTRO_CODEDIFF_SHADOW_V1",
        "candidate_only": True, "review_mode": "SHADOW",
        "sensor_mode": "DEGRADED_GIT_INVENTORY", "trusted_for_gate": False,
        "degradation_reasons": ["TRUSTED_TEXTDIFF_SENSOR_NOT_EXECUTED"],
        "code_diff_source": pins["codediff"]["repo"],
        "code_diff_source_commit": pins["codediff"]["source_commit"],
        "code_diff_policy_engine_actual": "EXECUTED",
        "code_diff_textdiff_adapter": "NOT_RUN",
        "leonardo_candidate_sha": pins["leonardo"]["latest_examined_candidate_sha"],
        "leonardo_candidate_ci": "FAILED_NOT_PROMOTED",
        "leonardo_actual_router": "NOT_RUN",
        "base_sha": base, "head_sha": head, "changed_paths": paths,
        "risk_model": model, "path_hits": path_hits, "risk": risk,
        "required_level": required, "required_reasons": reasons,
        "achieved_level": "SENSOR_ONLY", "analysis_status": "INSUFFICIENT_EVIDENCE",
        "gate_conclusion": "action_required",
        "independent_redagent": "NOT_RUN",
        "human_review": "NOT_RUN",
        "authority_effect": "NONE",
        "next_action": "OBTAIN_INDEPENDENT_REVIEW_BEFORE_MERGE",
    }



def persist_report_bound(path: Path, root: Path, report: dict[str, Any]) -> None:
    """Write a new report relative to a held directory FD (POSIX only).

    Lexical and resolved path checks alone are vulnerable to a parent-link
    exchange after the check. Never follow a replaced parent after opening its
    handle. On unsupported systems, HOLD rather than pretending atomicity.
    """
    if (os.name != "posix" or not hasattr(os, "O_DIRECTORY")
            or not hasattr(os, "O_NOFOLLOW")
            or os.open not in os.supports_dir_fd):
        raise ValueError("OUTPUT_DIRFD_UNSUPPORTED")
    parent = path.parent
    if parent.is_symlink() or path.exists() or path.is_symlink():
        raise ValueError("REVIEW_OUTPUT_INVALID")
    dirfd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    created = False
    owned_identity: tuple[int, int] | None = None
    try:
        def same_parent() -> bool:
            try:
                st = os.stat(parent, follow_symlinks=False)
                bound = os.fstat(dirfd)
                real = parent.resolve(strict=True)
                return (parent.is_dir() and not parent.is_symlink()
                        and not real.is_relative_to(root)
                        and st.st_dev == bound.st_dev and st.st_ino == bound.st_ino)
            except OSError:
                return False
        if not same_parent():
            raise ValueError("REVIEW_OUTPUT_PARENT_CHANGED")
        # O_EXCL/O_NOFOLLOW protect against existing-file/symlink swapping.
        # Serialize once, then prove the path points to the exact inode
        # containing those exact bytes. The parent-FD check alone permits
        # another writer to replace the directory entry after O_EXCL.
        payload = (json.dumps(report, sort_keys=True, indent=2) + "\n").encode("utf-8")
        if len(payload) > 1024 * 1024:
            raise ValueError("REVIEW_OUTPUT_TOO_LARGE")
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=dirfd)
        created = True
        owned = os.fstat(fd)
        owned_identity = (owned.st_dev, owned.st_ino)
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        # Reopen the *named* entry without following links; neither file
        # descriptor alone nor a successful fsync proves the current path.
        try:
            check_fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                               dir_fd=dirfd)
        except OSError as exc:
            raise ValueError("REVIEW_OUTPUT_IDENTITY_CHANGED") from exc
        try:
            observed = os.fstat(check_fd)
            if (not stat.S_ISREG(observed.st_mode)
                    or (observed.st_dev, observed.st_ino) != owned_identity
                    or observed.st_nlink != 1
                    or observed.st_size != len(payload)):
                raise ValueError("REVIEW_OUTPUT_IDENTITY_CHANGED")
            stored = os.read(check_fd, len(payload) + 1)
            if stored != payload:
                raise ValueError("REVIEW_OUTPUT_BYTES_CHANGED")
        finally:
            os.close(check_fd)
        if not same_parent():
            raise ValueError("REVIEW_OUTPUT_PARENT_CHANGED")
    except BaseException:
        if created and owned_identity is not None:
            try:
                # Never delete another process's substituted receipt. Only
                # remove the inode that this invocation actually created.
                candidate = os.stat(path.name, dir_fd=dirfd, follow_symlinks=False)
                if (candidate.st_dev, candidate.st_ino) == owned_identity:
                    os.unlink(path.name, dir_fd=dirfd)
            except OSError:
                pass
        raise
    finally:
        os.close(dirfd)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--out", type=Path, required=True)
    ns = parser.parse_args(argv)
    try:
        path = ns.out.absolute()
        root = ns.repo.resolve(strict=True)
        parent = path.parent.resolve(strict=True)
        # Resolve *before* open; a symlinked directory may point back into the
        # source root even when the lexical --out starts outside it.
        if (path.exists() or path.is_symlink() or not path.parent.is_dir()
                or path.resolve(strict=False).is_relative_to(root)
                or parent.is_relative_to(root)):
            raise ValueError("REVIEW_OUTPUT_INVALID")
        report = analyze(root, ns.base, ns.head)
        persist_report_bound(path, root, report)
        print(json.dumps({"sensor": "CODEDIFF_V25_POLICY_EXECUTED",
                          "mode": report["sensor_mode"],
                          "required_level": report["required_level"],
                          "gate_conclusion": report["gate_conclusion"],
                          "head_sha": ns.head, "paths": len(report["changed_paths"])}))
        return 0
    except (OSError, ValueError, KeyError, ImportError, NotImplementedError) as exc:
        reason = str(exc) if isinstance(exc, ValueError) and re.fullmatch(
            r"[A-Z][A-Z0-9_]{1,79}", str(exc)) else "REVIEW_INTEGRATION_ERROR"
        print(json.dumps({"status": "BLOCKED", "code": reason,
                          "trusted_for_gate": False, "authority_effect": "NONE"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
