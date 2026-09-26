"""Adversarial offline replays of Astra/Leonardo handoff boundary.

Not actual Leonardo or official node Astra execution; uses a pinned synthetic
Astra validator stub to exercise Maestro's input binding.
"""
import json
import subprocess
import unittest
from unittest.mock import patch
from pathlib import Path

import test_astra_v71_adapter as astra_fixture
from test_maestro import HASH


class OriginRouteTests(unittest.TestCase):
    def setUp(self):
        f=astra_fixture.OfficialAstraV71AdapterTests('runTest')
        f.setUp(); self.addCleanup(f.doCleanups);self.f=f

    def _setup_reuse(self):
        f=self.f
        # Immutable archived origin artifacts must exist BEFORE the current
        # phase rewrites the current router_output/index.
        original_output=f.root/'receipts/origin_router_output.json'
        original_capture=f.root/'receipts/origin_route_capture.json'
        original_output.write_bytes(f.route)
        original_capture.write_bytes((f.root/f.route_rel).read_bytes())
        capture=json.loads((f.root/f.plan_rel).read_text())
        capture.update(schema='ASTRA_PREP_CAPTURE_V3',
                       origin_route_output_file='receipts/origin_router_output.json',
                       origin_route_capture_file='receipts/origin_route_capture.json')
        f.write_json(f.plan_rel,capture)
        f.work.update(intent='REUSE_PLAN',stage='EXECUTE',plan_sha256=HASH((f.root/f.plan_file).read_bytes()))
        f.signal['stage']='EXECUTE'
        f.refresh_route();f.save_index()
        return f

    def test_historical_v2_receipt_cannot_reuse_unverified_origin(self):
        f=self.f
        f.work.update(intent='REUSE_PLAN',stage='EXECUTE',plan_sha256=HASH((f.root/f.plan_file).read_bytes()))
        f.signal['stage']='EXECUTE';f.refresh_route();f.save_index()
        old=json.loads((f.root/f.plan_rel).read_text())
        old['origin_route_output_sha256']='f'*64
        f.write_json(f.plan_rel,old)
        r=f.invoke()
        self.assertIn('HOLD_ASTRA_REUSE_ORIGIN_PROOF_REQUIRED',r['issue_codes'])
        self.assertNotEqual(r['next_action'],'BOUND_CANDIDATE_CHECKS_PASSED')

    def test_reuse_archived_origin_from_real_bytes_is_bounded_candidate(self):
        f=self._setup_reuse()
        r=f.invoke()
        self.assertEqual(r['next_action'],'BOUND_CANDIDATE_CHECKS_PASSED')
        self.assertFalse(r['host_mutation_authorized'])

    def test_reuse_wrong_origin_sha_is_hold(self):
        f=self._setup_reuse()
        cap=json.loads((f.root/f.plan_rel).read_text());cap['origin_route_output_sha256']='f'*64
        f.write_json(f.plan_rel,cap)
        self.assertIn('HOLD_ASTRA_ORIGIN_BYTES_MISMATCH',f.invoke()['issue_codes'])

    def test_reuse_wrong_original_task_is_hold(self):
        f=self._setup_reuse()
        origin=json.loads((f.root/'receipts/origin_router_output.json').read_text())
        origin['task_sha256']='0'*64
        (f.root/'receipts/origin_router_output.json').write_text(json.dumps(origin))
        cap=json.loads((f.root/f.plan_rel).read_text())
        cap['origin_route_output_sha256']=HASH((f.root/'receipts/origin_router_output.json').read_bytes())
        f.write_json(f.plan_rel,cap)
        old=json.loads((f.root/'receipts/origin_route_capture.json').read_text())
        old['routing_output_sha256']=cap['origin_route_output_sha256'];old['task_sha256']='0'*64
        (f.root/'receipts/origin_route_capture.json').write_text(json.dumps(old))
        self.assertIn('HOLD_ASTRA_ORIGIN_CAPTURE_BINDING',f.invoke()['issue_codes'])

    def test_reuse_origin_output_wrong_task_even_if_capture_claims_current_task(self):
        f=self._setup_reuse()
        origin=f.root/'receipts/origin_router_output.json'
        c=json.loads(origin.read_text());c['task_sha256']='0'*64
        origin.write_text(json.dumps(c))
        rec=json.loads((f.root/f.plan_rel).read_text())
        rec['origin_route_output_sha256']=HASH(origin.read_bytes())
        f.write_json(f.plan_rel,rec)
        original_capture=f.root/'receipts/origin_route_capture.json'
        evidence=json.loads(original_capture.read_text())
        evidence['routing_output_sha256']=rec['origin_route_output_sha256']
        original_capture.write_text(json.dumps(evidence))
        self.assertIn('HOLD_ASTRA_ORIGIN_OUTPUT_BINDING',f.invoke()['issue_codes'])

    def test_reuse_original_capture_wrong_route_version_is_hold(self):
        f=self._setup_reuse()
        origin=f.root/'receipts/origin_route_capture.json'
        c=json.loads(origin.read_text());c['router_version']='UNAPPROVED-ROUTER'
        origin.write_text(json.dumps(c))
        self.assertIn('HOLD_ASTRA_ORIGIN_CAPTURE_BINDING',f.invoke()['issue_codes'])

    def test_reuse_original_route_without_astra_skill_is_hold(self):
        f=self._setup_reuse()
        origin=f.root/'receipts/origin_router_output.json'
        c=json.loads(origin.read_text());c['mandatory_skills']=['o-prep']
        origin.write_text(json.dumps(c))
        cap=json.loads((f.root/f.plan_rel).read_text())
        cap['origin_route_output_sha256']=HASH(origin.read_bytes())
        f.write_json(f.plan_rel,cap)
        old=json.loads((f.root/'receipts/origin_route_capture.json').read_text())
        old['routing_output_sha256']=cap['origin_route_output_sha256']
        (f.root/'receipts/origin_route_capture.json').write_text(json.dumps(old))
        self.assertIn('HOLD_ASTRA_ORIGIN_PLAN_BRANCH',f.invoke()['issue_codes'])

    def test_reuse_origin_path_escape_is_hold(self):
        f=self._setup_reuse()
        cap=json.loads((f.root/f.plan_rel).read_text());cap['origin_route_output_file']='../../private.json'
        f.write_json(f.plan_rel,cap)
        self.assertIn('HOLD_ASTRA_ORIGIN_REFERENCE_INVALID',f.invoke()['issue_codes'])

    def test_v3_new_plan_origin_must_be_current_route(self):
        f=self._setup_reuse()
        f.work.update(intent='NEW_PLAN',stage='PLAN',plan_sha256=None)
        f.signal['stage']='PLAN'
        f.refresh_route();f.save_index()
        f.refresh_route(overrides={'mandatory_skills':['o-prep','astra-prep','different']})
        r=f.invoke()
        self.assertIn('HOLD_ASTRA_ORIGIN_CURRENT_ROUTE_MISMATCH',r['issue_codes'])

    def test_validator_stdout_contradictory_success_and_fail_is_hold(self):
        f=self.f
        mock=subprocess.CompletedProcess([],0,b'parser: synthetic-json\npython: synthetic-test\nFAIL: C10 invalid\nOK: pre-work plan is valid.\n',b'')
        with patch('maestro_prep.coordinator.subprocess.run',return_value=mock):r=f.invoke()
        self.assertIn('HOLD_ASTRA_VALIDATOR_OUTPUT_CONTRACT',r['issue_codes'])
        self.assertNotEqual(r['next_action'],'BOUND_CANDIDATE_CHECKS_PASSED')

    def test_validator_success_marker_with_nonempty_stderr_is_hold(self):
        f=self.f
        mock=subprocess.CompletedProcess([],0,b'parser: synthetic-json\npython: synthetic-test\nOK: pre-work plan is valid.\n',b'ERROR: C10\n')
        with patch('maestro_prep.coordinator.subprocess.run',return_value=mock):r=f.invoke()
        self.assertIn('HOLD_ASTRA_VALIDATOR_OUTPUT_CONTRACT',r['issue_codes'])

    def test_validator_success_marker_replayed_twice_is_hold(self):
        f=self.f
        mock=subprocess.CompletedProcess([],0,b'parser: synthetic-json\npython: synthetic-test\nOK: pre-work plan is valid.\nOK: pre-work plan is valid.\n',b'')
        with patch('maestro_prep.coordinator.subprocess.run',return_value=mock):r=f.invoke()
        self.assertIn('HOLD_ASTRA_VALIDATOR_OUTPUT_CONTRACT',r['issue_codes'])

