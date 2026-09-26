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
import subprocess
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
VENDOR = BASE / 'components' / 'o_prep_v0_3' / 'src'
SHA256 = re.compile(r'^[a-f0-9]{64}$')
MAX_ROUTE_AGE = timedelta(hours=4)  # Candidate-only conservative freshness window, owner must ratify.
CLOCK_SKEW_BUDGET = timedelta(minutes=5)  # Local host clock is not remote time attestation.
ROUTE_OUTPUT_FIELDS = frozenset({'schema','work_unit','node_id','stage','intent',
    'task_sha256','policy_sha256','execution_state','mandatory_skills','plan_gate','review_required'})

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


def read_json_owner_pinned(path: Path, owner_supplied_sha256: str, cap: int = 131072) -> dict:
    """Bind CLI lock bytes to an owner-supplied digest from outside this work.

    This is byte integrity ONLY; the caller must obtain the digest through
    their already-authorized local policy channel. It is not a signature,
    identity check, or proof that the named policy owner approved anything.
    """
    _sha(owner_supplied_sha256,'OWNER_LOCK_PIN_FORMAT_INVALID')
    current=path.absolute()
    while True:
        if current.is_symlink(): raise ContractError('OWNER_LOCK_PATH_SYMLINK')
        if current == current.parent: break
        current=current.parent
    if not path.is_file() or path.stat().st_size > cap:
        raise ContractError('OWNER_LOCK_FILE_INVALID')
    raw=path.read_bytes()
    if _hash(raw)!=owner_supplied_sha256: raise ContractError('OWNER_LOCK_BYTES_MISMATCH')
    return _json_bytes(raw, 'OWNER_LOCK_INVALID_JSON')


def _timezone(value: str) -> datetime:
    if not isinstance(value, str) or not (value.endswith('Z') or re.search(r'[+-]\d\d:\d\d$', value)):
        raise ContractError('TIMEZONE_REQUIRED')
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if dt.tzinfo is None: raise ValueError('naive')
        return dt
    except ValueError as exc: raise ContractError('INVALID_TIMESTAMP') from exc


def _fields(obj: dict, names: set[str], code: str) -> None:
    if not isinstance(obj, dict) or set(obj) != names: raise ContractError(code)


def _sha(value: str, code: str) -> None:
    if not isinstance(value, str) or not SHA256.fullmatch(value): raise ContractError(code)


def check_work(work: dict) -> None:
    mandatory={'schema','work_unit','node_id','captured_at_utc','stage','intent','task_sha256','plan_sha256'}
    optional={'baseline_id','baseline_sha256'}
    if not isinstance(work,dict) or not mandatory.issubset(work) or set(work)-mandatory-optional:
        raise ContractError('WORK_FIELDS_INVALID')
    if ('baseline_id' in work) != ('baseline_sha256' in work):
        raise ContractError('WORK_BASELINE_PAIR_REQUIRED')
    if 'baseline_id' in work:
        if not isinstance(work['baseline_id'],str) or not work['baseline_id'].strip():
            raise ContractError('WORK_BASELINE_ID_INVALID')
        _sha(work['baseline_sha256'],'WORK_BASELINE_HASH_INVALID')
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
    if work['stage'] in {'EXECUTE','PUBLISH','CLOSE'} and work['plan_sha256'] is None:
        raise ContractError('LATER_STAGE_NEEDS_PLAN_PIN')
    if work['intent'] == 'READ_ONLY' and work['stage'] != 'PLAN':
        raise ContractError('READ_ONLY_STAGE_INVALID')


def check_lock(lock: dict) -> None:
    _fields(lock, {'schema','astra','leonardo'}, 'LOCK_FIELDS_INVALID')
    if lock['schema'] != 'MAESTRO_PREP_LOCK_V1': raise ContractError('LOCK_SCHEMA_INVALID')
    astra_keys = set(lock['astra']) if isinstance(lock['astra'], dict) else set()
    if astra_keys not in ({'skill_sha256','approved_version_label'}, {'skill_sha256','approved_version_label','official_v71'}):
        raise ContractError('ASTRA_LOCK_INVALID')
    if 'official_v71' in lock['astra']:
        pins = lock['astra']['official_v71']
        _fields(pins, {'validator_sha256','schema_sha256','profile_sha256',
                       'manifest_sha256'}, 'ASTRA_OFFICIAL_PINS_INVALID')
        for k in ('validator_sha256','schema_sha256','profile_sha256','manifest_sha256'):
            _sha(pins[k], 'ASTRA_OFFICIAL_HASH_INVALID')
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


