"""V0.3 adversarial tests on synthetic data; cannot certify a production node."""
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'tests'))
from o_prep import (OPrepError, _read_json, _secure_out_file, audit_4a_bundle,
                    evaluate_signal, evaluate_bound_signal, validate_signal)
from evidence_bindings import BindingError, verify_local_bindings
from test_o_prep import signal, ArchiveAuditTests
try:
    from jsonschema import Draft202012Validator, ValidationError
except ImportError:
    Draft202012Validator = None


def binding_fixture(root: Path, stage='CLOSE', missing=()):
    s = signal(stage)
    files = {
        'router_input': b'{"synthetic":"router input"}',
        'router_policy': b'{"synthetic":"router policy"}',
        'router_output': b'{"synthetic":"router output"}',
        'review_subject': b'synthetic-reviewed-artifact-bytes',
    }
    files['review_receipt'] = json.dumps({
        'work_unit': s['work_unit'], 'reviewed_sha256': hashlib.sha256(files['review_subject']).hexdigest(),
        'review_status': s['review']['status'], 'review_evidence_class': s['review']['evidence_class'],
    }).encode()
    files['dedup_receipt'] = json.dumps({
        'work_unit': s['work_unit'], 'idempotency_key': s['delivery']['idempotency_key'],
        'record_count':1, 'evidence_scope':'HOST_DB_READBACK_PRODUCER_REPORTED',
    }).encode()
    files['ack_receipt'] = json.dumps({
        'work_unit':s['work_unit'], 'idempotency_key':s['delivery']['idempotency_key'], 'state':'ACKED'
    }).encode()
    files['acceptance_receipt'] = json.dumps({
        'work_unit':s['work_unit'], 'idempotency_key':s['delivery']['idempotency_key'],
        'disposition':'ACCEPTED', 'decision_ref':'SYNTHETIC-ONLY',
    }).encode()
    rows=[]
    for role,b in files.items():
        if role in missing:continue
        name='evidence/'+role+'.dat'
        p=root/name;p.parent.mkdir(parents=True, exist_ok=True);p.write_bytes(b)
        rows.append({'role':role,'path':name,'sha256':hashlib.sha256(b).hexdigest(),'size_bytes':len(b)})
    index={
        'schema':'O_PREP_RECEIPT_INDEX_V1','work_unit':s['work_unit'],
        'node_id':s['node_id'],'stage':s['stage'],
        'captured_at_utc':s['captured_at_utc'],'receipts':rows,
    }
    index_path=root/'receipt_index.json';index_path.write_text(json.dumps(index))
    return s,index,index_path


class V03DecisionTests(unittest.TestCase):
    def test_pass_with_blocking_findings_now_reworks(self):
        x=signal('CLOSE');x['review']['blocking_findings']=True
        y=evaluate_signal(x)
        self.assertEqual(y['next_action'],'REWORK')
        self.assertIn('PASS_CONTRADICTS_BLOCKING_FINDINGS', {f['code'] for f in y['issues']})

    def test_same_lineage_cannot_self_close(self):
        x=signal('PUBLISH');x['review'].update(evidence_class='SAME_LINEAGE',verified_independent=False)
        self.assertEqual(evaluate_signal(x)['next_action'],'HOLD_REVIEW')

    def test_premature_full_closeout_is_hold(self):
        x=signal('PLAN');x['assertions']['claims_full_closeout']=True
        self.assertEqual(evaluate_signal(x)['next_action'],'HOLD_EVIDENCE')

    def test_claim_of_simultaneous_metrics_requires_data(self):
        x=signal();x['assertions']['metrics_simultaneous_claim']=True
        self.assertIn('SIMULTANEOUS_METRICS_WITHOUT_EVIDENCE',{r['code'] for r in evaluate_signal(x)['issues']})

    def test_not_run_delivery_cannot_ack(self):
        x=signal('CLOSE');x['delivery']['state']='NOT_RUN'
        self.assertIn('ACK_WITHOUT_DELIVERY',{r['code'] for r in evaluate_signal(x)['issues']})

    def test_rejects_unknown_top_and_nested_fields(self):
        x=signal();x['secret_payload']='something'
        with self.assertRaises(OPrepError):validate_signal(x)
        x=signal();x['review']['extra']='something'
        with self.assertRaises(OPrepError):validate_signal(x)

    def test_rejects_duplicate_and_nonfinite_json(self):
        with self.assertRaisesRegex(OPrepError,'duplicate'):_read_json(b'{"schema":1,"schema":2}','test')
        with self.assertRaisesRegex(OPrepError,'nonfinite'):_read_json(b'{"x":NaN}','test')


