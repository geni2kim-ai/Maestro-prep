"""Manifest scan must be equally strict in extracted ZIP and Actions checkout."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from tools.verify_package import scan

class PackageGitCheckoutTests(unittest.TestCase):
    def test_ignored_git_metadata_not_in_source_inventory(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            (root/'.git/objects').mkdir(parents=True)
            (root/'.git/objects/a').write_bytes(b'git object not shipped')
            (root/'src').mkdir()
            (root/'src/entry.py').write_bytes(b'print(1)\n')
            (root/'__pycache__').mkdir()
            (root/'__pycache__/entry.cpython-313.pyc').write_bytes(b'cache')
            self.assertEqual([f['path'] for f in scan(root)],['src/entry.py'])
    def test_unlisted_source_does_not_get_silently_ignored(self):
        with TemporaryDirectory() as td:
            root=Path(td); (root/'.github/workflows').mkdir(parents=True)
            (root/'.github/workflows/ci.yml').write_bytes(b'name: test\n')
            self.assertEqual([f['path'] for f in scan(root)],['.github/workflows/ci.yml'])
    def test_source_symlink_not_followed(self):
        with TemporaryDirectory() as td:
            root=Path(td); (root/'real.py').write_bytes(b'print(1)')
            try:(root/'link.py').symlink_to(root/'real.py')
            except OSError:self.skipTest('OS denies symlinks')
            with self.assertRaisesRegex(ValueError,'SYMLINK_FORBIDDEN'):
                scan(root)
