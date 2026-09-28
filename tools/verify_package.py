#!/usr/bin/env python3
"""Read-only verifier for the distributable public candidate inventory.

Repository-only CI, feedback and the current hotfix evidence report are not
release payload. Every other regular file remains strictly manifest-bound.
This inventory is not an external authenticity signature: compare a separately
supplied archive SHA-256 before trusting a received release.
"""
from pathlib import Path
import hashlib
import json
import sys

EXCLUDE = {'MANIFEST.json', 'SHA256SUMS.txt'}
GIT_METADATA = {'.git', '.github', '.gitattributes', '__pycache__', '.pytest_cache', '.venv'}
CONTROL_DOCS = {
    'feedback/feedback_v0.1.0-public-redacted-hotfix.md',
    'evidence/evidence_v0.1.0-public-redacted-hotfix.md',
    'feedback/feedback_v0.1.0-public-redacted-hotfix_followup.md',
    'evidence/evidence_v0.1.0-public-redacted-hotfix_followup.md',
}

def scan(root: Path) -> list[dict]:
    out = []
    for p in sorted(root.rglob('*'), key=lambda path: path.relative_to(root).as_posix()):
        relative = p.relative_to(root).as_posix()
        parts = p.relative_to(root).parts
        if any(part in GIT_METADATA for part in parts) or p.suffix == '.pyc':
            continue
        if p.is_symlink():
            raise ValueError('SYMLINK_FORBIDDEN')
        if not p.is_file() or relative in EXCLUDE or relative in CONTROL_DOCS:
            continue
        data = p.read_bytes()
        out.append({'path': relative, 'bytes': len(data),
                    'sha256': hashlib.sha256(data).hexdigest()})
    return out

def verify(root: Path) -> dict:
    manifest = json.loads((root / 'MANIFEST.json').read_text(encoding='utf-8'))
    if (set(manifest) != {'schema', 'version', 'file_count', 'files', 'evidence_boundary'}
            or manifest['schema'] != 'MAESTRO_PREP_PACKAGE_V1'):
        raise ValueError('MANIFEST_CONTRACT_INVALID')
    actual = scan(root)
    if manifest['file_count'] != len(actual) or manifest['files'] != actual:
        raise ValueError('FILE_SET_OR_HASH_MISMATCH')
    lines = (root / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines()
    expected = [v['sha256'] + '  ' + v['path'] for v in actual]
    if lines != expected:
        raise ValueError('SHA256SUMS_MISMATCH')
    return {'schema': 'MAESTRO_PACKAGE_VERIFICATION_V1', 'verified': True,
            'files': len(actual), 'source': 'CURRENT_CHECKOUT_DISTRIBUTABLE_BYTES',
            'host_authority': False}

if __name__ == '__main__':
    try:
        print(json.dumps(verify(Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')), indent=2))
    except (ValueError, KeyError, OSError, UnicodeError) as exc:
        print(json.dumps({'verified': False, 'code': str(exc).split(':')[0]}))
        sys.exit(2)