def _origin_route_proof(work: dict, lock: dict, root: Path, capture: dict,
                        plan_at: datetime, route_at: datetime | None,
                        route_sha: str | None) -> list[str]:
    """Bind a reused plan to its *archived* Leonardo origin, not a bare hash.

    This verifies only producer-provided local bytes and their relationships;
    an external signed attestation is still required for host execution claims.
    Historical route bytes remain immutable when the current stage re-routes.
    """
    try:
        output_bytes = _relative_file(root, capture['origin_route_output_file'])
        capture_bytes = _relative_file(root, capture['origin_route_capture_file'])
    except (ContractError, OSError, KeyError, TypeError):
        return ['HOLD_ASTRA_ORIGIN_REFERENCE_INVALID']
    if _hash(output_bytes) != capture['origin_route_output_sha256']:
        return ['HOLD_ASTRA_ORIGIN_BYTES_MISMATCH']
    try:
        origin = _json_bytes(output_bytes, 'HOLD_ASTRA_ORIGIN_OUTPUT_INVALID')
        receipt = _json_bytes(capture_bytes, 'HOLD_ASTRA_ORIGIN_CAPTURE_INVALID')
    except ContractError as exc:
        return [str(exc)]
    if set(origin) != ROUTE_OUTPUT_FIELDS or origin.get('schema') != 'LEONARDO_ROUTE_DECISION_V1':
        return ['HOLD_ASTRA_ORIGIN_OUTPUT_CONTRACT']
    expected_capture={'schema','work_unit','node_id','router_version',
        'task_sha256','policy_sha256','routing_output_sha256','exit_code',
        'execution_state','captured_at_utc'}
    if (set(receipt) != expected_capture or receipt.get('schema') != 'LEONARDO_ROUTE_CAPTURE_V1'
        or receipt.get('routing_output_sha256') != capture['origin_route_output_sha256']
        or receipt.get('router_version') != lock['leonardo']['router_version']
        or receipt.get('task_sha256') != work['task_sha256']
        or receipt.get('policy_sha256') != lock['leonardo']['policy_sha256']
        or receipt.get('work_unit') != work['work_unit']
        or receipt.get('node_id') != work['node_id']
        or receipt.get('execution_state') != 'READY'
        or type(receipt.get('exit_code')) is not int or receipt['exit_code'] != 0):
        return ['HOLD_ASTRA_ORIGIN_CAPTURE_BINDING']
    if (origin.get('work_unit') != work['work_unit'] or origin.get('node_id') != work['node_id']
        or origin.get('task_sha256') != work['task_sha256']
        or origin.get('policy_sha256') != lock['leonardo']['policy_sha256']
        or origin.get('execution_state') != 'READY'):
        return ['HOLD_ASTRA_ORIGIN_OUTPUT_BINDING']
    skills=origin.get('mandatory_skills')
    if (origin.get('intent') not in {'NEW_PLAN','REPLAN'}
        or origin.get('plan_gate') != 'CALL_ASTRA_PREP'
        or origin.get('stage') not in {'PLAN','EXECUTE','PUBLISH','CLOSE'}
        or not isinstance(skills,list) or any(not isinstance(s,str) for s in skills)
        or len(skills) != len(set(skills))
        or not {'astra-prep','o-prep'}.issubset(skills)
        or type(origin.get('review_required')) is not bool
        or (origin['stage'] in {'PUBLISH','CLOSE'} and not origin['review_required'])):
        return ['HOLD_ASTRA_ORIGIN_PLAN_BRANCH']
    try:
        original_at=_timezone(receipt.get('captured_at_utc'))
    except ContractError:
        return ['HOLD_ASTRA_ORIGIN_TIMESTAMP_INVALID']
    if original_at > plan_at or original_at > _timezone(work['captured_at_utc']):
        return ['HOLD_ASTRA_ORIGIN_TIMESTAMP_ORDER']
    # An old route cannot be revived by writing a new capture/plan timestamp.
    # This is a candidate policy window, not an independently trusted host clock.
    if plan_at - original_at > MAX_ROUTE_AGE:
        return ['HOLD_ASTRA_ORIGIN_STALE_AT_PLAN']
    if work['intent'] in {'NEW_PLAN','REPLAN'}:
        if route_sha is None or route_at is None or route_sha != capture['origin_route_output_sha256'] or route_at != original_at:
            return ['HOLD_ASTRA_ORIGIN_CURRENT_ROUTE_MISMATCH']
    return []


