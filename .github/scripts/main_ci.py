#!/usr/bin/env python3
"""Fail-closed, self-contained main-profile CI; no host execution or reviewer authority."""
from __future__ import annotations
import json
import hashlib
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
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

# All 27 required accounting test identities: same-count substitutions reject.
# These are candidate-owned guardrails, NOT third-party verification.
CI_GUARD_EXPECTED_IDS = (
    'test_all_skipped_coordinator_is_not_a_pass',
    'test_ci_accounting_current_floor_runs_normally',
    'test_ci_guard_duplicate_name_in_valid_count_is_blocked',
    'test_ci_guard_exact_identity_inventory_is_accepted',
    'test_ci_guard_no_names_with_matching_count_is_blocked',
    'test_cache_prefix_is_fresh_for_each_child',
    'test_ci_launch_forces_python_cache_prefix',
    'test_ci_guard_replaced_required_identity_is_blocked',
    'test_ci_guard_source_pin_blocks_missing_file',
    'test_ci_guard_source_pin_blocks_symlink_source',
    'test_ci_guard_source_pin_detects_neutralized_body',
    'test_ci_guard_source_pin_matches_current_checkout',
    'test_isolated_cache_prevents_preexisting_pyc_execution',
    'test_clean_coordinator_with_no_skips_passes',
    'test_component_clean_receipt_matches_known_optional_skips',
    'test_component_opaque_skips_cannot_gain_a_green_by_count',
    'test_component_receipt_with_wrong_summary_count_blocks',
    'test_component_same_skip_count_wrong_identity_is_rejected',
    'test_component_skip_duplicate_does_not_substitute_required_case',
    'test_conflicting_run_counts_even_with_single_ok_are_rejected',
    'test_contradictory_coordinator_summary_is_not_green',
    'test_dropped_coordinator_regression_is_rejected',
    'test_dropped_public_component_regression_is_rejected',
    'test_fake_vendor_gap_without_skips_is_still_blocked',
    'test_installed_optional_schema_runs_all_without_skips',
    'test_missing_optional_schema_requires_five_skips',
    'test_removed_ci_accounting_tests_below_baseline_are_rejected',
    'test_unexplained_public_component_skip_is_rejected',
    'test_windows_coordinator_same_expected_name_wrong_reason_unverified',
    'test_windows_coordinator_skip_records_verified_cases_without_pass',
    'test_windows_coordinator_summary_without_verbose_is_unverified',
    'test_windows_coordinator_unrelated_skips_not_misattributed',
    'test_windows_coordinator_uses_verbose_mode_for_trace',
    'test_windows_unprivileged_vendor_is_not_approved_as_green',
)

def check_ci_guard_trace(stderr: str, count: int) -> tuple[bool, str]:
    # unittest -v emits one observed name and result per test. Compare the
    # identity-qualified executed set rather than trusting a numeric summary.
    names = re.findall(
        r'(?m)^(test_[A-Za-z0-9_]+) \(test_main_ci_contract\.CIAccountingTests\.\1\) \.\.\. ok\r?$',
        stderr,
    )
    verified = (len(names) == count == len(CI_GUARD_EXPECTED_IDS)
                and len(names) == len(set(names))
                and set(names) == set(CI_GUARD_EXPECTED_IDS))
    return (verified, 'CI_GUARD_TEST_IDENTITIES_VERIFIED' if verified
            else 'CI_GUARD_TEST_IDENTITIES_UNEXPECTED')

# SHA256 of the complete, reviewed CI-accounting implementation bytes.
# Test method names alone are insufficient: disabled test bodies can print OK.
# This literal pin is candidate-owned and does NOT constitute a trusted
# external signature. Independent diff/HUMAN review must approve pin updates.
CI_GUARD_SOURCE_PIN_SHA256 = "1e021d2028189689f04f6b2c59e12d16e026f0234ebb21d185668df0d689f7a2"

