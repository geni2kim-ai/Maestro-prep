#!/usr/bin/env python3
"""Offline synthetic connection replay; NEVER invokes an external Leonardo or Astra installation."""
from __future__ import annotations
import json
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / 'tests'))
from test_astra_v71_adapter import OfficialAstraV71AdapterTests  # Pinned synthetic validator only.


def run():
    cases = [
        ('baseline', None, 'BOUND_CANDIDATE_CHECKS_PASSED'),
        ('leonardo_omits_o', 'omit_o', 'HOLD_LEONARDO_MANDATORY_SKILL_MISSING'),
        ('leonardo_wrong_plan_gate', 'wrong_plan', 'HOLD_LEONARDO_WRONG_PLAN_BRANCH'),
        ('router_policy_changed', 'policy', 'HOLD_LEONARDO_ARTIFACT_PIN_MISMATCH'),
        ('router_stale', 'stale', 'HOLD_LEONARDO_ROUTE_STALE'),
        ('astra_after_router', 'sequential', 'BOUND_CANDIDATE_CHECKS_PASSED'),
        ('astra_before_router', 'out_of_order', 'HOLD_ASTRA_PLAN_PREDATES_ROUTE'),
        ('o_fail_plus_external_fail', 'independent_issues', 'MANIFEST_UNVERIFIED'),
    ]
    records = []
    for name, mutation, expected in cases:
        f = OfficialAstraV71AdapterTests('runTest')
        f.setUp()
        try:
            kw = {}
            if mutation == 'omit_o':
                f.refresh_route(overrides={'mandatory_skills':['astra-prep']})
            elif mutation == 'wrong_plan':
                f.refresh_route(overrides={'plan_gate':'REUSE_PINNED_PLAN'})
            elif mutation == 'policy':
                f.lock['leonardo']['policy_sha256'] = 'f' * 64
            elif mutation == 'stale':
                f.write_json(f.route_rel, {**json.loads((f.root / f.route_rel).read_text()),
                          'captured_at_utc':'2026-09-24T17:00:00Z'})
            elif mutation == 'sequential':
                f.write_json(f.route_rel, {**json.loads((f.root / f.route_rel).read_text()),
                          'captured_at_utc':'2026-09-24T23:00:00Z'})
                f.write_json(f.plan_rel, {**json.loads((f.root / f.plan_rel).read_text()),
                          'captured_at_utc':'2026-09-25T00:30:00Z'})
                f.work['captured_at_utc'] = '2026-09-25T01:00:00Z'
                f.signal['captured_at_utc'] = '2026-09-25T01:00:00Z'
                f.save_index()
            elif mutation == 'out_of_order':
                f.write_json(f.route_rel, {**json.loads((f.root / f.route_rel).read_text()),
                          'captured_at_utc':'2026-09-24T23:30:00Z'})
                f.write_json(f.plan_rel, {**json.loads((f.root / f.plan_rel).read_text()),
                          'captured_at_utc':'2026-09-24T23:00:00Z'})
            elif mutation == 'independent_issues':
                f.signal['evidence']['manifest_verified'] = False
                kw.update(astra_skill_path=None, leonardo_route_rel=None)
            result = f.invoke(**kw)
            observed = result['next_action'] if expected.startswith('BOUND') else expected if expected in result['issue_codes'] else 'NO_EXPECTED_ISSUE'
            passed = observed == expected
            records.append({'scenario':name, 'matched':passed, 'next_action':result['next_action'],
                            'issue_codes':result['issue_codes']})
        finally:
            f.doCleanups()
    if not all(x['matched'] for x in records):
        raise AssertionError('CONNECTION_REPLAY_MISMATCH')
    return {'schema':'MAESTRO_CONNECTION_SYNTHETIC_V1','candidate_only':True,
            'astra_actual':'NOT_RUN','leonardo_actual':'NOT_RUN',
            'cases':len(cases), 'matched':len(cases), 'records':records}


if __name__ == '__main__':
    print(json.dumps(run(),ensure_ascii=False,indent=2))
