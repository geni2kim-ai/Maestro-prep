"""On Windows preserve O_EXCL and path isolation, without claiming POSIX ACLs."""
import os
import tempfile
import unittest
from pathlib import Path
from maestro_prep.coordinator import vendor_module

@unittest.skipUnless(os.name == 'nt', 'Windows-only O_EXCL check; POSIX mode assertions in vendor suite')
class WindowsVendorOutputTests(unittest.TestCase):
    def test_exclusive_output_is_not_overwritten_even_without_posix_mode(self):
        vendor=vendor_module()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            file=root/'receipt.json'
            vendor._secure_out_file(file,root,'{"synthetic":true}')
            self.assertEqual(file.read_text(encoding='utf-8'),'{"synthetic":true}')
            with self.assertRaises(FileExistsError):
                vendor._secure_out_file(file,root,'tampered')
            self.assertEqual(file.read_text(encoding='utf-8'),'{"synthetic":true}')
            self.assertFalse(file.is_symlink())
