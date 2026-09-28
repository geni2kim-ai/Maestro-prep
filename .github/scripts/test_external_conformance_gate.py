"""Local synthetic gate contract tests; NOT external-reference conformance."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).with_name("external_conformance_gate.py")
SPEC = importlib.util.spec_from_file_location("external_conformance_gate", SCRIPT)
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)
SHA = lambda data: hashlib.sha256(data).hexdigest()
COMMIT = "a" * 40

def fixture(tmp: Path):
    root = tmp / "private-reference"
    root.mkdir()
    for name, data in (("profile.json", b'{"profile":"synthetic"}'),
                       ("schema.json", b'{"schema":"synthetic"}'),
                       ("validator.py", b"# synthetic, not executed\n"),
                       ("SKILL.md", b"# synthetic contract\n")):
        (root / name).write_bytes(data)
    bundled = b"synthetic payload"
    manifest = {"schema": "OWNER_APPROVED_REFERENCE_BUNDLE_V1",
                "files": [{"path": "payload.txt", "bytes": len(bundled), "sha256": SHA(bundled)}]}
    (root / "bundle_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with zipfile.ZipFile(root / "reference_archive.zip", "w", compression=zipfile.ZIP_STORED) as zf:
        zf.writestr("payload.txt", bundled)
    harness = tmp / "owner_harness.py"
    harness.write_text("# Synthetic unexecuted harness\n", encoding="utf-8")
    pin = {"schema": "MAESTRO_EXTERNAL_REFERENCE_PIN_V1", "owner_approval_id": "synthetic-review-only",
           "approval_scope": "OFFLINE_REFERENCE_CONFORMANCE_ONLY", "maestro_source_commit": COMMIT,
           "reference_files": {role: {"path": name, "sha256": GATE.digest_file(root / name)}
                               for role, name in GATE.FILENAMES.items()},
           "trusted_harness_sha256": GATE.digest_file(harness)}
    pin_file = tmp / "owner-pin.json"
    pin_file.write_text(json.dumps(pin), encoding="utf-8")
    return root, pin, pin_file, harness

class ExternalGateTests(unittest.TestCase):
    def test_synthetic_pins_validate_without_running(self):
        with tempfile.TemporaryDirectory() as td:
            root, pin, pin_file, harness = fixture(Path(td))
            outcome = GATE.verify_pins(pin_file, root, harness, COMMIT)
            self.assertEqual(outcome["gate"], "PINNED_OWNER_BYTES_VALIDATED")
            self.assertEqual(outcome["actual_conformance"], "NOT_RUN")
            self.assertEqual(outcome["reference_members"], 1)
    def test_missing_owner_approval_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root, pin, pin_file, harness = fixture(Path(td))
            pin["owner_approval_id"] = "OWNER_APPROVAL_REQUIRED"
            pin_file.write_text(json.dumps(pin), encoding="utf-8")
            with self.assertRaisesRegex(GATE.GateError, "OWNER_APPROVAL"):
                GATE.verify_pins(pin_file, root, harness, COMMIT)
    def test_tampered_reference_and_wrong_commit_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root, pin, pin_file, harness = fixture(Path(td))
            with self.assertRaisesRegex(GATE.GateError, "CHECKOUT_COMMIT"):
                GATE.verify_pins(pin_file, root, harness, "b" * 40)
            (root / "profile.json").write_text('{"tampered": true}', encoding="utf-8")
            with self.assertRaisesRegex(GATE.GateError, "REFERENCE_HASH"):
                GATE.verify_pins(pin_file, root, harness, COMMIT)
    def test_unapproved_harness_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root, pin, pin_file, harness = fixture(Path(td))
            harness.write_text("print('different')\n")
            with self.assertRaisesRegex(GATE.GateError, "HARNESS_NOT"):
                GATE.verify_pins(pin_file, root, harness, COMMIT)

if __name__ == "__main__":
    unittest.main()
