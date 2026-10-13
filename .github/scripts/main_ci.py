#!/usr/bin/env python3
"""Fail-closed, self-contained main-profile CI; no host execution or reviewer authority."""
from __future__ import annotations
import json
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOST_IS_WINDOWS = os.name == 'nt'
# Exact method+reason allowlist for the *known* optional dependency and
# Windows filesystem mode-bit exception. Unknown skips must not be treated as
# a clean baseline, even when their count matches.
OPTIONAL_JSONSCHEMA_SKIPS = (
    ('SchemaTests.test_input_signal_validates', 'jsonschema optional dependency unavailable'),
    ('SchemaTests.test_output_decision_validates', 'jsonschema optional dependency unavailable'),
    ('SchemaTests.test_unexpected_authority_is_schema_rejected', 'jsonschema optional dependency unavailable'),
    ('SchemaTests.test_unexpected_codepath_field_is_rejected', 'jsonschema optional dependency unavailable'),
    ('V03LocalBindingTests.test_receipt_schema_validates', 'optional jsonschema package not present'),
)
WINDOWS_MODEBIT_SKIP = (
    'V03OutputTests.test_new_receipt_is_exclusive_and_private',
    'POSIX 0600 assertion is inapplicable to Windows; actual NTFS ACL remains NOT_RUN',
)

def expected_component_skips() -> list[dict[str, str]]:
    expected = [] if importlib.util.find_spec('jsonschema') is not None else list(OPTIONAL_JSONSCHEMA_SKIPS)
    if HOST_IS_WINDOWS:
        expected.append(WINDOWS_MODEBIT_SKIP)
    return sorted([{'id': ident, 'reason': reason} for ident, reason in expected],
                  key=lambda item: (item['id'], item['reason']))

def check_component_receipt(stdout: str, count: int, skipped: int) -> tuple[bool, str]:
    prefix = 'MAESTRO_COMPONENT_TEST_RESULT_V1='
    # No multi-line or repeated receipt is accepted. The producer is still
    # local test code, not an independent attestation or a trusted validator.
    if not stdout.startswith(prefix) or stdout.count(prefix) != 1:
        return False, 'COMPONENT_SKIP_INVENTORY_MISSING'
    try:
        record = json.loads(stdout[len(prefix):].strip())
    except ValueError:
        return False, 'COMPONENT_SKIP_INVENTORY_MALFORMED'
    if not isinstance(record, dict):
        return False, 'COMPONENT_SKIP_INVENTORY_MALFORMED'
    checks = (record.get('schema') == 'MAESTRO_COMPONENT_TEST_RESULT_V1'
              and type(record.get('tests_run')) is int and record['tests_run'] == count
              and type(record.get('errors')) is int and record['errors'] == 0
              and type(record.get('failures')) is int and record['failures'] == 0
              and record.get('was_successful') is True
              and isinstance(record.get('skipped'), list)
              and len(record['skipped']) == skipped)
    if not checks:
        return False, 'COMPONENT_SKIP_INVENTORY_INCONSISTENT'
    if record['skipped'] != expected_component_skips():
        return False, 'COMPONENT_SKIP_IDENTITIES_UNEXPECTED'
    return True, 'COMPONENT_SKIP_IDENTITIES_VERIFIED'

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
    if HOST_IS_WINDOWS:
        # Resolve the runner's temp-root aliases for exact-path public component tests.
        import tempfile
        base = Path(os.environ.get('RUNNER_TEMP', tempfile.gettempdir())).resolve(strict=True)
        temp = base / 'maestro-prep-main-ci'
        temp.mkdir(parents=True, exist_ok=True)
        env.update(TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp))
    # Only Windows requires per-test skip provenance. A summary count is not
    # evidence that the two known symlink-dependent cases were skipped.
    actual_args = list(args)
    if kind == 'coordinator' and HOST_IS_WINDOWS and actual_args[-1:] == ['-q']:
        actual_args[-1] = '-v'
    proc = subprocess.run([sys.executable, *actual_args], cwd=ROOT, env=env,
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
    platform_gaps = sorted(set(re.findall(r'VENDOR_PLATFORM_GAP:([A-Z0-9_]+):', proc.stderr)))
    if platform_gaps:
        details['platform_gaps'] = platform_gaps
        passed = False
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
        minimum = 79 if kind == 'coordinator' else (6 if kind == 'release_tests' else (7 if kind == 'ci_guard_tests' else (9 if kind == 'external_gate_tests' else 70)))
        allowed_skips = ((0 if importlib.util.find_spec('jsonschema') is not None else 5) +
                         (1 if HOST_IS_WINDOWS else 0)) if kind == 'component' else 0
        passed = passed and details['skipped'] == allowed_skips
        # Contradictory or multiple unittest summary lines must never be
        # counted as a successful test run merely because one says OK.
        summary = re.findall(r'(?m)^(?:OK(?: \(skipped=\d+\))?|FAILED(?: \([^\r\n]+\))?)\r?$', proc.stderr)
        passed = (passed and count >= minimum and len(summary) == 1
                  and summary[0].startswith('OK'))
        if kind == 'component':
            verified, reason = check_component_receipt(proc.stdout, count, details['skipped'])
            details['skip_inventory_status'] = reason
            passed = passed and verified
        if kind == 'coordinator' and HOST_IS_WINDOWS and details['skipped']:
            # unittest -v names each skipped case; do not infer the reason
            # merely from the total summary count. This is an
            # evidence classification, never an acceptance exception.
            skipped_lines = re.findall(
                r'(?m)^test_[A-Za-z0-9_]+ \([^\r\n]{1,200}\) \.\.\. skipped [^\r\n]+$',
                proc.stderr)
            pairs = re.findall(
                r"(?m)^(test_[A-Za-z0-9_]+) \([^\r\n]{1,200}\) \.\.\. skipped '([^'\r\n]{1,120})'$",
                proc.stderr)
            expected = {
                ('test_external_skill_symlink_rejected', 'Symlinks restricted'),
                ('test_symlinked_evidence_root_ancestor_is_rejected', 'Symlinks restricted'),
            }
            corroborated = (len(skipped_lines) == len(pairs) == details['skipped']
                            and len(pairs) == len(set(pairs))
                            and set(pairs).issubset(expected))
            details['platform_gaps'] = [
                'COORDINATOR_SYMLINK_TESTS_SKIPPED' if corroborated
                else 'COORDINATOR_SKIP_CAUSE_UNVERIFIED'
            ]
            # Even corroborated missing tests are never passed.
            passed = False
        if kind == 'component' and HOST_IS_WINDOWS:
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
