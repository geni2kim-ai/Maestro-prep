"""Read-only coordinator: conditional Astra-Prep, compulsory O-Prep, pinned Leonardo evidence.

Astra/Leonardo are EXTERNAL authoritative node installations. This module executes
neither of them: its receipts are checked against locally present bytes but may be
producer-authored. Passing is never permission to mutate, publish or deploy.
"""
from __future__ import annotations

import builtins
import hashlib
import json
import re
import stat
from types import ModuleType
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn, Protocol, cast

BASE = Path(__file__).resolve().parents[1]
VENDOR = BASE / 'components' / 'o_prep_v0_3' / 'src'
SHA256 = re.compile(r'^[a-f0-9]{64}$')
_REPARSE_POINT = getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)
JsonDict = dict[str, Any]


class OPrepModule(Protocol):
    __file__: str | None
    OPrepError: type[Exception]
    VERSION: str

    def evaluate_bound_signal(
        self, signal: JsonDict, receipt_index_path: str, evidence_root: str
    ) -> JsonDict: ...

    def audit_transport_bundle(self, zip_path: str, peer_audit: str | None = None) -> JsonDict: ...


class ContractError(ValueError):
    """Non-sensitive failure code; never include node-local paths or data."""


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(data: bytes, code: str) -> JsonDict:
    def unique(pairs: list[tuple[str, Any]]) -> JsonDict:
        out: JsonDict = {}
        for k, v in pairs:
            if k in out: raise ContractError('DUPLICATE_JSON_KEY')
            out[k] = v
        return out
    def bad_constant(_value: str) -> NoReturn: raise ContractError('NONFINITE_JSON_NUMBER')
    try: source = data.decode('utf-8')
    except UnicodeError as exc: raise ContractError(code) from exc
    # Reject depth bombs consistently across Python parser versions. Brackets inside
    # quoted JSON strings (including escaped quotes) must not count as containers.
    depth = 0
    quoted = False
    escaped = False
    for char in source:
        if quoted:
            if escaped: escaped = False
            elif char == '\\': escaped = True
            elif char == '"': quoted = False
        elif char == '"': quoted = True
        elif char in '{[':
            depth += 1
            if depth > 256: raise ContractError('JSON_NESTING_LIMIT')
        elif char in '}]':
            depth -= 1
    try: obj = json.loads(source, object_pairs_hook=unique, parse_constant=bad_constant)
    except ContractError: raise
    except (json.JSONDecodeError, ValueError, RecursionError) as exc: raise ContractError(code) from exc
    if not isinstance(obj, dict): raise ContractError(code)
    return cast(JsonDict, obj)


def _is_link(path: Path) -> bool:
    """Symlink, NTFS junction or other reparse point; `is_symlink()` misses junctions."""
    try: st = path.lstat()
    except OSError: return False
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, 'st_file_attributes', 0) & _REPARSE_POINT)


def _link_free_ancestry(path: Path) -> bool:
    current = path.absolute()
    while True:
        if _is_link(current): return False
        if current == current.parent: return True
        current = current.parent


def read_json(path: Path, cap: int = 131072) -> JsonDict:
    if _is_link(path) or not path.is_file() or path.stat().st_size > cap:
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


def _fields(obj: JsonDict, names: set[str], code: str) -> None:
    if not isinstance(obj, dict) or set(obj) != names: raise ContractError(code)


def _sha(value: str, code: str) -> None:
    if not isinstance(value, str) or not SHA256.fullmatch(value): raise ContractError(code)


def check_work(work: JsonDict) -> None:
    _fields(work, {'schema','work_unit','node_id','captured_at_utc','stage','intent','task_sha256','plan_sha256'}, 'WORK_FIELDS_INVALID')
    if (work['schema'] != 'MAESTRO_PREP_WORK_V1' or not isinstance(work['stage'], str)
            or work['stage'] not in {'PLAN','EXECUTE','PUBLISH','CLOSE'}):
        raise ContractError('WORK_SCHEMA_OR_STAGE_INVALID')
    if not isinstance(work['intent'], str) or work['intent'] not in {'NEW_PLAN','REPLAN','REUSE_PLAN','READ_ONLY'}:
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


def check_lock(lock: JsonDict) -> None:
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
        if _is_link(node): raise ContractError('EVIDENCE_SYMLINK_FORBIDDEN')
    if not node.is_file() or not node.resolve().is_relative_to(root.resolve()):
        raise ContractError('EVIDENCE_FILE_MISSING')
    if node.stat().st_size > limit: raise ContractError('EVIDENCE_SIZE_LIMIT')
    return node.read_bytes()


