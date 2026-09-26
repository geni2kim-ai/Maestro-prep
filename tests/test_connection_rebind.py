"""Synthetic Leonardo/Astra/O-Prep cross-binding and fail-closed regressions.

No actual Leonardo router or node-approved Astra validator is available here.
"""
import json
import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import test_astra_v71_adapter as astra_fixture
from test_maestro import Fixture, HASH


class CrossBindingTests(unittest.TestCase):
    def setUp(self):
        self.fixture=astra_fixture.OfficialAstraV71AdapterTests('runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def __getattr__(self, name):
        fixture = self.__dict__.get('fixture')
        if fixture is None:
            raise AttributeError(name)
        return getattr(fixture,name)

    def _replace_task_and_rebind_route_only(self):
        changed = b'SYNTHETIC CHANGED USER REQUEST: different requirements'
        self.fixture.task = changed
        self.work['task_sha256'] = HASH(changed)
        self.root.joinpath('receipts/router_input.bin').write_bytes(changed)
        input_row = next(x for x in self.receipts if x['role'] == 'router_input')
        input_row.update(sha256=HASH(changed), size_bytes=len(changed))
        self.refresh_route()
        route_receipt = json.loads((self.root / self.route_rel).read_text())
        route_receipt['task_sha256'] = HASH(changed)
        self.write_json(self.route_rel, route_receipt)
        self.save_index()

    def test_new_task_cannot_reuse_previous_plan_even_when_route_ready(self):
        self.assertEqual(self.invoke()['next_action'], 'BOUND_CANDIDATE_CHECKS_PASSED')
        self._replace_task_and_rebind_route_only()
        decision = self.invoke()
        self.assertIn('HOLD_ASTRA_PLAN_TASK_CHANGED', decision['issue_codes'])
        self.assertEqual(decision['astra_official_validation']['status'], 'NOT_RUN_INVALID_CAPTURE')
        self.assertEqual(decision['next_action'], 'HOLD_INTEGRATION')

    def test_valid_Leonardo_replan_route_change_invalidates_old_plan(self):
        self.assertEqual(self.invoke()['next_action'], 'BOUND_CANDIDATE_CHECKS_PASSED')
        self.refresh_route(overrides={'mandatory_skills':['o-prep','astra-prep','extra-skill']})
        decision = self.invoke()
        self.assertNotIn('HOLD_LEONARDO_MANDATORY_SKILL_MISSING', decision['issue_codes'])
        self.assertIn('HOLD_ASTRA_PLAN_ROUTE_CHANGED', decision['issue_codes'])
        self.assertEqual(decision['next_action'], 'HOLD_INTEGRATION')

    def test_reuse_plan_accepts_new_stage_route_but_preserves_task_binding(self):
        # Preserve the immutable *original* plan-route output and capture before
        # the current EXECUTE route replaces the current receipt-index role.
        (self.root/'receipts/origin_router_output.json').write_bytes(self.route)
        (self.root/'receipts/origin_route_capture.json').write_bytes((self.root/self.route_rel).read_bytes())
        capture=json.loads((self.root/self.plan_rel).read_text())
        capture.update(schema='ASTRA_PREP_CAPTURE_V3',
                       origin_route_output_file='receipts/origin_router_output.json',
                       origin_route_capture_file='receipts/origin_route_capture.json')
        self.write_json(self.plan_rel,capture)
        self.work.update(intent='REUSE_PLAN',stage='EXECUTE',
                         plan_sha256=HASH((self.root/self.plan_file).read_bytes()))
        self.signal['stage']='EXECUTE'
        self.refresh_route()  # new phase output SHA; the original receipt SHA stays pinned
        self.save_index()
        result=self.invoke()
        self.assertNotIn('HOLD_ASTRA_PLAN_ROUTE_CHANGED',result['issue_codes'])
        self.assertEqual(result['next_action'],'BOUND_CANDIDATE_CHECKS_PASSED')

    def test_v1_producer_receipt_cannot_reenter_official_path(self):
        capture = json.loads((self.root/self.plan_rel).read_text())
        capture['schema'] = 'ASTRA_PREP_CAPTURE_V1'
        del capture['task_sha256']
        del capture['origin_route_output_sha256']
        self.write_json(self.plan_rel,capture)
        decision = self.invoke()
        self.assertIn('HOLD_ASTRA_LEGACY_RECEIPT_UNBOUND',decision['issue_codes'])
        self.assertEqual(decision['astra_official_validation']['status'],'NOT_RUN_INVALID_CAPTURE')

    def test_missing_plan_still_requires_all_approved_bundle_pins(self):
        self.schema.write_bytes(b'{"tampered":"yes"}')
        result = self.invoke(astra_plan_receipt_rel=None)
        self.assertIn('ASTRA_MANIFEST_FILE_MISMATCH',result['issue_codes'])
        self.assertIn('CALL_ASTRA_PREP',result['issue_codes'])
        self.assertEqual(result['next_action'],'HOLD_INTEGRATION')

    def test_plan_is_rehashed_after_external_validator_execution(self):
        def mutate(*_,**__):
            (self.root/self.plan_file).write_bytes(b'{"changed":true}')
            return subprocess.CompletedProcess([],0,b'OK: pre-work plan is valid.\n',b'')
        with patch('maestro_prep.coordinator.subprocess.run',side_effect=mutate):
            result = self.invoke()
        self.assertIn('HOLD_ASTRA_PLAN_CHANGED_DURING_VALIDATION',result['issue_codes'])

    def test_bundle_is_rehashed_after_validator_execution(self):
        def mutate(*_,**__):
            self.script.write_bytes(b'print("changed after preflight")')
            return subprocess.CompletedProcess([],0,b'OK: pre-work plan is valid.\n',b'')
        with patch('maestro_prep.coordinator.subprocess.run',side_effect=mutate):
            result = self.invoke()
        self.assertIn('HOLD_ASTRA_DEPENDENCY_CHANGED_DURING_VALIDATION',result['issue_codes'])

    def test_relative_evidence_and_bundle_paths_are_passed_as_absolute_to_validator(self):
        original=Path.cwd()
        try:
            os.chdir(self.tmp)
            from maestro_prep.coordinator import decide
            result=decide(self.work,self.lock,self.signal,
                          Path('private/receipt_index.json'),Path('private'),
                          astra_skill_path=Path('node_approved_astra/SKILL.md'),
                          astra_bundle_root=Path('node_approved_astra'),
                          astra_plan_receipt_rel=self.plan_rel,
                          leonardo_route_rel=self.route_rel)
        finally:
            os.chdir(original)
        self.assertEqual(result['next_action'],'BOUND_CANDIDATE_CHECKS_PASSED')

    def test_plan_pending_with_intact_approved_bundle_requests_generation(self):
        result = self.invoke(astra_plan_receipt_rel=None)
        self.assertEqual(result['next_action'],'CALL_ASTRA_PREP')
        self.assertEqual(result['astra_official_validation']['status'],'PINNED_BUNDLE_PRESENT_PLAN_PENDING')
        self.assertFalse(result['host_mutation_authorized'])

    def test_o_prep_unexpected_failure_is_not_uncaught(self):
        with patch('maestro_prep.coordinator.vendor_module',side_effect=ValueError('synthetic broken API')):
            result=self.invoke()
        self.assertIn('HOLD_O_MODULE_MISSING',result['issue_codes'])
        self.assertEqual(result['next_action'],'HOLD_O_MODULE_MISSING')

    def test_wrong_task_and_router_failure_preserve_both_findings(self):
        self._replace_task_and_rebind_route_only()
        self.lock['leonardo']['policy_sha256'] = 'f'*64
        result=self.invoke()
        self.assertIn('HOLD_LEONARDO_ARTIFACT_PIN_MISMATCH',result['issue_codes'])
        self.assertIn('HOLD_ASTRA_PLAN_TASK_CHANGED',result['issue_codes'])


class LegacyBypassTests(Fixture):
    def test_version_label_is_not_owner_approved_validator_proof(self):
        self.lock['astra']['approved_version_label']='v7.0-legacy-reported'
        result=self.invoke()
        self.assertIn('HOLD_ASTRA_OFFICIAL_PIN_MISSING',result['issue_codes'])
        self.assertEqual(result['astra_official_validation']['status'],
                         'NOT_RUN_APPROVED_VALIDATOR_PINS_MISSING')
        self.assertNotEqual(result['next_action'],'BOUND_CANDIDATE_CHECKS_PASSED')

    def test_absent_v71_pins_prevents_unverified_plan_call(self):
        result=self.invoke(astra_plan_receipt_rel=None)
        self.assertIn('HOLD_ASTRA_OFFICIAL_PIN_MISSING',result['issue_codes'])
        self.assertEqual(result['next_action'],'HOLD_INTEGRATION')


if __name__=='__main__': unittest.main()
