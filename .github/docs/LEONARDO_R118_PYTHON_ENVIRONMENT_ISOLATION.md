# R1.18 — Python environment import-shadow hardening (non-final)

Date: 2026-10-13. Base candidate `bf3e1b13d8f3f69006b4323ec45f566f924210bd`, GitHub Actions Run #96. This is an isolated Python CI evidence-execution fix. **Not** production authority, external attestation, independent Leonardo review, merge or deployment.

## Executed attack on exact R1.17 source

Retrieved the tracked-source archive for `bf3e1b13d8f3f69006b4323ec45f566f924210bd` from Run #96; nested source ZIP SHA-256 `ce4c1b67e4e2de656c7eb36b8b9d777d38e1de732e4aac833e92605cd5970150`. The untouched baseline produced offline CI **9/9 PASS**. With R1.17 original CI, executed the top-level program as `python -I -B .github/scripts/main_ci.py` so that the parent interpreter itself did not import untrusted environment content; the **children** still inherited `PYTHONPATH` and started as `python -B -X pycache_prefix=<new-dir>`.

Set `PYTHONPATH` to a disposable folder containing a harmless replacement `unittest` package. Its initializer wrote a marker to a separate test file then delegated to the real stdlib `unittest` implementation, so legitimate tests could proceed. **Five actual child imports executed the unreviewed marker code**, while offline CI nevertheless reported **9/9 PASS**. Git tracked source and the R1.17 pinned test source bytes were unchanged. This was a local synthetic environment and marker, not a production-node compromise or a poisoned Python interpreter.

The new `pycache_prefix` in R1.17 addressed stale bytecode reads but not environment-based module search-path injection.

## R1.18 correction

1. Every main-profile CI child starts with `python -E -s -B -X pycache_prefix=<unique-empty-tempdir>`. `-E` ignores `PYTHONPATH`, `PYTHONHOME`, `PYTHONWARNINGS` and other Python-specific environment settings; `-s` excludes the user site directory; `-B` and the empty isolated cache prefix retain the R1.17 behavior. The repository's expected package paths remain available to commands using `-m` or scripts because `-I` is not forced on those children.
2. The GitHub CI **top-level** entrypoint runs as `python -I -B .github/scripts/main_ci.py`, preventing a poisoned inherited Python path from executing before the child launch controls apply.
3. Two additional tests verify argument order even with hostile inherited Python environment values, and directly reproduce the `unittest` path-shadow import with CPython `-B` versus `-E -s -B` in a disposable folder. Existing empty bytecode cache isolation tests updated to check the new flags.
4. Required CI accounting methods **34→36**, expected method IDs and source SHA256 pin `c811694b713f651d58782a4bba1da0869740c4f3a4b23ddc28d48792fa2c917d` updated. Mandatory component and synthetic gate semantics unchanged.

## Local retest and expected evidence

Actual fixed source on Linux Python 3.13: offline CI **9/9**, accounting **36/36**, coordinator **79**, component **70**, CodeDiff integration **21/21**, public privacy check PASS. Repeated complete CI with the same hostile `PYTHONPATH` and a `-I` parent: offline **9/9 PASS**, **no injected marker file**. The green score is not the proof alone; the before/after import marker is the distinguishing evidence. Source Git objects of the executed files: `main_ci.py a50cdf88e0c33a4761812ae06433769423785cc1`, `test_main_ci_contract.py 401d77957d4b50fe86d972c3eca2f34ed3b99331`, `candidate-ci.yml 277eac2a63f6158ae646aabc39d657d6aff48ad4`.

## Leonardo provenance (critical qualification)

Verified the **original Leonardo R2.30 policy-use module** Git blob `2dedbc58ba968da3d10fd783f54f43e762c52763`, contract blob `4665c26f9be9e52b4bba1bb968660bb654bd7f67`, and JSON utility `36b526f73692609d1b230b2ef7760f64f2d435ec`; executed them in a disposable import harness. Signals were **hand-assigned using a minimal compatibility dataclass**, not extracted by Leonardo's actual signal classifier. The real R2.30 `signals.py` at its repo path is a different **88KB** Git blob `cc9d9d735f38de499489bd227e3ebd13013f3ba8`; the small 279-byte harness signals class `34c8d412ad376ed21a5ca94a5cfc65c173a09be5` used in earlier probes is **not the original full signal detector**. Avoid labeling it as such.

Limited outputs: frozen-evidence `FORBIDDEN_INSIDE_REVIEW`; multiagent authority-sensitive change `MANDATORY`; deterministic checksum `BYPASS`; synthetic contract mutation invalidated its SHA. Actual natural-language signals detection, full `route_task`, models, connected Leonardo operator and independent RedAgent/HUMAN review: **NOT_RUN**.

## Remaining trust and operator boundary

Python `-E -s` does not sandbox system site-packages, interpreter startup hooks in **trusted** installation paths, a compromised Python executable, source files replaced after invocation, or attacker-controlled checkout `sys.path` imports. CodeDiff policy SHADOW remains `SENSOR_ONLY`, `required_level=HUMAN`, and `authority_effect=NONE`. Existing ordinary-user Windows symlink privilege gap remains HOLD despite any hosted CI success.

Re-run the exact-head GitHub CI and pinned official CodeDiff v2.5 SHADOW. **No new local sandbox test kit**, since this bug was reproduced and can be regression-tested in hosted Windows/Linux jobs with isolated synthetic imports; it does not change operator-node OS privileges. Keep the PR Draft, main untouched, no merge or deployment.