def _verified_vendor_bytes(manifest: JsonDict, name: str) -> tuple[Path, bytes]:
    """Read a source snapshot once; execute only the exact bytes just hashed."""
    pins = manifest.get('files')
    if not isinstance(pins, dict) or name not in pins:
        raise ContractError('O_MODULE_PIN_INCOMPLETE')
    digest = pins[name]
    _sha(digest, 'O_MODULE_PIN_INVALID')
    fp = BASE / 'components' / 'o_prep_v0_3' / name
    if not fp.is_file() or _is_link(fp):
        raise ContractError('O_MODULE_HASH_MISMATCH')
    data = fp.read_bytes()
    if _hash(data) != digest:
        raise ContractError('O_MODULE_HASH_MISMATCH')
    return fp, data


def _exec_pinned(name: str, path: Path, data: bytes, *,
                 bindings: ModuleType | None = None) -> ModuleType:
    """Run pinned code without importing preloaded names from sys.modules.

    Source and dependency bytes are independently hashed first. This is *not*
    a Python sandbox: a compromised interpreter/process can still tamper.
    """
    module = ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = ''
    if bindings is not None:
        importer = builtins.__import__
        def pinned_import(target: str, globals: JsonDict | None = None,
                          locals: JsonDict | None = None, fromlist: tuple[str, ...] = (),
                          level: int = 0) -> Any:
            if target == 'evidence_bindings' and level == 0:
                return bindings
            return importer(target, globals, locals, fromlist, level)
        safe_builtins = vars(builtins).copy()
        safe_builtins['__import__'] = pinned_import
        module.__dict__['__builtins__'] = safe_builtins
    exec(compile(data, str(path), 'exec'), module.__dict__)
    return module


def vendor_module() -> OPrepModule:
    """Load fresh, directly from both hash-verified source snapshots.

    In particular, never trust sys.modules['o_prep'] or a cached
    sys.modules['evidence_bindings'] with a spoofed __file__ attribute.
    """
    manifest = read_json(BASE / 'components' / 'o_prep_v0_3' / 'SOURCE_PIN.json')
    if manifest.get('component') != 'o-prep' or manifest.get('version') != '0.3.0-prep':
        raise ContractError('O_MODULE_VERSION_MISMATCH')
    bind_path, bind_bytes = _verified_vendor_bytes(manifest, 'src/evidence_bindings.py')
    source_path, source_bytes = _verified_vendor_bytes(manifest, 'src/o_prep.py')
    bindings = _exec_pinned('_maestro_pinned_evidence_bindings', bind_path, bind_bytes)
    module = _exec_pinned('_maestro_pinned_o_prep', source_path, source_bytes, bindings=bindings)
    if getattr(module, 'VERSION', None) != '0.3.0-prep':
        raise ContractError('O_MODULE_VERSION_MISMATCH')
    return cast(OPrepModule, module)


def _astra_binding(work: JsonDict, lock: JsonDict, root: Path, skill_path: Path | None, plan_receipt_rel: str | None) -> list[str]:
    issues: list[str] = []
    if work['intent'] == 'READ_ONLY': return issues
    if skill_path is None: return ['HOLD_PLAN_MODULE_MISSING']
    try:
        # Astra remains an exact, separately approved local installation.
        if _is_link(skill_path) or not skill_path.is_file() or _hash(skill_path.read_bytes()) != lock['astra']['skill_sha256']:
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


def _route_binding(work: JsonDict, lock: JsonDict, root: Path, index_path: Path, route_rel: str | None) -> list[str]:
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
    rows: dict[str, JsonDict] = {}
    for row in idx['receipts']:
        if not isinstance(row, dict) or not isinstance(row.get('role'), str):
            return ['HOLD_O_INDEX_INVALID']
        rows[row['role']] = row
    for role, captured, expected in [
        ('router_input', receipt['task_sha256'], work['task_sha256']),
        ('router_policy', receipt['policy_sha256'], lock['leonardo']['policy_sha256']),
        ('router_output', receipt['routing_output_sha256'], None)]:
        if role not in rows or rows[role].get('sha256') != captured or (expected is not None and captured != expected):
            return ['HOLD_LEONARDO_ARTIFACT_PIN_MISMATCH']
    # An index SHA confirms bytes, *not* that a producer's separate READY
    # capture agrees with those bytes. Bind the actual recorded route contract.
    # Re-read after the O-Prep gate to detect a changed artifact between gates.
    route_row = rows['router_output']
    route_path = route_row.get('path')
    if not isinstance(route_path, str):
        return ['HOLD_LEONARDO_ARTIFACT_PIN_MISMATCH']
    route_bytes = _relative_file(root, route_path, limit=2*1024*1024)
    if _hash(route_bytes) != receipt['routing_output_sha256']:
        return ['HOLD_LEONARDO_ARTIFACT_BYTES_CHANGED']
    route = _json_bytes(route_bytes, 'LEONARDO_ROUTING_OUTPUT_INVALID')
    # Accept only a captured *local candidate* route, never a blocked/held
    # Leonardo contract falsely described as READY in the adapter receipt.
    if (route.get('execution_state') != 'READY_FOR_LOCAL_CANDIDATE_WORK'
            or route.get('candidate_work_allowed') is not True):
        return ['HOLD_LEONARDO_RAW_ROUTE_NOT_READY']
    request = route.get('request')
    bindings = route.get('input_bindings')
    if not isinstance(request, dict) or not isinstance(bindings, dict):
        return ['HOLD_LEONARDO_RAW_ROUTE_BINDING']
    if (request.get('request_sha256') != receipt['task_sha256']
            or bindings.get('policy_sha256') != receipt['policy_sha256']):
        return ['HOLD_LEONARDO_RAW_ROUTE_BINDING']
    guard = route.get('guard')
    if not isinstance(guard, dict) or not isinstance(guard.get('blocks'), list) or guard['blocks']:
        return ['HOLD_LEONARDO_RAW_ROUTE_NOT_READY']
    return []


