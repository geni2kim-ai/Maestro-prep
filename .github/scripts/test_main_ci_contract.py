"""Synthetic CI accounting contract checks; no external runner touched."""
import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

PATH = Path(__file__).with_name("main_ci.py")
SPEC = importlib.util.spec_from_file_location("main_ci_under_test", PATH)
CI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CI)

class CIAccountingTests(unittest.TestCase):
    def simulate(self, name, kind, text):
        fake = subprocess.CompletedProcess(["python"], 0, stdout="", stderr=text)
        with patch.object(CI.subprocess, "run", return_value=fake):
            return CI.run_case(name, ["-m", "unittest"], kind)
    def test_all_skipped_coordinator_is_not_a_pass(self):
        item = self.simulate("coordinator_tests", "coordinator", "Ran 41 tests\nOK (skipped=41)\n")
        self.assertFalse(item["passed"])
    def test_clean_coordinator_with_no_skips_passes(self):
        item = self.simulate("coordinator_tests", "coordinator", "Ran 41 tests\nOK\n")
        self.assertTrue(item["passed"])
    def test_dropped_coordinator_regression_is_rejected(self):
        item = self.simulate("coordinator_tests", "coordinator", "Ran 40 tests\nOK\n")
        self.assertFalse(item["passed"])
    def test_unexplained_public_component_skip_is_rejected(self):
        item = self.simulate("public_component_tests", "component", "Ran 61 tests\nOK (skipped=0)\n")
        self.assertFalse(item["passed"])

if __name__ == "__main__":
    unittest.main()
