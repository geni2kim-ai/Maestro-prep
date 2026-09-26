#!/usr/bin/env python3
"""Fail closed if public files contain nonfunctional private topology markers.

Detects labels, stamped internal ticket names, host root examples and private
repository references. External product names required by the public interface
are permissible. This check covers only the *current* working tree.
"""
from __future__ import annotations
import json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EXCLUDE={'MANIFEST.json','SHA256SUMS.txt'}
RULES={
 'internal_label':re.compile(r'(?<![A-Za-z0-9])(?:[1-9][ACX]|PC\d{1,3}|BETA:(?:\w+))(?![A-Za-z0-9])|(?<=[_-])(?:1a|1c|2x|3x|4a|4c|4x)(?=[_-])'),
 'dated_internal_reference':re.compile(r'\[\d{6}-[A-Z]\d{2,4}\]|\b\d{6}-[A-Z]\d{2,4}\b',re.I),
 'private_path_layout':re.compile(r'(?i)(?:hub[/\\]skills[/\\]|approved[/\\]astra[-_]|relay[/\\]astra[-_]|[A-Z]:[/\\]Shared[/\\]|[A-Z]:[/\\]Workspace[/\\])'),
 'private_repo_reference':re.compile(r'(?i)(?:Leonardo[-_]P3[-_]addon|chatgpt[-_]work[-_]cloud|chatgpt[-_]redagent)'),
 'private_raw_contract':re.compile(r'(?i)(?:LOCAL[-_]ROUTING[-_]CONTRACT[-_]\d|\bP3V\d{1,3}\b)'),
}
def scan(root:Path=ROOT)->list[dict]:
 findings=[]
 for path in sorted(root.rglob('*')):
  if not path.is_file() or any(x in {'.git','__pycache__','.pytest_cache','.venv'} for x in path.parts) or path.name in EXCLUDE:continue
  rel=path.relative_to(root).as_posix()
  for name,rule in RULES.items():
   if rule.search(rel):findings.append({'path':rel,'rule':'filename_'+name})
  try:content=path.read_text('utf-8')
  except UnicodeError:continue  # Synthetic .bin bytes are inspected by packaging and tests.
  for name,rule in RULES.items():
   if rule.search(content):findings.append({'path':rel,'rule':name})
 return findings
if __name__=='__main__':
 bad=scan();print(json.dumps({'schema':'MAESTRO_PUBLIC_PRIVACY_AUDIT_V1','status':'PASS' if not bad else 'FAIL','issues':bad,'scope':'CURRENT_PUBLISHED_FILES_ONLY'},ensure_ascii=False,indent=2))
 sys.exit(2 if bad else 0)
