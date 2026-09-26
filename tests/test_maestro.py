"""Synthetic-only cross-module, hostile-input, outage and isolation tests."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from maestro_prep.coordinator import (
    ContractError, check_work, check_lock, decide, read_json, vendor_module,verify_generic_file,
)
from tools.replay_simulation import run, fresh_signal

HASH=lambda x:hashlib.sha256(x).hexdigest()
TS='2026-09-25T00:00:00Z'

class Fixture(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.tmp=Path(t.name);self.root=self.tmp/'private';self.root.mkdir()
        self.astra=self.tmp/'approved_astra_skill.md';self.astra.write_bytes(b'SYNTHETIC-ONLY ASTRA-PLAN SKILL')
        self.task=b'SYNTHETIC LEONARDO TASK';self.policy=b'SYNTHETIC LEONARDO POLICY'
        self.work={'schema':'MAESTRO_PREP_WORK_V1','work_unit':'SYNTHETIC-UNIT-TEST','node_id':'synthetic',
                   'captured_at_utc':TS,'stage':'PLAN','intent':'NEW_PLAN','task_sha256':HASH(self.task),'plan_sha256':None}
        self.lock={'schema':'MAESTRO_PREP_LOCK_V1','astra':{'skill_sha256':HASH(self.astra.read_bytes()),'approved_version_label':'SYNTHETIC-ONLY'},
                   'leonardo':{'router_version':'SYNTHETIC-ROUTER','policy_sha256':HASH(self.policy)}}
        self.signal=fresh_signal('PLAN')
        self.signal.update(work_unit=self.work['work_unit'],node_id=self.work['node_id'],captured_at_utc=TS)
        self.route=json.dumps(self.normalized_route(),sort_keys=True).encode()
        self.receipts=[]
        for role,data in [('router_input',self.task),('router_policy',self.policy),('router_output',self.route)]:
            self.add_role(role,data)
        self.index=self.root/'receipt_index.json';self.save_index()
        self.route_rel='route_capture.json'
        self.write_json(self.route_rel,{
            'schema':'LEONARDO_ROUTE_CAPTURE_V1','work_unit':self.work['work_unit'],'node_id':self.work['node_id'],
            'router_version':'SYNTHETIC-ROUTER','task_sha256':HASH(self.task),'policy_sha256':HASH(self.policy),
            'routing_output_sha256':HASH(self.route),'exit_code':0,'execution_state':'READY','captured_at_utc':TS})
        self.plan_rel='astra_capture.json';self.plan_file='plan.json'
        plan=b'{"description":"synthetic only"}';(self.root/self.plan_file).write_bytes(plan)
        self.write_json(self.plan_rel,{
            'schema':'ASTRA_PREP_CAPTURE_V2','work_unit':self.work['work_unit'],'node_id':self.work['node_id'],
            'astra_skill_sha256':self.lock['astra']['skill_sha256'],'plan_sha256':HASH(plan),
            'plan_file':self.plan_file,'status':'READY_FOR_LOCAL_CANDIDATE_WORK','captured_at_utc':TS,
            'task_sha256':HASH(self.task),'origin_route_output_sha256':HASH(self.route)})
    def normalized_route(self):
        gates={'NEW_PLAN':'CALL_ASTRA_PREP','REPLAN':'CALL_ASTRA_PREP',
               'REUSE_PLAN':'REUSE_PINNED_PLAN','READ_ONLY':'NO_NEW_PLAN'}
        skills=['o-prep']+(['astra-prep'] if self.work['intent'] in {'NEW_PLAN','REPLAN'} else [])
        return {'schema':'LEONARDO_ROUTE_DECISION_V1','work_unit':self.work['work_unit'],
                'node_id':self.work['node_id'],'stage':self.work['stage'],'intent':self.work['intent'],
                'task_sha256':HASH(self.task),'policy_sha256':HASH(self.policy),
                'execution_state':'READY','mandatory_skills':skills,
                'plan_gate':gates[self.work['intent']],
                'review_required':self.work['stage'] in {'PUBLISH','CLOSE'}}
    def refresh_route(self, *, overrides=None):
        obj=self.normalized_route();obj.update(overrides or {})
        self.route=json.dumps(obj,sort_keys=True).encode()
        p=self.root/'receipts/router_output.bin';p.write_bytes(self.route)
        row=next(x for x in self.receipts if x['role']=='router_output')
        row.update(sha256=HASH(self.route),size_bytes=len(self.route))
        receipt=read_json(self.root/self.route_rel)
        receipt['routing_output_sha256']=HASH(self.route)
        self.write_json(self.route_rel,receipt)
        self.save_index()
    def add_role(self,role,data):
        name='receipts/'+role+'.bin';p=self.root/name;p.parent.mkdir(exist_ok=True);p.write_bytes(data)
        self.receipts.append({'role':role,'path':name,'sha256':HASH(data),'size_bytes':len(data)})
    def save_index(self):
        idx={'schema':'O_PREP_RECEIPT_INDEX_V1','work_unit':self.work['work_unit'],
             'node_id':self.work['node_id'],'stage':self.work['stage'],'captured_at_utc':self.work['captured_at_utc'],'receipts':self.receipts}
        self.index.write_text(json.dumps(idx))
    def write_json(self,name,obj): (self.root/name).write_text(json.dumps(obj))
    def invoke(self,**kw):
        opts={'astra_skill_path':self.astra,'astra_plan_receipt_rel':self.plan_rel,'leonardo_route_rel':self.route_rel}
        opts.update(kw)
        return decide(copy.deepcopy(self.work),copy.deepcopy(self.lock),copy.deepcopy(self.signal),self.index,self.root,**opts)

class CoordinatorTests(Fixture):
    def test_legacy_capture_without_official_validator_must_hold(self):
        x=self.invoke();self.assertEqual(x['next_action'],'HOLD_INTEGRATION')
        self.assertIn('HOLD_ASTRA_OFFICIAL_PIN_MISSING',x['issue_codes'])
        self.assertTrue(x['o_prep_gate_invoked']);self.assertFalse(x['host_mutation_authorized'])
        self.assertEqual(x['astra_execution'],'NOT_RUN_BY_MAESTRO');self.assertEqual(x['leonardo_execution'],'NOT_RUN_BY_MAESTRO')
    def test_absent_astra_new_work_is_hold(self):
        x=self.invoke(astra_skill_path=None)
        self.assertEqual(x['next_action'],'HOLD_INTEGRATION')
        self.assertIn('HOLD_PLAN_MODULE_MISSING',x['issue_codes'])
    def test_astra_missing_read_only_plan_is_not_blocked(self):
        self.work.update(intent='READ_ONLY',plan_sha256=None)
        self.refresh_route()
        x=self.invoke(astra_skill_path=None,astra_plan_receipt_rel=None)
        self.assertEqual(x['next_action'],'BOUND_CANDIDATE_CHECKS_PASSED')
    def test_missing_official_validator_prevents_unpinned_plan_call(self):
        x=self.invoke(astra_plan_receipt_rel=None)
        self.assertEqual(x['next_action'],'HOLD_INTEGRATION')
        self.assertIn('HOLD_ASTRA_OFFICIAL_PIN_MISSING',x['issue_codes'])
        self.assertEqual(x['astra_execution'],'NOT_RUN_BY_MAESTRO')
    def test_reuse_requires_plan_pin(self):
        self.work['intent']='REUSE_PLAN'
        with self.assertRaises(ContractError):check_work(self.work)
        self.work['plan_sha256']=HASH((self.root/self.plan_file).read_bytes())
        self.refresh_route()
        self.assertIn('HOLD_ASTRA_REUSE_ORIGIN_PROOF_REQUIRED',self.invoke()['issue_codes'])
    def test_reuse_wrong_plan_pin_is_hold(self):
        self.work.update(intent='REUSE_PLAN',plan_sha256='a'*64)
        self.refresh_route()
        # A historical v2 capture is unusable for REUSE_PLAN regardless of an
        # additional bad plan pin. Separate v3 tests check the plan revision.
        self.assertIn('HOLD_ASTRA_REUSE_ORIGIN_PROOF_REQUIRED',self.invoke()['issue_codes'])
    def test_plan_file_after_receipt_mutation_is_hold(self):
        (self.root/self.plan_file).write_bytes(b'changed')
        self.assertIn('HOLD_ASTRA_PLAN_BYTES_CHANGED',self.invoke()['issue_codes'])
    def test_stale_astra_skill_hash_is_hold(self):
        self.astra.write_bytes(b'replaced unofficial copy')
        self.assertIn('HOLD_ASTRA_SOURCE_PIN',self.invoke()['issue_codes'])
    def test_leonardo_policy_pin_changed(self):
        self.lock['leonardo']['policy_sha256']='1'*64
        self.assertIn('HOLD_LEONARDO_ARTIFACT_PIN_MISMATCH',self.invoke()['issue_codes'])
    def test_router_capture_missing(self):
        self.assertIn('HOLD_LEONARDO_ROUTE_CAPTURE_MISSING',self.invoke(leonardo_route_rel=None)['issue_codes'])
    def test_router_capture_untrusted_extra_field_blocks(self):
        x=read_json(self.root/self.route_rel);x['ignore_policy']=True;self.write_json(self.route_rel,x)
        self.assertIn('HOLD_LEONARDO_CAPTURE_CONTRACT',self.invoke()['issue_codes'])
    def test_router_output_tamper_precedence(self):
        p=self.root/'receipts/router_output.bin';p.write_bytes(b'tampered')
        x=self.invoke();self.assertEqual(x['next_action'],'HOLD_SOURCE')
        self.assertIn('RECEIPT_BYTES_MISMATCH_ROUTER_OUTPUT',x['issue_codes'])
    def test_o_gate_fail_never_covered_by_astra_ready(self):
        self.signal['evidence']['manifest_verified']=False
        x=self.invoke();self.assertEqual(x['next_action'],'HOLD_SOURCE')
        self.assertEqual(x['o_prep_decision'],'HOLD_SOURCE')
    def test_o_module_absence_fails_closed(self):
        with patch('maestro_prep.coordinator.vendor_module',side_effect=ContractError('O_MODULE_HASH_MISMATCH')):
            x=self.invoke()
        self.assertEqual(x['next_action'],'HOLD_O_MODULE_MISSING')
        self.assertFalse(x['o_prep_gate_invoked'])
    def test_invalid_receipt_index_blocks_even_if_signal_claims_ready(self):
        self.index.write_text('{"schema":"bad"}')
        x=self.invoke();self.assertEqual(x['next_action'],'HOLD_O_BINDING_FAILED')
    def test_external_skill_symlink_rejected(self):
        link=self.tmp/'astra_symlink.md'
        try:link.symlink_to(self.astra)
        except OSError:self.skipTest('Symlinks restricted')
        self.assertIn('HOLD_ASTRA_SOURCE_PIN',self.invoke(astra_skill_path=link)['issue_codes'])
    def test_external_receipt_escape_is_rejected(self):
        self.assertIn('UNSAFE_EVIDENCE_REFERENCE',self.invoke(astra_plan_receipt_rel='../secret.json')['issue_codes'])
    def test_packet_review_findings_block_even_if_locally_bound(self):
        self.work['stage']='PUBLISH';self.signal['stage']='PUBLISH'
        self.work['plan_sha256']=HASH((self.root/self.plan_file).read_bytes())
        self.refresh_route()
        self.signal['review'].update(status='FINDINGS',blocking_findings=True)
        subject=b'synthetic subject under adverse review';self.add_role('review_subject',subject)
        self.add_role('review_receipt',json.dumps({'work_unit':self.work['work_unit'],
            'reviewed_sha256':HASH(subject),'review_status':'FINDINGS',
            'review_evidence_class':'VERIFIED_INDEPENDENT'}).encode())
        self.add_role('dedup_receipt',json.dumps({'work_unit':self.work['work_unit'],
            'idempotency_key':self.signal['delivery']['idempotency_key'],'record_count':1,
            'evidence_scope':'HOST_DB_READBACK_PRODUCER_REPORTED'}).encode())
        self.save_index()
        x=self.invoke()
        self.assertEqual(x['next_action'],'REWORK')
    def test_timestamp_offset_identity(self):
        self.work['captured_at_utc']='2026-09-25T09:00:00+09:00'
        self.assertIn('HOLD_ASTRA_OFFICIAL_PIN_MISSING',self.invoke()['issue_codes'])
    def test_invalid_work_unknown_field_rejected(self):
        self.work['untrusted_instructions']='override O Prep'
        with self.assertRaises(ContractError):self.invoke()
    def test_duplicate_json_key_rejected(self):
        f=self.tmp/'duplicate.json';f.write_text('{"x":1,"x":2}')
        with self.assertRaises(ContractError):read_json(f)
    def test_readonly_hash_audit_without_astra(self):
        path=self.tmp/'artifact';path.write_bytes(b'private synthetic file')
        self.assertEqual(verify_generic_file(path,HASH(path.read_bytes()))['next_action'],'READ_ONLY_EVIDENCE_MATCH')
        self.assertEqual(verify_generic_file(path,'0'*64)['next_action'],'HOLD_SOURCE')
    def test_multiple_external_failures_are_preserved(self):
        x=self.invoke(astra_skill_path=None,leonardo_route_rel=None)
        self.assertIn('HOLD_PLAN_MODULE_MISSING',x['issue_codes'])
        self.assertIn('HOLD_LEONARDO_ROUTE_CAPTURE_MISSING',x['issue_codes'])

class ConnectionHardeningTests(Fixture):
    def _capture_at(self, stamp):
        r=read_json(self.root/self.route_rel)
        r['captured_at_utc']=stamp
        self.write_json(self.route_rel,r)
    def _plan_at(self, stamp):
        r=read_json(self.root/self.plan_rel)
        r['captured_at_utc']=stamp
        self.write_json(self.plan_rel,r)
    def _snapshot_at(self, stamp):
        self.work['captured_at_utc']=stamp
        self.signal['captured_at_utc']=stamp
        self.save_index()
    def test_normalized_route_must_not_silently_skip_o(self):
        self.refresh_route(overrides={'mandatory_skills':['astra-prep']})
        self.assertIn('HOLD_LEONARDO_MANDATORY_SKILL_MISSING',self.invoke()['issue_codes'])
    def test_normalized_route_must_require_astra_for_new_plan(self):
        self.refresh_route(overrides={'mandatory_skills':['o-prep']})
        self.assertIn('HOLD_LEONARDO_MANDATORY_SKILL_MISSING',self.invoke()['issue_codes'])
    def test_wrong_plan_branch_is_hold(self):
        self.refresh_route(overrides={'plan_gate':'REUSE_PINNED_PLAN'})
        self.assertIn('HOLD_LEONARDO_WRONG_PLAN_BRANCH',self.invoke()['issue_codes'])
    def test_forged_route_ready_not_enough_without_schema(self):
        self.refresh_route(overrides={'schema':'ANOTHER_SCHEMA'})
        self.assertIn('HOLD_LEONARDO_ROUTE_OUTPUT_CONTRACT',self.invoke()['issue_codes'])
    def test_wrong_work_identity_in_output_is_hold(self):
        self.refresh_route(overrides={'node_id':'other-node'})
        self.assertIn('HOLD_LEONARDO_ROUTE_OUTPUT_BINDING',self.invoke()['issue_codes'])
    def test_output_policy_is_bound_to_work_lock(self):
        self.refresh_route(overrides={'policy_sha256':'f'*64})
        self.assertIn('HOLD_LEONARDO_ROUTE_OUTPUT_BINDING',self.invoke()['issue_codes'])
    def test_duplicate_mandatory_skill_is_hold(self):
        self.refresh_route(overrides={'mandatory_skills':['o-prep','o-prep','astra-prep']})
        self.assertIn('HOLD_LEONARDO_MANDATORY_SKILL_MISSING',self.invoke()['issue_codes'])
    def test_publishing_must_require_review_in_route(self):
        self.work['stage']='PUBLISH'; self.signal['stage']='PUBLISH'
        self.work['plan_sha256']=HASH((self.root/self.plan_file).read_bytes())
        self.refresh_route(overrides={'review_required':False})
        self.assertIn('HOLD_LEONARDO_REVIEW_GATE_OMITTED',self.invoke()['issue_codes'])
    def test_review_required_must_be_boolean(self):
        self.refresh_route(overrides={'review_required':'false'})
        self.assertIn('HOLD_LEONARDO_REVIEW_GATE_OMITTED',self.invoke()['issue_codes'])
    def test_route_snapshot_may_precede_current_evaluation(self):
        self._capture_at('2026-09-24T23:00:00Z')
        self._plan_at('2026-09-25T00:30:00Z')
        self._snapshot_at('2026-09-25T01:00:00Z')
        x=self.invoke()
        self.assertNotIn('HOLD_ASTRA_PLAN_PREDATES_ROUTE',x['issue_codes'])
        self.assertIn('HOLD_ASTRA_OFFICIAL_PIN_MISSING',x['issue_codes'])
    def test_route_capture_older_than_freshness_budget_is_held(self):
        self._capture_at('2026-09-24T17:00:00Z')
        self.assertIn('HOLD_LEONARDO_ROUTE_STALE',self.invoke()['issue_codes'])
    def test_future_route_is_held(self):
        self._capture_at('2026-09-25T01:00:00Z')
        self.assertIn('HOLD_LEONARDO_ROUTE_FROM_FUTURE',self.invoke()['issue_codes'])
    def test_new_plan_cannot_predate_route(self):
        self._capture_at('2026-09-24T23:30:00Z')
        self._plan_at('2026-09-24T23:00:00Z')
        self.assertIn('HOLD_ASTRA_PLAN_PREDATES_ROUTE',self.invoke()['issue_codes'])
    def test_future_astra_plan_is_held(self):
        self._plan_at('2026-09-25T02:00:00Z')
        self.assertIn('HOLD_ASTRA_RECEIPT_FROM_FUTURE',self.invoke()['issue_codes'])
    def test_multiple_failures_keep_all_diagnostics_even_if_o_fails(self):
        self.signal['evidence']['manifest_verified']=False
        x=self.invoke(astra_skill_path=None,leonardo_route_rel=None)
        self.assertEqual(x['next_action'],'HOLD_SOURCE')
        self.assertIn('MANIFEST_UNVERIFIED',x['issue_codes'])
        self.assertIn('HOLD_PLAN_MODULE_MISSING',x['issue_codes'])
        self.assertIn('HOLD_LEONARDO_ROUTE_CAPTURE_MISSING',x['issue_codes'])
    def test_missing_o_module_still_reports_missing_external_modules(self):
        with patch('maestro_prep.coordinator.vendor_module',side_effect=ContractError('O_MODULE_HASH_MISMATCH')):
            x=self.invoke(astra_skill_path=None,leonardo_route_rel=None)
        self.assertEqual(x['next_action'],'HOLD_O_MODULE_MISSING')
        self.assertIn('HOLD_PLAN_MODULE_MISSING',x['issue_codes'])
        self.assertIn('HOLD_LEONARDO_ROUTE_CAPTURE_MISSING',x['issue_codes'])
    def test_all_later_stages_require_plan_pin(self):
        for stage in ['EXECUTE','PUBLISH','CLOSE']:
            w=copy.deepcopy(self.work);w['stage']=stage
            with self.subTest(stage=stage),self.assertRaisesRegex(ContractError,'LATER_STAGE_NEEDS_PLAN_PIN'):
                check_work(w)
    def test_malformed_nested_lock_is_stable_contract_error(self):
        self.lock['astra']=[]
        with self.assertRaisesRegex(ContractError,'ASTRA_LOCK_INVALID'):
            self.invoke()
    def test_later_stage_json_schema_requires_plan_pin(self):
        schema=json.loads((Path(__file__).resolve().parents[1]/'schemas'/'work.schema.json').read_text())
        self.assertTrue(any('EXECUTE' in str(rule) and 'plan_sha256' in str(rule) for rule in schema['allOf']))
    def test_symlinked_evidence_ancestor_is_rejected(self):
        link = self.tmp / 'linked-root'
        try: link.symlink_to(self.tmp, target_is_directory=True)
        except OSError: self.skipTest('Symlinks restricted')
        with self.assertRaisesRegex(ContractError,'EVIDENCE_ROOT_ANCESTOR_SYMLINK'):
            decide(copy.deepcopy(self.work),copy.deepcopy(self.lock),copy.deepcopy(self.signal),
                   link/'private'/'receipt_index.json',link/'private',astra_skill_path=self.astra,
                   astra_plan_receipt_rel=self.plan_rel,leonardo_route_rel=self.route_rel)
    def test_component_claimed_ready_does_not_prove_runtime(self):
        self.refresh_route()
        x=self.invoke()
        self.assertEqual(x['astra_execution'],'NOT_RUN_BY_MAESTRO')
        self.assertEqual(x['leonardo_execution'],'NOT_RUN_BY_MAESTRO')
        self.assertFalse(x['host_mutation_authorized'])

class ReplayTests(unittest.TestCase):
    def test_prior_twenty_synthetic_cases_match_current_pinned_o(self):
        x=run();self.assertEqual((x['scenario_count'],x['o_prep_cases_matched'],x['naive_choice_skips']), (20,20,11))
        self.assertEqual(x['c_compulsory_gate_skips_when_available'],0)
    def test_connection_failure_replay(self):
        from tools.run_connection_scenarios import run as replay
        result = replay()
        self.assertEqual((result['cases'], result['matched']), (8, 8))
    def test_vendor_source_pin(self): self.assertEqual(vendor_module().VERSION,'0.3.0-prep')

if __name__=='__main__':unittest.main()
