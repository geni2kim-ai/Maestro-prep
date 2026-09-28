"""Synthetic/repository-local tests of the candidate ZIP builder."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
SCRIPT = Path(__file__).with_name("build_release.py")
SPEC = importlib.util.spec_from_file_location("build_release", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)
ROOT = SCRIPT.resolve().parents[2]

class ReleaseBuilderTests(unittest.TestCase):
    def test_exact_40_file_payload_plus_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "output"
            receipt = MOD.build(ROOT, output)
            manifest = json.loads((ROOT / "MANIFEST.json").read_text(encoding="utf-8"))
            paths = sorted([*(x["path"] for x in manifest["files"]), "MANIFEST.json", "SHA256SUMS.txt"])
            archive = output / MOD.ZIP_NAME
            self.assertEqual((receipt["payload_files"], receipt["archive_entries"]), (40, 42))
            self.assertEqual(receipt["owner_out_of_band_digest_comparison"], "NOT_RUN")
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), receipt["archive_sha256"])
            self.assertEqual((output / "SHA256SUMS.txt").read_bytes(), (ROOT / "SHA256SUMS.txt").read_bytes())
            with zipfile.ZipFile(archive) as zf:
                self.assertEqual(zf.namelist(), paths)
                for x in manifest["files"]:
                    self.assertEqual(hashlib.sha256(zf.read(x["path"])).hexdigest(), x["sha256"])
                self.assertTrue(all(x.compress_type == zipfile.ZIP_STORED for x in zf.infolist()))

    def test_determinism_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            a, b = Path(td) / "one", Path(td) / "two"
            MOD.build(ROOT, a)
            MOD.build(ROOT, b)
            self.assertEqual((a / MOD.ZIP_NAME).read_bytes(), (b / MOD.ZIP_NAME).read_bytes())
            with self.assertRaises(FileExistsError):
                MOD.build(ROOT, a)

    def test_refuse_destination_inside_checkout(self):
        with self.assertRaisesRegex(ValueError, "OUTPUT_MUST_BE_SEPARATE"):
            MOD.build(ROOT, ROOT / "release-output")

if __name__ == "__main__":
    unittest.main()