def _astra_binding(work: dict, lock: dict, root: Path, skill_path: Path | None,
                   plan_receipt_rel: str | None, route_at: datetime | None,
                   route_sha: str | None) -> list[str]:
    if work['intent'] == 'READ_ONLY':
        return []
    if skill_path is None:
        return ['HOLD_PLAN_MODULE_MISSING']
    try:
        # Astra is external: only the already approved SKILL.md's exact bytes are pinned.
        if skill_path.is_symlink() or not skill_path.is_file() or _hash(skill_path.read_bytes()) != lock['astra']['skill_sha256']:
            return ['HOLD_ASTRA_SOURCE_PIN']
    except OSError:
        return ['HOLD_ASTRA_SOURCE_PIN']
    if not plan_receipt_rel:
        return ['CALL_ASTRA_PREP' if work['intent'] in {'NEW_PLAN','REPLAN'} else 'HOLD_EXISTING_PLAN_RECEIPT']
    receipt = _json_bytes(_relative_file(root, plan_receipt_rel), 'ASTRA_RECEIPT_JSON_INVALID')
    expected = {'schema','work_unit','node_id','astra_skill_sha256','plan_sha256',
                'plan_file','status','captured_at_utc','task_sha256','origin_route_output_sha256'}
    origin_fields = {'origin_route_output_file','origin_route_capture_file'}
    # V1 had no task or originating route binding. It is retained as historical
    # evidence, but must never pass a new work unit's connection gate.
    if receipt.get('schema') == 'ASTRA_PREP_CAPTURE_V1':
        return ['HOLD_ASTRA_LEGACY_RECEIPT_UNBOUND']
    version=receipt.get('schema')
    if ((version == 'ASTRA_PREP_CAPTURE_V2' and set(receipt) != expected)
        or (version == 'ASTRA_PREP_CAPTURE_V3' and set(receipt) != expected | origin_fields)
        or version not in {'ASTRA_PREP_CAPTURE_V2','ASTRA_PREP_CAPTURE_V3'}):
        return ['HOLD_ASTRA_RECEIPT_CONTRACT']
    if work['intent'] == 'REUSE_PLAN' and version != 'ASTRA_PREP_CAPTURE_V3':
        return ['HOLD_ASTRA_REUSE_ORIGIN_PROOF_REQUIRED']
    if any(receipt[k] != work[k] for k in ('work_unit','node_id')) or receipt['astra_skill_sha256'] != lock['astra']['skill_sha256']:
        return ['HOLD_ASTRA_RECEIPT_BINDING']
    if receipt['status'] != 'READY_FOR_LOCAL_CANDIDATE_WORK':
        return ['HOLD_ASTRA_PLAN_NOT_READY']
    _sha(receipt['task_sha256'], 'ASTRA_CAPTURE_TASK_HASH_INVALID')
    _sha(receipt['origin_route_output_sha256'], 'ASTRA_CAPTURE_ROUTE_HASH_INVALID')
    if receipt['task_sha256'] != work['task_sha256']:
        return ['HOLD_ASTRA_PLAN_TASK_CHANGED']
    if version == 'ASTRA_PREP_CAPTURE_V2' and work['intent'] in {'NEW_PLAN','REPLAN'} and (
            route_sha is None or receipt['origin_route_output_sha256'] != route_sha):
        return ['HOLD_ASTRA_PLAN_ROUTE_CHANGED']
    _sha(receipt['plan_sha256'], 'ASTRA_RECEIPT_PLAN_HASH_INVALID')
    if work['plan_sha256'] is not None and work['plan_sha256'] != receipt['plan_sha256']:
        return ['HOLD_ASTRA_PLAN_REVISION_CHANGED']
    plan_at = _timezone(receipt['captured_at_utc'])
    snapshot_at = _timezone(work['captured_at_utc'])
    if plan_at > snapshot_at:
        return ['HOLD_ASTRA_RECEIPT_FROM_FUTURE']
    if route_at is not None and work['intent'] in {'NEW_PLAN','REPLAN'} and plan_at < route_at:
        return ['HOLD_ASTRA_PLAN_PREDATES_ROUTE']
    if _hash(_relative_file(root, receipt['plan_file'])) != receipt['plan_sha256']:
        return ['HOLD_ASTRA_PLAN_BYTES_CHANGED']
    if version == 'ASTRA_PREP_CAPTURE_V3':
        origin_issues = _origin_route_proof(work,lock,root,receipt,plan_at,route_at,route_sha)
        if origin_issues: return origin_issues
    return []


