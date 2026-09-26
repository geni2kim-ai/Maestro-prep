import copy
import hashlib
import io
import json
import os
import stat
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from o_prep import OPrepError, audit_transport_bundle, evaluate_signal, validate_signal, _check_out_path

Z = '0' * 64
TS = '2026-09-25T00:00:00Z'


def signal(stage='PLAN'):
    return {
        'schema': 'O_PREP_SIGNAL_V1', 'work_unit': 'SYNTHETIC-UNIT-TEST',
        'node_id': 'synthetic', 'captured_at_utc': TS, 'stage': stage,
        'router': {'status':'READY', 'exit_code':0, 'local_router_executed':True,
                   'policy_hash_verified':True, 'input_hash_verified':True,
                   'output_hash_verified':True, 'evidence_root_isolated':True},
        'evidence': {'manifest_verified':True, 'summary_raw_consistent':True,
                     'timestamp_provenance_verified':True, 'backfill_disclosed':True},
        'execution': {'secret_exposure':False,'mutation_requested':False,
                      'authority_verified':False,'live_action_requested':False,
                      'shared_router_tree_write':False,'reviewed_bytes_changed':False, 'blocked_node_contact':False},
        'review': {'status':'PASS', 'evidence_class':'VERIFIED_INDEPENDENT',
                   'verified_independent':True, 'harness_separately_verified':True,
                   'fresh_context_policy_verified':False, 'adjudicator_separate':True,
                   'review_hash_matches':True, 'blocking_findings':False},
        'delivery': {'required':True, 'state':'PROCESSED','disposition':'ACCEPTED',
                     'ack_required':True, 'ack_verified':True,'dedup_persistence_verified':True, 'disposition_evidence_verified':True,
                     'claims_accepted':True, 'idempotency_key':'synthetic-nonce-01'},
        'assertions': {'metrics_simultaneous_claim':False,
                       'claims_backfill_proves_history':False, 'claims_full_closeout':False},
        'metrics': [], 'open_gates': [],
    }


