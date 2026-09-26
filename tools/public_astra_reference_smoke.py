#!/usr/bin/env python3
"""Test the real published Astra v7.1 validator through Maestro's adapter.

ONLY a public, immutable-commit reference test on CI: a matching repo commit and
its self-declared file manifest are never proof of node approval or runtime authority.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import tempfile
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from maestro_prep.coordinator import _verify_astra_manifest, ContractError  # noqa: E402
from test_astra_v71_adapter import OfficialAstraV71AdapterTests  # noqa: E402

HASH = lambda b: hashlib.sha256(b).hexdigest()

def smoke(reference: Path, expected_commit: str) -> dict:
    if not (reference / '.git').exists():
        raise ContractError('ASTRA_REFERENCE_REQUIRES_COMMIT_CHECKOUT')
    actual = subprocess.run(['git', '-C', str(reference), 'rev-parse', 'HEAD'],
                            capture_output=True, text=True, check=True, timeout=5).stdout.strip()
    if actual != expected_commit or not (len(expected_commit) == 40 and all(c in '0123456789abcdef' for c in expected_commit)):
        raise ContractError('ASTRA_REFERENCE_COMMIT_MISMATCH')
    manifest_bytes = (reference / 'CANDIDATE_HASHES.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    # Diagnose published mirror drift without altering its manifest, approving
    # changed bytes, or re-signing anything. Only public relative paths appear.
    mismatches = []
    for rel, declared in sorted(manifest.get('files', {}).items()):
        path = reference / rel
        if not path.is_file() or HASH(path.read_bytes()) != declared:
            mismatches.append(rel)
    # A published manifest mismatch MUST remain HOLD. Independently test the
    # published validator's compatibility using a clearly named temporary
    # synthetic reference overlay; never rewrite the official/public manifest.
    # The overlay is an integration fixture, NOT an integrity repair, node pin,
    # or promotion of any changed public file.
    temporary = None
    if mismatches:
        print(json.dumps({'schema':'ASTRA_PUBLIC_MIRROR_AUDIT_V1',
                          'manifest_status':'MISMATCH',
                          'changed_public_paths':mismatches,
                          'commit':actual,'node_authority':False}), flush=True)
        temporary = tempfile.TemporaryDirectory(prefix='maestro-public-astra-test-only-')
        snapshot = Path(temporary.name) / 'untrusted-public-bytes-fixture'
        shutil.copytree(reference, snapshot, ignore=shutil.ignore_patterns('.git'))
        actual_files = {}
        for rel in manifest['files']:
            if (not isinstance(rel, str) or not rel or '\\' in rel or
                    rel.startswith('/') or any(part in ('', '.', '..') or ':' in part
                    for part in rel.split('/'))):
                temporary.cleanup()
                raise ContractError('ASTRA_REFERENCE_UNSAFE_MANIFEST_PATH')
            actual_files[rel] = HASH((snapshot / rel).read_bytes())
        test_only_manifest = {'manifest_version':'TEST_ONLY_NOT_SOURCE_PROVENANCE',
                              'file_count':len(actual_files), 'files':actual_files,
                              'bundle_aggregate_sha256': HASH(''.join(
                                  f'{rel}  {actual_files[rel]}\n' for rel in sorted(actual_files)
                              ).encode('utf-8'))}
        (snapshot / 'CANDIDATE_HASHES.json').write_text(
            json.dumps(test_only_manifest, sort_keys=True) + '\n', encoding='utf-8')
        reference = snapshot
        manifest_bytes = (snapshot / 'CANDIDATE_HASHES.json').read_bytes()
        manifest = test_only_manifest
    try:
        _verify_astra_manifest(reference, HASH(manifest_bytes))
    except BaseException:
        if temporary:
            temporary.cleanup()
        raise
    if len(manifest['files']) != 25:
        raise ContractError('ASTRA_REFERENCE_INVENTORY_UNEXPECTED')

    f = OfficialAstraV71AdapterTests('runTest')
    f.setUp()
    try:
        # Use a *real* public validator and reference files, but synthetic
        # ephemeral private work/evidence; do NOT relabel this as node-approved.
        f.bundle = reference
        f.astra = reference / 'SKILL.md'
        f.script = reference / 'scripts' / 'validate_prework.py'
        f.schema = reference / 'schemas' / 'prework-plan.schema.json'
        f.profile = reference / 'profiles' / 'ai-maestro.md'
        f.lock['astra'] = {
            'skill_sha256': HASH(f.astra.read_bytes()),
            'approved_version_label': 'PUBLIC_REFERENCE_TEST_ONLY_NOT_NODE_APPROVED',
            'official_v71': {
                'validator_sha256': HASH(f.script.read_bytes()),
                'schema_sha256': HASH(f.schema.read_bytes()),
                'profile_sha256': HASH(f.profile.read_bytes()),
                'manifest_sha256': HASH(manifest_bytes),
            },
        }
        capture = json.loads((f.root / f.plan_rel).read_text())
        capture['astra_skill_sha256'] = f.lock['astra']['skill_sha256']
        f.write_json(f.plan_rel, capture)
        # Fill the published strict C1–C15-compatible sidecar contract. The
        # previous stub's deliberately partial JSON is not a real Astra plan.
        f.plan.update({
            'provenance': {
                'handoff': {'path': 'synthetic/handoff.md', 'sha256': '2'*64},
                'state': {'path': 'synthetic/state.json', 'sha256': 'NONE_RESOLVED'},
                'tree': {'worktree': 'NO_WORKTREE', 'branch': None},
                'drift_at_start': False,
            },
            'review': {
                'required': False,
                'independence_target': 'R0',
                'author_reviewer_distinct': None,
                'route_id': None,
                'bundle_path': None,
            },
            'artifact_hygiene': [{'artifact':'synthetic test receipt','location':'host-local',
                                  'retention_reason':None}],
        })
        f.plan['requirements'][0]['target']['review_independence'] = 'R0'
        f.plan['forecast']['best_reachable_cell'] = 'E2/R0'
        f.sync_plan()
        good = f.invoke()
        if good['next_action'] != 'BOUND_CANDIDATE_CHECKS_PASSED' or good['astra_official_validation']['status'] != 'LOCAL_VALIDATOR_PASS_NOT_APPROVAL':
            raise ContractError('ASTRA_PUBLIC_ADAPTER_GOOD_PLAN_FAILED:'+str(good.get('issue_codes')))
        # A producer-resigned invalid sidecar must still fail *official* C10.
        del f.plan['provenance']
        f.sync_plan()
        bad = f.invoke()
        if 'HOLD_ASTRA_OFFICIAL_VALIDATOR_FAILED' not in bad['issue_codes']:
            raise ContractError('ASTRA_PUBLIC_ADAPTER_INVALID_PLAN_NOT_REJECTED:'+str(bad.get('issue_codes')))
        if bad['next_action'] == 'BOUND_CANDIDATE_CHECKS_PASSED':
            raise ContractError('ASTRA_PUBLIC_ADAPTER_FAIL_OPEN')
        result = {
            'schema':'MAESTRO_PUBLIC_REFERENCE_SMOKE_V1',
            'public_reference_commit':actual,'manifest_files':len(manifest['files']),
            'real_public_validator_normal_sidecar':'PASS',
            'real_public_validator_bad_sidecar':'REJECTED',
            'public_manifest_status':'MISMATCH' if mismatches else 'MATCH',
            'public_validator_material': ('TEST_ONLY_REHASHED_PUBLIC_BYTES'
                                          if mismatches else 'PUBLIC_MANIFEST_MATCHED'),
            'node_approved_astra':'NOT_RUN', 'approved_leonardo':'NOT_RUN',
            'candidate_only':True,'decision_authority':'none',
        }
        if mismatches:
            print(json.dumps(result),flush=True)
            raise ContractError('ASTRA_PUBLIC_REFERENCE_MANIFEST_DRIFT')
        return result
    finally:
        f.doCleanups()
        if temporary:
            temporary.cleanup()

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('reference',type=Path)
    p.add_argument('--commit',required=True)
    args=p.parse_args()
    try:
        print(json.dumps(smoke(args.reference,args.commit),indent=2))
        return 0
    except (ContractError,OSError,ValueError,KeyError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
        print(json.dumps({'schema':'MAESTRO_PUBLIC_REFERENCE_SMOKE_V1',
                          'status':'HOLD','code':str(exc).split(':')[0],
                          'node_approved_astra':'NOT_RUN'}))
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
