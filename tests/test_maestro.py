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
        self.task=b'SYNTHETIC LEONARDO TASK';self.policy=b'SYNTHETIC LEONARDO POLICY';self.route=b'{"route":"synthetic"}'
        self.work={'schema':'MAESTRO_PREP_WORK_V1','work_unit':'SYNTHETIC-UNIT-TEST','node_id':'synthetic',
                   'captured_at_utc':TS,'stage':'PLAN','intent':'NEW_PLAN','task_sha256':HASH(self.task),'plan_sha256':None}
        self.lock={'schema':'MAESTRO_PREP_LOCK_V1','astra':{'skill_sha256':HASH(self.astra.read_bytes()),'approved_version_label':'SYNTHETIC-ONLY'},
                   'leonardo':{'router_version':'SYNTHETIC-ROUTER','policy_sha256':HASH(self.policy)}}
        self.signal=fresh_signal('PLAN')
        self.signal.update(work_unit=self.work['work_unit'],node_id=self.work['node_id'],captured_at_utc=TS)
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
            'schema':'ASTRA_PREP_CAPTURE_V1','work_unit':self.work['work_unit'],'node_id':self.work['node_id'],
            'astra_skill_sha256':self.lock['astra']['skill_sha256'],'plan_sha256':HASH(plan),
            'plan_file':self.plan_file,'status':'READY_FOR_LOCAL_CANDIDATE_WORK','captured_at_utc':TS})
    def add_role(self,role,data):
        name='receipts/'+role+'.bin';p=self.root/name;p.parent.mkdir(exist_ok=True);p.write_bytes(data)
        self.receipts.append({'role':role,'path':name,'sha256':HASH(data),'size_bytes':len(data)})
    def save_index(self):
        idx={'schema':'O_PREP_RECEIPT_INDEX_V1','work_unit':self.work['work_unit'],
             'node_id':self.work['node_id'],'stage':self.work['stage'],'captured_at_utc':TS,'receipts':self.receipts}
        self.index.write_text(json.dumps(idx))
    def write_json(self,name,obj): (self.root/name).write_text(json.dumps(obj))
    def invoke(self,**kw):
        opts={'astra_skill_path':self.astra,'astra_plan_receipt_rel':self.plan_rel,'leonardo_route_rel':self.route_rel}
        opts.update(kw)
        return decide(copy.deepcopy(self.work),copy.deepcopy(self.lock),copy.deepcopy(self.signal),self.index,self.root,**opts)

class CoordinatorTests(Fixture):
    def test_pinned_external_4_way_synthetic_pass_is_not_authorization(self):
        x=self.invoke();self.assertEqual(x['next_action'],'BOUND_CANDIDATE_CHECKS_PASSED')
        self.assertTrue(x['o_prep_gate_invoked']);self.assertFalse(x['host_mutation_authorized'])
        self.assertEqual(x['astra_execution'],'NOT_RUN_BY_MAESTRO');self.assertEqual(x['leonardo_execution'],'NOT_RUN_BY_MAESTRO')
    def test_absent_astra_new_work_is_hold(self):
        x=self.invoke(astra_skill_path=None)
        self.assertEqual(x['next_action'],'HOLD_INTEGRATION')
        self.assertIn('HOLD_PLAN_MODULE_MISSING',x['issue_codes'])
    def test_astra_missing_read_only_plan_is_not_blocked(self):
        self.work.update(intent='READ_ONLY',plan_sha256=None)
        x=self.invoke(astra_skill_path=None,astra_plan_receipt_rel=None)
        self.assertEqual(x['next_action'],'BOUND_CANDIDATE_CHECKS_PASSED')
    def test_astra_present_no_plan_receipt_prompts_no_automatic_execution(self):
        x=self.invoke(astra_plan_receipt_rel=None)
        self.assertEqual(x['next_action'],'CALL_ASTRA_PREP')
        self.assertEqual(x['astra_execution'],'NOT_RUN_BY_MAESTRO')
    def test_reuse_requires_plan_pin(self):
        self.work['intent']='REUSE_PLAN'
        with self.assertRaises(ContractError):check_work(self.work)
        self.work['plan_sha256']=HASH((self.root/self.plan_file).read_bytes())
        self.assertEqual(self.invoke()['next_action'],'BOUND_CANDIDATE_CHECKS_PASSED')
    def test_reuse_wrong_plan_pin_is_hold(self):
        self.work.update(intent='REUSE_PLAN',plan_sha256='a'*64)
        self.assertIn('HOLD_ASTRA_PLAN_REVISION_CHANGED',self.invoke()['issue_codes'])
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
        self.assertEqual(self.invoke()['next_action'],'BOUND_CANDIDATE_CHECKS_PASSED')
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

class ReplayTests(unittest.TestCase):
    def test_prior_twenty_synthetic_cases_match_current_pinned_o(self):
        x=run();self.assertEqual((x['scenario_count'],x['o_prep_cases_matched'],x['naive_choice_skips']), (20,20,11))
        self.assertEqual(x['c_compulsory_gate_skips_when_available'],0)
    def test_vendor_source_pin(self): self.assertEqual(vendor_module().VERSION,'0.3.0-prep')

if __name__=='__main__':unittest.main()
