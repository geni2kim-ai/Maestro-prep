"""Read-only coordinator: conditional Astra-Prep, compulsory O-Prep, pinned Leonardo evidence.

Astra/Leonardo are EXTERNAL authoritative node installations. This module executes
neither of them: its receipts are checked against locally present bytes but may be
producer-authored. Passing is never permission to mutate, publish or deploy.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
VENDOR = BASE / 'components' / 'o_prep_v0_3' / 'src'
SHA256 = re.compile(r'^[a-f0-9]{64}$')

class ContractError(ValueError):
    """Non-sensitive failure code; never include node-local paths or data."""


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(data: bytes, code: str) -> dict:
    def unique(pairs):
        out = {}
        for k, v in pairs:
            if k in out: raise ContractError('DUPLICATE_JSON_KEY')
            out[k] = v
        return out
    def bad_constant(_): raise ContractError('NONFINITE_JSON_NUMBER')
    try: obj = json.loads(data.decode('utf-8'), object_pairs_hook=unique, parse_constant=bad_constant)
    except (UnicodeError, json.JSONDecodeError) as exc: raise ContractError(code) from exc
    if not isinstance(obj, dict): raise ContractError(code)
    return obj


def read_json(path: Path, cap: int = 131072) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > cap:
        raise ContractError('JSON_SOURCE_MISSING_OR_INVALID')
    return _json_bytes(path.read_bytes(), 'INVALID_JSON_SOURCE')


def _timezone(value: str) -> datetime:
    if not isinstance(value, str) or not (value.endswith('Z') or re.search(r'[+-]\d\d:\d\d$', value)):
        raise ContractError('TIMEZONE_REQUIRED')
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if dt.tzinfo is None: raise ValueError('naive')
        return dt
    except ValueError as exc: raise ContractError('INVALID_TIMESTAMP') from exc


def _fields(obj: dict, names: set[str], code: str) -> None:
    if set(obj) != names: raise ContractError(code)


def _sha(value: str, code: str) -> None:
    if not isinstance(value, str) or not SHA256.fullmatch(value): raise ContractError(code)


def check_work(work: dict) -> None:
    _fields(work, {'schema','work_unit','node_id','captured_at_utc','stage','intent','task_sha256','plan_sha256'}, 'WORK_FIELDS_INVALID')
    if work['schema'] != 'MAESTRO_PREP_WORK_V1' or work['stage'] not in {'PLAN','EXECUTE','PUBLISH','CLOSE'}:
        raise ContractError('WORK_SCHEMA_OR_STAGE_INVALID')
    if work['intent'] not in {'NEW_PLAN','REPLAN','REUSE_PLAN','READ_ONLY'}:
        raise ContractError('WORK_INTENT_INVALID')
    if any(not isinstance(work[k], str) or not work[k].strip() or len(work[k]) > 160 for k in ('work_unit','node_id')):
        raise ContractError('WORK_ID_INVALID')
    _timezone(work['captured_at_utc'])
    _sha(work['task_sha256'], 'TASK_HASH_INVALID')
    if work['plan_sha256'] is not None: _sha(work['plan_sha256'], 'PLAN_HASH_INVALID')
    if work['intent'] == 'REUSE_PLAN' and work['plan_sha256'] is None:
        raise ContractError('REUSED_PLAN_NEEDS_PIN')
    if work['intent'] == 'READ_ONLY' and work['stage'] != 'PLAN':
        raise ContractError('READ_ONLY_STAGE_INVALID')


def check_lock(lock: dict) -> None:
    _fields(lock, {'schema','astra','leonardo'}, 'LOCK_FIELDS_INVALID')
    if lock['schema'] != 'MAESTRO_PREP_LOCK_V1': raise ContractError('LOCK_SCHEMA_INVALID')
    _fields(lock['astra'], {'skill_sha256','approved_version_label'}, 'ASTRA_LOCK_INVALID')
    _fields(lock['leonardo'], {'router_version','policy_sha256'}, 'LEONARDO_LOCK_INVALID')
    _sha(lock['astra']['skill_sha256'], 'ASTRA_SKILL_HASH_INVALID')
    _sha(lock['leonardo']['policy_sha256'], 'LEONARDO_POLICY_HASH_INVALID')
    for group,key in [('astra','approved_version_label'),('leonardo','router_version')]:
        x=lock[group][key]
        if not isinstance(x,str) or not x.strip() or len(x)>100: raise ContractError('COMPONENT_VERSION_INVALID')


def _relative_file(root: Path, rel: str, limit: int = 1024*1024) -> bytes:
    if not isinstance(rel, str) or not rel or '\\' in rel or '\x00' in rel or rel.startswith(('/', './')):
        raise ContractError('UNSAFE_EVIDENCE_REFERENCE')
    parts = rel.split('/')
    if any(x in {'.','..',''} or x.endswith((' ','.')) or ':' in x for x in parts):
        raise ContractError('UNSAFE_EVIDENCE_REFERENCE')
    node = root
    for part in parts:
        node = node / part
        if node.is_symlink(): raise ContractError('EVIDENCE_SYMLINK_FORBIDDEN')
    if not node.is_file() or not node.resolve().is_relative_to(root.resolve()):
        raise ContractError('EVIDENCE_FILE_MISSING')
    if node.stat().st_size > limit: raise ContractError('EVIDENCE_SIZE_LIMIT')
    return node.read_bytes()


def vendor_module():
    """Verify O-Prep exact copied source against this package's pinned manifest."""
    manifest = read_json(BASE / 'components' / 'o_prep_v0_3' / 'SOURCE_PIN.json')
    if manifest.get('component') != 'o-prep' or manifest.get('version') != '0.3.0-prep':
        raise ContractError('O_MODULE_VERSION_MISMATCH')
    for name in ('src/o_prep.py', 'src/evidence_bindings.py'):
        if name not in manifest.get('files', {}): raise ContractError('O_MODULE_PIN_INCOMPLETE')
        fp = BASE / 'components' / 'o_prep_v0_3' / name
        if not fp.is_file() or fp.is_symlink() or _hash(fp.read_bytes()) != manifest['files'][name]:
            raise ContractError('O_MODULE_HASH_MISMATCH')
    if str(VENDOR) not in sys.path: sys.path.insert(0,str(VENDOR))
    module = importlib.import_module('o_prep')
    if Path(module.__file__).resolve() != (VENDOR/'o_prep.py').resolve():
        raise ContractError('O_MODULE_IMPORT_PATH_MISMATCH')
    return module


