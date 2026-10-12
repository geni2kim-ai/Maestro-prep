"""Self-tests for the vendored CodeDiff policy SHADOW, no external reviewers."""
from __future__ import annotations
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SHADOW = Path(__file__).with_name("codediff_shadow.py")
spec = importlib.util.spec_from_file_location("codediff_shadow_under_test", SHADOW)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CodediffIntegrationTests(unittest.TestCase):
    def test_exact_original_policy_pins(self):
        pinned, official = module.trusted_source_snapshot()
        self.assertEqual(pinned["codediff"]["version"], "2.5")
        self.assertTrue(callable(official.classify_paths))
        self.assertFalse(pinned["leonardo"]["promoted_to_mandatory_runtime"])

    def test_protected_path_overlay_and_upstream(self):
        _, engine = module.trusted_source_snapshot()
        cfg = engine.load_yaml(module.VENDOR / "protected-paths.yml")
        merged = {k: list(cfg.get(k, [])) + module.OVERLAY.get(k, [])
                  for k in module.OVERLAY}
        classified = engine.classify_paths([
            "maestro_prep/coordinator.py", ".github/workflows/candidate-ci.yml",
            "components/o_prep_v0_3/src/o_prep.py",
        ], merged)
        self.assertIn("maestro_prep/coordinator.py", classified["human_floor"])
        self.assertIn(".github/workflows/candidate-ci.yml", classified["governance"])
        self.assertIn(".github/scripts/main_ci.py", engine.classify_paths(
            [".github/scripts/main_ci.py"], merged)["human_floor"])
        self.assertIn("components/o_prep_v0_3/src/o_prep.py", classified["adversarial_floor"])

    def test_sha_immovable_metadata_rejected(self):
        with self.assertRaisesRegex(ValueError, "UNPINNED_GIT_REFERENCE"):
            module.analyze(Path("."), "HEAD", "branch")

    def test_renames_include_both_paths(self):
        with patch.object(module, "git", return_value="R100\0old.py\0new.py\0"):
            paths = module.git_status(Path("."), "a"*40, "b"*40)
        self.assertEqual(paths, ["new.py", "old.py"])

    def test_leonardo_r230_not_promoted_and_shadow_no_authority(self):
        pin = json.loads(module.PIN_PATH.read_text("utf-8"))
        self.assertFalse(pin["leonardo"]["promoted_to_mandatory_runtime"])
        self.assertEqual(pin["codediff"]["mode"], "SHADOW")
        self.assertFalse(pin["codediff"]["trusted_textdiff_sensor"])


if __name__ == "__main__":
    unittest.main()
