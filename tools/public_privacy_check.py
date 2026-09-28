#!/usr/bin/env python3
"""Fail-closed current-file privacy marker check; never certifies historical objects.

UTF-8 text, non-UTF-8 binary ASCII fragments and BOM-free UTF-16 LE/BE
views are checked. Unreadable files and links are findings, not silent skips.
This bounded pattern check is NOT a proof about compressed/encoded content,
historical Git objects, Actions caches or previously distributed artifacts.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE = {"MANIFEST.json", "SHA256SUMS.txt"}
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv"}
RULES = {
    "internal_label": re.compile(r"(?<![A-Za-z0-9])(?:[1-9][ACX]|PC\d{1,3}|BETA:(?:\w+))(?![A-Za-z0-9])|(?<=[_-])(?:1a|1c|2x|3x|4a|4c|4x)(?=[_-])"),
    "dated_internal_reference": re.compile(r"\[\d{6}-[A-Z]\d{2,4}\]|\b\d{6}-[A-Z]\d{2,4}\b", re.I),
    "private_path_layout": re.compile(r"(?i)(?:hub[/\\]skills[/\\]|approved[/\\]astra[-_]|relay[/\\]astra[-_]|[A-Z]:[/\\]Shared[/\\]|[A-Z]:[/\\]Workspace[/\\])"),
    "private_repo_reference": re.compile(r"(?i)(?:Leonardo[-_]P3[-_]addon|chatgpt[-_]work[-_]cloud|chatgpt[-_]redagent)"),
    "private_raw_contract": re.compile(r"(?i)(?:LOCAL[-_]ROUTING[-_]CONTRACT[-_]\d|\bP3V\d{1,3}\b)"),
}

def text_views(data: bytes) -> tuple[str, ...]:
    views = [data.decode("utf-8", errors="ignore")]
    # Detect BOM-free UTF-16 substrings even when the original file has a
    # binary prefix; both byte alignments are necessary for mixed payloads.
    if b"\x00" in data:
        for encoding in ("utf-16-le", "utf-16-be"):
            for offset in (0, 1):
                views.append(data[offset:].decode(encoding, errors="ignore"))
    return tuple(views)

def scan(root: Path = ROOT) -> list[dict]:
    findings = []
    for path in sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix()):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            findings.append({"path": relative, "rule": "link_forbidden"})
            continue
        if not path.is_file() or path.name in EXCLUDE:
            continue
        for name, rule in RULES.items():
            if rule.search(relative):
                findings.append({"path": relative, "rule": "filename_" + name})
        try:
            data = path.read_bytes()
        except OSError:
            findings.append({"path": relative, "rule": "unreadable_file"})
            continue
        views = text_views(data)
        for name, rule in RULES.items():
            if any(rule.search(view) for view in views):
                findings.append({"path": relative, "rule": name})
    return findings

if __name__ == "__main__":
    bad = scan()
    print(json.dumps({
        "schema": "MAESTRO_PUBLIC_PRIVACY_AUDIT_V1",
        "status": "PASS" if not bad else "FAIL",
        "issues": bad, "scope": "CURRENT_CHECKOUT_UTF8_BINARY_ASCII_UTF16_ONLY",
        "historical_objects": "NOT_RUN",
    }, ensure_ascii=False, indent=2))
    sys.exit(2 if bad else 0)
