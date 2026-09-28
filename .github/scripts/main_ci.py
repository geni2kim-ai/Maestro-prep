#!/usr/bin/env python3
"""Fail-closed, self-contained main-profile CI; no host execution or reviewer authority."""
from __future__ import annotations
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASES = (
    ('release_inventory', ['tools/verify_package.py', '.'], 'package'),
    ('public_privacy', ['tools/public_privacy_check.py'], 'privacy'),
    ('included_component_pin', ['-m', 'maestro_prep.cli', 'component-check'], 'pin'),
    ('coordinator_tests', ['-m', 'unittest', 'discover', '-s', 'tests', '-q'], 'coordinator'),
    ('public_component_tests', ['.github/scripts/run_public_component_tests.py'], 'component'),
    ('synthetic_replay', ['tools/replay_simulation.py'], 'replay'),
    ('release_builder_tests', ['-m', 'unittest', 'discover', '-s', '.github/scripts', '-p', 'test_release_builder.py', '-q'], 'release_tests'),
    ('external_gate_synthetic_tests', ['-m', 'unittest', 'discover', '-s', '.github/scripts', '-p', 'test_external_conformance_gate.py', '-q'], 'external_gate_tests'),
    ('ci_receipt_accounting_tests', ['-m', 'unittest', 'discover', '-s', '.github/scripts', '-p', 'test_main_ci_contract.py', '-q'], 'ci_guard_tests'),
)

def run_case(name: str, args: list[str], kind: str) -> dict:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    if os.name == 'nt':
        # Resolve the runner's temp-root aliases for exact-path public component tests.
        import tempfile
        base = Path(os.environ.get('RUNNER_TEMP', tempfile.gettempdir())).resolve(strict=True)
        temp = base / 'maestro-prep-main-ci'
        temp.mkdir(parents=True, exist_ok=True)
        env.update(TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp))
    proc = subprocess.run([sys.executable, *args], cwd=ROOT, env=env,
                          timeout=180, capture_output=True, text=True,
                          encoding='utf-8', errors='replace')
    data = None
    if kind in {'package', 'privacy', 'pin', 'replay'}:
        try:
            data = json.loads(proc.stdout)
        except ValueError:
            pass
    passed = proc.returncode == 0
    details = {}
    if kind == 'package':
        passed = passed and isinstance(data, dict) and data.get('verified') is True
        passed = passed and data.get('files') == 40 and data.get('host_authority') is False
        details['verified_files'] = data.get('files') if isinstance(data, dict) else None
    elif kind == 'privacy':
        passed = passed and isinstance(data, dict) and data.get('status') == 'PASS' and data.get('issues') == []
    elif kind == 'pin':
        passed = passed and isinstance(data, dict) and data.get('o_prep_v03_pinned') is True
    elif kind == 'replay':
        passed = (passed and isinstance(data, dict)
                  and data.get('scenario_count') == 20
                  and data.get('o_prep_cases_matched') == 20
                  and data.get('c_model_cases_matched') == 20
                  and data.get('c_compulsory_gate_skips_when_available') == 0
                  and data.get('host_mutation_authorized') is False)
        details['matched_cases'] = data.get('o_prep_cases_matched') if isinstance(data, dict) else None
    else:
        m = re.search(r'Ran (\d+) tests', proc.stderr)
        count = int(m.group(1)) if m else 0
        skips = re.search(r'OK \(skipped=(\d+)\)', proc.stderr)
        details.update(tests=count, skipped=int(skips.group(1)) if skips else 0)
        minimum = 30 if kind == 'coordinator' else (3 if kind in {'release_tests', 'ci_guard_tests'} else (9 if kind == 'external_gate_tests' else 61))
        allowed_skips = (5 + (1 if os.name == 'nt' else 0)) if kind == 'component' else 0
        passed = passed and details['skipped'] == allowed_skips
        passed = passed and count >= minimum and re.search(r'(?m)^OK(?: \(skipped=\d+\))?$', proc.stderr) is not None
        if kind == 'component' and os.name == 'nt':
            passed = passed and proc.stderr.count('VENDOR_PLATFORM_EXCEPTION') == 1
            passed = passed and details['skipped'] >= 1
    receipt = dict(name=name, passed=bool(passed), exit_code=proc.returncode,
                   scope='CURRENT_MAIN_PUBLIC_BYTES_AND_SYNTHETIC_ONLY', **details)
    if not passed:
        # Truncate rather than publish full unknown CI diagnostics.
        receipt['diagnostic'] = (proc.stderr or proc.stdout)[:800]
    return receipt

def main() -> int:
    results = []
    for name, args, kind in CASES:
        print('START ' + name, file=sys.stderr, flush=True)
        try:
            results.append(run_case(name, args, kind))
        except (OSError, subprocess.TimeoutExpired) as exc:
            results.append({'name': name, 'passed': False,
                            'diagnostic': type(exc).__name__})
    report = {
        'schema': 'MAESTRO_MAIN_PUBLIC_OFFLINE_CI_V1',
        'candidate_only': True, 'version': '0.1.0-public-redacted-hotfix',
        'approved_planning_host': 'NOT_RUN', 'actual_router': 'NOT_RUN',
        'independent_review': 'NOT_RUN', 'deployment_authorized': False,
        'checks': results, 'passed': sum(x['passed'] for x in results),
        'total': len(results),
    }
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report['passed'] == report['total'] else 2

if __name__ == '__main__':
    raise SystemExit(main())