class DecisionGateTests(unittest.TestCase):
    def test_clean_synthetic_stage_advancement_is_non_authoritative(self):
        for stage in ['PLAN','EXECUTE','PUBLISH','CLOSE']:
            with self.subTest(stage=stage):
                r=evaluate_signal(signal(stage))
                self.assertEqual(r['next_action'], 'ADVANCE_CANDIDATE')
                self.assertFalse(r['host_mutation_authorized'])
                self.assertEqual(r['live_effect'], 'NOT_RUN')

    def test_eight_subject_probes_plus_fail_closed_cases(self):
        probes = [
            ('bad_z_timestamp', 'evidence', 'timestamp_provenance_verified', False, 'HOLD_EVIDENCE'),
            ('mtime_without_verified_provenance', 'evidence', 'timestamp_provenance_verified', False, 'HOLD_EVIDENCE'),
            ('undisclosed_later_backfill', 'assertions', 'claims_backfill_proves_history', True, 'HOLD_EVIDENCE'),
            ('missing_dedup_record', 'delivery', 'dedup_persistence_verified', False, 'HOLD_DELIVERY'),
            ('non_simultaneous_metrics', 'assertions', 'metrics_simultaneous_claim', True, 'HOLD_EVIDENCE'),
            ('review_bytes_changed', 'execution', 'reviewed_bytes_changed', True, 'REWORK'),
            ('same_harness_falsely_independent', 'review', 'evidence_class', 'FRESH_CONTEXT', 'HOLD_REVIEW'),
            ('processed_only_not_accepted', 'delivery', 'disposition', 'NOT_RUN', 'HOLD_DELIVERY'),
            ('raw_summary_conflict', 'evidence', 'summary_raw_consistent', False, 'HOLD_EVIDENCE'),
            ('manifest_not_verified', 'evidence', 'manifest_verified', False, 'HOLD_SOURCE'),
            ('missing_policy_pin', 'router', 'policy_hash_verified', False, 'HOLD_ROUTING'),
            ('unverified_router_run', 'router', 'local_router_executed', False, 'HOLD_ROUTING'),
            ('secret', 'execution', 'secret_exposure', True, 'STOP_DISCLOSURE'),
            ('unapproved_mutation', 'execution', 'mutation_requested', True, 'STOP_MUTATION'),
            ('live_rejected_even_if_authorized', 'execution', 'live_action_requested', True, 'STOP_MUTATION'),
            ('shared_tree_write', 'execution', 'shared_router_tree_write', True, 'STOP_ROUTER_WRITE'),
            ('frozen_node_contact', 'execution', 'blocked_node_contact', True, 'STOP_MUTATION'),
            ('unverified_acceptance_receipt', 'delivery', 'disposition_evidence_verified', False, 'HOLD_DELIVERY'),
            ('review_hash_unverified', 'review', 'review_hash_matches', False, 'HOLD_REVIEW'),
            ('missing_packet_key', 'delivery', 'idempotency_key', None, 'HOLD_DELIVERY'),
            ('ack_missing', 'delivery', 'ack_verified', False, 'HOLD_DELIVERY'),
        ]
        for name, group, key, value, expected in probes:
            with self.subTest(case=name):
                x = signal('CLOSE')
                x[group][key] = value
                if name == 'non_simultaneous_metrics':
                    x['metrics'] = [{'name':'A','captured_at_utc':TS,'source_sha256':Z},
                                    {'name':'B','captured_at_utc':'2026-09-24T00:00:00Z','source_sha256':'1'*64}]
                if name == 'same_harness_falsely_independent':
                    x['review']['verified_independent'] = True
                self.assertEqual(evaluate_signal(x)['next_action'], expected)

    def test_processed_without_acceptance_does_not_close(self):
        x=signal('CLOSE');x['delivery']['disposition']='HELD'
        y=evaluate_signal(x)
        self.assertEqual(y['next_action'],'HOLD_DELIVERY')
        self.assertIn('TRANSPORT_IS_NOT_ACCEPTANCE', [v['code'] for v in y['issues']])

    def test_unresolved_external_gate_blocks_close_even_without_claim(self):
        x=signal('CLOSE');x['open_gates']=['REMOTE_REVIEW_PENDING']
        self.assertEqual(evaluate_signal(x)['next_action'],'HOLD_DELIVERY')

    def test_router_exit_code_required_and_bound(self):
        for exit_code in (None,2,3):
            with self.subTest(exit_code=exit_code):
                x=signal();x['router']['exit_code']=exit_code
                with self.assertRaises(OPrepError): validate_signal(x)
        x=signal();x['router'].update(status='NOT_RUN',exit_code=None)
        self.assertEqual(evaluate_signal(x)['next_action'],'HOLD_ROUTING')

    def test_all_required_boolean_fields_fail_closed(self):
        x=signal();del x['router']['evidence_root_isolated']
        with self.assertRaises(OPrepError):validate_signal(x)
        x=signal();x['delivery']['ack_verified']='yes'
        with self.assertRaises(OPrepError):validate_signal(x)

    def test_malformed_metric_is_not_accepted(self):
        x=signal();x['metrics']=[{'name':'A','captured_at_utc':TS,'source_sha256':'not-hash'}]
        with self.assertRaises(OPrepError):validate_signal(x)

    def test_good_same_instant_normalized_offsets(self):
        x=signal();x['assertions']['metrics_simultaneous_claim']=True
        x['metrics']=[{'name':'A','captured_at_utc':TS,'source_sha256':Z},
                      {'name':'B','captured_at_utc':'2026-09-25T09:00:00+09:00','source_sha256':Z}]
        self.assertEqual(evaluate_signal(x)['next_action'],'ADVANCE_CANDIDATE')

    def test_fresh_context_requires_policy_and_distinct_adjudicator(self):
        x=signal('PUBLISH');x['review'].update(evidence_class='FRESH_CONTEXT',verified_independent=False)
        self.assertEqual(evaluate_signal(x)['next_action'],'HOLD_REVIEW')
        x['review'].update(fresh_context_policy_verified=True,adjudicator_separate=True)
        self.assertEqual(evaluate_signal(x)['next_action'],'ADVANCE_CANDIDATE')

    def test_nonrun_review_not_pass(self):
        x=signal('PUBLISH');x['review'].update(status='NOT_RUN', evidence_class='NOT_RUN')
        self.assertEqual(evaluate_signal(x)['next_action'],'HOLD_REVIEW')

    def test_secret_prioritized_over_other_findings(self):
        x=signal('CLOSE');x['execution']['secret_exposure']=True
        x['delivery']['ack_verified']=False;x['router']['policy_hash_verified']=False
        y=evaluate_signal(x)
        self.assertEqual(y['next_action'],'STOP_DISCLOSURE')
        self.assertGreaterEqual(len(y['issues']),3)

    def test_all_skipped_legacy_as_not_run(self):
        x=signal('PLAN');x['router'].update(status='NOT_RUN',exit_code=None,local_router_executed=False)
        self.assertEqual(evaluate_signal(x)['next_action'],'HOLD_ROUTING')

    def test_bad_datetime_is_rejected(self):
        x=signal();x['captured_at_utc']='2026-09-25T00:00:00'
        with self.assertRaises(OPrepError):validate_signal(x)


