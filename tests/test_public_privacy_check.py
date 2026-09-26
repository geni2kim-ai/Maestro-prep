"""Synthetic negative controls for the current public file scanner."""
import tempfile,unittest
from pathlib import Path
from tools.public_privacy_check import scan
class PrivacyScannerTests(unittest.TestCase):
 def test_clean_synthetic_data_passes(self):
  with tempfile.TemporaryDirectory() as td:
   Path(td,'generic.md').write_text('Owner pins: route, plan and evidence only.\n')
   self.assertEqual(scan(Path(td)),[])
 def test_short_internal_node_label_is_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   Path(td,'fixture.md').write_text('This is node '+str(1)+chr(65)+'.')
   self.assertTrue(scan(Path(td)))
 def test_old_private_path_is_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   Path(td,'fixture.md').write_text('Path '+'Hub'+'/skills/relay/hidden')
   self.assertTrue(scan(Path(td)))
 def test_private_repository_reference_is_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   Path(td,'fixture.md').write_text('Repository: '+'Leonardo'+'-P3-addon')
   self.assertTrue(scan(Path(td)))
 def test_filename_must_be_generic(self):
  with tempfile.TemporaryDirectory() as td:
   Path(td,'artifact_'+str(1)+chr(65)+'.md').write_text('generic')
   self.assertTrue(scan(Path(td)))
