"""R1.19 Python environment-containment regressions; non-authoritative."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PATH = Path(__file__).with_name('main_ci.py')
SPEC = importlib.util.spec_from_file_location('maestro_main_ci_r119', PATH)
assert SPEC is not None and SPEC.loader is not None
CI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CI)

class ChildEnvironmentIsolationTests(unittest.TestCase):
    def test_run_case_strips_ambient_python_environment_before_child(self):
        fake = subprocess.CompletedProcess(['python'], 0, stdout='',
                                           stderr='Ran 79 tests\nOK\n')
        poison = {'PYTHONPATH': 'synthetic-untrusted-package-path',
                  'PYTHONHOME': 'synthetic-home',
                  'PYTHONUSERBASE': 'synthetic-user',
                  'PYTHONPYCACHEPREFIX': 'synthetic-pyc',
                  'PYTHONWARNINGS': 'ignore'}
        with patch.dict(CI.os.environ, poison):
            with patch.object(CI.subprocess, 'run', return_value=fake) as runner:
                receipt = CI.run_case('coordinator_tests', ['ignored'], 'coordinator')
        self.assertTrue(receipt['passed'])
        arguments = runner.call_args.args[0]
        self.assertEqual(arguments[1:5], ['-E', '-s', '-B', '-X'])
        child_env = runner.call_args.kwargs['env']
        for key in poison:
            self.assertNotIn(key, child_env)
        self.assertEqual(child_env['PYTHONDONTWRITEBYTECODE'], '1')

    def test_grandchild_shadow_import_before_after_environment_scrub(self):
        # Only a harmless module created inside a fresh temp directory.
        with tempfile.TemporaryDirectory(prefix='maestro-grandchild-') as temp:
            root = Path(temp)
            attacker = root / 'untrusted'
            attacker.mkdir()
            module = 'maestro_synthetic_grandchild_import'
            (attacker / (module + '.py')).write_text(
                'MARKER = "INJECTED"\n', encoding='utf-8')
            probe = ('import subprocess,sys; '
                     'r=subprocess.run([sys.executable,"-B","-c",'
                     '"import ' + module + ';print(' + module + '.MARKER)"],'
                     'capture_output=True,text=True); '
                     'print(r.returncode);print(r.stdout.strip())')
            argv = [sys.executable, '-E', '-s', '-B', '-c', probe]
            inherited = dict(os.environ, PYTHONPATH=str(attacker),
                             PYTHONDONTWRITEBYTECODE='1')
            baseline = subprocess.run(argv, cwd=root, env=inherited,
                                      capture_output=True, text=True, check=True)
            self.assertEqual(baseline.stdout.strip(), '0\nINJECTED')
            filtered = {key: value for key, value in inherited.items()
                        if not key.upper().startswith('PYTHON')}
            filtered['PYTHONDONTWRITEBYTECODE'] = '1'
            protected = subprocess.run(argv, cwd=root, env=filtered,
                                       capture_output=True, text=True, check=True)
            self.assertEqual(protected.stdout.strip(), '1')

if __name__ == '__main__':
    unittest.main()
