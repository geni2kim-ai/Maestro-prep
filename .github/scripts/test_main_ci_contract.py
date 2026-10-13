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

    def test_ci_guard_source_pin_matches_current_checkout(self):
        matched, digest = CI.check_ci_guard_source(CI.ROOT)
        self.assertTrue(matched)
        self.assertEqual(digest, CI.CI_GUARD_SOURCE_PIN_SHA256)

    def test_ci_guard_source_pin_detects_neutralized_body(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / '.github' / 'scripts' / 'test_main_ci_contract.py'
            target.parent.mkdir(parents=True)
            source = PATH.read_bytes()
            target.write_bytes(source.replace(
                b'def test_contradictory_coordinator_summary_is_not_green',
                b'def test_contradictory_coordinator_summary_is_noop', 1))
            matched, digest = CI.check_ci_guard_source(root)
            self.assertFalse(matched)
            self.assertNotEqual(digest, CI.CI_GUARD_SOURCE_PIN_SHA256)

    def test_ci_guard_source_pin_blocks_missing_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            matched, digest = CI.check_ci_guard_source(Path(folder))
        self.assertFalse(matched)
        self.assertEqual(digest, 'NOT_VERIFIED')

    def test_ci_guard_source_pin_blocks_symlink_source(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / '.github' / 'scripts' / 'test_main_ci_contract.py'
            target.parent.mkdir(parents=True)
            target.write_bytes(PATH.read_bytes())
            # Symlink simulation is deterministic and does not ask Windows
            # users to create a privileged real reparse point.
            with patch.object(Path, 'is_symlink', autospec=True,
                              side_effect=lambda p: p == target):
                matched, digest = CI.check_ci_guard_source(root)
        self.assertFalse(matched)
        self.assertEqual(digest, 'NOT_VERIFIED')

    def test_ci_launch_ignores_inherited_python_environment(self):
        # Genuine child prefix and safe startup switches must be supplied
        # even when ambient PYTHONPATH contains unreviewed modules.
        with patch.dict(CI.os.environ, {'PYTHONPATH':'untrusted-path',
                                       'PYTHONPYCACHEPREFIX':'untrusted-cache'}):
            with patch.object(CI.subprocess, 'run', return_value=subprocess.CompletedProcess(
                ['python'], 0, stdout='', stderr='Ran 79 tests\nOK\n')) as runner:
                row=CI.run_case('coordinator_tests',['ignored'],'coordinator')
        self.assertTrue(row['passed'])
        argv=runner.call_args.args[0]
        self.assertEqual(argv[1:5], ['-E', '-s', '-B', '-X'])
        self.assertTrue(argv[5].startswith('pycache_prefix='))

    def test_pythonpath_unittest_shadow_does_not_run_in_isolated_child(self):
        # Actual CPython child import; only a harmless temp-file marker is
        # written by the simulated untrusted unittest module. No live
        # services, host secrets or privileged filesystem nodes are touched.
        import os
        import tempfile
        with tempfile.TemporaryDirectory(prefix='maestro-shadow-import-') as tmp:
            root=Path(tmp)
            shadow=root/'untrusted'/'unittest'
            shadow.mkdir(parents=True)
            (shadow/'__init__.py').write_text(
                'from pathlib import Path\n'
                'Path(__import__("os").environ["MAESTRO_SIMULATED_MARKER"]).write_text("EXECUTED")\n',
                encoding='utf-8')
            marker=root/'marker.txt'
            env=dict(os.environ,PYTHONPATH=str(root/'untrusted'),
                     MAESTRO_SIMULATED_MARKER=str(marker),
                     PYTHONDONTWRITEBYTECODE='1')
            args=['-B','-c','import unittest; print(unittest.__file__)']
            old=subprocess.run([CI.sys.executable,*args],env=env,cwd=root,
                               capture_output=True,text=True,check=True)
            self.assertIn(str(shadow),old.stdout)
            self.assertEqual(marker.read_text(),'EXECUTED')
            marker.unlink()
            new=subprocess.run([CI.sys.executable,'-E','-s',*args],env=env,cwd=root,
                               capture_output=True,text=True,check=True)
            self.assertNotIn(str(shadow),new.stdout)
            self.assertFalse(marker.exists())

    def test_ci_launch_forces_python_cache_prefix(self):
        # Even when user sets a hostile inherited prefix, -X overrides it.
        observed=[]
        def fake_run(argv, **kwargs):
            self.assertEqual(argv[1:5], ['-E', '-s', '-B', '-X'])
            self.assertTrue(argv[5].startswith('pycache_prefix='))
            cache=Path(argv[5].split('=',1)[1])
            self.assertTrue(cache.is_dir())
            self.assertEqual(list(cache.iterdir()), [])
            observed.append(str(cache))
            self.assertEqual(kwargs['env']['PYTHONDONTWRITEBYTECODE'], '1')
            return subprocess.CompletedProcess(argv,0,stdout='',stderr='Ran 79 tests\nOK\n')
        with patch.dict(CI.os.environ, {'PYTHONPYCACHEPREFIX': 'inherited-untrusted-prefix'}), patch.object(CI.subprocess,'run', side_effect=fake_run):
            item=CI.run_case('coordinator_tests',['ignored'],'coordinator')
        self.assertTrue(item['passed'])
        self.assertEqual(len(observed),1)

    def test_cache_prefix_is_fresh_for_each_child(self):
        seen=[]
        def fake_run(argv, **kwargs):
            seen.append(argv[5])
            return subprocess.CompletedProcess(argv,0,stdout='',stderr='Ran 79 tests\nOK\n')
        with patch.object(CI.subprocess,'run',side_effect=fake_run):
            first=CI.run_case('coordinator_tests',['ignored'],'coordinator')
            second=CI.run_case('coordinator_tests',['ignored'],'coordinator')
        self.assertTrue(first['passed'] and second['passed'])
        self.assertEqual(len(seen),2)
        self.assertNotEqual(seen[0],seen[1])

    def test_isolated_cache_prevents_preexisting_pyc_execution(self):
        # Actual CPython import test, not a mocked subprocess result. Both
        # bytecode and source are harmless markers (no arbitrary commands).
        import importlib.util
        import marshal
        import struct
        import sys
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/'maestro_probe_module.py'
            source.write_text('VALUE = "SOURCE"\n', encoding='utf-8')
            stat=source.stat()
            # The outer CI runs with a private -X prefix. Construct the
            # *legacy default* __pycache__ path explicitly for the attack.
            with patch.object(sys, 'pycache_prefix', None):
                target=Path(importlib.util.cache_from_source(str(source)))
            target.parent.mkdir(parents=True,exist_ok=True)
            code=compile('VALUE = "POISON"\n',str(source),'exec')
            cache=(importlib.util.MAGIC_NUMBER
                   + struct.pack('<III',0,int(stat.st_mtime),stat.st_size)
                   + marshal.dumps(code))
            target.write_bytes(cache)
            env=dict(os.environ, PYTHONPATH=str(root), PYTHONDONTWRITEBYTECODE='1')
            probe='import maestro_probe_module; print(maestro_probe_module.VALUE)'
            vulnerable=subprocess.run([sys.executable,'-B','-c',probe],env=env,
                                      cwd=root,capture_output=True,text=True,check=True)
            self.assertEqual(vulnerable.stdout.strip(),'POISON')
            prefix=root/'empty-fresh-pycache'
            prefix.mkdir()
            safe=subprocess.run([sys.executable,'-B','-X',f'pycache_prefix={prefix}',
                                 '-c',probe],env=env,cwd=root,capture_output=True,
                                text=True,check=True)
            self.assertEqual(safe.stdout.strip(),'SOURCE')

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