def _trusted_bundle_file(root: Path, relative: str, expected: str) -> Path:
    """Check pinned installed bundle file; never download or copy from public mirror."""
    p = root
    for part in relative.split('/'):
        if part in {'', '.', '..'} or ':' in part or '\\' in part or part.endswith((' ', '.')):
            raise ContractError('ASTRA_BUNDLE_UNSAFE_PATH')
        p = p / part
        if p.is_symlink():
            raise ContractError('ASTRA_BUNDLE_SYMLINK')
    if not p.is_file() or not p.resolve().is_relative_to(root.resolve()):
        raise ContractError('ASTRA_BUNDLE_FILE_MISSING')
    if p.stat().st_size > 1024 * 1024 or _hash(p.read_bytes()) != expected:
        raise ContractError('ASTRA_BUNDLE_HASH_MISMATCH')
    return p


def _verify_astra_manifest(bundle_root: Path, owner_manifest_sha: str) -> dict[str, str]:
    """Verify *all* manifest-listed installed bytes, not just four entry points.

    The manifest SHA must arrive independently through the owner-pinned lock.
    A matching self-authored manifest is not approval, provenance or a signature.
    The public Astra repository is a reference mirror, not a node-local pin.
    """
    file = _trusted_bundle_file(bundle_root, 'CANDIDATE_HASHES.json', owner_manifest_sha)
    manifest = _json_bytes(file.read_bytes(), 'ASTRA_MANIFEST_INVALID')
    files = manifest.get('files')
    if (not isinstance(files, dict) or not 4 <= len(files) <= 128
            or manifest.get('file_count') != len(files)):
        raise ContractError('ASTRA_MANIFEST_INVENTORY_INVALID')
    required = {'SKILL.md', 'scripts/validate_prework.py',
                'schemas/prework-plan.schema.json', 'profiles/ai-maestro.md',
                'references/evidence-model.md', 'references/domain-checks.md'}
    if not required.issubset(files):
        raise ContractError('ASTRA_MANIFEST_REQUIRED_FILES_MISSING')
    for rel, expected in sorted(files.items()):
        if (not isinstance(rel, str) or not rel or '\\' in rel or '\x00' in rel
            or any(p in {'', '.', '..'} or ':' in p or p.endswith((' ', '.'))
                   for p in rel.split('/')) or rel.startswith('/')):
            raise ContractError('ASTRA_MANIFEST_UNSAFE_PATH')
        _sha(expected, 'ASTRA_MANIFEST_DIGEST_INVALID')
        try:
            _trusted_bundle_file(bundle_root, rel, expected)
        except ContractError as exc:
            raise ContractError('ASTRA_MANIFEST_FILE_MISMATCH') from exc
    stream = ''.join(f'{rel}  {files[rel]}\n' for rel in sorted(files)).encode('utf-8')
    aggregate = _hash(stream)
    if manifest.get('bundle_aggregate_sha256') != aggregate:
        raise ContractError('ASTRA_MANIFEST_AGGREGATE_MISMATCH')
    return files


