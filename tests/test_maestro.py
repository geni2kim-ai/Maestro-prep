"""Synthetic-only cross-module, hostile-input, outage and isolation tests."""
import copy
from contextlib import redirect_stdout
from io import StringIO
import hashlib
import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from maestro_prep import coordinator, cli
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
        # R3-shaped synthetic raw router contract; not a real Leonardo receipt.
        self.route=json.dumps({
            'schema_version': 'SYNTHETIC_ROUTER_CONTRACT_V1',
            'execution_state': 'READY_FOR_LOCAL_CANDIDATE_WORK',
            'candidate_work_allowed': True,
            'request': {'request_sha256': HASH(self.task)},
            'input_bindings': {'policy_sha256': HASH(self.policy)},
            'next_action': 'HANDOFF_TO_SELECTED_LOCAL_ROUTE',
            'guard': {'blocks': [], 'block_codes': [], 'block_details': [],
                      'candidate_only': True, 'local_only': True,
                      'tests_required': True, 'small_change_units_required': True,
                      'source_originals_immutable': True,
                      'network': 'FORBIDDEN', 'deployment': 'FORBIDDEN',
                      'external_actions': 'FORBIDDEN', 'credential_access': 'FORBIDDEN',
                      'production_mutation': 'FORBIDDEN'},
        }, sort_keys=True).encode('utf-8')
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


    def test_unhashable_work_stage_is_rejected_not_crashed(self):
        for bad in ([], {}, None, 4):
            with self.subTest(stage=bad):
                self.work['stage'] = bad
                with self.assertRaises(ContractError) as ctx:
                    self.invoke()
                self.assertEqual(str(ctx.exception), 'WORK_SCHEMA_OR_STAGE_INVALID')

    def test_unhashable_work_intent_is_rejected_not_crashed(self):
        for bad in ([], {}, None, 4):
            with self.subTest(intent=bad):
                self.work['intent'] = bad
                with self.assertRaises(ContractError) as ctx:
                    self.invoke()
                self.assertEqual(str(ctx.exception), 'WORK_INTENT_INVALID')

    def test_untrusted_nested_lock_shape_is_contract_error(self):
        for field in ('astra', 'leonardo'):
            for bad in ([], None, 123):
                with self.subTest(field=field, value=bad):
                    self.lock[field] = bad
                    with self.assertRaises(ContractError) as ctx:
                        self.invoke()
                    self.assertIn(str(ctx.exception), ('ASTRA_LOCK_INVALID', 'LEONARDO_LOCK_INVALID'))
                    self.setUp_lock_for_next_case(field)

    def setUp_lock_for_next_case(self, field):
        if field == 'astra':
            self.lock[field] = {'skill_sha256': HASH(self.astra.read_bytes()),
                                'approved_version_label': 'SYNTHETIC-ONLY'}
        else:
            self.lock[field] = {'router_version': 'SYNTHETIC-ROUTER',
                                'policy_sha256': HASH(self.policy)}

    def test_deeply_nested_json_returns_stable_hold_error(self):
        f = self.tmp / 'nested.json'
        f.write_text('{"x":' + '[' * 1200 + '0' + ']' * 1200 + '}')
        with self.assertRaises(ContractError) as ctx:
            read_json(f)
        self.assertEqual(str(ctx.exception), 'JSON_NESTING_LIMIT')

    def test_depth_marker_in_json_string_is_not_counted(self):
        f = self.tmp / 'bracket_string.json'
        f.write_text(json.dumps({'x': '[' * 1200 + ']' * 1200}))
        self.assertEqual(read_json(f)['x'], '[' * 1200 + ']' * 1200)

    def test_untrusted_vendor_type_error_fails_closed(self):
        with patch('maestro_prep.coordinator.vendor_module') as vendor:
            vendor.return_value.OPrepError = ValueError
            vendor.return_value.evaluate_bound_signal.side_effect = TypeError('hostile nested shape')
            result = self.invoke()
        self.assertEqual(result['next_action'], 'HOLD_O_BINDING_FAILED')
        self.assertFalse(result['host_mutation_authorized'])


    def test_vendor_unexpected_errors_always_hold(self):
        for klass in (AttributeError, IndexError, KeyError, TypeError, RuntimeError, RecursionError):
            with self.subTest(error=klass.__name__):
                with patch('maestro_prep.coordinator.vendor_module') as mock:
                    mock.return_value.evaluate_bound_signal.side_effect = klass('private-path')
                    result = self.invoke()
                self.assertEqual(result['next_action'], 'HOLD_O_BINDING_FAILED')
                self.assertFalse(result['host_mutation_authorized'])

    def test_vendor_malformed_response_holds(self):
        with patch('maestro_prep.coordinator.vendor_module') as mock:
            mock.return_value.evaluate_bound_signal.return_value = {'issues': None}
            self.assertEqual(self.invoke()['next_action'], 'HOLD_O_BINDING_FAILED')

    def test_vendor_import_unexpected_error_holds(self):
        with patch('maestro_prep.coordinator.vendor_module', side_effect=RuntimeError('private')):
            self.assertEqual(self.invoke()['next_action'], 'HOLD_O_MODULE_MISSING')

    def test_router_receipt_unhashable_role_rejected(self):
        data = read_json(self.index)
        data['receipts'][0]['role'] = []
        self.write_json('receipt_index.json', data)
        result = coordinator._route_binding(self.work, self.lock, self.root, self.index, self.route_rel)
        self.assertEqual(result, ['HOLD_O_INDEX_INVALID'])

    def test_extended_malformed_lock_matrix(self):
        for key in ('astra', 'leonardo'):
            for invalid in ({}, {'bogus': 1}, 'not-a-map'):
                with self.subTest(key=key, invalid=invalid):
                    self.lock[key] = invalid
                    with self.assertRaises(ContractError) as ctx:
                        self.invoke()
                    self.assertEqual(str(ctx.exception), 'ASTRA_LOCK_INVALID' if key == 'astra' else 'LEONARDO_LOCK_INVALID')
                    self.setUp_lock_for_next_case(key)

    def test_depth_256_257_mixed_boundary(self):
        f = self.tmp / 'depth.json'
        for n in (254, 255):
            f.write_text('{"x":' + '['*n + '0' + ']'*n + '}')
            self.assertIn('x', read_json(f))
        f.write_text('{"x":' + '['*256 + '0' + ']'*256 + '}')
        with self.assertRaises(ContractError) as ctx:
            read_json(f)
        self.assertEqual(str(ctx.exception), 'JSON_NESTING_LIMIT')
        mixed = {'outer': [{'inner': [42]}]}
        f.write_text(json.dumps(mixed))
        self.assertEqual(read_json(f), mixed)

    def test_escaped_brackets_quote_backslash_not_false_positive(self):
        f = self.tmp / 'quoted.json'
        item = {'text': ('literal [{()}] " quote and backslash ' + chr(92)) * 40}
        f.write_text(json.dumps(item))
        self.assertEqual(read_json(f), item)

    def test_huge_integer_json_raises_stable_contract_code(self):
        f = self.tmp / 'integer.json'
        f.write_text('{"value":' + '9'*5000 + '}')
        with self.assertRaises(ContractError) as ctx:
            read_json(f)
        self.assertEqual(str(ctx.exception), 'INVALID_JSON_SOURCE')

    def test_cli_large_integer_safe_code_exit_2(self):
        f = self.tmp / 'integer.json'
        f.write_text('{"value":' + '9'*5000 + '}')
        argv=['decide','--work',str(f),'--lock','x','--o-signal','x',
              '--receipt-index','x','--evidence-root','x']
        with redirect_stdout(StringIO()) as out:
            rc=cli.main(argv)
        self.assertEqual(rc,2)
        self.assertEqual(json.loads(out.getvalue())['issue_code'], 'INVALID_JSON_SOURCE')
        self.assertNotIn('Exceeds',out.getvalue())

    def test_cli_unexpected_errors_are_redacted(self):
        argv=['decide','--work','x','--lock','x','--o-signal','x',
              '--receipt-index','x','--evidence-root','x']
        for failure in (ValueError('SECRET:/path'), OSError('/secret/token'),
                        AttributeError('private'), IndexError('private')):
            with self.subTest(error=type(failure).__name__):
                with patch('maestro_prep.cli.read_json',side_effect=failure), \
                     redirect_stdout(StringIO()) as out:
                    rc=cli.main(argv)
                self.assertEqual(rc,2)
                self.assertEqual(json.loads(out.getvalue())['issue_code'],'MALFORMED_INPUT')
                self.assertNotIn('private',out.getvalue())
                self.assertNotIn('secret',out.getvalue().lower())

    def test_cli_contract_error_vocabulary_sanitized(self):
        argv=['decide','--work','x','--lock','x','--o-signal','x',
              '--receipt-index','x','--evidence-root','x']
        with patch('maestro_prep.cli.read_json',side_effect=ContractError('PRIVATE: /secret')), \
             redirect_stdout(StringIO()) as out:
            rc=cli.main(argv)
        self.assertEqual(rc,2)
        self.assertEqual(json.loads(out.getvalue())['issue_code'],'CONTRACT_INVALID')

    def test_cli_surrogate_escape_ascii_safe(self):
        argv=['decide','--work','x','--lock','x','--o-signal','x',
              '--receipt-index','x','--evidence-root','x']
        payload={'next_action':'BOUND_CANDIDATE_CHECKS_PASSED','work_unit':chr(0xD800)}
        with patch('maestro_prep.cli.read_json',return_value=self.work), \
             patch('maestro_prep.cli.decide',return_value=payload), \
             redirect_stdout(StringIO()) as out:
            rc=cli.main(argv)
        self.assertEqual(rc,0)
        self.assertTrue(out.getvalue().isascii())
        self.assertEqual(json.loads(out.getvalue())['work_unit'],chr(0xD800))

    def test_sys_modules_o_prep_spoof_cannot_bypass_required_gate(self):
        class SpoofedOPrep:
            __file__ = str(coordinator.VENDOR / 'o_prep.py')
            VERSION = '0.3.0-prep'
            OPrepError = ValueError
            @staticmethod
            def evaluate_bound_signal(*_args):
                return {'issues': [], 'next_action': 'ADVANCE_CANDIDATE',
                        'evidence_binding': {'status': 'LOCAL_BYTES_VERIFIED_ONLY'}}
        self.signal['evidence']['manifest_verified'] = False
        with patch.dict(sys.modules, {'o_prep': SpoofedOPrep()}):
            result = self.invoke()
        self.assertEqual(result['next_action'], 'HOLD_SOURCE')
        self.assertIn('MANIFEST_UNVERIFIED', result['issue_codes'])

    def test_sys_modules_evidence_bindings_spoof_cannot_bypass_gate(self):
        class SpoofedBindings:
            __file__ = str(coordinator.VENDOR / 'evidence_bindings.py')
            class BindingError(ValueError):
                pass
            @staticmethod
            def verify_local_bindings(*_args):
                return {'status':'LOCAL_BYTES_VERIFIED_ONLY','issues':[]}
            @staticmethod
            def is_link(*_args):
                return False
        (self.root/'receipts/router_output.bin').write_bytes(b'tampered')
        with patch.dict(sys.modules, {'evidence_bindings': SpoofedBindings()}):
            result = self.invoke()
        self.assertEqual(result['next_action'], 'HOLD_SOURCE')
        self.assertIn('RECEIPT_BYTES_MISMATCH_ROUTER_OUTPUT', result['issue_codes'])

    def test_pinned_loading_does_not_change_sys_modules(self):
        before = (sys.modules.get('o_prep'), sys.modules.get('evidence_bindings'))
        result = self.invoke()
        after = (sys.modules.get('o_prep'), sys.modules.get('evidence_bindings'))
        self.assertEqual(result['next_action'], 'BOUND_CANDIDATE_CHECKS_PASSED')
        self.assertEqual(before, after)


    def update_raw_route(self, raw):
        payload = json.dumps(raw, sort_keys=True).encode('utf-8')
        (self.root / 'receipts/router_output.bin').write_bytes(payload)
        for row in self.receipts:
            if row['role'] == 'router_output':
                row['sha256'] = HASH(payload)
                row['size_bytes'] = len(payload)
        self.save_index()
        capture = read_json(self.root / self.route_rel)
        capture['routing_output_sha256'] = HASH(payload)
        self.write_json(self.route_rel, capture)
        return payload

    def test_capture_ready_cannot_override_raw_blocked_leonardo_contract(self):
        raw = json.loads(self.route)
        raw['execution_state'] = 'BLOCKED_BY_LOCAL_POLICY'
        raw['candidate_work_allowed'] = False
        self.update_raw_route(raw)
        result = self.invoke()
        self.assertIn('HOLD_LEONARDO_RAW_ROUTE_NOT_READY', result['issue_codes'])
        self.assertEqual(result['next_action'], 'HOLD_INTEGRATION')

    def test_capture_ready_cannot_override_raw_policy_mismatch(self):
        raw = json.loads(self.route)
        raw['input_bindings']['policy_sha256'] = HASH(b'FORGED POLICY')
        self.update_raw_route(raw)
        self.assertIn('HOLD_LEONARDO_RAW_ROUTE_BINDING', self.invoke()['issue_codes'])

    def test_capture_ready_cannot_override_raw_request_mismatch(self):
        raw = json.loads(self.route)
        raw['request']['request_sha256'] = HASH(b'OTHER TASK')
        self.update_raw_route(raw)
        self.assertIn('HOLD_LEONARDO_RAW_ROUTE_BINDING', self.invoke()['issue_codes'])

    def test_capture_ready_rejects_nonboolean_candidate_flag(self):
        raw = json.loads(self.route)
        raw['candidate_work_allowed'] = 1
        self.update_raw_route(raw)
        self.assertIn('HOLD_LEONARDO_RAW_ROUTE_NOT_READY', self.invoke()['issue_codes'])

    def test_raw_router_output_modified_after_o_prep_gate_is_hold(self):
        o = vendor_module()
        evaluated = o.evaluate_bound_signal
        def mutate_after_gate(*args):
            value = evaluated(*args)
            (self.root / 'receipts/router_output.bin').write_bytes(b'AFTER_GATE_TAMPER')
            return value
        with patch('maestro_prep.coordinator.vendor_module') as injected:
            injected.return_value.evaluate_bound_signal.side_effect = mutate_after_gate
            result = self.invoke()
        self.assertIn('HOLD_LEONARDO_ARTIFACT_BYTES_CHANGED', result['issue_codes'])

    def test_broken_raw_router_shape_is_held_even_if_capture_ready(self):
        self.update_raw_route({'execution_state':'READY_FOR_LOCAL_CANDIDATE_WORK',
                               'candidate_work_allowed': True})
        self.assertIn('HOLD_LEONARDO_RAW_ROUTE_BINDING', self.invoke()['issue_codes'])

    def test_malformed_router_guard_fails_closed(self):
        for guard in (None, [], {'blocks': None}, {'blocks': 'invalid'}):
            with self.subTest(guard=guard):
                raw = json.loads(self.route)
                raw['guard'] = guard
                self.update_raw_route(raw)
                self.assertIn('HOLD_LEONARDO_RAW_ROUTE_NOT_READY', self.invoke()['issue_codes'])

    def test_nonobject_raw_output_fails_closed(self):
        self.update_raw_route(['READY_FOR_LOCAL_CANDIDATE_WORK'])
        self.assertIn('LEONARDO_ROUTING_OUTPUT_INVALID', self.invoke()['issue_codes'])

    def test_raw_router_blocks_nonempty_even_when_flag_true(self):
        raw = json.loads(self.route)
        raw['guard'] = {'blocks': ['POLICY_CONFLICT']}
        self.update_raw_route(raw)
        self.assertIn('HOLD_LEONARDO_RAW_ROUTE_NOT_READY', self.invoke()['issue_codes'])


    def test_post_o_gate_router_input_replacement_is_hold(self):
        o = vendor_module()
        real = o.evaluate_bound_signal
        def mutate(*args):
            answer = real(*args)
            (self.root/'receipts/router_input.bin').write_bytes(b'ADVERSARIAL POST-GATE INPUT')
            return answer
        with patch('maestro_prep.coordinator.vendor_module') as stub:
            stub.return_value.evaluate_bound_signal.side_effect = mutate
            result = self.invoke()
        self.assertEqual(result['next_action'], 'HOLD_INTEGRATION')
        self.assertIn('HOLD_LEONARDO_ARTIFACT_BYTES_CHANGED', result['issue_codes'])

    def test_post_o_gate_router_policy_replacement_is_hold(self):
        o = vendor_module()
        real = o.evaluate_bound_signal
        def mutate(*args):
            answer = real(*args)
            (self.root/'receipts/router_policy.bin').write_bytes(b'ALLOWED:NETWORK')
            return answer
        with patch('maestro_prep.coordinator.vendor_module') as stub:
            stub.return_value.evaluate_bound_signal.side_effect = mutate
            result = self.invoke()
        self.assertIn('HOLD_LEONARDO_ARTIFACT_BYTES_CHANGED', result['issue_codes'])

    def test_post_o_gate_receipt_index_replacement_is_hold(self):
        o = vendor_module()
        real = o.evaluate_bound_signal
        def mutate(*args):
            answer = real(*args)
            idx = read_json(self.index)
            idx['receipts'][0]['path'] = 'receipts/router_output.bin'
            self.write_json('receipt_index.json',idx)
            return answer
        with patch('maestro_prep.coordinator.vendor_module') as stub:
            stub.return_value.evaluate_bound_signal.side_effect = mutate
            result = self.invoke()
        self.assertIn('HOLD_O_INDEX_CHANGED_AFTER_GATE', result['issue_codes'])

    def test_raw_route_other_block_channels_must_be_empty(self):
        for field, bad in (('block_codes', ['NETWORK_REQUESTED']),
                           ('block_details', [{'code': 'NETWORK_REQUESTED'}]),
                           ('block_codes', None), ('block_details','INVALID')):
            with self.subTest(field=field,bad=bad):
                raw = json.loads(self.route)
                raw['guard'][field] = bad
                self.update_raw_route(raw)
                self.assertIn('HOLD_LEONARDO_RAW_ROUTE_NOT_READY', self.invoke()['issue_codes'])

    def test_raw_route_effective_network_and_deployment_relaxation_holds(self):
        for field in ('network', 'deployment', 'external_actions', 'credential_access', 'production_mutation'):
            with self.subTest(field=field):
                raw = json.loads(self.route)
                raw['guard'][field] = 'ALLOWED'
                self.update_raw_route(raw)
                self.assertIn('HOLD_LEONARDO_RAW_POLICY_RELAXED', self.invoke()['issue_codes'])

    def test_raw_route_missing_mandatory_candidate_guards_holds(self):
        for field in ('candidate_only', 'local_only', 'tests_required',
                      'small_change_units_required', 'source_originals_immutable'):
            with self.subTest(field=field):
                raw = json.loads(self.route)
                raw['guard'][field] = False
                self.update_raw_route(raw)
                self.assertIn('HOLD_LEONARDO_RAW_POLICY_RELAXED', self.invoke()['issue_codes'])

    def test_raw_route_contradictory_next_action_holds(self):
        raw = json.loads(self.route)
        raw['next_action'] = 'CORRECT_POLICY_OR_TASK_BOUNDARY'
        self.update_raw_route(raw)
        self.assertIn('HOLD_LEONARDO_RAW_ROUTE_NOT_READY',self.invoke()['issue_codes'])

    def test_raw_route_missing_critical_policy_field_holds(self):
        raw = json.loads(self.route)
        del raw['guard']['network']
        self.update_raw_route(raw)
        self.assertIn('HOLD_LEONARDO_RAW_POLICY_RELAXED',self.invoke()['issue_codes'])

