"""Self-tests for the vendored CodeDiff policy SHADOW, no external reviewers."""
from __future__ import annotations
import importlib.util
import json
import importlib.util
import importlib._bootstrap_external as bootstrap_external
import sys
import tempfile
import shutil
import subprocess
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

SHADOW = Path(__file__).with_name("codediff_shadow.py")
spec = importlib.util.spec_from_file_location("codediff_shadow_under_test", SHADOW)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CodediffIntegrationTests(unittest.TestCase):
    def test_exact_original_policy_pins(self):
        pinned, official = module.trusted_source_snapshot()
        self.assertEqual(pinned["codediff"]["version"], "2.5")
        self.assertTrue(callable(official.classify_paths))
        self.assertFalse(pinned["leonardo"]["promoted_to_mandatory_runtime"])

    def test_protected_path_overlay_and_upstream(self):
        _, engine = module.trusted_source_snapshot()
        cfg = engine.load_yaml(module.VENDOR / "protected-paths.yml")
        merged = {k: list(cfg.get(k, [])) + module.OVERLAY.get(k, [])
                  for k in module.OVERLAY}
        classified = engine.classify_paths([
            "maestro_prep/coordinator.py", ".github/workflows/candidate-ci.yml",
            "components/o_prep_v0_3/src/o_prep.py",
        ], merged)
        self.assertIn("maestro_prep/coordinator.py", classified["human_floor"])
        self.assertIn(".github/workflows/candidate-ci.yml", classified["governance"])
        self.assertIn(".github/scripts/main_ci.py", engine.classify_paths(
            [".github/scripts/main_ci.py"], merged)["human_floor"])
        self.assertIn("components/o_prep_v0_3/src/o_prep.py", classified["adversarial_floor"])

    def test_sha_immovable_metadata_rejected(self):
        with self.assertRaisesRegex(ValueError, "UNPINNED_GIT_REFERENCE"):
            module.analyze(Path("."), "HEAD", "branch")

    def test_renames_include_both_paths(self):
        with patch.object(module, "git", return_value="R100\0old.py\0new.py\0"):
            paths = module.git_status(Path("."), "a"*40, "b"*40)
        self.assertEqual(paths, ["new.py", "old.py"])

    def test_leonardo_r230_not_promoted_and_shadow_no_authority(self):
        pin = json.loads(module.PIN_PATH.read_text("utf-8"))
        self.assertFalse(pin["leonardo"]["promoted_to_mandatory_runtime"])
        self.assertEqual(pin["codediff"]["mode"], "SHADOW")
        self.assertFalse(pin["codediff"]["trusted_textdiff_sensor"])



    def test_output_symlink_parent_cannot_write_into_repo(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            repo = home / "repo"
            repo.mkdir()
            outside = home / "out"
            outside.mkdir()
            link = outside / "alias"
            link.symlink_to(repo, target_is_directory=True)
            with patch.object(module, "analyze") as fake:
                with patch.object(module, "ROOT", repo):
                    result = module.main(["--repo", str(repo), "--base", "a" * 40,
                                          "--head", "b" * 40,
                                          "--out", str(link / "receipt.json")])
            self.assertEqual(result, 2)
            fake.assert_not_called()
            self.assertFalse((repo / "receipt.json").exists())

    def test_pin_manifest_cannot_redirect_upstream_identity(self):
        original = json.loads(module.PIN_PATH.read_text(encoding="utf-8"))
        original["codediff"]["repo"] = "attacker/codediff-clone"
        with tempfile.TemporaryDirectory() as folder:
            fn = Path(folder) / "modified.json"
            fn.write_text(json.dumps(original), encoding="utf-8")
            with patch.object(module, "PIN_PATH", fn):
                with self.assertRaisesRegex(ValueError, "UNTRUSTED_UPSTREAM_SOURCE_DESCRIPTOR"):
                    module.trusted_source_snapshot()

    def test_pin_manifest_cannot_repeat_same_file(self):
        original = json.loads(module.PIN_PATH.read_text(encoding="utf-8"))
        original["codediff"]["upstream_files"][1] = original["codediff"]["upstream_files"][0]
        with tempfile.TemporaryDirectory() as folder:
            fn = Path(folder) / "modified.json"
            fn.write_text(json.dumps(original), encoding="utf-8")
            with patch.object(module, "PIN_PATH", fn):
                with self.assertRaisesRegex(ValueError, "UNTRUSTED_UPSTREAM_SOURCE_DESCRIPTOR"):
                    module.trusted_source_snapshot()

    def test_dirty_worktree_is_not_a_trusted_review(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder)
            def git(*args):
                return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.DEVNULL).decode().strip()
            git("init", "-q")
            git("config", "user.email", "test@example.invalid")
            git("config", "user.name", "Test")
            (repo / "hello.txt").write_text("original\n")
            git("add", "hello.txt")
            git("commit", "-qm", "base")
            base = git("rev-parse", "HEAD")
            (repo / "hello.txt").write_text("candidate\n")
            git("commit", "-qam", "head")
            head = git("rev-parse", "HEAD")
            (repo / "hello.txt").write_text("not in commit\n")
            with self.assertRaisesRegex(ValueError, "DIRTY_REVIEW_WORKTREE"):
                module.analyze(repo, base, head)
            (repo / "hello.txt").write_text("candidate\n")
            (repo / "new-script.py").write_text("print('not in commit')\n")
            with self.assertRaisesRegex(ValueError, "DIRTY_REVIEW_WORKTREE"):
                module.analyze(repo, base, head)

    def test_forged_valid_timestamp_bytecode_is_not_executed(self):
        # A crafted CPython .pyc bearing the original file mtime+length can
        # execute an entirely different code object via SourceFileLoader.
        # The policy source itself remains byte-for-byte upstream-pinned.
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder)
            home = temp / ".github" / "review_tools" / "codediff_v25"
            home.mkdir(parents=True)
            for source in module.TRUSTED_VENDOR_BLOBS:
                p = temp / source
                p.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(module.ROOT / source, p)
            policy = home / "policy_engine.py"
            clean = policy.read_text(encoding="utf-8")
            self.assertEqual(module.object_id(policy.read_bytes()),
                             module.TRUSTED_VENDOR_BLOBS[".github/review_tools/codediff_v25/policy_engine.py"])
            bad = clean.replace("from __future__ import annotations",
                                "from __future__ import annotations\nINJECTED_PYC_EXECUTED=True", 1)
            code = compile(bad, str(policy), "exec")
            cache = Path(importlib.util.cache_from_source(str(policy)))
            cache.parent.mkdir()
            stat = policy.stat()
            cache.write_bytes(bootstrap_external._code_to_timestamp_pyc(
                code, int(stat.st_mtime), stat.st_size))
            # Pin loader input to the fresh copied source and keep the package
            # manifest itself unchanged; no private inputs leave the tmpdir.
            with patch.object(module, "ROOT", temp), patch.object(module, "VENDOR", home):
                upstream_pins, loaded = module.trusted_source_snapshot()
                self.assertFalse(hasattr(loaded, "INJECTED_PYC_EXECUTED"))
                self.assertEqual(upstream_pins["codediff"]["mode"], "SHADOW")
            self.assertTrue(cache.exists())  # Attack remained present.

    def test_verified_yaml_is_not_loaded_from_second_file_read(self):
        pins, engine = module.trusted_source_snapshot()
        baseline = engine.yaml.safe_load(engine._maestro_verified_policy_yaml["protected-paths.yml"])
        self.assertIn(".github/workflows/**", baseline["governance_paths"])
        self.assertEqual(set(engine._maestro_verified_policy_yaml),
                         {"protected-paths.yml", "escalation-policy.yml", "sensor-policy.yml"})
        with self.assertRaises(TypeError):
            engine._maestro_verified_policy_yaml["protected-paths.yml"] = b"changed"

    def test_policy_snapshots_are_bound_to_raw_upstream_bytes(self):
        _, engine = module.trusted_source_snapshot()
        for policy in ("protected-paths.yml", "escalation-policy.yml", "sensor-policy.yml"):
            data = engine._maestro_verified_policy_yaml[policy]
            self.assertEqual(module.object_id(data), module.TRUSTED_VENDOR_BLOBS[
                ".github/review_tools/codediff_v25/" + policy])

    def test_output_parent_swapped_after_check_is_not_followed(self):
        if module.os.name != "posix":
            self.skipTest("Linux/POSIX fd-bound writer required")
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            repo = home / "repo"
            repo.mkdir()
            out = home / "outside"
            out.mkdir()
            parent = out / "clean"
            parent.mkdir()
            moved = out / "moved"
            expected = repo / "review.json"
            def swap(*args):
                parent.rename(moved)
                parent.symlink_to(repo, target_is_directory=True)
                return {"sensor_mode": "DEGRADED_GIT_INVENTORY",
                        "required_level": "HUMAN", "gate_conclusion": "action_required",
                        "changed_paths": ["sample.py"]}
            with patch.object(module, "analyze", side_effect=swap):
                result = module.main(["--repo", str(repo), "--base", "a" * 40,
                                     "--head", "b" * 40,
                                     "--out", str(parent / "review.json")])
            self.assertEqual(result, 2)
            self.assertFalse(expected.exists())
            self.assertFalse((moved / "review.json").exists())

    def test_parent_swap_after_dirfd_open_is_rejected(self):
        if module.os.name != "posix":
            self.skipTest("POSIX directory-descriptor regression")
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            repo = home / "repo"
            repo.mkdir()
            out = home / "outside"
            out.mkdir()
            parent = out / "clean"
            parent.mkdir()
            moved = out / "moved"
            original_fstat = module.os.fstat
            did_swap = [False]
            def linked_swap(fd):
                if not did_swap[0]:
                    did_swap[0] = True
                    parent.rename(moved)
                    parent.symlink_to(repo, target_is_directory=True)
                return original_fstat(fd)
            with patch.object(module.os, "fstat", side_effect=linked_swap):
                with self.assertRaisesRegex(ValueError, "REVIEW_OUTPUT_PARENT_CHANGED"):
                    module.persist_report_bound(parent / "review.json", repo,
                                                {"result": "SIMULATED"})
            self.assertTrue(did_swap[0])
            self.assertFalse((repo / "review.json").exists())
            self.assertFalse((moved / "review.json").exists())

    def test_leonardo_candidate_sha_is_not_user_supplied(self):
        descriptor = json.loads(module.PIN_PATH.read_text(encoding="utf-8"))
        descriptor["leonardo"]["latest_examined_candidate_sha"] = "0" * 40
        with tempfile.TemporaryDirectory() as folder:
            pin = Path(folder) / "pin.json"
            pin.write_text(json.dumps(descriptor), encoding="utf-8")
            with patch.object(module, "PIN_PATH", pin):
                with self.assertRaisesRegex(ValueError, "LEONARDO_PROVENANCE_PIN_MISMATCH"):
                    module.trusted_source_snapshot()

    def test_leonardo_main_and_branch_are_pinned(self):
        for key, value in (("stable_main_sha", "0" * 40),
                           ("candidate_branch", "candidate/misleading"),
                           ("repo", "attacker/Leonardo")):
            with self.subTest(key=key):
                descriptor = json.loads(module.PIN_PATH.read_text(encoding="utf-8"))
                descriptor["leonardo"][key] = value
                with tempfile.TemporaryDirectory() as folder:
                    pin = Path(folder) / "pin.json"
                    pin.write_text(json.dumps(descriptor), encoding="utf-8")
                    with patch.object(module, "PIN_PATH", pin):
                        with self.assertRaisesRegex(ValueError, "LEONARDO_PROVENANCE_PIN_MISMATCH"):
                            module.trusted_source_snapshot()

    def test_safe_new_output_receipt_has_restricted_mode(self):
        if module.os.name != "posix":
            self.skipTest("POSIX directory-descriptor regression")
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            repo = home / "repo"
            repo.mkdir()
            parent = home / "outside"
            parent.mkdir()
            path = parent / "review.json"
            module.persist_report_bound(path, repo, {"result": "NON_FINAL"})
            self.assertEqual(json.loads(path.read_text()), {"result": "NON_FINAL"})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaisesRegex(ValueError, "REVIEW_OUTPUT_INVALID"):
                module.persist_report_bound(path, repo, {"result": "OVERWRITE"})

    def test_shell_alias_cannot_change_expected_git_command(self):
        with patch.object(module.subprocess, "run") as proc:
            proc.return_value.returncode = 0
            proc.return_value.stdout = b""
            module.git(Path("."), "rev-parse", "HEAD")
        argv = proc.call_args.args[0]
        self.assertIn("core.fsmonitor=false", argv)
        self.assertEqual(argv[-2:], ["rev-parse", "HEAD"])

if __name__ == "__main__":
    unittest.main()
