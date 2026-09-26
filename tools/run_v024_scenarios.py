#!/usr/bin/env python3
"""Run only the new v0.2.4 deterministic synthetic adversarial regressions.

No live Leonardo, approved Astra, remote node or production effects.
"""
import io
import json
import sys
import unittest
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE));sys.path.insert(0,str(BASE/'tests'))
import test_astra_manifest_v024
suite=unittest.defaultTestLoader.loadTestsFromModule(test_astra_manifest_v024)
out=io.StringIO();r=unittest.TextTestRunner(stream=out,verbosity=0).run(suite)
print(json.dumps({
    'schema':'MAESTRO_V024_SYNTHETIC_CONNECTION_GUARDS_V1',
    'scenarios':r.testsRun,'passed':r.testsRun-len(r.failures)-len(r.errors)-len(r.skipped),
    'failures':len(r.failures),'errors':len(r.errors),'skipped':len(r.skipped),
    'status':'PASS' if r.wasSuccessful() else 'FAIL',
    'failed_names':[str(t) for t,_ in r.failures+r.errors],
    'leonardo_executable':'NOT_RUN','approved_node_astra':'NOT_RUN',
    'validator':'HASH_PINNED_SYNTHETIC_STUB',
    'candidate_only':True,'host_mutation_authorized':False,
},indent=2));sys.exit(0 if r.wasSuccessful() else 2)