def _astra_binding(work: dict, lock: dict, root: Path, skill_path: Path | None, plan_receipt_rel: str | None) -> list[str]:
    issues=[]
    if work['intent'] == 'READ_ONLY': return issues
    if skill_path is None: return ['HOLD_PLAN_MODULE_MISSING']
    try:
        # Astra remains an exact, separately approved local installation.
        if skill_path.is_symlink() or not skill_path.is_file() or _hash(skill_path.read_bytes()) != lock['astra']['skill_sha256']:
            return ['HOLD_ASTRA_SOURCE_PIN']
    except OSError:
        return ['HOLD_ASTRA_SOURCE_PIN']
    if not plan_receipt_rel: return ['CALL_ASTRA_PREP' if work['intent'] in {'NEW_PLAN','REPLAN'} else 'HOLD_EXISTING_PLAN_RECEIPT']
    receipt = _json_bytes(_relative_file(root,plan_receipt_rel), 'ASTRA_RECEIPT_JSON_INVALID')
    expected = {'schema','work_unit','node_id','astra_skill_sha256','plan_sha256','plan_file','status','captured_at_utc'}
    if set(receipt) != expected or receipt.get('schema') != 'ASTRA_PREP_CAPTURE_V1': return ['HOLD_ASTRA_RECEIPT_CONTRACT']
    if any(receipt[k] != work[k] for k in ('work_unit','node_id')) or receipt['astra_skill_sha256'] != lock['astra']['skill_sha256']:
        return ['HOLD_ASTRA_RECEIPT_BINDING']
    if receipt['status'] != 'READY_FOR_LOCAL_CANDIDATE_WORK': return ['HOLD_ASTRA_PLAN_NOT_READY']
    _sha(receipt['plan_sha256'],'ASTRA_RECEIPT_PLAN_HASH_INVALID')
    if work['plan_sha256'] is not None and work['plan_sha256'] != receipt['plan_sha256']:
        return ['HOLD_ASTRA_PLAN_REVISION_CHANGED']
    if _timezone(receipt['captured_at_utc']) > _timezone(work['captured_at_utc']):
        return ['HOLD_ASTRA_RECEIPT_FROM_FUTURE']
    if _hash(_relative_file(root,receipt['plan_file'])) != receipt['plan_sha256']:
        return ['HOLD_ASTRA_PLAN_BYTES_CHANGED']
    return issues


def _route_binding(work: dict, lock: dict, root: Path, index_path: Path, route_rel: str | None) -> list[str]:
    if not route_rel: return ['HOLD_LEONARDO_ROUTE_CAPTURE_MISSING']
    receipt = _json_bytes(_relative_file(root, route_rel), 'LEONARDO_RECEIPT_JSON_INVALID')
    required = {'schema','work_unit','node_id','router_version','task_sha256','policy_sha256',
                'routing_output_sha256','exit_code','execution_state','captured_at_utc'}
    if set(receipt) != required or receipt.get('schema') != 'LEONARDO_ROUTE_CAPTURE_V1':
        return ['HOLD_LEONARDO_CAPTURE_CONTRACT']
    if any(receipt[k] != work[k] for k in ('work_unit','node_id')) or receipt['router_version'] != lock['leonardo']['router_version']:
        return ['HOLD_LEONARDO_BINDING_MISMATCH']
    if receipt['execution_state'] != 'READY' or type(receipt['exit_code']) is not int or receipt['exit_code'] != 0:
        return ['HOLD_LEONARDO_NOT_READY']
    if _timezone(receipt['captured_at_utc']) != _timezone(work['captured_at_utc']):
        return ['HOLD_LEONARDO_SNAPSHOT_MISMATCH']
    idx = read_json(index_path)
    if not isinstance(idx.get('receipts'),list):return ['HOLD_O_INDEX_INVALID']
    rows = {r.get('role'):r for r in idx['receipts'] if isinstance(r,dict)}
    for role, captured, expected in [
        ('router_input',receipt['task_sha256'],work['task_sha256']),
        ('router_policy',receipt['policy_sha256'],lock['leonardo']['policy_sha256']),
        ('router_output',receipt['routing_output_sha256'],None)]:
        if role not in rows or rows[role].get('sha256') != captured or (expected is not None and captured != expected):
            return ['HOLD_LEONARDO_ARTIFACT_PIN_MISMATCH']
    return []


