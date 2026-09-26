"""Synthetic publication privacy checks; no actual private topology is included."""
import tempfile
import unittest
from pathlib import Path

from tools.public_privacy_check import scan


class PrivacyScannerTests(unittest.TestCase):
    def check_finding(self, path: str, payload: bytes, expected: str):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            self.assertIn(expected, {x['rule'] for x in scan(Path(td))})

    def test_clean_generic_source(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / 'generic.md').write_text('Independent routing, planning and evidence.\n')
            self.assertEqual(scan(Path(td)), [])

    def test_internal_alias(self):
        self.check_finding('generic.txt', ('alias: ' + str(1) + chr(65)).encode(), 'internal_label')

    def test_old_private_path(self):
        self.check_finding('generic.txt', ('location: ' + 'Hub' + '/skills/relay/hidden').encode(), 'private_path_layout')

    def test_private_repository(self):
        self.check_finding('generic.txt', ('repository: ' + 'Leonardo' + '-P3-addon').encode(), 'private_repo_reference')

    def test_filename_not_generic(self):
        self.check_finding('artifact_' + str(1) + chr(65) + '.md', b'generic', 'filename_internal_label')

    def test_non_utf8_binary_cannot_hide_private_label(self):
        self.check_finding('fixture.bin', b'\xff\xfe\x01' + bytes([49, 65]) + b'\xfe\xff', 'internal_label')

    def test_utf16_bom_cannot_hide_private_label(self):
        self.check_finding('fixture.txt', ('alias: ' + str(1) + chr(65)).encode('utf-16'), 'internal_label')

    def test_genericized_public_export(self):
        self.check_finding('archive.txt', ('public-' + 'astra-' + 'mirror').encode(), 'unneeded_cross_repo_audit')

    def test_no_symbolic_link_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'target').write_text('generic')
            try:
                (root / 'linked').symlink_to(root / 'target')
            except (OSError, NotImplementedError):
                self.skipTest('symlink unavailable')
            self.assertIn('symlink_file', {x['rule'] for x in scan(root)})

    def test_manifest_filename_checked(self):
        self.check_finding('MANIFEST.json', ('{"name":"' + str(1) + chr(65) + '"}').encode(), 'internal_label')


if __name__ == '__main__':
    unittest.main()
