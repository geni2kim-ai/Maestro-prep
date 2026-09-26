"""Synthetic Leonardo/Astra connecting boundary: whole-bundle pins and chronology.

Runs only a fake hash-pinned Astra CLI, not an approved node Astra/Leonardo runtime.
"""
import hashlib
import json
import subprocess
import unittest
from unittest.mock import patch

import test_astra_v71_adapter as fixture
from maestro_prep.coordinator import ContractError, check_lock

HASH=lambda b:hashlib.sha256(b).hexdigest()


class WholeBundleManifestTests(unittest.TestCase):
    def setUp(self):
        f=fixture.OfficialAstraV71AdapterTests('runTest')
        f.setUp();self.addCleanup(f.doCleanups);self.f=f

    def rewrite_manifest(self, modify):
        f=self.f;p=f.bundle/'CANDIDATE_HASHES.json'
        manifest=json.loads(p.read_text());modify(manifest)
        data=json.dumps(manifest,sort_keys=True).encode();p.write_bytes(data)
        f.lock['astra']['official_v71']['manifest_sha256']=HASH(data)

    def test_nominal_pinned_synthetic_bundle_passes(self):
        self.assertEqual(self.f.invoke()['next_action'],'BOUND_CANDIDATE_CHECKS_PASSED')

    def test_evidence_model_tamper_is_hold(self):
        (self.f.bundle/'references/evidence-model.md').write_text('unreviewed E/R policy change')
        self.assertIn('ASTRA_MANIFEST_FILE_MISMATCH',self.f.invoke()['issue_codes'])

    def test_domain_checks_tamper_is_hold(self):
        (self.f.bundle/'references/domain-checks.md').write_text('unreviewed preflight change')
        self.assertIn('ASTRA_MANIFEST_FILE_MISMATCH',self.f.invoke()['issue_codes'])

    def test_owner_manifest_pin_missing_is_rejected(self):
        del self.f.lock['astra']['official_v71']['manifest_sha256']
        with self.assertRaisesRegex(ContractError,'ASTRA_OFFICIAL_PINS_INVALID'):
            check_lock(self.f.lock)

    def test_manifest_bytes_modified_with_same_owner_pin_is_hold(self):
        manifest=self.f.bundle/'CANDIDATE_HASHES.json'
        manifest.write_bytes(manifest.read_bytes()+b' ')
        self.assertIn('ASTRA_BUNDLE_HASH_MISMATCH',self.f.invoke()['issue_codes'])

    def test_owner_signed_omission_of_required_domain_ref_is_hold(self):
        def change(m):
            m['files'].pop('references/domain-checks.md')
            m['file_count']=len(m['files'])
            m['bundle_aggregate_sha256']=HASH(''.join(
                f'{rel}  {m["files"][rel]}\n' for rel in sorted(m['files'])).encode())
        self.rewrite_manifest(change)
        self.assertIn('ASTRA_MANIFEST_REQUIRED_FILES_MISSING',self.f.invoke()['issue_codes'])

    def test_owner_signed_bad_aggregate_is_hold(self):
        self.rewrite_manifest(lambda m:m.update(bundle_aggregate_sha256='f'*64))
        self.assertIn('ASTRA_MANIFEST_AGGREGATE_MISMATCH',self.f.invoke()['issue_codes'])

    def test_owner_signed_path_escape_is_hold(self):
        def change(m):
            m['files']['../out-of-scope.txt']='a'*64
            m['file_count']=len(m['files'])
            m['bundle_aggregate_sha256']=HASH(''.join(
                f'{rel}  {m["files"][rel]}\n' for rel in sorted(m['files'])).encode())
        self.rewrite_manifest(change)
        self.assertIn('ASTRA_MANIFEST_UNSAFE_PATH',self.f.invoke()['issue_codes'])

    def test_reference_tamper_while_validator_runs_is_hold(self):
        p=self.f.bundle/'references/domain-checks.md'
        def mutate(*_a,**_k):
            p.write_text('mutation during validation')
            return subprocess.CompletedProcess([],0,b'parser: synthetic-json\npython: synthetic-test\nOK: pre-work plan is valid.\n',b'')
        with patch('maestro_prep.coordinator.subprocess.run',side_effect=mutate):
            out=self.f.invoke()
        self.assertIn('HOLD_ASTRA_DEPENDENCY_CHANGED_DURING_VALIDATION',out['issue_codes'])

    def test_manifest_tamper_while_validator_runs_is_hold(self):
        p=self.f.bundle/'CANDIDATE_HASHES.json'
        def mutate(*_a,**_k):
            p.write_bytes(p.read_bytes()+b' ')
            return subprocess.CompletedProcess([],0,b'parser: synthetic-json\npython: synthetic-test\nOK: pre-work plan is valid.\n',b'')
        with patch('maestro_prep.coordinator.subprocess.run',side_effect=mutate):
            out=self.f.invoke()
        self.assertIn('HOLD_ASTRA_MANIFEST_CHANGED_DURING_VALIDATION',out['issue_codes'])

    def test_sidecar_must_not_be_postdated_after_capture_receipt(self):
        f=self.f
        f.work['captured_at_utc']='2026-09-25T00:30:00Z'
        f.signal['captured_at_utc']=f.work['captured_at_utc']
        f.save_index()
        f.plan['generated_at']='2026-09-25T00:15:00Z'
        f.sync_plan()
        self.assertIn('HOLD_ASTRA_PLAN_GENERATED_AFTER_RECEIPT',f.invoke()['issue_codes'])

    def test_reused_plan_origin_route_not_overdue_when_plan_created(self):
        f=self.f
        route_rel='receipts/origin_router_output.json'
        capture_rel='receipts/origin_route_capture.json'
        (f.root/route_rel).write_bytes(f.route)
        origin=json.loads((f.root/f.route_rel).read_text())
        origin['captured_at_utc']='2026-09-24T18:00:00Z' # 6h before plan
        f.write_json(capture_rel, origin)
        receipt=json.loads((f.root/f.plan_rel).read_text())
        receipt.update(schema='ASTRA_PREP_CAPTURE_V3',origin_route_output_file=route_rel,
                       origin_route_capture_file=capture_rel)
        f.write_json(f.plan_rel,receipt)
        f.work.update(intent='REUSE_PLAN',stage='EXECUTE',plan_sha256=HASH((f.root/f.plan_file).read_bytes()))
        f.signal['stage']='EXECUTE';f.refresh_route();f.save_index()
        self.assertIn('HOLD_ASTRA_ORIGIN_STALE_AT_PLAN',f.invoke()['issue_codes'])


if __name__=='__main__':unittest.main()
