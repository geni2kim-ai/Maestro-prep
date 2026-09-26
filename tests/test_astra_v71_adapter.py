"""Only synthetic, pin-checked stub tests for the official Astra v7.1 adapter.

The real node-approved Astra-Prep validator was not transported or executed.
These tests exercise connector selection, byte pinning, subprocess result
handling, identity checking, gap escalation, and O-Prep coexistence.
"""
import copy
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from test_maestro import Fixture, HASH
from maestro_prep.coordinator import ContractError, check_lock

STUB = b'''# SYNTHETIC ONLY - NOT THE ASTRA-PREP VALIDATOR
import json, sys
p=json.load(open(sys.argv[1],encoding="utf-8"))
if p.get("force_stub_fail"):
    print("FAIL: synthetic stub rejected plan")
    sys.exit(1)
print("parser: synthetic-json")
print("python: synthetic-test")
print("OK: pre-work plan is valid.")
'''


class OfficialAstraV71AdapterTests(Fixture):
    def setUp(self):
        super().setUp()
        self.bundle=self.tmp/'node_approved_astra'; self.bundle.mkdir()
        for sub in ('scripts','schemas','profiles','references'):
            (self.bundle/sub).mkdir()
        self.astra=self.bundle/'SKILL.md'
        self.astra.write_text('SYNTHETIC ASTRA V7.1 APPROVED SKILL, NOT PRODUCTION')
        self.script=self.bundle/'scripts/validate_prework.py'; self.script.write_bytes(STUB)
        self.schema=self.bundle/'schemas/prework-plan.schema.json'; self.schema.write_text('{"title":"synthetic stub"}')
        self.profile=self.bundle/'profiles/ai-maestro.md'; self.profile.write_text('synthetic profile')
        (self.bundle/'references/evidence-model.md').write_text('synthetic E/R evidence model')
        (self.bundle/'references/domain-checks.md').write_text('synthetic domain preflight rules')
        self.lock['astra']={
            'skill_sha256':HASH(self.astra.read_bytes()),
            'approved_version_label':'v7.1-approved-SYNTHETIC',
            'official_v71':{
                'validator_sha256':HASH(self.script.read_bytes()),
                'schema_sha256':HASH(self.schema.read_bytes()),
                'profile_sha256':HASH(self.profile.read_bytes()),
                'manifest_sha256':'0'*64,
            }}
        self.resign_manifest()
        receipt=json.loads((self.root/self.plan_rel).read_text())
        receipt['astra_skill_sha256']=self.lock['astra']['skill_sha256']
        self.write_json(self.plan_rel,receipt)
        self.plan={
            'work_unit': self.work['work_unit'], 'actor': self.work['node_id'],
            'generated_at': self.work['captured_at_utc'], 'baseline_id':'synthetic-one-baseline',
            'starting_candidate': {'type':'doc','ref':'synthetic','sha256':'1'*64},
            'starting_point_readback': {'candidate_path':'synthetic','candidate_sha256':'1'*64,
                                       'points_at_candidate':True,'git_state':{'kind':'non-git','declaration':'synthetic'}},
            'requirements': [{'id':'R-1','text':'synthetic test','implementation':'module',
                              'module':None,'target':{'evidence_level':'E2','review_independence':'R1'},
                              'reachable':True,'capability_decision':None,'accept_as_open_end_state':None}],
            'forecast': {'best_reachable_cell':'E2/R1','dispositions':['CANDIDATE_READY'],
                         'raise_with_caller':[]}}
        self.work['baseline_id']='synthetic-one-baseline'
        self.work['baseline_sha256']='1'*64
        self.plan_file='prework-plan.json'
        self.sync_plan()

    def sync_plan(self):
        data=json.dumps(self.plan,ensure_ascii=False,sort_keys=True).encode()
        (self.root/self.plan_file).write_bytes(data)
        rec=json.loads((self.root/self.plan_rel).read_text())
        rec['plan_sha256']=HASH(data);rec['plan_file']=self.plan_file
        self.write_json(self.plan_rel,rec)

    def resign_manifest(self):
        """Fixture owner pin: synthetic-only, never representative of node authority."""
        paths=['SKILL.md','scripts/validate_prework.py',
               'schemas/prework-plan.schema.json','profiles/ai-maestro.md',
               'references/evidence-model.md','references/domain-checks.md']
        files={rel:HASH((self.bundle/rel).read_bytes()) for rel in paths}
        aggregate=HASH(''.join(f'{rel}  {files[rel]}\n' for rel in sorted(files)).encode())
        manifest={'file_count':len(files),'files':files,'bundle_aggregate_sha256':aggregate}
        data=json.dumps(manifest,sort_keys=True).encode()
        (self.bundle/'CANDIDATE_HASHES.json').write_bytes(data)
        self.lock['astra']['official_v71']['manifest_sha256']=HASH(data)

    def invoke(self,**kw):
        kw.setdefault('astra_bundle_root',self.bundle)
        return super().invoke(**kw)

    def test_synthetic_validator_pass_is_never_deployment_authority(self):
        x=self.invoke()
        self.assertEqual(x['next_action'],'BOUND_CANDIDATE_CHECKS_PASSED')
        self.assertEqual(x['astra_official_validation']['status'],'LOCAL_VALIDATOR_PASS_NOT_APPROVAL')
        self.assertEqual(x['astra_official_validation']['target_cells'],{'E2/R1':1})
        self.assertFalse(x['host_mutation_authorized'])

    def test_official_label_without_pins_must_hold(self):
        del self.lock['astra']['official_v71']
        self.assertIn('HOLD_ASTRA_OFFICIAL_PIN_MISSING', self.invoke()['issue_codes'])

    def test_official_bundle_absent_must_hold(self):
        self.assertIn('HOLD_ASTRA_BUNDLE_MISSING',self.invoke(astra_bundle_root=None)['issue_codes'])

    def test_validator_script_changed_must_hold(self):
        self.script.write_text('print("OK: pre-work plan is valid.")')
        self.assertIn('ASTRA_MANIFEST_FILE_MISMATCH', self.invoke()['issue_codes'])

    def test_schema_changed_must_hold(self):
        self.schema.write_text('{"synthetic":"tampered"}')
        self.assertIn('ASTRA_MANIFEST_FILE_MISMATCH', self.invoke()['issue_codes'])

    def test_profile_changed_must_hold(self):
        self.profile.write_text('tampered')
        self.assertIn('ASTRA_MANIFEST_FILE_MISMATCH', self.invoke()['issue_codes'])

    def test_bundle_root_skill_must_be_same_as_pinned_skill(self):
        elsewhere=self.tmp/'unrelated.md';elsewhere.write_bytes(self.astra.read_bytes())
        self.assertIn('HOLD_ASTRA_SKILL_PATH_NOT_BUNDLE',self.invoke(astra_skill_path=elsewhere)['issue_codes'])

    def test_plan_identity_is_checked_even_when_validator_stub_accepts(self):
        self.plan['actor']='other-node';self.sync_plan()
        self.assertIn('HOLD_ASTRA_OFFICIAL_PLAN_IDENTITY',self.invoke()['issue_codes'])

    def test_open_forecast_is_not_candidate_ready(self):
        self.plan['forecast']['dispositions']=['CAPABILITY_GAP'];self.sync_plan()
        x=self.invoke()
        self.assertIn('HOLD_ASTRA_FORECAST_GAPS_OPEN',x['issue_codes'])
        self.assertEqual(x['astra_official_validation']['forecast_dispositions'],['CAPABILITY_GAP'])

    def test_future_plan_generated_at_must_hold(self):
        self.plan['generated_at']='2026-09-26T00:00:00Z';self.sync_plan()
        self.assertIn('HOLD_ASTRA_OFFICIAL_PLAN_FUTURE',self.invoke()['issue_codes'])

    def test_validator_failure_even_when_capture_claims_ready(self):
        self.script.write_bytes(STUB.replace(b'if p.get("force_stub_fail"):',b'if True:'))
        self.lock['astra']['official_v71']['validator_sha256']=HASH(self.script.read_bytes())
        self.resign_manifest()
        self.assertIn('HOLD_ASTRA_OFFICIAL_VALIDATOR_FAILED',self.invoke()['issue_codes'])

    def test_validator_success_exit_without_terminal_marker_is_hold(self):
        self.script.write_bytes(b'print("NO PASS MARKER")')
        self.lock['astra']['official_v71']['validator_sha256']=HASH(self.script.read_bytes())
        self.resign_manifest()
        self.assertIn('HOLD_ASTRA_OFFICIAL_VALIDATOR_FAILED',self.invoke()['issue_codes'])

    def test_timeout_fails_closed(self):
        with patch('maestro_prep.coordinator.subprocess.run',side_effect=subprocess.TimeoutExpired('synthetic',15)):
            self.assertIn('HOLD_ASTRA_VALIDATOR_TIMEOUT',self.invoke()['issue_codes'])

    def test_json_sidecar_required(self):
        self.plan_file='prework-plan.yaml';self.sync_plan()
        self.assertIn('HOLD_ASTRA_OFFICIAL_JSON_SIDECAR_REQUIRED',self.invoke()['issue_codes'])

    def test_bad_producer_capture_must_not_execute_official_validator(self):
        rec=json.loads((self.root/self.plan_rel).read_text())
        rec['astra_skill_sha256']='f'*64
        self.write_json(self.plan_rel,rec)
        with patch('maestro_prep.coordinator.subprocess.run') as run:
            result=self.invoke()
        run.assert_not_called()
        self.assertIn('HOLD_ASTRA_RECEIPT_BINDING',result['issue_codes'])
        self.assertEqual(result['astra_official_validation']['status'],'NOT_RUN_INVALID_CAPTURE')

    def test_official_adapter_requires_external_baseline_pin(self):
        del self.work['baseline_id'];del self.work['baseline_sha256']
        self.assertIn('HOLD_ASTRA_BASELINE_PIN_REQUIRED',self.invoke()['issue_codes'])

    def test_official_adapter_rejects_stale_candidate_baseline(self):
        self.work['baseline_sha256']='e'*64
        self.assertIn('HOLD_ASTRA_BASELINE_MISMATCH',self.invoke()['issue_codes'])

    def test_no_plan_receipt_only_requests_astra(self):
        x=self.invoke(astra_plan_receipt_rel=None)
        self.assertEqual(x['next_action'],'CALL_ASTRA_PREP')
        self.assertEqual(x['astra_official_validation']['status'],'PINNED_BUNDLE_PRESENT_PLAN_PENDING')

    def test_invalid_lock_pins_must_fail_before_running(self):
        del self.lock['astra']['official_v71']['schema_sha256']
        with self.assertRaises(ContractError):check_lock(self.lock)

    def test_read_only_does_not_invoke_official_validator(self):
        self.work.update(intent='READ_ONLY',plan_sha256=None);self.refresh_route()
        x=self.invoke(astra_skill_path=None,astra_plan_receipt_rel=None,astra_bundle_root=None)
        self.assertEqual(x['astra_official_validation']['status'],'NOT_RUN')
        self.assertEqual(x['next_action'],'BOUND_CANDIDATE_CHECKS_PASSED')

    def test_o_prep_stop_overrides_official_validator_success(self):
        self.signal['evidence']['manifest_verified']=False
        x=self.invoke()
        self.assertEqual(x['astra_official_validation']['status'],'LOCAL_VALIDATOR_PASS_NOT_APPROVAL')
        self.assertEqual(x['next_action'],'HOLD_SOURCE')

if __name__=='__main__':unittest.main()