class V03LocalBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'private';self.root.mkdir()
        self.s,self.idx,self.idxpath=binding_fixture(self.root)

    def rewrite(self):
        self.idxpath.write_text(json.dumps(self.idx))

    def rewrite_role(self,role,data):
        item=next(i for i in self.idx['receipts'] if i['role']==role)
        p=self.root/item['path'];p.write_bytes(data)
        item['sha256']=hashlib.sha256(data).hexdigest();item['size_bytes']=len(data)
        self.rewrite()

    def test_clean_bytes_are_local_only_not_authorization(self):
        r=evaluate_bound_signal(self.s,str(self.idxpath),str(self.root))
        self.assertEqual(r['next_action'],'ADVANCE_CANDIDATE')
        self.assertEqual(r['evaluation_mode'],'LOCAL_BYTES_BOUND_CANDIDATE')
        self.assertEqual(r['evidence_binding']['status'],'LOCAL_BYTES_VERIFIED_ONLY')
        self.assertEqual(r['evidence_binding']['provenance_limit'],'BYTES_ONLY_NO_AUTHORITY_ASSERTED')
        self.assertFalse(r['host_mutation_authorized'])
        self.assertEqual(r['decision_authority'],'none')
        self.assertNotIn('path',str(r['evidence_binding']))

    def test_missing_router_output_fails_closed(self):
        self.idx['receipts']=[v for v in self.idx['receipts'] if v['role']!='router_output'];self.rewrite()
        r=evaluate_bound_signal(self.s,str(self.idxpath),str(self.root))
        self.assertEqual(r['next_action'],'HOLD_SOURCE')
        self.assertIn('BOUND_RECEIPT_MISSING_ROUTER_OUTPUT',{f['code'] for f in r['issues']})

    def test_corrupted_artifact_even_with_clean_metadata_fails_closed(self):
        item=next(v for v in self.idx['receipts'] if v['role']=='router_policy')
        (self.root/item['path']).write_bytes(b'injected different data')
        self.assertEqual(evaluate_bound_signal(self.s,str(self.idxpath),str(self.root))['next_action'],'HOLD_SOURCE')

    def test_root_path_escape_fails_closed(self):
        self.idx['receipts'][0]['path']='../outside.txt';self.rewrite()
        with self.assertRaises(BindingError):verify_local_bindings(str(self.idxpath),str(self.root),self.s)

    def test_symlink_to_external_file_fails_closed(self):
        item=self.idx['receipts'][0];original=self.root/item['path'];original.unlink()
        external=Path(self.temp.name)/'outside';external.write_bytes(b'something')
        original.symlink_to(external)
        with self.assertRaisesRegex(BindingError,'symlink'):verify_local_bindings(str(self.idxpath),str(self.root),self.s)

    def test_duplicate_receipt_role_fails_closed(self):
        self.idx['receipts'].append(copy.deepcopy(self.idx['receipts'][0]));self.rewrite()
        with self.assertRaises(BindingError):verify_local_bindings(str(self.idxpath),str(self.root),self.s)

    def test_snapshot_binding_mismatch_fails_closed(self):
        self.idx['captured_at_utc']='2026-09-24T00:00:00Z';self.rewrite()
        with self.assertRaisesRegex(BindingError,'snapshot'):verify_local_bindings(str(self.idxpath),str(self.root),self.s)

    def test_cross_retarget_review_receipt_is_held(self):
        item=next(v for v in self.idx['receipts'] if v['role']=='review_receipt')
        obj=json.loads((self.root/item['path']).read_text());obj['reviewed_sha256']='0'*64
        self.rewrite_role('review_receipt',json.dumps(obj).encode())
        r=evaluate_bound_signal(self.s,str(self.idxpath),str(self.root))
        self.assertEqual(r['next_action'],'HOLD_EVIDENCE')
        self.assertIn('REVIEW_RECEIPT_BINDING_MISMATCH',{f['code'] for f in r['issues']})

    def test_dedup_receipt_wrong_key_held(self):
        item=next(v for v in self.idx['receipts'] if v['role']=='dedup_receipt')
        obj=json.loads((self.root/item['path']).read_text());obj['idempotency_key']='not-the-same'
        self.rewrite_role('dedup_receipt',json.dumps(obj).encode())
        self.assertIn('DEDUP_RECEIPT_BINDING_MISMATCH', {f['code'] for f in evaluate_bound_signal(self.s,str(self.idxpath),str(self.root))['issues']})

    def test_wrong_ack_or_acceptance_receipt_held(self):
        for role,key,value,code in [
            ('ack_receipt','state','PENDING','ACK_RECEIPT_BINDING_MISMATCH'),
            ('acceptance_receipt','disposition','FINDINGS','ACCEPTANCE_RECEIPT_BINDING_MISMATCH'),
        ]:
            with self.subTest(role=role):
                item=next(v for v in self.idx['receipts'] if v['role']==role)
                obj=json.loads((self.root/item['path']).read_text());obj[key]=value
                self.rewrite_role(role,json.dumps(obj).encode())
                self.assertIn(code,{f['code'] for f in evaluate_bound_signal(self.s,str(self.idxpath),str(self.root))['issues']})

    def test_bad_index_duplicate_json_keys_fails_closed(self):
        self.idxpath.write_bytes(b'{"schema":1,"schema":2}')
        with self.assertRaises(BindingError):verify_local_bindings(str(self.idxpath),str(self.root),self.s)

    def test_plan_requires_router_only(self):
        plan,index,p=binding_fixture(self.root/'plan','PLAN',missing=('review_receipt','dedup_receipt','ack_receipt','acceptance_receipt'))
        r=evaluate_bound_signal(plan,str(p),str(p.parent))
        self.assertEqual(r['next_action'],'ADVANCE_CANDIDATE')

    @unittest.skipIf(Draft202012Validator is None,'optional jsonschema package not present')
    def test_receipt_schema_validates(self):
        schema=json.loads((ROOT/'schemas'/'receipt_index.schema.json').read_text())
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(self.idx)


