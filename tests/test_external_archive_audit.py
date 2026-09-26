"""Synthetic only: no historical node or workflow identifiers in fixtures."""
import json,hashlib,stat,tempfile,unittest
from pathlib import Path
from zipfile import ZipFile,ZipInfo
from unittest.mock import patch
from tools.audit_external_archive import audit,AuditError,_sha,main

def packed(values):return (json.dumps(values,sort_keys=True,separators=(',',':'))+'\n').encode()
class PublicArchiveAuditTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.path=Path(self.temp.name)/'synthetic.zip'
  self.data={'evidence/payload.json':packed({'event':'synthetic'}),'evidence/receipt.json':packed({'scope':'test-only'})}
  self.build()
 def build(self,extra=None):
  values=dict(self.data)
  if extra:values.update(extra)
  self.manifest=packed({'files':{k:{'bytes':len(v),'sha256':_sha(v)} for k,v in values.items()}})
  with ZipFile(self.path,'w') as z:
   for k,v in values.items():z.writestr(k,v)
   z.writestr('manifest.json',self.manifest)
 def pins(self):return {'owner_bundle_sha256':_sha(self.path.read_bytes()),'owner_manifest_sha256':_sha(self.manifest)}
 def test_self_consistent_without_owner_is_not_approved(self):
  x=audit(self.path);self.assertEqual(x['status'],'SELF_CONSISTENT_OWNER_PINS_MISSING');self.assertFalse(x['authorized_to_deploy'])
 def test_correct_two_owner_pins_only_verify_bytes(self):
  x=audit(self.path,**self.pins());self.assertEqual(x['status'],'OWNER_PINNED_BYTES_VERIFIED_EXTERNAL_GATES_OPEN');self.assertFalse(x['authorized_to_deploy'])
 def test_wrong_archive_pin_holds(self):self.assertIn('OWNER_PIN_MISMATCH',audit(self.path,owner_bundle_sha256='0'*64,owner_manifest_sha256=_sha(self.manifest))['issues'])
 def test_wrong_manifest_pin_holds(self):self.assertIn('OWNER_PIN_MISMATCH',audit(self.path,owner_bundle_sha256=_sha(self.path.read_bytes()),owner_manifest_sha256='0'*64)['issues'])
 def test_one_missing_owner_pin_keeps_hold(self):self.assertEqual(audit(self.path,owner_bundle_sha256=_sha(self.path.read_bytes()))['status'],'SELF_CONSISTENT_OWNER_PINS_MISSING')
 def test_tamper_member_holds(self):
  self.data['evidence/payload.json']=b'changed';
  with ZipFile(self.path,'w') as z:
   for k,v in self.data.items():z.writestr(k,v)
   z.writestr('manifest.json',self.manifest)
  self.assertIn('MEMBER_BYTES_MISMATCH',audit(self.path)['issues'])
 def test_extra_member_holds(self):
  with ZipFile(self.path,'a') as z:z.writestr('unlisted.txt','x')
  self.assertIn('UNLISTED_OR_MISSING_MEMBERS',audit(self.path)['issues'])
 def test_missing_manifest_rejected(self):
  with ZipFile(self.path,'w') as z:z.writestr('data.json','{}')
  with self.assertRaisesRegex(AuditError,'ARCHIVE_MEMBER_COUNT|MANIFEST_REQUIRED'):audit(self.path)
 def test_traversal_rejected(self):
  with ZipFile(self.path,'a') as z:z.writestr('../escape.txt','x')
  with self.assertRaisesRegex(AuditError,'UNSAFE_MEMBER_PATH'):audit(self.path)
 def test_windows_drive_rejected(self):
  with ZipFile(self.path,'a') as z:z.writestr('Q:/bad.txt','x')
  with self.assertRaisesRegex(AuditError,'UNSAFE_MEMBER_PATH'):audit(self.path)
 def test_casefold_duplicate_rejected(self):
  with ZipFile(self.path,'a') as z:z.writestr('MANIFEST.json','x')
  with self.assertRaisesRegex(AuditError,'DUPLICATE_MEMBER_PATH'):audit(self.path)
 def test_symlink_rejected(self):
  with ZipFile(self.path,'a') as z:
   m=ZipInfo('link');m.create_system=3;m.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(m,'outside')
  with self.assertRaisesRegex(AuditError,'SYMLINK_MEMBER'):audit(self.path)
 def test_extraction_limit(self):
  with ZipFile(self.path,'a') as z:z.writestr('large.bin',b'x'*(2*1024*1024+1))
  with self.assertRaisesRegex(AuditError,'EXPANSION_LIMIT'):audit(self.path)
 def test_invalid_digest_format_holds(self):
  x=audit(self.path,owner_bundle_sha256='wrong',owner_manifest_sha256='0'*64)
  self.assertIn('OWNER_PIN_INVALID',x['issues'])
 def test_duplicate_manifest_key_rejected(self):
  with ZipFile(self.path,'w') as z:
   for k,v in self.data.items():z.writestr(k,v)
   z.writestr('manifest.json',b'{"files":{},"files":{}}')
  with self.assertRaises(AuditError):audit(self.path)
 def test_missing_listed_item_holds(self):
  with ZipFile(self.path,'w') as z:
   z.writestr('evidence/receipt.json',self.data['evidence/receipt.json']);z.writestr('manifest.json',self.manifest)
  self.assertIn('MEMBER_BYTES_MISMATCH',audit(self.path)['issues'])
 def test_owner_pin_is_bound_to_same_snapshot(self):
  pin=self.pins();orig=Path.read_bytes
  def change_after_first_read(path):
   value=orig(path)
   if Path(path)==self.path:self.path.write_bytes(b'invalid second read')
   return value
  with patch.object(Path,'read_bytes',autospec=True,side_effect=change_after_first_read):
   x=audit(self.path,**pin)
  self.assertEqual(x['status'],'OWNER_PINNED_BYTES_VERIFIED_EXTERNAL_GATES_OPEN')
 def test_cli_bad_archive_is_hold(self):
  self.path.write_bytes(b'invalid')
  from io import StringIO
  output=StringIO()
  with patch('sys.stdout',output):ret=main([str(self.path)])
  self.assertEqual(ret,2);self.assertEqual(json.loads(output.getvalue())['status'],'HOLD')
