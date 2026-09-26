"""Offline adversarial tests for the public mirror auditor. No approved node data."""
from __future__ import annotations
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import stat

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from audit_public_mirror import audit, aggregate, load_manifest, unique_json, AuditError, exclusive_report, assess_known_drift
from audit_public_mirror import is_reparse_or_link

H=lambda b: hashlib.sha256(b).hexdigest()

class PublicMirrorAuditorTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)/'repo';self.root.mkdir()
        self.files = {'SKILL.md':b'synthetic-skill\n','scripts/validate_prework.py':b'synthetic-validator\n'}
        (self.root/'scripts').mkdir()
        for name,payload in self.files.items():
            (self.root/name).write_bytes(payload)
        self.mapping={name:H(data) for name,data in self.files.items()}
        self.write_manifest(self.mapping)
    def write_manifest(self, mapping, aggregate_override=None):
        self.doc={'file_count':len(mapping),'files':mapping,'bundle_aggregate_sha256':aggregate_override or aggregate(mapping)}
        (self.root/'CANDIDATE_HASHES.json').write_text(json.dumps(self.doc),encoding='utf8')
    def test_untampered_is_match_not_authorization(self):
        r=audit(self.root)
        self.assertEqual(r['status'],'MATCH_NOT_AUTHORIZATION')
        self.assertEqual(r['node_approved_astra'],'NOT_RUN')
    def test_mutation_yields_disclosed_hold(self):
        (self.root/'SKILL.md').write_bytes(b'mutated-synthetic-skill')
        r=audit(self.root)
        self.assertEqual(r['status'],'HOLD_UNRECONCILED')
        self.assertEqual([i['path'] for i in r['mismatches']],['SKILL.md'])
    def test_stale_aggregate_fails_even_with_matching_file_hashes(self):
        self.write_manifest(self.mapping, '0'*64)
        r=audit(self.root)
        self.assertEqual(r['mismatch_count'],0)
        self.assertFalse(r['declared_aggregate_internally_consistent'])
        self.assertEqual(r['status'],'HOLD_UNRECONCILED')
    def test_rejects_traversal_member(self):
        self.write_manifest({'../outside':H(b'x')})
        with self.assertRaisesRegex(AuditError,'UNSAFE_MANIFEST_PATH'): audit(self.root)
    def test_rejects_duplicate_json_keys(self):
        with self.assertRaisesRegex(AuditError,'DUPLICATE_MANIFEST_KEY'):
            unique_json(b'{"files":{},"files":{}}')
    def test_rejects_symlink_member(self):
        external=Path(self.t.name)/'outside';external.write_bytes(b'x')
        try:(self.root/'evil').symlink_to(external)
        except (OSError,NotImplementedError):self.skipTest('symlink not supported')
        self.write_manifest({'evil':H(b'x')})
        with self.assertRaisesRegex(AuditError,'MANIFEST_LINK_OR_REPARSE_PATH'):audit(self.root)
    def test_report_cannot_overwrite_manifest_or_source(self):
        with self.assertRaisesRegex(AuditError,'REPORT_MUST_BE_OUTSIDE_PUBLIC_SOURCE_TREE'):
            exclusive_report(self.root/'report.json',{},self.root)
    def test_report_exclusive_creation(self):
        path=Path(self.t.name)/'out.json'
        exclusive_report(path,{'status':'HOLD'},self.root)
        with self.assertRaises(FileExistsError): exclusive_report(path,{'status':'OVERRIDE'},self.root)
        self.assertEqual(json.loads(path.read_text())['status'],'HOLD')

    def _make_git_reference(self):
        def cmd(*args):
            return subprocess.run(['git','-C',str(self.root),*args],check=True,capture_output=True,text=True).stdout.strip()
        cmd('init','-q')
        cmd('add','.')
        cmd('-c','user.name=MirrorFixture','-c','user.email=fixture@example.invalid','commit','-qm','synthetic baseline')
        return cmd,cmd('rev-parse','HEAD')
    def _v2_policy(self, report, baseline):
        policy_path = Path(self.t.name)/'expected.json'
        policy_path.write_text(json.dumps({
            'schema':'ASTRA_PUBLIC_MIRROR_KNOWN_DRIFT_V2',
            'baseline_commit':baseline,
            'manifest_sha256':report['manifest_sha256'],
            'declared_aggregate_sha256':report['declared_aggregate'],
            'observed_aggregate_sha256':report['observed_aggregate'],
            'known_mismatch_sha256':{x['path']:x['observed_sha256'] for x in report['mismatches']},
        }),encoding='utf-8')
        return policy_path
    def test_known_drift_remains_hold_not_approval(self):
        (self.root/'SKILL.md').write_bytes(b'mutated synthetic fixture')
        cmd, baseline = self._make_git_reference()
        result=audit(self.root)
        policy_path=self._v2_policy(result,baseline)
        receipt=assess_known_drift(result,self.root,policy_path)
        self.assertEqual(result['status'],'HOLD_UNRECONCILED')
        self.assertEqual(receipt['status'],'EXPECTED_DRIFT_STILL_HOLD')
        self.assertTrue(receipt['exact_known_drift'])
        self.assertFalse(receipt['node_authority'])
    def test_changed_public_payload_invalidates_known_drift_exception(self):
        (self.root/'SKILL.md').write_bytes(b'mutated synthetic fixture')
        cmd, baseline = self._make_git_reference()
        policy_path = self._v2_policy(audit(self.root),baseline)
        (self.root/'SKILL.md').write_bytes(b'another unreviewed mutation')
        cmd('add','SKILL.md')
        cmd('-c','user.name=MirrorFixture','-c','user.email=fixture@example.invalid','commit','-qm','drift')
        receipt=assess_known_drift(audit(self.root),self.root,policy_path)
        self.assertFalse(receipt['exact_known_drift'])
        self.assertEqual(receipt['historic_payload_changed_since_commit'],['SKILL.md'])

    def test_leonardo_repro_dirty_worktree_same_mismatch_paths_must_hold(self):
        (self.root/'SKILL.md').write_bytes(b'known public drift')
        cmd,baseline=self._make_git_reference()
        policy=self._v2_policy(audit(self.root),baseline)
        (self.root/'SKILL.md').write_bytes(b'unreviewed changed public drift')
        result=assess_known_drift(audit(self.root),self.root,policy)
        self.assertFalse(result['exact_known_drift'])
        self.assertFalse(result['source_worktree_clean'])
        self.assertFalse(result['exact_mismatch_bytes'])

    def test_staged_change_rejected_even_when_named_mismatch_unchanged(self):
        (self.root/'SKILL.md').write_bytes(b'known public drift')
        cmd,baseline=self._make_git_reference()
        policy=self._v2_policy(audit(self.root),baseline)
        (self.root/'extra.txt').write_text('untracked change')
        cmd('add','extra.txt')
        result=assess_known_drift(audit(self.root),self.root,policy)
        self.assertFalse(result['source_worktree_clean'])
        self.assertFalse(result['exact_known_drift'])

    def test_head_drift_rejected_even_if_listed_source_unmodified(self):
        (self.root/'SKILL.md').write_bytes(b'known public drift')
        cmd,baseline=self._make_git_reference()
        policy=self._v2_policy(audit(self.root),baseline)
        (self.root/'extra.txt').write_text('new commit')
        cmd('add','extra.txt')
        cmd('-c','user.name=MirrorFixture','-c','user.email=fixture@example.invalid','commit','-qm','extra')
        result=assess_known_drift(audit(self.root),self.root,policy)
        self.assertFalse(result['checkout_bound_to_commit'])
        self.assertFalse(result['exact_known_drift'])

    def test_report_snapshot_stale_even_if_same_mismatch_paths(self):
        (self.root/'SKILL.md').write_bytes(b'known public drift')
        cmd,baseline=self._make_git_reference()
        report=audit(self.root);policy=self._v2_policy(report,baseline)
        (self.root/'SKILL.md').write_bytes(b'changed after audit')
        result=assess_known_drift(report,self.root,policy)
        self.assertFalse(result['audit_snapshot_stable'])
        self.assertFalse(result['exact_known_drift'])

    def test_v1_path_only_known_drift_policy_is_not_sufficient(self):
        (self.root/'SKILL.md').write_bytes(b'known public drift')
        cmd,baseline=self._make_git_reference()
        policy=Path(self.t.name)/'v1.json'
        policy.write_text(json.dumps({'schema':'ASTRA_PUBLIC_MIRROR_KNOWN_DRIFT_V1',
            'baseline_commit':baseline,'known_mismatched_paths':['SKILL.md']}))
        with self.assertRaisesRegex(AuditError,'UNKNOWN_KNOWN_DRIFT_POLICY_SHAPE'):
            assess_known_drift(audit(self.root),self.root,policy)

    def test_v2_wrong_declared_manifest_pin_rejected(self):
        (self.root/'SKILL.md').write_bytes(b'known public drift')
        cmd,baseline=self._make_git_reference()
        policy=self._v2_policy(audit(self.root),baseline)
        obj=json.loads(policy.read_text());obj['manifest_sha256']='0'*64
        policy.write_text(json.dumps(obj))
        result=assess_known_drift(audit(self.root),self.root,policy)
        self.assertFalse(result['exact_known_drift'])

    def test_pinned_real_public_drift_policy_matches_observed_ci_receipt(self):
        # The real 25-file audit in GitHub run 36176525107 independently
        # observed this specific path SHA at the pinned public commit. The
        # first v0.2.7 CI replay caught a manually transposed hex nibble.
        # This fixture catches recurrence without treating an audit as owner
        # approval or altering the historical Astra manifest.
        policy_path=Path(__file__).resolve().parents[1]/'tools/expected_public_mirror_drift.json'
        policy=unique_json(policy_path.read_bytes())
        self.assertEqual(policy['schema'],'ASTRA_PUBLIC_MIRROR_KNOWN_DRIFT_V2')
        self.assertEqual(len(policy['known_mismatch_sha256']),10)
        self.assertEqual(policy['known_mismatch_sha256']['tests/fixtures/invalid_unknown_top_key.json'],
                         '1f08ed3330be517efb7bfe19c7a2b3424e1ea202d8a84ae0353ab622a86ac7ba')

    def test_known_drift_cli_requires_policy_even_if_current_files_now_match(self):
        (self.root/'SKILL.md').write_bytes(b'known public drift')
        cmd,baseline=self._make_git_reference()
        policy=self._v2_policy(audit(self.root),baseline)
        # A new mirror that happens to match the historical manifest is not the
        # same source snapshot as the owner-reviewed known-drift V2 policy.
        (self.root/'SKILL.md').write_bytes(self.files['SKILL.md'])
        cmd('add','SKILL.md')
        cmd('-c','user.name=MirrorFixture','-c','user.email=fixture@example.invalid','commit','-qm','new-mirror')
        script=Path(__file__).resolve().parents[1]/'tools/audit_public_mirror.py'
        p=subprocess.run([sys.executable,str(script),'--root',str(self.root),
                          '--known-drift-policy',str(policy)],capture_output=True,text=True)
        self.assertEqual(p.returncode,2)
        self.assertEqual(json.loads(p.stdout)['known_drift']['status'],'UNEXPECTED_DELTA_HOLD')

    def test_root_symlink_rejected_before_resolve(self):
        link=Path(self.t.name)/'root-symlink'
        try:link.symlink_to(self.root,target_is_directory=True)
        except (OSError,NotImplementedError):self.skipTest('symlink unavailable')
        with self.assertRaisesRegex(AuditError,'AUDIT_ROOT_LINK_OR_REPARSE'):
            audit(link)

    def test_windows_reparse_attribute_detected(self):
        fake=SimpleNamespace(st_mode=stat.S_IFREG,st_file_attributes=0x400)
        with patch('audit_public_mirror.os.lstat',return_value=fake):
            self.assertTrue(is_reparse_or_link(self.root/'SKILL.md'))

    def test_reparse_intermediate_path_rejected_on_windows_model(self):
        (self.root/'other').mkdir()
        (self.root/'other/file').write_text('x')
        self.write_manifest({'other/file':H(b'x')})
        import audit_public_mirror
        original=audit_public_mirror.is_reparse_or_link
        def pretend_reparse(p):
            return p == self.root/'other' or original(p)
        with patch('audit_public_mirror.is_reparse_or_link',side_effect=pretend_reparse):
            with self.assertRaisesRegex(AuditError,'MANIFEST_LINK_OR_REPARSE_PATH'):
                audit(self.root)

    def test_file_count_must_match_manifest_inventory(self):
        self.doc['file_count']=1
        (self.root/'CANDIDATE_HASHES.json').write_text(json.dumps(self.doc))
        with self.assertRaisesRegex(AuditError,'MANIFEST_COUNT_MISMATCH'):load_manifest(self.root)

if __name__=='__main__':unittest.main()
