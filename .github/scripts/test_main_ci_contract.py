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
        if kind == "component" and CI.os.name == "nt":
            text = "VENDOR_PLATFORM_EXCEPTION\n" + text
        fake = subprocess.CompletedProcess(["python"], 0, stdout="", stderr=text)
        with patch.object(CI.subprocess, "run", return_value=fake):
            return CI.run_case(name, ["-m", "unittest"], kind)
    def test_all_skipped_coordinator_is_not_a_pass(self):
        item = self.simulate("coordinator_tests", "coordinator", "Ran 71 tests\nOK (skipped=71)\n")
        self.assertFalse(item["passed"])
    def test_clean_coordinator_with_no_skips_passes(self):
        item = self.simulate("coordinator_tests", "coordinator", "Ran 71 tests\nOK\n")
        self.assertTrue(item["passed"])
    def test_dropped_coordinator_regression_is_rejected(self):
        item = self.simulate("coordinator_tests", "coordinator", "Ran 70 tests\nOK\n")
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