def _official_astra_validation(work: dict, lock: dict, root: Path,
                               skill_path: Path | None, plan_receipt_rel: str | None,
                               bundle_root: Path | None, route_at: datetime | None) -> tuple[list[str], dict]:
    """Opt-in validation using the node's hash-pinned, *approved* Astra v7.1.

    The published GitHub repository is a reference mirror, NOT a node authority.
    This runs an external local validator only when a bundle root and exact owner
    pins are explicitly supplied. It never creates, installs, or repairs plans.
    """
    summary = {'status': 'NOT_RUN', 'validator_exit_code': None,
               'validator_stdout_sha256': None, 'target_cells': {},
               'forecast_dispositions': []}
    if work['intent'] == 'READ_ONLY':
        return [], summary
    # A producer-authored capture and an approved-version *label* are never a
    # substitute for the exact node-approved validator/schema/profile pins.
    if 'official_v71' not in lock['astra']:
        summary['status'] = 'NOT_RUN_APPROVED_VALIDATOR_PINS_MISSING'
        return ['HOLD_ASTRA_OFFICIAL_PIN_MISSING'], summary
    if bundle_root is None or skill_path is None:
        return ['HOLD_ASTRA_BUNDLE_MISSING'], summary
    if bundle_root.is_symlink() or not bundle_root.is_dir():
        return ['HOLD_ASTRA_BUNDLE_INVALID'], summary
    for a in [bundle_root.absolute(), *bundle_root.absolute().parents]:
        if a.is_symlink():
            return ['HOLD_ASTRA_BUNDLE_SYMLINK'], summary
    if skill_path.resolve() != (bundle_root / 'SKILL.md').resolve():
        return ['HOLD_ASTRA_SKILL_PATH_NOT_BUNDLE'], summary
    try:
        skill_file = _trusted_bundle_file(bundle_root, 'SKILL.md', lock['astra']['skill_sha256'])
        pins=lock['astra']['official_v71']
        pinned_files = _verify_astra_manifest(bundle_root, pins['manifest_sha256'])
        if any(pinned_files[rel] != expected for rel, expected in (
                ('SKILL.md', lock['astra']['skill_sha256']),
                ('scripts/validate_prework.py', pins['validator_sha256']),
                ('schemas/prework-plan.schema.json', pins['schema_sha256']),
                ('profiles/ai-maestro.md', pins['profile_sha256']))):
            return ['HOLD_ASTRA_LOCK_MANIFEST_DISAGREE'], summary
        script = _trusted_bundle_file(bundle_root, 'scripts/validate_prework.py', pins['validator_sha256'])
        schema_file = _trusted_bundle_file(bundle_root, 'schemas/prework-plan.schema.json', pins['schema_sha256'])
        profile_file = _trusted_bundle_file(bundle_root, 'profiles/ai-maestro.md', pins['profile_sha256'])
        _json_bytes(schema_file.read_bytes(), 'ASTRA_SCHEMA_INVALID')
        if not plan_receipt_rel:
            summary['status'] = 'PINNED_BUNDLE_PRESENT_PLAN_PENDING'
            return [], summary  # explicitly request plan creation, not approval
        receipt = _json_bytes(_relative_file(root, plan_receipt_rel), 'ASTRA_RECEIPT_JSON_INVALID')
        if not isinstance(receipt.get('plan_file'), str):
            return ['HOLD_ASTRA_PLAN_REFERENCE'], summary
        planbytes = _relative_file(root, receipt['plan_file'])
        # JSON sidecars are mandatory for this v0.2.2 adapter. Astra's native YAML
        # validator remains available to the node, but not to this bounded connector.
        if not receipt['plan_file'].lower().endswith('.json'):
            return ['HOLD_ASTRA_OFFICIAL_JSON_SIDECAR_REQUIRED'], summary
        plan=_json_bytes(planbytes, 'ASTRA_OFFICIAL_PLAN_JSON_INVALID')
        if plan.get('work_unit') != work['work_unit'] or plan.get('actor') != work['node_id']:
            return ['HOLD_ASTRA_OFFICIAL_PLAN_IDENTITY'], summary
        captured=_timezone(work['captured_at_utc'])
        generated=_timezone(plan.get('generated_at'))
        if generated > captured:
            return ['HOLD_ASTRA_OFFICIAL_PLAN_FUTURE'], summary
        # A sidecar written *after* its producer receipt is a reconstructed
        # history, even if both timestamps precede this work snapshot.
        receipt_at=_timezone(receipt.get('captured_at_utc'))
        if generated > receipt_at:
            return ['HOLD_ASTRA_PLAN_GENERATED_AFTER_RECEIPT'], summary
        if route_at is not None and work['intent'] in {'NEW_PLAN','REPLAN'} and generated < route_at:
            return ['HOLD_ASTRA_OFFICIAL_PLAN_PREDATES_ROUTE'], summary
        if 'baseline_id' not in work:
            return ['HOLD_ASTRA_BASELINE_PIN_REQUIRED'], summary
        if (plan.get('baseline_id') != work['baseline_id'] or
            not isinstance(plan.get('starting_candidate'),dict) or
            plan['starting_candidate'].get('sha256') != work['baseline_sha256'] or
            not isinstance(plan.get('starting_point_readback'),dict) or
            plan['starting_point_readback'].get('candidate_sha256') != work['baseline_sha256']):
            return ['HOLD_ASTRA_BASELINE_MISMATCH'], summary
        forecast=plan.get('forecast')
        if not isinstance(forecast, dict) or not isinstance(forecast.get('dispositions'), list):
            return ['HOLD_ASTRA_OFFICIAL_FORECAST_INVALID'], summary
        # No exceptions/overrides: check only an approved node-local validator.
        # -I removes Python startup hooks/user site; -B disables bytecode writes.
        # The validator has its own cwd. Absolute arguments are essential when
        # the node CLI supplies relative evidence/bundle roots.
        child_env={'PYTHONIOENCODING':'utf-8','PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1'}
        if os.name == 'nt':
            # Windows CPython may need these system paths to discover the stdlib;
            # never forward PYTHONPATH, credentials or the full host environment.
            child_env.update({k:os.environ[k] for k in ('SYSTEMROOT','WINDIR','TEMP','TMP')
                              if k in os.environ})
        process=subprocess.run([sys.executable, '-I', '-B', str(script.absolute()),
                                str((root / receipt['plan_file']).absolute())],
                               cwd=str(bundle_root.absolute()), capture_output=True, timeout=15,
                               env=child_env,
                               check=False)
        # Detect mutable evidence or bundle bytes while the validator was
        # running. Does not pretend to be a sandbox or defeat a malicious owner.
        if _hash(_relative_file(root, receipt['plan_file'])) != receipt['plan_sha256']:
            return ['HOLD_ASTRA_PLAN_CHANGED_DURING_VALIDATION'], summary
        # The manifest and every listed dependency remain pinned during the
        # validator invocation, not only the four files consumed directly here.
        manifest_after=bundle_root/'CANDIDATE_HASHES.json'
        if (manifest_after.is_symlink() or not manifest_after.is_file()
            or _hash(manifest_after.read_bytes()) != pins['manifest_sha256']):
            return ['HOLD_ASTRA_MANIFEST_CHANGED_DURING_VALIDATION'], summary
        try:
            _verify_astra_manifest(bundle_root, pins['manifest_sha256'])
        except ContractError:
            return ['HOLD_ASTRA_DEPENDENCY_CHANGED_DURING_VALIDATION'], summary
        for path, expected_hash in ((skill_file,lock['astra']['skill_sha256']),
                                    (script,pins['validator_sha256']),
                                    (schema_file,pins['schema_sha256']),
                                    (profile_file,pins['profile_sha256'])):
            if path.is_symlink() or not path.is_file() or _hash(path.read_bytes()) != expected_hash:
                return ['HOLD_ASTRA_BUNDLE_CHANGED_DURING_VALIDATION'], summary
        if len(process.stdout) > 65536 or len(process.stderr) > 65536:
            return ['HOLD_ASTRA_VALIDATOR_OUTPUT_LIMIT'], summary
        summary['validator_exit_code']=process.returncode
        summary['validator_stdout_sha256']=_hash(process.stdout)
        lines=process.stdout.splitlines()
        if process.returncode != 0 or b'OK: pre-work plan is valid.' not in lines:
            return ['HOLD_ASTRA_OFFICIAL_VALIDATOR_FAILED'], summary
        # The published v7.1 CLI emits exactly parser, Python and terminal OK
        # on success. An OK substring is insufficient when diagnostics conflict.
        if (process.stderr or len(lines)!=3 or not lines[0].startswith(b'parser: ')
            or not lines[1].startswith(b'python: ') or lines[2]!=b'OK: pre-work plan is valid.'
            or any(b'\x00' in line for line in lines)):
            return ['HOLD_ASTRA_VALIDATOR_OUTPUT_CONTRACT'], summary
        targets=Counter()
        for req in plan.get('requirements', []):
            if not isinstance(req, dict) or not isinstance(req.get('target'), dict):
                return ['HOLD_ASTRA_OFFICIAL_REQUIREMENTS_INVALID'], summary
            cell=f"{req['target'].get('evidence_level')}/{req['target'].get('review_independence')}"
            targets[cell] += 1
        summary['target_cells']=dict(sorted(targets.items()))
        summary['forecast_dispositions']=forecast['dispositions']
        summary['status']='LOCAL_VALIDATOR_PASS_NOT_APPROVAL'
        if forecast['dispositions'] != ['CANDIDATE_READY']:
            return ['HOLD_ASTRA_FORECAST_GAPS_OPEN'], summary
        return [], summary
    except ContractError as exc:
        return [str(exc)], summary
    except subprocess.TimeoutExpired:
        return ['HOLD_ASTRA_VALIDATOR_TIMEOUT'], summary
    except (OSError, TypeError, KeyError, ValueError):
        return ['HOLD_ASTRA_OFFICIAL_VALIDATION_INVALID'], summary