class V03OutputTests(unittest.TestCase):
    def test_new_receipt_is_exclusive_and_private(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);target=root/'receipt.json'
            _secure_out_file(target,root,'{}')
            self.assertEqual(target.read_text(),'{}')
            self.assertEqual(target.stat().st_mode & 0o777,0o600)
            with self.assertRaises(FileExistsError):_secure_out_file(target,root,'new')
            self.assertEqual(target.read_text(),'{}')

    def test_output_outside_explicit_root_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'private';root.mkdir();outside=Path(temp)/'outside.json'
            with self.assertRaises(OPrepError):_secure_out_file(outside,root,'{}')
            self.assertFalse(outside.exists())

    def test_symlinked_output_parent_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'private';root.mkdir();other=Path(temp)/'other';other.mkdir()
            (root/'linked').symlink_to(other,target_is_directory=True)
            with self.assertRaises(OPrepError):_secure_out_file(root/'linked'/'receipt.json',root,'{}')

    def test_cli_requires_output_root(self):
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/'out.json'
            r=subprocess.run([sys.executable,str(ROOT/'src'/'o_prep.py'),'evaluate',
                '--signal',str(ROOT/'examples'/'example_hold.json'),'--out',str(target)],capture_output=True)
            self.assertEqual(r.returncode,2)
            self.assertFalse(target.exists())


class V03ArchiveTests(unittest.TestCase):
    def test_manifest_duplicate_json_field_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'s.zip';ArchiveAuditTests().make_archive(p)
            with __import__('zipfile').ZipFile(p) as z:
                members={n:z.read(n) for n in z.namelist()}
            manifest=members['manifest.json'].decode()
            members['manifest.json']=manifest.replace('{','{"total_entries":10,',1).encode()
            with __import__('zipfile').ZipFile(p,'w') as z:
                for n,b in members.items():z.writestr(n,b)
            with self.assertRaisesRegex(OPrepError,'duplicate'):audit_4a_bundle(str(p))

    def test_bad_ledger_direction_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'s.zip';ArchiveAuditTests().make_archive(p)
            with __import__('zipfile').ZipFile(p) as z:
                members={n:z.read(n) for n in z.namelist()}
            obj=json.loads(members['packet_reconciliation.json'])
            obj['four_c_four_a_packet_ledger'][0]['receiver_node_id']='4A'
            members['packet_reconciliation.json']=json.dumps(obj).encode()
            manifest=json.loads(members['manifest.json'])
            for row in manifest['entries']:
                if row['relative_path']=='packet_reconciliation.json':
                    row['size_bytes']=len(members['packet_reconciliation.json'])
                    row['sha256']=hashlib.sha256(members['packet_reconciliation.json']).hexdigest()
            members['manifest.json']=json.dumps(manifest).encode()
            with __import__('zipfile').ZipFile(p,'w') as z:
                for n,b in members.items():z.writestr(n,b)
            with self.assertRaisesRegex(OPrepError,'direction'):audit_4a_bundle(str(p))


if __name__=='__main__':unittest.main()
