"""Synthetic CLI policy-lock pin and local host clock controls."""
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path
from maestro_prep.coordinator import ContractError, read_json_owner_pinned
import test_astra_v71_adapter as astra_fixture

PKG = Path(__file__).resolve().parents[1]
class LockCLIRegressionTests(unittest.TestCase):
    def setUp(self):
        self.f=astra_fixture.OfficialAstraV71AdapterTests('runTest');self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.lockpath=self.f.tmp/'lock.json'
        self.workpath=self.f.tmp/'work.json'
        self.signalpath=self.f.tmp/'signal.json'
        self.lockpath.write_text(json.dumps(self.f.lock))
        self.workpath.write_text(json.dumps(self.f.work))
        self.signalpath.write_text(json.dumps(self.f.signal))
        self.args=[sys.executable,'-m','maestro_prep.cli','decide',
                   '--lock',str(self.lockpath),'--work',str(self.workpath),
                   '--o-signal',str(self.signalpath),'--receipt-index',str(self.f.index),
                   '--evidence-root',str(self.f.root),'--astra-skill',str(self.f.astra),
                   '--astra-plan-receipt',self.f.plan_rel,
                   '--astra-bundle-root',str(self.f.bundle),
                   '--leonardo-route',self.f.route_rel]
    def call(self,*extra):
        c=subprocess.run(self.args+list(extra),cwd=PKG,capture_output=True,text=True,timeout=20)
        return c,json.loads(c.stdout)

    def test_real_mode_refuses_self_reported_policy_lock(self):
        proc,out=self.call()
        self.assertEqual(proc.returncode,2)
        self.assertEqual(out['issue_code'],'OWNER_LOCK_PIN_REQUIRED')

    def test_supplied_wrong_digest_refused_before_decision(self):
        proc,out=self.call('--approved-lock-sha256','0'*64)
        self.assertEqual(proc.returncode,2)
        self.assertEqual(out['issue_code'],'OWNER_LOCK_BYTES_MISMATCH')

    def test_owner_pin_read_is_byte_exact(self):
        pin=hashlib.sha256(self.lockpath.read_bytes()).hexdigest()
        value=read_json_owner_pinned(self.lockpath,pin)
        self.assertEqual(value,self.f.lock)
        self.lockpath.write_text(self.lockpath.read_text()+'\n')
        with self.assertRaisesRegex(ContractError,'OWNER_LOCK_BYTES_MISMATCH'):
            read_json_owner_pinned(self.lockpath,pin)

    def test_offline_replay_is_annotated_as_unverified(self):
        proc,out=self.call('--offline-replay')
        self.assertEqual(proc.returncode,0)
        self.assertEqual(out['lock_binding'],'SELF_REPORTED_OFFLINE_ONLY')
        self.assertEqual(out['clock_binding'],'SELF_REPORTED_OFFLINE_ONLY')
        self.assertEqual(out['simulated_next_action'],'BOUND_CANDIDATE_CHECKS_PASSED')
        self.assertEqual(out['next_action'],'OFFLINE_REPLAY_NON_AUTHORIZING')
        self.assertFalse(out['host_mutation_authorized'])

    def test_out_of_band_pin_does_not_waive_real_clock(self):
        pin=hashlib.sha256(self.lockpath.read_bytes()).hexdigest()
        proc,out=self.call('--approved-lock-sha256',pin)
        # Static 2026-09-25 00Z fixture is stale relative to this session's
        # later 2026-09-25 UTC host clock. Assert gating only, no wall-clock
        # time dependency in the test.
        self.assertEqual(out['lock_binding'],'OWNER_SUPPLIED_SHA256_LOCAL_BYTES_ONLY')
        self.assertEqual(out['clock_binding'],'LOCAL_PROCESS_CLOCK_ONLY')
        self.assertIn(proc.returncode,(0,2))
        self.assertFalse(out['host_mutation_authorized'])

if __name__=='__main__':unittest.main()
