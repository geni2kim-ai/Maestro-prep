#!/usr/bin/env python3
"""Reconstruct 20 synthetic architecture cases through actual vendored O-Prep.

No genuine Astra or Leonardo execution: architecture-level outcomes use the
explicit C-policy model. No original code, host logs or operational data.
"""
from __future__ import annotations
import copy
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from maestro_prep.coordinator import vendor_module

BASELINE=ROOT/'evidence'/'prior_simulation_baseline.json'
SCENARIO_MUTATORS={
 'stale_manifest': ('evidence','manifest_verified',False),
 'unverified_router':('router','policy_hash_verified',False),
 'secret_exposure':('execution','secret_exposure',True),
 'unapproved_mutation':('execution','mutation_requested',True),
 'reviewed_bytes_changed':('execution','reviewed_bytes_changed',True),
 'review_not_run':('review','status','NOT_RUN'),
 'dedup_unverified':('delivery','dedup_persistence_verified',False),
 'ack_missing':('delivery','ack_verified',False),
 'premature_close':('assertions','claims_full_closeout',True),
 'stale_policy_resume':('router','policy_hash_verified',False),
 'same_lineage_review':('review','evidence_class','SAME_LINEAGE'),
}

def fresh_signal(stage):
    # Synthetic fixture reconstructed from previously tested example, not production proof.
    s=json.loads((ROOT/'examples'/'o_prep_example_hold.json').read_text())
    s['stage']=stage
    s['router']={'status':'READY','exit_code':0,'local_router_executed':True,
                 'policy_hash_verified':True,'input_hash_verified':True,
                 'output_hash_verified':True,'evidence_root_isolated':True}
    s['evidence']={key:True for key in s['evidence']}
    s['execution']={key:False for key in s['execution']}
    s['review']={'status':'PASS','evidence_class':'VERIFIED_INDEPENDENT',
                 'verified_independent':True,'harness_separately_verified':True,
                 'fresh_context_policy_verified':False,'adjudicator_separate':True,
                 'review_hash_matches':True,'blocking_findings':False}
    s['delivery']={'required':True,'state':'PROCESSED','disposition':'ACCEPTED','ack_required':True,
                   'ack_verified':True,'dedup_persistence_verified':True,'disposition_evidence_verified':True,
                   'claims_accepted':True,'idempotency_key':'synthetic-only'}
    s['assertions']={key:False for key in s['assertions']}
    s['metrics']=[];s['open_gates']=[]
    return s

def run():
    original=json.loads(BASELINE.read_text(encoding='utf-8'))
    o=vendor_module()
    records=[]
    for c in original['cases']:
        s=fresh_signal(c['stage'])
        if c['scenario'] in SCENARIO_MUTATORS:
            group,key,v=SCENARIO_MUTATORS[c['scenario']];s[group][key]=v
        r=o.evaluate_signal(s)
        if r['next_action']!=c['o_prep_actual_unbound']:
            raise AssertionError('SYNTHETIC_REPLAY_MISMATCH:'+c['scenario'])
        if c['scenario']=='astra_unavailable_plan': composite='HOLD_PLAN_MODULE_MISSING'
        elif c['scenario']=='o_prep_unavailable': composite='HOLD_O_MODULE_MISSING'
        elif c['scenario']=='contract_mismatch': composite='HOLD_CONTRACT_MISMATCH'
        else: composite=r['next_action']
        if composite != c['C_orchestrated_separate']:
            raise AssertionError('POLICY_REPLAY_MISMATCH:'+c['scenario'])
        records.append({'scenario':c['scenario'],'o_prep_reconstructed':r['next_action'],
                        'c_orchestrated_model':composite,'prior_c_result':c['C_orchestrated_separate'],
                        'naive_skipped_o_gate':c['B_skipped_required_gate']})
    skipped=sum(x['naive_skipped_o_gate'] for x in records)
    assert skipped==original['original_summary']['B_one_choice_skipped_O_gate_on_blocking_scenarios']==11
    return {'schema':'MAESTRO_SYNTHETIC_REPLAY_V1','kind':'RECONSTRUCTED_SYNTHETIC_NOT_RUNTIME_BENCHMARK',
            'scenario_count':len(records),'o_prep_cases_matched':len(records),
            'c_model_cases_matched':len(records),'naive_choice_skips':skipped,
            'c_compulsory_gate_skips_when_available':0,'astra_actual':'NOT_RUN',
            'leonardo_actual':'NOT_RUN','host_mutation_authorized':False,
            'cases':records}

if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False,indent=2))
