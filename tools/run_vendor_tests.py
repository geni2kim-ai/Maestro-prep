#!/usr/bin/env python3
"""Run the redacted public O-Prep compatibility suite; this is not the public profile pin.

On Windows, exactly one POSIX-only 0600 mode-bit assertion is NOT_APPLICABLE:
Windows ACL confidentiality requires an independent, owner-run icacls/security
check on the real node. A separate Windows test still covers O_EXCL/no overwrite.
No other public profile test is skipped by this wrapper.
"""
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / 'components' / 'o_prep_v0_3'
sys.path.insert(0, str(VENDOR / 'src'))
sys.path.insert(0, str(VENDOR / 'tests'))

if os.name == 'nt':
    from test_v03_hardening import V03OutputTests
    original = V03OutputTests.test_new_receipt_is_exclusive_and_private
    V03OutputTests.test_new_receipt_is_exclusive_and_private = unittest.skip(
        'POSIX 0600 mode bits not meaningful on Windows; real-node NTFS ACL remains NOT_RUN'
    )(original)
    print('VENDOR_PLATFORM_EXCEPTION: Windows POSIX mode-bit assertion NOT_APPLICABLE; ACL NOT_RUN',
          file=sys.stderr)

suite = unittest.TestLoader().discover(str(VENDOR / 'tests'))
result = unittest.TextTestRunner(verbosity=1).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 2)
