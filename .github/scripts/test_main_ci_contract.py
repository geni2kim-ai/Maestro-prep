"""Synthetic CI accounting contract checks; no external runner touched."""
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

PATH = Path(__file__).with_name("main_ci.py")
SPEC = importlib.util.spec_from_file_location("main_ci_under_test", PATH)
CI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CI)

class CIAccountingTests(unittest.TestCase):
    def ci_guard_trace(self, names):
        return (''.join(f'{name} (test_main_ci_contract.CIAccountingTests.{name}) ... ok\n'
                        for name in names)
                + f'Ran {len(names)} tests in 0.006s\nOK\n')

    def simulate(self, name, kind, text):
        if kind == "component" and CI.os.name == "nt":
            text = "VENDOR_PLATFORM_EXCEPTION\n" + text
        stdout = ''
        if kind == 'component':
            # Honest fixture for existing count tests. Dedicated negative cases
            # below modify identities and require fail-closed handling.
            import re
            count = re.search(r'Ran (\d+) tests', text)
            stdout = 'MAESTRO_COMPONENT_TEST_RESULT_V1=' + json.dumps({
                'schema': 'MAESTRO_COMPONENT_TEST_RESULT_V1',
                'tests_run': int(count.group(1)) if count else 0,
                'errors': 0, 'failures': 0, 'was_successful': True,
                'skipped': CI.expected_component_skips(),
            }) + '\n'
        fake = subprocess.CompletedProcess(["python"], 0, stdout=stdout, stderr=text)
        with patch.object(CI.subprocess, "run", return_value=fake):
            return CI.run_case(name, ["-m", "unittest"], kind)
    def test_windows_coordinator_skip_records_verified_cases_without_pass(self):
        stderr = ("test_external_skill_symlink_rejected (test_maestro.CoordinatorTests) ... skipped 'Symlinks restricted'\n"
                  "test_symlinked_evidence_root_ancestor_is_rejected (test_maestro.JunctionGuardTests) ... skipped 'Symlinks restricted'\n"
                  'Ran 79 tests\nOK (skipped=2)\n')
        with patch.object(CI, 'HOST_IS_WINDOWS', True):
            row = self.simulate('coordinator_tests', 'coordinator', stderr)
        self.assertFalse(row['passed'])
        self.assertEqual(row['platform_gaps'], ['COORDINATOR_SYMLINK_TESTS_SKIPPED'])

    def test_windows_coordinator_unrelated_skips_not_misattributed(self):
        stderr = ("test_unrelated (test_example.OtherTests) ... skipped 'Another reason'\n"
                  "test_other (test_example.OtherTests) ... skipped 'Another reason'\n"
                  'Ran 79 tests\nOK (skipped=2)\n')
        with patch.object(CI, 'HOST_IS_WINDOWS', True):
            row = self.simulate('coordinator_tests', 'coordinator', stderr)
        self.assertFalse(row['passed'])
        self.assertEqual(row['platform_gaps'], ['COORDINATOR_SKIP_CAUSE_UNVERIFIED'])

    def test_windows_coordinator_summary_without_verbose_is_unverified(self):
        with patch.object(CI, 'HOST_IS_WINDOWS', True):
            row = self.simulate('coordinator_tests', 'coordinator', 'Ran 79 tests\nOK (skipped=2)\n')
        self.assertFalse(row['passed'])
        self.assertEqual(row['platform_gaps'], ['COORDINATOR_SKIP_CAUSE_UNVERIFIED'])

    def test_windows_coordinator_same_expected_name_wrong_reason_unverified(self):
        stderr = ("test_external_skill_symlink_rejected (test_maestro.CoordinatorTests) ... skipped 'unexpected'\n"
                  'Ran 79 tests\nOK (skipped=1)\n')
        with patch.object(CI, 'HOST_IS_WINDOWS', True):
            row = self.simulate('coordinator_tests', 'coordinator', stderr)
        self.assertFalse(row['passed'])
        self.assertEqual(row['platform_gaps'], ['COORDINATOR_SKIP_CAUSE_UNVERIFIED'])

    def test_windows_coordinator_uses_verbose_mode_for_trace(self):
        fake = subprocess.CompletedProcess(['python'], 0, stdout='', stderr='Ran 79 tests\nOK\n')
        with patch.object(CI, 'HOST_IS_WINDOWS', True), patch.object(CI.subprocess, 'run', return_value=fake) as runner:
            CI.run_case('coordinator_tests', ['-m','unittest','discover','-s','tests','-q'], 'coordinator')
        self.assertEqual(runner.call_args.args[0][-1], '-v')

    def test_windows_unprivileged_vendor_is_not_approved_as_green(self):
        with patch.object(CI, 'HOST_IS_WINDOWS', True):
            row = self.simulate('public_component_tests', 'component',
                 'VENDOR_PLATFORM_GAP:WINDOWS_SYMLINK_PRIVILEGE_UNAVAILABLE:test_symlink_to_external_file_fails_closed\n'
                 'Ran 70 tests\nOK (skipped=3)\n')
        self.assertFalse(row['passed'])
        self.assertEqual(row['platform_gaps'], ['WINDOWS_SYMLINK_PRIVILEGE_UNAVAILABLE'])

    def test_fake_vendor_gap_without_skips_is_still_blocked(self):
        with patch.object(CI, 'HOST_IS_WINDOWS', True):
            row = self.simulate('public_component_tests', 'component',
                 'VENDOR_PLATFORM_GAP:WINDOWS_SYMLINK_PRIVILEGE_UNAVAILABLE:malicious\n'
                 'Ran 70 tests\nOK (skipped=1)\n')
        self.assertFalse(row['passed'])

    def test_component_opaque_skips_cannot_gain_a_green_by_count(self):
        # R1.12 incorrectly accepted a matching summary without test IDs.
        from unittest.mock import patch
        with patch.object(CI.importlib.util, 'find_spec', return_value=None):
            fake = subprocess.CompletedProcess(['python'], 0, stdout='',
                    stderr=f'Ran 70 tests\nOK (skipped={len(CI.expected_component_skips())})\n')
            with patch.object(CI.subprocess, 'run', return_value=fake):
                row = CI.run_case('public_component_tests', ['ignored'], 'component')
        self.assertFalse(row['passed'])
        self.assertEqual(row['skip_inventory_status'], 'COMPONENT_SKIP_INVENTORY_MISSING')

    def test_component_same_skip_count_wrong_identity_is_rejected(self):
        with patch.object(CI.importlib.util, 'find_spec', return_value=None):
            skipped = CI.expected_component_skips()
            skipped[0] = {'id':'SensitiveTests.test_critical_guard','reason':'optional package'}
            fake = subprocess.CompletedProcess(['python'], 0,
                    stdout='MAESTRO_COMPONENT_TEST_RESULT_V1='+json.dumps({
                        'schema':'MAESTRO_COMPONENT_TEST_RESULT_V1', 'tests_run':70,
                        'errors':0,'failures':0,'skipped':skipped,'was_successful':True})+'\n',
                    stderr=f'Ran 70 tests\nOK (skipped={len(skipped)})\n')
            with patch.object(CI.subprocess, 'run', return_value=fake):
                row=CI.run_case('public_component_tests', ['ignored'], 'component')
        self.assertFalse(row['passed'])
        self.assertEqual(row['skip_inventory_status'], 'COMPONENT_SKIP_IDENTITIES_UNEXPECTED')

    def test_component_skip_duplicate_does_not_substitute_required_case(self):
        with patch.object(CI.importlib.util, 'find_spec', return_value=None):
            skipped=CI.expected_component_skips()
            skipped[0]=skipped[1]
            fake=subprocess.CompletedProcess(['python'],0,
                    stdout='MAESTRO_COMPONENT_TEST_RESULT_V1='+json.dumps({
                        'schema':'MAESTRO_COMPONENT_TEST_RESULT_V1','tests_run':70,
                        'errors':0,'failures':0,'skipped':skipped,'was_successful':True})+'\n',
                    stderr=f'Ran 70 tests\nOK (skipped={len(skipped)})\n')
            with patch.object(CI.subprocess,'run',return_value=fake):
                row=CI.run_case('public_component_tests',['ignored'],'component')
        self.assertFalse(row['passed'])

    def test_component_receipt_with_wrong_summary_count_blocks(self):
        skipped=CI.expected_component_skips()
        fake=subprocess.CompletedProcess(['python'],0,
            stdout='MAESTRO_COMPONENT_TEST_RESULT_V1='+json.dumps({
                 'schema':'MAESTRO_COMPONENT_TEST_RESULT_V1','tests_run':71,
                 'errors':0,'failures':0,'skipped':skipped,'was_successful':True})+'\n',
            stderr='Ran 70 tests\nOK'+(f' (skipped={len(skipped)})' if skipped else '')+'\n')
        with patch.object(CI.subprocess,'run',return_value=fake):
            row=CI.run_case('public_component_tests',['ignored'],'component')
        self.assertFalse(row['passed'])
        self.assertEqual(row['skip_inventory_status'], 'COMPONENT_SKIP_INVENTORY_INCONSISTENT')

    def test_contradictory_coordinator_summary_is_not_green(self):
        fake=subprocess.CompletedProcess(['python'],0,stdout='',
              stderr='Ran 79 tests\nOK\nFAILED (failures=1)\n')
        with patch.object(CI.subprocess,'run',return_value=fake):
            row=CI.run_case('coordinator_tests',['ignored'],'coordinator')
        self.assertFalse(row['passed'])

    def test_component_clean_receipt_matches_known_optional_skips(self):
        with patch.object(CI.importlib.util, 'find_spec', return_value=None):
            row=self.simulate('public_component_tests','component',
                              f'Ran 70 tests\nOK (skipped={len(CI.expected_component_skips())})\n')
        self.assertTrue(row['passed'])
        self.assertEqual(row['skip_inventory_status'], 'COMPONENT_SKIP_IDENTITIES_VERIFIED')

    def test_removed_ci_accounting_tests_below_baseline_are_rejected(self):
        # Old minimum=7 accepted 7/20; current baseline is 23 tests.
        fake = subprocess.CompletedProcess(['python'], 0, stdout='',
                                           stderr='Ran 7 tests\nOK\n')
        with patch.object(CI.subprocess, 'run', return_value=fake):
            row = CI.run_case('ci_receipt_accounting_tests', ['ignored'], 'ci_guard_tests')
        self.assertFalse(row['passed'])
        self.assertEqual(row['tests'], 7)

    def test_conflicting_run_counts_even_with_single_ok_are_rejected(self):
        fake = subprocess.CompletedProcess(['python'], 0, stdout='',
                  stderr='Ran 79 tests\nRan 2 tests\nOK\n')
        with patch.object(CI.subprocess, 'run', return_value=fake):
            row = CI.run_case('coordinator_tests', ['ignored'], 'coordinator')
        self.assertFalse(row['passed'])
        self.assertEqual(row['tests'], 0)

    def test_ci_accounting_current_floor_runs_normally(self):
        fake = subprocess.CompletedProcess(['python'], 0, stdout='',
                                           stderr=self.ci_guard_trace(CI.CI_GUARD_EXPECTED_IDS))
        with patch.object(CI.subprocess, 'run', return_value=fake):
            row = CI.run_case('ci_receipt_accounting_tests', ['ignored'], 'ci_guard_tests')
        self.assertTrue(row['passed'])
        self.assertEqual(row['tests'], len(CI.CI_GUARD_EXPECTED_IDS))

    def test_ci_guard_replaced_required_identity_is_blocked(self):
        ids = list(CI.CI_GUARD_EXPECTED_IDS)
        ids[0] = 'test_replacement_dummy'
        fake = subprocess.CompletedProcess(['python'], 0, stdout='', stderr=self.ci_guard_trace(ids))
        with patch.object(CI.subprocess, 'run', return_value=fake):
            row = CI.run_case('ci_receipt_accounting_tests', ['ignored'], 'ci_guard_tests')
        self.assertFalse(row['passed'])
        self.assertEqual(row['test_identity_status'], 'CI_GUARD_TEST_IDENTITIES_UNEXPECTED')

    def test_ci_guard_no_names_with_matching_count_is_blocked(self):
        fake = subprocess.CompletedProcess(['python'], 0, stdout='',
                  stderr=f'Ran {len(CI.CI_GUARD_EXPECTED_IDS)} tests\nOK\n')
        with patch.object(CI.subprocess, 'run', return_value=fake):
            row = CI.run_case('ci_receipt_accounting_tests', ['ignored'], 'ci_guard_tests')
        self.assertFalse(row['passed'])
        self.assertEqual(row['test_identity_status'], 'CI_GUARD_TEST_IDENTITIES_UNEXPECTED')

    def test_ci_guard_duplicate_name_in_valid_count_is_blocked(self):
        ids = list(CI.CI_GUARD_EXPECTED_IDS)
        ids[0] = ids[1]
        fake = subprocess.CompletedProcess(['python'], 0, stdout='', stderr=self.ci_guard_trace(ids))
        with patch.object(CI.subprocess, 'run', return_value=fake):
            row = CI.run_case('ci_receipt_accounting_tests', ['ignored'], 'ci_guard_tests')
        self.assertFalse(row['passed'])
        self.assertEqual(row['test_identity_status'], 'CI_GUARD_TEST_IDENTITIES_UNEXPECTED')

    def test_ci_guard_exact_identity_inventory_is_accepted(self):
        fake = subprocess.CompletedProcess(['python'], 0, stdout='',
                  stderr=self.ci_guard_trace(CI.CI_GUARD_EXPECTED_IDS))
        with patch.object(CI.subprocess, 'run', return_value=fake):
            row = CI.run_case('ci_receipt_accounting_tests', ['ignored'], 'ci_guard_tests')
        self.assertTrue(row['passed'])
        self.assertEqual(row['test_identity_status'], 'CI_GUARD_TEST_IDENTITIES_VERIFIED')

    def test_all_skipped_coordinator_is_not_a_pass(self):
        item = self.simulate("coordinator_tests", "coordinator", "Ran 79 tests\nOK (skipped=79)\n")
        self.assertFalse(item["passed"])
    def test_clean_coordinator_with_no_skips_passes(self):
        item = self.simulate("coordinator_tests", "coordinator", "Ran 79 tests\nOK\n")
        self.assertTrue(item["passed"])
    def test_dropped_coordinator_regression_is_rejected(self):
        item = self.simulate("coordinator_tests", "coordinator", "Ran 78 tests\nOK\n")
        self.assertFalse(item["passed"])
    def test_dropped_public_component_regression_is_rejected(self):
        item = self.simulate("public_component_tests", "component", "Ran 69 tests\nOK (skipped=5)\n")
        self.assertFalse(item["passed"])
    def test_unexplained_public_component_skip_is_rejected(self):
        with patch.object(CI.importlib.util, "find_spec", return_value=None):
            item = self.simulate("public_component_tests", "component", "Ran 70 tests\nOK (skipped=0)\n")
        self.assertFalse(item["passed"])
    def test_installed_optional_schema_runs_all_without_skips(self):
        with patch.object(CI.importlib.util, "find_spec", return_value=object()):
            suffix = "OK (skipped=1)\n" if CI.os.name == "nt" else "OK\n"
            item = self.simulate("public_component_tests", "component", "Ran 70 tests\n" + suffix)
        self.assertTrue(item["passed"])
    def test_missing_optional_schema_requires_five_skips(self):
        with patch.object(CI.importlib.util, "find_spec", return_value=None):
            skipped = 6 if CI.os.name == "nt" else 5
            item = self.simulate("public_component_tests", "component", f"Ran 70 tests\nOK (skipped={skipped})\n")
        self.assertTrue(item["passed"])

if __name__ == "__main__":
    unittest.main()