if __name__=='__main__':unittest.main()

# Host-clock replay assertions: tests invoke the deterministic API with a pinned
# host time; the interactive CLI uses its current process clock by default.
class LocalClockBindingTests(unittest.TestCase):
    def setUp(self):
        f=astra_fixture.OfficialAstraV71AdapterTests('runTest')
        f.setUp();self.addCleanup(f.doCleanups);self.f=f

    def test_identically_backdated_route_and_work_cannot_replay_as_current(self):
        from datetime import datetime, timezone
        from maestro_prep.coordinator import decide
        f=self.f
        # Baseline v0.2.2 accepted a jointly self-reported old work+route.
        kw=dict(astra_skill_path=f.astra,astra_plan_receipt_rel=f.plan_rel,
                leonardo_route_rel=f.route_rel,astra_bundle_root=f.bundle)
        old=decide(f.work,f.lock,f.signal,f.index,f.root,**kw)
        self.assertEqual(old['next_action'],'BOUND_CANDIDATE_CHECKS_PASSED')
        self.assertEqual(old['clock_binding'],'SELF_REPORTED_OFFLINE_ONLY')
        observed=datetime(2026,9,25,12,0,tzinfo=timezone.utc)
        now=decide(f.work,f.lock,f.signal,f.index,f.root,observed_now=observed,**kw)
        self.assertEqual(now['next_action'],'HOLD_INTEGRATION')
        self.assertIn('HOLD_WORK_SNAPSHOT_STALE_AGAINST_HOST',now['issue_codes'])
        self.assertEqual(now['clock_binding'],'LOCAL_PROCESS_CLOCK_ONLY')

    def test_snapshot_future_beyond_skew_rejected(self):
        from datetime import datetime, timezone
        from maestro_prep.coordinator import decide
        f=self.f
        observed=datetime(2026,9,24,23,0,tzinfo=timezone.utc)
        result=decide(f.work,f.lock,f.signal,f.index,f.root,astra_skill_path=f.astra,
            astra_plan_receipt_rel=f.plan_rel,leonardo_route_rel=f.route_rel,
            astra_bundle_root=f.bundle,observed_now=observed)
        self.assertIn('HOLD_WORK_SNAPSHOT_FUTURE_AGAINST_HOST',result['issue_codes'])
