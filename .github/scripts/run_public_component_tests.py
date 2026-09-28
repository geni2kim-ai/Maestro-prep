#!/usr/bin/env python3
"""Execute included public compatibility tests. No host-approved original is tested."""
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PUBLIC_COMPONENT = ROOT / 'components' / 'o_prep_v0_3'
sys.path.insert(0, str(PUBLIC_COMPONENT / 'src'))
sys.path.insert(0, str(PUBLIC_COMPONENT / 'tests'))

if os.name == 'nt':
    from test_v03_hardening import V03OutputTests
    original = V03OutputTests.test_new_receipt_is_exclusive_and_private
    V03OutputTests.test_new_receipt_is_exclusive_and_private = unittest.skip(
        'POSIX 0600 assertion is inapplicable to Windows; actual NTFS ACL remains NOT_RUN'
    )(original)
    print('VENDOR_PLATFORM_EXCEPTION: POSIX mode-bit check skipped; real NTFS ACL NOT_RUN',
          file=sys.stderr)

suite = unittest.TestLoader().discover(str(PUBLIC_COMPONENT / 'tests'))
result = unittest.TextTestRunner(verbosity=1).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 2)