def check_ci_guard_source(root: Path) -> tuple[bool, str]:
    source = root / '.github' / 'scripts' / 'test_main_ci_contract.py'
    try:
        if source.is_symlink() or not source.is_file():
            return False, 'NOT_VERIFIED'
        raw = source.read_bytes()
        if len(raw) > 1024 * 1024:
            return False, 'NOT_VERIFIED'
        digest = hashlib.sha256(raw).hexdigest()
        return digest == CI_GUARD_SOURCE_PIN_SHA256, digest
    except (OSError, ValueError):
        return False, 'NOT_VERIFIED'

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
        base = Path(os.environ.get('RUNNER_TEMP', tempfile.gettempdir())).resolve(strict=True)
        temp = base / 'maestro-prep-main-ci'
        temp.mkdir(parents=True, exist_ok=True)
        env.update(TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp))
    source_before = check_ci_guard_source(ROOT) if kind == 'ci_guard_tests' else None
    # Only Windows requires per-test skip provenance. A summary count is not
    # evidence that the two known symlink-dependent cases were skipped.
    actual_args = list(args)
    if (kind == 'ci_guard_tests' or (kind == 'coordinator' and HOST_IS_WINDOWS)) and actual_args[-1:] == ['-q']:
        actual_args[-1] = '-v'
    # `-B` / PYTHONDONTWRITEBYTECODE disable cache WRITES, not cache READS.
    # A pre-existing, valid .pyc can execute unreviewed test bodies while
    # source SHA and unittest method names both still match. Assign each
    # subprocess a *new empty* cache prefix, outside the checkout. CPython
    # then ignores repository __pycache__ even if untrusted files remain.
    with tempfile.TemporaryDirectory(prefix='maestro-fresh-pycache-') as cache:
        proc = subprocess.run(
            [sys.executable, '-B', '-X', f'pycache_prefix={cache}', *actual_args],
            cwd=ROOT, env=env, timeout=180, capture_output=True, text=True,
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
        # unittest prints exactly one complete run-count line. A second line
        # can disguise missing test execution even when a later OK exists.
        run_counts = re.findall(
            r'(?m)^Ran (\d+) tests(?: in \d+(?:\.\d+)?s)?\r?$', proc.stderr)
        count = int(run_counts[0]) if len(run_counts) == 1 else 0
        skips = re.search(r'OK \(skipped=(\d+)\)', proc.stderr)
        details.update(tests=count, skipped=int(skips.group(1)) if skips else 0)
        # Keep the CI self-check floor equal to the actually retained
        # security/accounting test inventory (R1.13:20, R1.14:23). A stale
        # floor of seven silently allowed thirteen required tests to vanish.
        minimum = {
            'coordinator': 79, 'component': 70, 'release_tests': 6,
            'external_gate_tests': 9, 'ci_guard_tests': 34,
        }.get(kind, 70)
        allowed_skips = ((0 if importlib.util.find_spec('jsonschema') is not None else 5) +
                         (1 if HOST_IS_WINDOWS else 0)) if kind == 'component' else 0
        passed = passed and details['skipped'] == allowed_skips
        # Contradictory or multiple unittest summary lines must never be
        # counted as a successful test run merely because one says OK.
        summary = re.findall(r'(?m)^(?:OK(?: \(skipped=\d+\))?|FAILED(?: \([^\r\n]+\))?)\r?$', proc.stderr)
        passed = (passed and len(run_counts) == 1 and count >= minimum
                  and len(summary) == 1 and summary[0].startswith('OK'))
        if kind == 'component':
            verified, reason = check_component_receipt(proc.stdout, count, details['skipped'])
            details['skip_inventory_status'] = reason
            passed = passed and verified
        if kind == 'ci_guard_tests':
            verified, reason = check_ci_guard_trace(proc.stderr, count)
            details['test_identity_status'] = reason
            source_after = check_ci_guard_source(ROOT)
            details['source_pin_status'] = (
                'CI_GUARD_SOURCE_BYTES_VERIFIED'
                if source_before is not None and source_before[0]
                and source_after[0] and source_before[1] == source_after[1]
                else 'CI_GUARD_SOURCE_PIN_MISMATCH'
            )
            passed = passed and verified and details['source_pin_status'] == 'CI_GUARD_SOURCE_BYTES_VERIFIED'
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
