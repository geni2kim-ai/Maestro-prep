"""Public CI checks only the source and isolated offline tests."""
import unittest
from pathlib import Path
from tools.ci_check import JOBS
ROOT = Path(__file__).resolve().parents[1]

class CIDefinitionTests(unittest.TestCase):
    def test_readonly_cross_platform_ci_without_historical_external_source_audit(self):
        doc = (ROOT / '.github/workflows/candidate-ci.yml').read_text(encoding='utf-8')
        self.assertIn('contents: read', doc)
        self.assertIn('persist-credentials: false', doc)
        self.assertIn('pull_request:', doc)
        self.assertIn("'fix/**'", doc)
        self.assertNotIn('pull_request_target:', doc)
        self.assertNotIn('secrets.', doc)
        self.assertIn('ubuntu-latest', doc)
        self.assertIn('windows-latest', doc)
        self.assertIn("'3.11'", doc)
        self.assertIn("'3.13'", doc)
        self.assertNotIn('public-astra', doc)
        self.assertNotIn('https://github.com/', doc)

    def test_all_offline_guards_remain(self):
        jobs = {name for name, _, _ in JOBS}
        self.assertEqual(jobs, {
            'package_integrity', 'public_privacy', 'vendor_pin', 'maestro_tests',
            'o_prep_tests', 'prior_replay', 'connection_replay', 'rebind_replay',
            'origin_replay', 'manifest_chronology_replay',
            'deployment_preflight_regressions', 'external_archive_synthetic_intake',
        })

if __name__ == '__main__':
    unittest.main()