def _route_binding(work: dict, lock: dict, root: Path, index_path: Path,
                   route_rel: str | None) -> tuple[list[str], datetime | None, str | None]:
    """Check node-produced capture AND the bytes of its normalized route decision.

    LEONARDO_ROUTE_DECISION_V1 is our adapter contract, not an assertion that an
    official Leonardo release emits this schema. Caller still needs owner-approved
    adapter and real execution evidence before making an authority claim.
    """
    if not route_rel:
        return ['HOLD_LEONARDO_ROUTE_CAPTURE_MISSING'], None, None
    receipt = _json_bytes(_relative_file(root, route_rel), 'LEONARDO_RECEIPT_JSON_INVALID')
    required = {'schema','work_unit','node_id','router_version','task_sha256','policy_sha256',
                'routing_output_sha256','exit_code','execution_state','captured_at_utc'}
    if set(receipt) != required or receipt.get('schema') != 'LEONARDO_ROUTE_CAPTURE_V1':
        return ['HOLD_LEONARDO_CAPTURE_CONTRACT'], None, None
    if any(receipt[k] != work[k] for k in ('work_unit','node_id')) or receipt['router_version'] != lock['leonardo']['router_version']:
        return ['HOLD_LEONARDO_BINDING_MISMATCH'], None, None
    if receipt['execution_state'] != 'READY' or type(receipt['exit_code']) is not int or receipt['exit_code'] != 0:
        return ['HOLD_LEONARDO_NOT_READY'], None, None
    route_at = _timezone(receipt['captured_at_utc'])
    snapshot_at = _timezone(work['captured_at_utc'])
    if route_at > snapshot_at:
        return ['HOLD_LEONARDO_ROUTE_FROM_FUTURE'], None, None
    if snapshot_at - route_at > MAX_ROUTE_AGE:
        return ['HOLD_LEONARDO_ROUTE_STALE'], None, None
    idx = read_json(index_path)
    if not isinstance(idx.get('receipts'), list):
        return ['HOLD_O_INDEX_INVALID'], None, None
    rows = {r.get('role'): r for r in idx['receipts'] if isinstance(r, dict)}
    raw_output = None
    for role, captured, expected in [
        ('router_input', receipt['task_sha256'], work['task_sha256']),
        ('router_policy', receipt['policy_sha256'], lock['leonardo']['policy_sha256']),
        ('router_output', receipt['routing_output_sha256'], None)]:
        if role not in rows or rows[role].get('sha256') != captured or (expected is not None and captured != expected):
            return ['HOLD_LEONARDO_ARTIFACT_PIN_MISMATCH'], None, None
        # O-Prep has checked these bytes; independently recheck the consumed copy
        # to avoid trusting only a producer-authored receipt-index row.
        body = _relative_file(root, rows[role].get('path'))
        if _hash(body) != captured:
            return ['HOLD_LEONARDO_CONSUMED_BYTES_CHANGED'], None, None
        if role == 'router_output':
            raw_output = body
    output = _json_bytes(raw_output, 'LEONARDO_ROUTE_OUTPUT_JSON_INVALID')
    if set(output) != ROUTE_OUTPUT_FIELDS or output['schema'] != 'LEONARDO_ROUTE_DECISION_V1':
        return ['HOLD_LEONARDO_ROUTE_OUTPUT_CONTRACT'], None, None
    if any(output[k] != work[k] for k in ('work_unit','node_id','stage','intent','task_sha256')) or output['policy_sha256'] != lock['leonardo']['policy_sha256']:
        return ['HOLD_LEONARDO_ROUTE_OUTPUT_BINDING'], None, None
    if output['execution_state'] != 'READY':
        return ['HOLD_LEONARDO_ROUTE_OUTPUT_NOT_READY'], None, None
    skills = output['mandatory_skills']
    if not isinstance(skills, list) or any(not isinstance(v, str) or not v.strip() for v in skills) or len(skills) != len(set(skills)) or 'o-prep' not in skills:
        return ['HOLD_LEONARDO_MANDATORY_SKILL_MISSING'], None, None
    plan_gates = {
        'NEW_PLAN': 'CALL_ASTRA_PREP', 'REPLAN': 'CALL_ASTRA_PREP',
        'REUSE_PLAN': 'REUSE_PINNED_PLAN', 'READ_ONLY': 'NO_NEW_PLAN',
    }
    if output['plan_gate'] != plan_gates[work['intent']]:
        return ['HOLD_LEONARDO_WRONG_PLAN_BRANCH'], None, None
    if work['intent'] in {'NEW_PLAN','REPLAN'} and 'astra-prep' not in skills:
        return ['HOLD_LEONARDO_MANDATORY_SKILL_MISSING'], None, None
    if type(output['review_required']) is not bool or (work['stage'] in {'PUBLISH','CLOSE'} and not output['review_required']):
        return ['HOLD_LEONARDO_REVIEW_GATE_OMITTED'], None, None
    return [], route_at, receipt['routing_output_sha256']


