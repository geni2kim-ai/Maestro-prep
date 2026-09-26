#!/usr/bin/env python3
"""Deterministic synthetic local connection adversarial scenarios; no node runtime."""
import io
import json
import sys
import unittest
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
sys.path.insert(0,str(BASE/'tests'))
import test_origin_route_hardening
import test_owner_pin_cli

suite=unittest.TestSuite((
    unittest.TestLoader().loadTestsFromModule(test_origin_route_hardening),
    unittest.TestLoader().loadTestsFromModule(test_owner_pin_cli),
))
output=io.StringIO()
result=unittest.TextTestRunner(stream=output,verbosity=0).run(suite)
print(json.dumps({
    'schema':'MAESTRO_ORIGIN_AND_CLOCK_SYNTHETIC_V1',
    'candidate_only':True,'actual_leonardo':'NOT_RUN',
    'actual_node_approved_astra':'NOT_RUN_SYNTHETIC_STUB_ONLY',
    'scenarios':result.testsRun,'failures':len(result.failures),
    'errors':len(result.errors),'skipped':len(result.skipped),
    'status':'PASS' if result.wasSuccessful() else 'FAIL',
    'failed_names':[str(t) for t,_ in result.failures+result.errors],
    'authority':'none','live_effect':'NOT_RUN',
},indent=2))
raise SystemExit(0 if result.wasSuccessful() else 2)