def decide(work: dict, lock: dict, o_signal: dict, index_path: Path, evidence_root: Path,
           *, astra_skill_path: Path | None = None, astra_plan_receipt_rel: str | None = None,
           leonardo_route_rel: str | None = None) -> dict:
    """Mandatory O-Prep bound gate; never executes Astra, Leonardo or host mutations."""
    check_work(work); check_lock(lock)
    if evidence_root.is_symlink() or not evidence_root.is_dir():raise ContractError('EVIDENCE_ROOT_INVALID')
    if (work['work_unit'],work['node_id'],work['stage'],_timezone(work['captured_at_utc'])) != (
            o_signal.get('work_unit'),o_signal.get('node_id'),o_signal.get('stage'),_timezone(o_signal.get('captured_at_utc'))):
        raise ContractError('O_SIGNAL_WORK_BINDING_MISMATCH')
    try:
        o = vendor_module()
    except (ContractError, ImportError, OSError):
        return _result(work,None,['HOLD_O_MODULE_MISSING'],False)
    try:
        decision = o.evaluate_bound_signal(o_signal,str(index_path),str(evidence_root))
    except (o.OPrepError, ValueError, OSError):
        return _result(work,None,['HOLD_O_BINDING_FAILED'],True)
    issues = [x['code'] for x in decision['issues']]
    if decision['next_action'] != 'ADVANCE_CANDIDATE':
        # Do not use producer-written booleans to bypass byte checks.
        return _result(work,decision,issues,True)
    if decision.get('evidence_binding',{}).get('status') != 'LOCAL_BYTES_VERIFIED_ONLY':
        return _result(work,decision,issues+['HOLD_O_BINDING_FAILED'],True)
    try:
        issues += _route_binding(work,lock,evidence_root,index_path,leonardo_route_rel)
        issues += _astra_binding(work,lock,evidence_root,astra_skill_path,astra_plan_receipt_rel)
    except ContractError as exc:
        issues.append(str(exc))
    return _result(work,decision,issues,True)


def _result(work: dict, o_decision: dict | None, issues: list[str], o_invoked: bool) -> dict:
    # O-Prep stop/hold is never overridden by Astra READY or a Leonardo branch.
    current = o_decision['next_action'] if o_decision is not None else ('HOLD_O_BINDING_FAILED' if 'HOLD_O_BINDING_FAILED' in issues else 'HOLD_O_MODULE_MISSING')
    if current != 'ADVANCE_CANDIDATE':
        next_action=current
    elif issues:
        next_action='HOLD_INTEGRATION' if any(x != 'CALL_ASTRA_PREP' for x in issues) else 'CALL_ASTRA_PREP'
    else:
        next_action='BOUND_CANDIDATE_CHECKS_PASSED'
    return {
        'schema':'MAESTRO_PREP_DECISION_V1','work_unit':work['work_unit'],'node_id':work['node_id'],
        'stage':work['stage'],'intent':work['intent'],'next_action':next_action,
        'issue_codes':sorted(set(issues)),'o_prep_gate_invoked':o_invoked,
        'o_prep_decision':current,'evidence_class':'LOCAL_BYTES_ONLY_PRODUCER_RECEIPTS',
        'astra_execution':'NOT_RUN_BY_MAESTRO','leonardo_execution':'NOT_RUN_BY_MAESTRO',
        'host_mutation_authorized':False,'candidate_only':True,'finality':'non_final',
        'decision_authority':'none','live_effect':'NOT_RUN',
    }


def verify_generic_file(path: Path, expected_sha: str) -> dict:
    _sha(expected_sha,'EXPECTED_HASH_INVALID')
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 25*1024*1024:
        raise ContractError('AUDIT_FILE_INVALID')
    observed = _hash(path.read_bytes())
    return {'schema':'MAESTRO_READ_ONLY_AUDIT_V1','sha256_matches':observed==expected_sha,
            'next_action':'READ_ONLY_EVIDENCE_MATCH' if observed==expected_sha else 'HOLD_SOURCE',
            'host_mutation_authorized':False,'decision_authority':'none','candidate_only':True}