def decide(work: dict, lock: dict, o_signal: dict, index_path: Path, evidence_root: Path,
           *, astra_skill_path: Path | None = None, astra_plan_receipt_rel: str | None = None,
           leonardo_route_rel: str | None = None,
           astra_bundle_root: Path | None = None,
           observed_now: datetime | None = None) -> dict:
    """Mandatory O-Prep bound gate; external captures are untrusted local evidence."""
    check_work(work)
    check_lock(lock)
    if evidence_root.is_symlink() or not evidence_root.is_dir():
        raise ContractError('EVIDENCE_ROOT_INVALID')
    ancestor = evidence_root.absolute()
    while True:
        if ancestor.is_symlink():
            raise ContractError('EVIDENCE_ROOT_ANCESTOR_SYMLINK')
        if ancestor == ancestor.parent: break
        ancestor = ancestor.parent
    if (work['work_unit'],work['node_id'],work['stage'],_timezone(work['captured_at_utc'])) != (
            o_signal.get('work_unit'),o_signal.get('node_id'),o_signal.get('stage'),_timezone(o_signal.get('captured_at_utc'))):
        raise ContractError('O_SIGNAL_WORK_BINDING_MISMATCH')
    issues: list[str] = []
    # Opt-in trusted *local host clock* at this library boundary. The CLI
    # supplies it by default for node invocations, while direct API callers
    # may intentionally omit it during offline deterministic replays. Without
    # it all captured_at timestamps are producer-reported and jointly replayable.
    if observed_now is not None:
        if not isinstance(observed_now, datetime) or observed_now.tzinfo is None:
            raise ContractError('HOST_CLOCK_INVALID')
        host_now=observed_now.astimezone(timezone.utc)
        snapshot_at=_timezone(work['captured_at_utc']).astimezone(timezone.utc)
        if snapshot_at > host_now+CLOCK_SKEW_BUDGET:
            issues.append('HOLD_WORK_SNAPSHOT_FUTURE_AGAINST_HOST')
        if host_now-snapshot_at > MAX_ROUTE_AGE:
            issues.append('HOLD_WORK_SNAPSHOT_STALE_AGAINST_HOST')
    decision = None
    o_invoked = False
    o = None
    # Diagnose independent modules even when another module is held. No later
    # module can override O-Prep's STOP/HOLD/REWORK precedence.
    try:
        o = vendor_module()
        o_invoked = True
        # The vendored O-Prep v0.3 compares resolved receipt files against
        # its root path. On Windows, RUNNER_TEMP can contain a junction whose
        # absolute spelling differs from its resolved spelling. Canonicalize
        # only the already-checked root and reattach the *lexical* index path;
        # do not resolve the index itself (that would hide an index symlink).
        canonical_root = evidence_root.resolve(strict=True)
        try:
            lexical_index = index_path.absolute().relative_to(evidence_root.absolute())
        except ValueError as exc:
            raise ContractError('O_INDEX_OUTSIDE_EVIDENCE_ROOT') from exc
        canonical_index = canonical_root / lexical_index
        decision = o.evaluate_bound_signal(o_signal, str(canonical_index), str(canonical_root))
        issues.extend(x['code'] for x in decision['issues'])
        if decision.get('evidence_binding', {}).get('status') != 'LOCAL_BYTES_VERIFIED_ONLY':
            issues.append('HOLD_O_BINDING_FAILED')
    except Exception:  # fail closed even if import/ABI mismatch hides OPrepError
        issues.append('HOLD_O_MODULE_MISSING' if not o_invoked else 'HOLD_O_BINDING_FAILED')
    # A missing or malformed index cannot waive mandatory O-Prep.
    route_at = None
    route_sha = None
    try:
        route_issues, route_at, route_sha = _route_binding(work, lock, evidence_root, index_path, leonardo_route_rel)
        issues.extend(route_issues)
    except ContractError as exc:
        issues.append(str(exc))
    except (OSError, TypeError, KeyError):
        issues.append('HOLD_LEONARDO_CAPTURE_INVALID')
    astra_receipt_ok = False
    try:
        astra_issues = _astra_binding(work, lock, evidence_root, astra_skill_path,
                                      astra_plan_receipt_rel, route_at, route_sha)
        issues.extend(astra_issues)
        astra_receipt_ok = not astra_issues
    except ContractError as exc:
        issues.append(str(exc))
    except (OSError, TypeError, KeyError):
        issues.append('HOLD_ASTRA_CAPTURE_INVALID')
    # External Astra official v7.1 validation is additive to the producer receipt;
    # even a valid synthetic receipt cannot impersonate the actual validator.
    official_summary = {'status': 'NOT_RUN'}
    if astra_receipt_ok or (not astra_plan_receipt_rel and work['intent'] != 'READ_ONLY'):
        try:
            extra, official_summary = _official_astra_validation(
                work, lock, evidence_root, astra_skill_path, astra_plan_receipt_rel,
                astra_bundle_root, route_at)
            issues.extend(extra)
        except (OSError, TypeError, KeyError, ContractError):
            issues.append('HOLD_ASTRA_OFFICIAL_VALIDATION_INVALID')
    elif work['intent'] != 'READ_ONLY':
        official_summary['status'] = 'NOT_RUN_INVALID_CAPTURE'
    out = _result(work, decision, issues, o_invoked)
    out['clock_binding'] = 'LOCAL_PROCESS_CLOCK_ONLY' if observed_now is not None else 'SELF_REPORTED_OFFLINE_ONLY'
    out['astra_official_validation'] = official_summary
    return out


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
