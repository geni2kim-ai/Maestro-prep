"""Repository CI file and isolated offline/non-authority contract."""
import unittest
from pathlib import Path
from tools.ci_check import JOBS

ROOT=Path(__file__).resolve().parents[1]
class CIDefinitionTests(unittest.TestCase):
    def test_workflow_uses_readonly_permission_and_pinned_actions(self):
        doc=(ROOT/'.github/workflows/candidate-ci.yml').read_text(encoding='utf-8')
        self.assertIn('contents: read',doc)
        self.assertIn('persist-credentials: false',doc)
        self.assertIn('pull_request:',doc)
        self.assertIn("'fix/**'",doc)
        self.assertNotIn('pull_request_target:',doc)
        self.assertNotIn('secrets.',doc)
        self.assertIn('54b0444002613309a6a47af281aa70f69202bd6d',doc)
        self.assertIn('pytest==9.0.3',doc)
    def test_runner_replays_every_pinned_synthetic_guard(self):
        jobs={name for name,_,_ in JOBS}
        self.assertEqual(jobs,{'package_integrity','public_privacy','vendor_pin','maestro_tests','o_prep_tests',
            'prior_replay','connection_replay','rebind_replay','origin_replay','manifest_chronology_replay',
            'deployment_preflight_regressions','external_archive_synthetic_intake'})
if __name__=='__main__':unittest.main()
