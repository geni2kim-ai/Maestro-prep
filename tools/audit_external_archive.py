#!/usr/bin/env python3
"""Read-only public interface for independent owner-pinned archive byte auditing.

No private node structure, routing contract or historical export layout is encoded
here. Detailed routing validation requires a *separately approved, local* profile.
Never treat self-consistency or a reported manifest as owner authentication.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, stat, sys
from io import BytesIO
from pathlib import Path, PurePosixPath, PureWindowsPath
from zipfile import ZipFile, BadZipFile
MAX_ARCHIVE = 8 * 1024 * 1024
MAX_MEMBER = 2 * 1024 * 1024
MAX_ENTRIES = 128
DIGEST = re.compile(r'[a-f0-9]{64}\Z')
class AuditError(ValueError): pass

def _sha(raw:bytes)->str: return hashlib.sha256(raw).hexdigest()
def _safe(name:str)->bool:
    if not isinstance(name,str) or not name or '\\' in name or '\0' in name or name.startswith('/'):
        return False
    w,p=PureWindowsPath(name),PurePosixPath(name)
    return not (w.drive or w.root or p.is_absolute()) and all(
        x not in ('','.','..') and ':' not in x and not x.endswith((' ','.'))
        for x in name.rstrip('/').split('/'))
def _parse(raw:bytes)->dict:
    def unique(pairs):
        out={}
        for k,v in pairs:
            if k in out: raise AuditError('DUPLICATE_JSON_KEY')
            out[k]=v
        return out
    try: obj=json.loads(raw.decode('utf-8'),object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(AuditError('NONFINITE_JSON_VALUE')))
    except (ValueError,UnicodeError) as exc: raise AuditError('BAD_JSON') from exc
    if not isinstance(obj,dict):raise AuditError('JSON_OBJECT_REQUIRED')
    return obj
def _no_link(path:Path)->bool:
    cur=path.absolute()
    while True:
        try:
            st=os.lstat(cur)
        except OSError:return False
        if stat.S_ISLNK(st.st_mode) or getattr(st,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400):return False
        if cur==cur.parent:return True
        cur=cur.parent

def audit(path:Path, *, owner_bundle_sha256:str|None=None,
          owner_manifest_sha256:str|None=None)->dict:
    """Hashes the *same* immutable byte snapshot from which members are read."""
    if not _no_link(path) or not path.is_file() or path.stat().st_size>MAX_ARCHIVE:
        raise AuditError('ARCHIVE_PATH_UNSAFE_OR_OVERSIZE')
    raw=path.read_bytes(); digest=_sha(raw)
    if len(raw)>MAX_ARCHIVE:raise AuditError('ARCHIVE_OVERSIZE_AFTER_READ')
    try:
        with ZipFile(BytesIO(raw)) as z:
            infos=z.infolist();data={};total=0;seen=set()
            if not 2<=len(infos)<=MAX_ENTRIES:raise AuditError('ARCHIVE_MEMBER_COUNT')
            for info in infos:
                name=info.filename
                if not _safe(name):raise AuditError('UNSAFE_MEMBER_PATH')
                norm=name.rstrip('/');folded=norm.casefold()
                if folded in seen:raise AuditError('DUPLICATE_MEMBER_PATH')
                seen.add(folded)
                mode=stat.S_IFMT(info.external_attr>>16)
                if mode==stat.S_IFLNK:raise AuditError('SYMLINK_MEMBER')
                if info.is_dir():continue
                total+=info.file_size
                if info.file_size>MAX_MEMBER or total>MAX_ARCHIVE:raise AuditError('EXPANSION_LIMIT')
                member=z.read(info)
                if len(member)!=info.file_size:raise AuditError('SIZE_CONFLICT')
                data[norm]=member
    except (BadZipFile,OSError,RuntimeError,EOFError) as exc:raise AuditError('BAD_ARCHIVE') from exc
    if 'manifest.json' not in data:raise AuditError('MANIFEST_REQUIRED')
    manifest=_parse(data['manifest.json']);listed=manifest.get('files')
    if not isinstance(listed,dict):raise AuditError('MANIFEST_MAP_REQUIRED')
    issues=[]
    verified=[]
    for name,row in listed.items():
        if not _safe(name) or name=='manifest.json' or not isinstance(row,dict):
            issues.append('INVALID_MANIFEST_ENTRY');continue
        size=row.get('bytes');sha=row.get('sha256')
        if type(size)is not int or not isinstance(sha,str) or not DIGEST.fullmatch(sha):
            issues.append('INVALID_MANIFEST_ENTRY');continue
        if name not in data or len(data[name])!=size or _sha(data[name])!=sha:
            issues.append('MEMBER_BYTES_MISMATCH')
        else:verified.append(name)
    if set(listed)!=set(data)-{'manifest.json'}:
        issues.append('UNLISTED_OR_MISSING_MEMBERS')
    # A producer's embedded digest is *never* an owner pin.
    if owner_bundle_sha256 is None or owner_manifest_sha256 is None:
        gates=['INDEPENDENT_OWNER_PINS_REQUIRED']
    elif not all(isinstance(x,str) and DIGEST.fullmatch(x) for x in (owner_bundle_sha256,owner_manifest_sha256)):
        issues.append('OWNER_PIN_INVALID');gates=[]
    elif digest!=owner_bundle_sha256 or _sha(data['manifest.json'])!=owner_manifest_sha256:
        issues.append('OWNER_PIN_MISMATCH');gates=[]
    else:gates=[]
    return {'schema':'MAESTRO_PUBLIC_EXTERNAL_ARCHIVE_AUDIT_V1',
      'status':'HOLD' if issues else ('SELF_CONSISTENT_OWNER_PINS_MISSING' if gates else 'OWNER_PINNED_BYTES_VERIFIED_EXTERNAL_GATES_OPEN'),
      'archive_sha256':digest,'manifest_sha256':_sha(data['manifest.json']),
      'verified_member_count':len(verified),'issues':sorted(set(issues)),'external_gates':sorted(gates+[
        'ROUTE_SEMANTICS_NOT_VALIDATED','PROVIDER_EXECUTION_NOT_ESTABLISHED',
        'LOCAL_POLICY_NOT_VERIFIED','INDEPENDENT_REVIEW_NOT_RUN']),
      'authorized_to_deploy':False,'candidate_only':True,'decision_authority':'none'}
def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('evidence_zip',type=Path)
    p.add_argument('--owner-bundle-sha256')
    p.add_argument('--owner-manifest-sha256')
    a=p.parse_args(argv)
    try:r=audit(a.evidence_zip,owner_bundle_sha256=a.owner_bundle_sha256,
                owner_manifest_sha256=a.owner_manifest_sha256)
    except (OSError,AuditError) as exc:
        r={'schema':'MAESTRO_PUBLIC_EXTERNAL_ARCHIVE_AUDIT_V1','status':'HOLD',
           'issues':[str(exc).split(':')[0]],'authorized_to_deploy':False}
    print(json.dumps(r,ensure_ascii=False,sort_keys=True,indent=2))
    return 2 if r['status']=='HOLD' else 0
if __name__=='__main__':sys.exit(main())