class JunctionGuardTests(Fixture):
    """NTFS junctions are reparse points that Path.is_symlink() does not report."""
    def flag(self,*paths):
        marked={p.absolute() for p in paths}
        return patch.object(coordinator,'_is_link',side_effect=lambda p:p.absolute() in marked)
    def test_reparse_point_attribute_is_treated_as_link(self):
        fake=SimpleNamespace(st_mode=stat.S_IFDIR,st_file_attributes=0x400)
        with patch.object(Path,'lstat',return_value=fake):
            self.assertTrue(coordinator._is_link(self.root))
        self.assertFalse(coordinator._is_link(self.root))
    def test_junction_evidence_root_is_rejected(self):
        with self.flag(self.root),self.assertRaises(ContractError) as ctx:self.invoke()
        self.assertEqual(str(ctx.exception),'EVIDENCE_ROOT_INVALID')
    def test_junction_evidence_root_ancestor_is_rejected(self):
        with self.flag(self.tmp),self.assertRaises(ContractError) as ctx:self.invoke()
        self.assertEqual(str(ctx.exception),'EVIDENCE_ROOT_INVALID')
    def test_symlinked_evidence_root_ancestor_is_rejected(self):
        link=self.tmp.parent/(self.tmp.name+'_alias')
        try:link.symlink_to(self.tmp,target_is_directory=True)
        except OSError:self.skipTest('Symlinks restricted')
        self.addCleanup(link.unlink)
        with self.assertRaises(ContractError) as ctx:
            decide(copy.deepcopy(self.work),copy.deepcopy(self.lock),copy.deepcopy(self.signal),
                   link/'private'/'receipt_index.json',link/'private',astra_skill_path=self.astra,
                   astra_plan_receipt_rel=self.plan_rel,leonardo_route_rel=self.route_rel)
        self.assertEqual(str(ctx.exception),'EVIDENCE_ROOT_INVALID')
    def test_junction_inside_evidence_root_is_rejected(self):
        with self.flag(self.root/self.route_rel):x=self.invoke()
        self.assertEqual(x['next_action'],'HOLD_INTEGRATION')
        self.assertIn('EVIDENCE_SYMLINK_FORBIDDEN',x['issue_codes'])
    def test_junction_astra_skill_is_rejected(self):
        with self.flag(self.astra):x=self.invoke()
        self.assertIn('HOLD_ASTRA_SOURCE_PIN',x['issue_codes'])
    def test_junction_audit_file_is_rejected(self):
        path=self.tmp/'artifact';path.write_bytes(b'private synthetic file')
        with self.flag(path),self.assertRaises(ContractError):verify_generic_file(path,HASH(path.read_bytes()))

class ReplayTests(unittest.TestCase):
    def test_prior_twenty_synthetic_cases_match_current_pinned_o(self):
        x=run();self.assertEqual((x['scenario_count'],x['o_prep_cases_matched'],x['naive_choice_skips']), (20,20,11))
        self.assertEqual(x['c_compulsory_gate_skips_when_available'],0)
    def test_vendor_source_pin(self): self.assertEqual(vendor_module().VERSION,'0.3.0-prep')

if __name__=='__main__':unittest.main()
