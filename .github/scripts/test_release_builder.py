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


    def test_read_only_zip_recheck_accepts_local_bytes_but_not_origin(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "output"
            created = MOD.build(ROOT, output)
            archive = output / MOD.ZIP_NAME
            check = MOD.verify_candidate_archive(ROOT, archive, created["archive_sha256"])
            self.assertEqual(check["archive_entries"], 42)
            self.assertEqual(check["local_byte_integrity"], "PASS")
            self.assertEqual(check["digest_channel_independence"], "NOT_VERIFIED")
            with self.assertRaisesRegex(ValueError, "OWNER_DIGEST_MISMATCH"):
                MOD.verify_candidate_archive(ROOT, archive, "a" * 64)

    def test_unexpected_and_duplicate_members_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "original"
            MOD.build(ROOT, out)
            base = out / MOD.ZIP_NAME
            for extra in ("extra.txt", "../outside.txt", "README.md"):
                archive = Path(td) / ("changed-" + str(len(extra)) + "-" + str(extra.startswith(".")) + ".zip")
                archive.write_bytes(base.read_bytes())
                with zipfile.ZipFile(archive, "a") as zf:
                    import warnings
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", UserWarning)
                        zf.writestr(extra, b"synthetic")
                actual = hashlib.sha256(archive.read_bytes()).hexdigest()
                with self.assertRaisesRegex(ValueError, "ARCHIVE_MEMBER_SET_MISMATCH"):
                    MOD.verify_candidate_archive(ROOT, archive, actual)

    def test_changed_member_metadata_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "original"
            MOD.build(ROOT, out)
            original = out / MOD.ZIP_NAME
            changed = Path(td) / "changed.zip"
            with zipfile.ZipFile(original) as src, zipfile.ZipFile(changed, "w") as dest:
                for original_entry in src.infolist():
                    item = zipfile.ZipInfo(original_entry.filename, MOD.FIXED_TIME)
                    item.create_system = 3
                    item.compress_type = zipfile.ZIP_STORED
                    item.external_attr = (0o120777 if original_entry.filename == "README.md"
                                          else 0o100644) << 16
                    dest.writestr(item, src.read(original_entry))
            with self.assertRaisesRegex(ValueError, "ARCHIVE_MEMBER_METADATA_INVALID"):
                MOD.verify_candidate_archive(ROOT, changed,
                                             hashlib.sha256(changed.read_bytes()).hexdigest())

if __name__ == "__main__":
    unittest.main()
