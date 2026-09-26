#!/usr/bin/env python3
"""Fail-closed, current-tree publication scanner for nonfunctional private identifiers.

This tool checks *current files only*. It cannot erase earlier Git commits, CI logs,
PR conversations, forks, cached copies, or previously shared packages.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {'.git', '__pycache__', '.pytest_cache', '.venv', 'venv'}
RULES = {
    'internal_label': re.compile(
        r'(?<![A-Za-z0-9])(?:[1-9][ACX]|PC\d{1,3}|BETA:\w+)(?![A-Za-z0-9])'
        r'|(?<=[_-])(?:1a|1c|2x|3x|4a|4c|4x)(?=[_-])'),
    'dated_internal_reference': re.compile(r'\[\d{6}-[A-Z]\d{2,4}\]|\b\d{6}-[A-Z]\d{2,4}\b', re.I),
    'private_path_layout': re.compile(
        r'(?:hub[/\\]skills[/\\]|approved[/\\]astra[-_]|relay[/\\]astra[-_]'
        r'|[A-Z]:[/\\]Shared[/\\]|[A-Z]:[/\\]Workspace[/\\])', re.I),
    'private_repo_reference': re.compile(
        r'(?:Leonardo[-_]P3[-_]addon|chatgpt[-_]work[-_]cloud|chatgpt[-_]redagent)', re.I),
    'private_raw_contract': re.compile(
        r'(?:LOCAL[-_]ROUTING[-_]CONTRACT[-_]\d|\bP3V\d{1,3}\b)', re.I),
    # Public sources need no fixed external repository identity or historical
    # reference-integrity workflow; locally approved dependency pins are separate.
    'unneeded_cross_repo_audit': re.compile(
        r'(?:public[-_]astra[-_](?:reference|mirror)|astra[-_]prep\.git'
        r'|github\.com[/\\][\w-]+[/\\]astra[-_]prep)', re.I),
}

def scan(root: Path = ROOT) -> list[dict]:
    findings: list[dict] = []
    for directory, dirs, files in os.walk(root, topdown=True, followlinks=False):
        base = Path(directory)
        for name in list(dirs):
            if name in SKIP_DIRS:
                dirs.remove(name)
            elif (base / name).is_symlink():
                findings.append({'path': (base / name).relative_to(root).as_posix(), 'rule': 'symlink_directory'})
                dirs.remove(name)
        for name in sorted(files):
            path = base / name
            rel = path.relative_to(root).as_posix()
            for rule, pattern in RULES.items():
                if pattern.search(rel):
                    findings.append({'path': rel, 'rule': 'filename_' + rule})
            if path.is_symlink():
                findings.append({'path': rel, 'rule': 'symlink_file'})
                continue
            try:
                raw = path.read_bytes()
            except OSError:
                findings.append({'path': rel, 'rule': 'unreadable_file'})
                continue
            # Invalid UTF-8 must not let ASCII identifiers in a binary file
            # bypass the scanner. UTF-16 with a BOM is checked as well.
            decoded = [raw.decode('utf-8', errors='ignore')]
            if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
                try:
                    decoded.append(raw.decode('utf-16'))
                except UnicodeError:
                    findings.append({'path': rel, 'rule': 'malformed_utf16'})
            for rule, pattern in RULES.items():
                if any(pattern.search(data) for data in decoded):
                    findings.append({'path': rel, 'rule': rule})
    return sorted(findings, key=lambda x: (x['path'], x['rule']))

if __name__ == '__main__':
    bad = scan()
    print(json.dumps({
        'schema': 'MAESTRO_PUBLIC_PRIVACY_AUDIT_V2',
        'status': 'PASS' if not bad else 'FAIL',
        'issues': bad,
        'scope': 'CURRENT_PUBLISHED_FILES_ONLY',
        'historical_repository_purge': 'NOT_CLAIMED',
    }, ensure_ascii=False, indent=2))
    sys.exit(2 if bad else 0)
