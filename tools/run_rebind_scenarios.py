#!/usr/bin/env python3
"""Synthetic Leonardo/Astra cross-binding replay, with no node access."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
from test_connection_rebind import CrossBindingTests
from test_maestro import Fixture


def run():
    scenarios=[
        ('valid_pinned_synthetic_bundle', None, 'BOUND_CANDIDATE_CHECKS_PASSED',None),
        ('changed_task_previous_sidecar', 'task_drift', 'HOLD_INTEGRATION','HOLD_ASTRA_PLAN_TASK_CHANGED'),
        ('changed_route_previous_sidecar', 'route_drift', 'HOLD_INTEGRATION','HOLD_ASTRA_PLAN_ROUTE_CHANGED'),
        ('unbound_legacy_v1_receipt', 'legacy_v1', 'HOLD_INTEGRATION','HOLD_ASTRA_LEGACY_RECEIPT_UNBOUND'),
        ('pinned_bundle_plan_pending', 'plan_pending', 'CALL_ASTRA_PREP',None),
        ('tampered_bundle_plan_pending', 'tampered_pending', 'HOLD_INTEGRATION','ASTRA_MANIFEST_FILE_MISMATCH'),
        ('o_prep_loader_fault', 'o_failure', 'HOLD_O_MODULE_MISSING','HOLD_O_MODULE_MISSING'),
        ('unapproved_legacy_bundle', 'legacy_bundle', 'HOLD_INTEGRATION','HOLD_ASTRA_OFFICIAL_PIN_MISSING'),
    ]
    records=[]
    for name,mutation,expected,issue in scenarios:
        t=Fixture('runTest') if mutation=='legacy_bundle' else CrossBindingTests('runTest')
        t.setUp()
        try:
            kwargs={}
            if mutation=='task_drift':t._replace_task_and_rebind_route_only()
            elif mutation=='route_drift': t.refresh_route(overrides={'mandatory_skills':['o-prep','astra-prep','extra-skill']})
            elif mutation=='legacy_v1':
                p=t.root/t.plan_rel
                capture=json.loads(p.read_text())
                capture['schema']='ASTRA_PREP_CAPTURE_V1'
                del capture['task_sha256'];del capture['origin_route_output_sha256']
                p.write_text(json.dumps(capture))
            elif mutation=='plan_pending':kwargs['astra_plan_receipt_rel']=None
            elif mutation=='tampered_pending':
                t.schema.write_bytes(b'{"tampered":true}')
                kwargs['astra_plan_receipt_rel']=None
            if mutation=='o_failure':
                with patch('maestro_prep.coordinator.vendor_module',side_effect=ValueError('synthetic fault')):
                    result=t.invoke(**kwargs)
            else:
                result=t.invoke(**kwargs)
            matched=result['next_action']==expected and (issue is None or issue in result['issue_codes'])
            records.append({'case':name,'matched':matched,'next_action':result['next_action'],
                            'expected_issue':issue,'issues':result['issue_codes']})
        finally:
            t.doCleanups()
    if not all(r['matched'] for r in records):
        raise AssertionError('REBIND_SYNTHETIC_REPLAY_MISMATCH')
    return {'schema':'MAESTRO_SYNTHETIC_REBIND_V1','cases':len(records),'matched':len(records),
            'actual_leonardo':'NOT_RUN','actual_astra_validator':'NOT_RUN_SYNTHETIC_STUB_ONLY',
            'candidate_only':True,'records':records}


if __name__=='__main__': print(json.dumps(run(),ensure_ascii=False,indent=2))