def decide(work: JsonDict, lock: JsonDict, o_signal: JsonDict, index_path: Path, evidence_root: Path,
           *, astra_skill_path: Path | None = None, astra_plan_receipt_rel: str | None = None,
           leonardo_route_rel: str | None = None) -> JsonDict:
    """Mandatory O-Prep bound gate; never executes Astra, Leonardo or host mutations."""
    check_work(work); check_lock(lock)
    # The root and every ancestor must be link-free, including junctions the pinned O-Prep check misses.
    if not evidence_root.is_dir() or not _link_free_ancestry(evidence_root):raise ContractError('EVIDENCE_ROOT_INVALID')
    if (work['work_unit'],work['node_id'],work['stage'],_timezone(work['captured_at_utc'])) != (
            o_signal.get('work_unit'),o_signal.get('node_id'),o_signal.get('stage'),_timezone(cast(str, o_signal.get('captured_at_utc')))):
        raise ContractError('O_SIGNAL_WORK_BINDING_MISMATCH')
    try:
        o = vendor_module()
    except Exception:
        return _result(work, None, ['HOLD_O_MODULE_MISSING'], False)
    try:
        decision = o.evaluate_bound_signal(o_signal, str(index_path), str(evidence_root))
        decision_issues = cast(list[JsonDict], decision['issues'])
        issues: list[str] = [cast(str, x['code']) for x in decision_issues]
        if decision['next_action'] != 'ADVANCE_CANDIDATE':
            return _result(work, decision, issues, True)
        if decision.get('evidence_binding', {}).get('status') != 'LOCAL_BYTES_VERIFIED_ONLY':
            return _result(work, decision, issues + ['HOLD_O_BINDING_FAILED'], True)
        try:
            issues += _route_binding(work, lock, evidence_root, index_path, leonardo_route_rel)
            issues += _astra_binding(work, lock, evidence_root, astra_skill_path, astra_plan_receipt_rel)
        except ContractError as exc:
            issues.append(str(exc))
        return _result(work, decision, issues, True)
    except Exception:
        # Untrusted external evaluation and malformed result shapes must fail closed.
        # Do not catch BaseException.
        return _result(work, None, ['HOLD_O_BINDING_FAILED'], True)

def _result(work: JsonDict, o_decision: JsonDict | None, issues: list[str], o_invoked: bool) -> JsonDict:
    # O-Prep stop/hold is never overridden by Astra READY or a Leonardo branch.
    current = cast(str, o_decision['next_action']) if o_decision is not None else ('HOLD_O_BINDING_FAILED' if 'HOLD_O_BINDING_FAILED' in issues else 'HOLD_O_MODULE_MISSING')
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


def verify_generic_file(path: Path, expected_sha: str) -> JsonDict:
    _sha(expected_sha,'EXPECTED_HASH_INVALID')
    if not path.is_file() or _is_link(path) or path.stat().st_size > 25*1024*1024:
        raise ContractError('AUDIT_FILE_INVALID')
    observed = _hash(path.read_bytes())
    return {'schema':'MAESTRO_READ_ONLY_AUDIT_V1','sha256_matches':observed==expected_sha,
            'next_action':'READ_ONLY_EVIDENCE_MATCH' if observed==expected_sha else 'HOLD_SOURCE',
            'host_mutation_authorized':False,'decision_authority':'none','candidate_only':True}
