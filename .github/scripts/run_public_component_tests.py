#!/usr/bin/env python3
"""Execute included public compatibility tests. No host-approved original is tested."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PUBLIC_COMPONENT = ROOT / 'components' / 'o_prep_v0_3'
sys.path.insert(0, str(PUBLIC_COMPONENT / 'src'))
sys.path.insert(0, str(PUBLIC_COMPONENT / 'tests'))

if os.name == 'nt':
    from test_v03_hardening import V03OutputTests, V03LocalBindingTests
    original = V03OutputTests.test_new_receipt_is_exclusive_and_private
    V03OutputTests.test_new_receipt_is_exclusive_and_private = unittest.skip(
        'POSIX 0600 assertion is inapplicable to Windows; actual NTFS ACL remains NOT_RUN'
    )(original)
    print('VENDOR_PLATFORM_EXCEPTION: POSIX mode-bit check skipped; real NTFS ACL NOT_RUN',
          file=sys.stderr)

    # A standard-user Windows sandbox often cannot create symlinks. Record
    # that capability gap rather than reporting OSError 1314 as a product bug.
    # The tests MUST remain unverified and cannot count as a CI approval.
    for case, directory in (
        ((V03LocalBindingTests, 'test_symlink_to_external_file_fails_closed'), False),
        ((V03OutputTests, 'test_symlinked_output_parent_is_blocked'), True),
    ):
        klass, testname = case
        with tempfile.TemporaryDirectory(prefix='maestro-link-probe-') as folder:
            root = Path(folder)
            target = root / 'target'
            if directory:
                target.mkdir()
            else:
                target.write_bytes(b'probe')
            link = root / 'link'
            try:
                link.symlink_to(target, target_is_directory=directory)
            except OSError as exc:
                if getattr(exc, 'winerror', None) != 1314:
                    raise
                original_test = getattr(klass, testname)
                setattr(klass, testname, unittest.skip(
                    'WINDOWS_SYMLINK_PRIVILEGE_UNAVAILABLE: REAL_LINK_NOT_TESTED'
                )(original_test))
                print('VENDOR_PLATFORM_GAP:WINDOWS_SYMLINK_PRIVILEGE_UNAVAILABLE:' + testname,
                      file=sys.stderr)
            else:
                link.unlink()

suite = unittest.TestLoader().discover(str(PUBLIC_COMPONENT / 'tests'))
result = unittest.TextTestRunner(verbosity=1).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 2)
