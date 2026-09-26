#!/usr/bin/env python3
"""Reproducible CI runner: no node secrets, installs, deploys, or network access.

Exit non-zero on *any* failed test or malformed scenario receipt. Prints one
machine-readable source-labelled report, not host or reviewer attestation.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOBS = [
    ("package_integrity", ["tools/verify_package.py", "."], "package"),
    ("public_privacy", ["tools/public_privacy_check.py"], "privacy"),
    ("vendor_pin", ["-m", "maestro_prep.cli", "component-check"], "vendor"),
    ("maestro_tests", ["-m", "unittest", "discover", "-s", "tests", "-q"], "tests"),
    ("o_prep_tests", ["tools/run_vendor_tests.py"], "tests"),
    ("prior_replay", ["tools/replay_simulation.py"], "prior"),
    ("connection_replay", ["tools/run_connection_scenarios.py"], "scenario"),
    ("rebind_replay", ["tools/run_rebind_scenarios.py"], "scenario"),
    ("origin_replay", ["tools/run_origin_hardening_scenarios.py"], "status"),
    ("manifest_chronology_replay", ["tools/run_v024_scenarios.py"], "status"),
    ("deployment_preflight_regressions", ["-m", "unittest", "discover", "-s", "tests", "-p", "test_local_node_preflight.py", "-q"], "preflight"),
    ("external_archive_synthetic_intake", ["-m", "unittest", "discover", "-s", "tests", "-p", "test_external_archive_audit.py", "-q"], "external_archive"),
]

def check(name: str, args: list[str], kind: str) -> dict:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    if os.name == 'nt':
        # GitHub-hosted Windows temp roots may be NTFS junction aliases. The
        # original O-Prep v0.3 local-byte reader compares a resolved receipt
        # path against an absolute root. Keep the public-profile regression tests on
        # a canonical, external, isolated temp root instead of disabling them.
        import tempfile
        base = Path(os.environ.get('RUNNER_TEMP', tempfile.gettempdir())).resolve(strict=True)
        canonical_temp = base / 'maestro-prep-ci-temp'
        canonical_temp.mkdir(parents=True, exist_ok=True)
        env.update(TEMP=str(canonical_temp), TMP=str(canonical_temp), TMPDIR=str(canonical_temp))
    result = subprocess.run([sys.executable, *args], cwd=ROOT, env=env, timeout=120,
                            text=True, encoding="utf-8", errors="replace", capture_output=True)
    data = None
    try:
        data = json.loads(result.stdout)
    except (ValueError, TypeError):
        pass
    success = result.returncode == 0 and isinstance(data, dict)
    if kind == "package":
        success = success and data.get("verified") is True and data.get("host_authority") is False
    elif kind == "privacy":
        success = success and data.get("status") == "PASS" and data.get("issues") == []
    elif kind == "vendor":
        success = success and data.get("o_prep_v03_pinned") is True
    elif kind == "prior":
        success = (success and data.get("scenario_count") == 20
                   and data.get("o_prep_cases_matched") == 20
                   and data.get("c_compulsory_gate_skips_when_available") == 0)
    elif kind == "scenario":
        success = success and data.get("cases") == data.get("matched") and data.get("cases") == 8
    elif kind == "status":
        expected = {"origin_replay":19,"manifest_chronology_replay":12}[name]
        success = (success and data.get("status") == "PASS"
                   and data.get("scenarios") == expected and data.get("failures") == 0
                   and data.get("errors") == 0 and data.get("skipped") == 0)
    # Unit tests emit stderr even with -q; guard against false-green zero discovery.
    elif kind == "preflight":
        import re
        match = re.search(r"Ran (\d+) tests", result.stderr)
        success = (result.returncode == 0 and match is not None
                   and int(match.group(1)) >= 14 and "OK" in result.stderr)
    elif kind == "external_archive":
        import re
        match = re.search(r"Ran (\d+) tests", result.stderr)
        success = (result.returncode == 0 and match is not None
                   and int(match.group(1)) >= 18 and "OK" in result.stderr)
    elif kind == "tests":
        import re
        matched = re.search(r"Ran (\d+) tests", result.stderr)
        minimum = 170 if name == "maestro_tests" else 61
        success = (result.returncode == 0 and matched is not None
                   and int(matched.group(1)) >= minimum and "OK" in result.stderr)
        if name == 'o_prep_tests' and os.name == 'nt':
            # Exactly one POSIX-only mode-bit assertion is not applicable on
            # Windows; no other original vendor case may be hidden by this
            # platform-specific wrapper. The 5 existing vendor Windows skips
            # plus this one must be accounted for explicitly.
            success = (success and result.stderr.count('VENDOR_PLATFORM_EXCEPTION') == 1
                       and re.search(r'OK \(skipped=6\)', result.stderr) is not None)
    receipt = {"name":name,"exit_code":result.returncode,"passed":bool(success),
               "scope":"OFFLINE_LOCAL_BYTES_AND_SYNTHETIC"}
    if not success:
        # Truncate stderr: never ingest private node files or arbitrary full logs.
        receipt["diagnostic"] = (result.stderr or result.stdout)[:1200]
    return receipt

def main() -> int:
    receipts = []
    for name, args, kind in JOBS:
        print(f"CI_START {name}", file=sys.stderr, flush=True)
        try:
            r = check(name,args,kind)
        except (OSError,subprocess.TimeoutExpired) as exc:
            r = {"name":name,"passed":False,"exit_code":None,"diagnostic":type(exc).__name__}
        receipts.append(r)
    result = {"schema":"MAESTRO_OFFLINE_CI_RECEIPT_V1","candidate_only":True,
              "real_leonardo":"NOT_RUN","node_approved_astra":"NOT_RUN",
              "host_mutation_authorized":False,"jobs":receipts,
              "passed":sum(r["passed"] for r in receipts),"total":len(receipts)}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] == result["total"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
