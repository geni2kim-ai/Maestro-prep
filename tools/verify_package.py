#!/usr/bin/env python3
"""Read-only verifier for Maestro-Prep candidate file inventory and SHA-256.

The manifest is itself inside the archive; compare the ZIP SHA-256 received
through a separate trusted channel before treating the inventory as authoritative.
"""
from pathlib import Path
import hashlib
import os
import json
import re
import sys

EXCLUDE={'MANIFEST.json','SHA256SUMS.txt'}

def scan(root:Path) -> list[dict]:
    """Scan distributable source, not Git metadata or execution caches.

    Actions checks out a .git directory, whereas the offline ZIP does not.
    Excluding Git metadata makes the exact same source manifest check work in
    either location without silently excluding any new distributable source.
    """
    out=[]
    skip_dirs={'.git','__pycache__','.pytest_cache','.venv','venv'}
    for directory, dirs, files in os.walk(root,followlinks=False):
        base=Path(directory)
        for name in dirs:
            if name not in skip_dirs and (base/name).is_symlink():
                raise ValueError('SYMLINK_FORBIDDEN')
        dirs[:]=[name for name in dirs if name not in skip_dirs]
        for filename in files:
            p=base/filename
            relative=p.relative_to(root).as_posix()
            if relative in EXCLUDE or p.suffix=='.pyc':
                continue
            if p.is_symlink():
                raise ValueError('SYMLINK_FORBIDDEN')
            if not p.is_file():
                continue
            data=p.read_bytes()
            out.append({'path':relative,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    return sorted(out,key=lambda r:r['path'])

def verify(root:Path) -> dict:
    manifest=json.loads((root/'MANIFEST.json').read_text(encoding='utf-8'))
    if set(manifest)!={'schema','version','file_count','files','evidence_boundary'} or manifest['schema']!='MAESTRO_PREP_PACKAGE_V1':
        raise ValueError('MANIFEST_CONTRACT_INVALID')
    actual=scan(root)
    if manifest['file_count']!=len(actual) or manifest['files']!=actual:
        raise ValueError('FILE_SET_OR_HASH_MISMATCH')
    lines=(root/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines()
    expected=[v['sha256']+'  '+v['path'] for v in actual]
    if lines!=expected:raise ValueError('SHA256SUMS_MISMATCH')
    return {'schema':'MAESTRO_PACKAGE_VERIFICATION_V1','verified':True,'files':len(actual),'source':'CURRENT_LOCAL_EXTRACTED_BYTES','host_authority':False}

if __name__=='__main__':
    try:
        print(json.dumps(verify(Path(sys.argv[1]) if len(sys.argv)>1 else Path('.')),indent=2))
    except (ValueError,KeyError,OSError,UnicodeError) as e:
        print(json.dumps({'verified':False,'code':str(e).split(':')[0]}));sys.exit(2)