class ArchiveAuditTests(unittest.TestCase):
    def make_archive(self, location, *, tamper=False, member_override=None, unsafe_member=None):
        names = ['node_snapshot.json','router_policy_manifest.json','episodes.json','branch_probes.json',
                 'packet_reconciliation.json','test_receipts.json','open_gates.json','evidence_ledger.json','handoff.md']
        files = {n: b'{}' for n in names}
        files.update({
            'node_snapshot.json': json.dumps({
                'packet_metrics_lifetime': {'packets_sent_by_subject':1, 'packets_received_by_subject':0,'packet_deliveries_involving_subject':1},
                'packet_metrics_72h_window': {'window_start_utc':'2026-09-24T00:00:00Z',
                    'window_end_utc':'2026-09-25T23:00:00Z', 'packets_sent_by_subject':1,'packets_received_by_subject':0,'total_packets_in_window':1},
                'regression_test_baseline': {'passed':1,'skipped':0,'failures':0,'errors':0,'total_tests':1},
                'queue_status_disk':{'incoming':{'count':0}}}).encode(),
            'router_policy_manifest.json': json.dumps({'installed_router': {'package_version':'synthetic'}}).encode(),
            'episodes.json': b'[]', 'branch_probes.json':b'[]',
            'packet_reconciliation.json': json.dumps({
                'peer_packet_ledger':[{'delivery_id':'id','sender_node_id':'SUBJECT','receiver_node_id':'PEER','created_at':TS}],
                'secondary_packet_ledger':[]}).encode(),
            'test_receipts.json': b'{"test_suites":[{"total_tests":1}]}',
            'open_gates.json':b'{"gates":[]}', 'evidence_ledger.json':b'{"claims":[]}',
            'handoff.md':b'Synthetic test fixture',
        })
        manifest={'total_entries':10,'entries':[{'relative_path':k,'size_bytes':len(v),
                 'sha256':hashlib.sha256(v).hexdigest()} for k,v in files.items()]}
        if tamper:manifest['entries'][0]['sha256']='0'*64
        with zipfile.ZipFile(location,'w',zipfile.ZIP_DEFLATED) as z:
            for n,v in files.items(): z.writestr(n,v)
            if member_override: z.writestr(member_override,b'unlisted')
            if unsafe_member:
                if unsafe_member=='symlink':
                    info=zipfile.ZipInfo('link');info.create_system=3
                    info.external_attr=(stat.S_IFLNK | 0o777) <<16
                    z.writestr(info,'/tmp/something')
                else: z.writestr(unsafe_member,b'unsafe')
            z.writestr('manifest.json',json.dumps(manifest).encode())

    def test_synthetic_archive_passes_manifest_and_metrics(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'synthetic.zip';self.make_archive(p)
            r=audit_transport_bundle(str(p))
            self.assertTrue(r['manifest_verified'])
            self.assertEqual(r['observed_from_transported_ledger']['window_using_literal_recorded_timestamps']['total'],1)
            self.assertNotIn('WINDOW_LEDGER_MISMATCH',[f['code'] for f in r['findings']])
            self.assertEqual(r['router_status'],'NOT_RUN')

    def test_manifest_hash_tamper_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'synthetic.zip';self.make_archive(p,tamper=True)
            with self.assertRaisesRegex(OPrepError,'hash'):audit_transport_bundle(str(p))

    def test_extra_member_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'synthetic.zip';self.make_archive(p,member_override='unexpected.json')
            with self.assertRaises(OPrepError):audit_transport_bundle(str(p))

    def test_path_traversal_blocked_without_extracting(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'synthetic.zip';self.make_archive(p,unsafe_member='../escape.txt')
            with self.assertRaisesRegex(OPrepError,'unsafe'):audit_transport_bundle(str(p))

    def test_symlink_member_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'synthetic.zip';self.make_archive(p,unsafe_member='symlink')
            with self.assertRaisesRegex(OPrepError,'unsafe'):audit_transport_bundle(str(p))

    def test_duplicate_member_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'synthetic.zip'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('manifest.json','{}')
                z.writestr('Manifest.json','{}')
            with self.assertRaisesRegex(OPrepError,'duplicate'):audit_transport_bundle(str(p))

    def test_expansion_limit_before_read(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'synthetic.zip'
            with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:
                z.writestr('manifest.json','{}')
                z.writestr('data.json','x'*(11*1024*1024))
            with self.assertRaisesRegex(OPrepError,'expansion'):audit_transport_bundle(str(p))

    def test_immutability_of_input_archives(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'synthetic.zip';self.make_archive(p)
            h1=hashlib.sha256(p.read_bytes()).digest()
            audit_transport_bundle(str(p))
            self.assertEqual(h1,hashlib.sha256(p.read_bytes()).digest())

    def test_outside_shared_skill_dir_allowed_inside_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            _check_out_path(Path(temp)/'evidence'/'audit.json')
            with self.assertRaises(OPrepError):
                _check_out_path(Path(temp)/'skills'/'active_shared'/'o-prep'/'output'/'audit.json')

if __name__=='__main__':unittest.main()
