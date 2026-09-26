"""Local read-only CLI for Maestro-Prep v0.2.5 candidate. No connector or network calls."""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from .coordinator import ContractError, read_json, read_json_owner_pinned, decide, vendor_module, verify_generic_file


def main(argv=None):
    p=argparse.ArgumentParser(prog='maestro-prep',description='Candidate-only orchestration. No runtime authority.')
    sub=p.add_subparsers(dest='cmd',required=True)
    d=sub.add_parser('decide',help='evaluate a locally byte-bound work unit')
    for key in ('work','lock','o-signal','receipt-index','evidence-root'):
        d.add_argument('--'+key,required=True)
    for key in ('astra-skill','astra-plan-receipt','leonardo-route','astra-bundle-root'):
        d.add_argument('--'+key)
    d.add_argument('--approved-lock-sha256',help='owner-supplied out-of-band SHA-256 of exact lock JSON; required except --offline-replay')
    d.add_argument('--offline-replay',action='store_true',help='synthetic/historical-only: skip live host-clock comparison')
    a=sub.add_parser('audit-file',help='read-only file hash check, independent of Astra')
    a.add_argument('--file',required=True);a.add_argument('--sha256',required=True)
    f=sub.add_parser('audit-transport',help='invoke the pinned O-Prep SUBJECT evidence archive auditor')
    f.add_argument('--zip',required=True)
    sub.add_parser('component-check',help='check pinned vendored O-Prep source bytes')
    args=p.parse_args(argv)
    try:
        if args.cmd=='decide':
            if not args.offline_replay and not args.approved_lock_sha256:
                raise ContractError('OWNER_LOCK_PIN_REQUIRED')
            lock=(read_json_owner_pinned(Path(args.lock),args.approved_lock_sha256)
                  if args.approved_lock_sha256 else read_json(Path(args.lock)))
            out=decide(read_json(Path(args.work)),lock,read_json(Path(args.o_signal)),
                Path(args.receipt_index),Path(args.evidence_root),astra_skill_path=Path(args.astra_skill) if args.astra_skill else None,
                astra_plan_receipt_rel=args.astra_plan_receipt,leonardo_route_rel=args.leonardo_route,
                astra_bundle_root=Path(args.astra_bundle_root) if args.astra_bundle_root else None,
                observed_now=None if args.offline_replay else datetime.now(timezone.utc))
            out['lock_binding']=('OWNER_SUPPLIED_SHA256_LOCAL_BYTES_ONLY' if args.approved_lock_sha256
                                 else 'SELF_REPORTED_OFFLINE_ONLY')
            # A synthetic/historical replay must never emit the same green
            # next_action as a candidate backed by a current host/policy check.
            if args.offline_replay and out.get('next_action') == 'BOUND_CANDIDATE_CHECKS_PASSED':
                out['simulated_next_action'] = out['next_action']
                out['next_action'] = 'OFFLINE_REPLAY_NON_AUTHORIZING'
        elif args.cmd=='audit-file': out=verify_generic_file(Path(args.file),args.sha256)
        elif args.cmd=='audit-transport': out=vendor_module().audit_transport_bundle(args.zip)
        else:
            vendor_module();out={'schema':'MAESTRO_COMPONENT_CHECK_V1','o_prep_v03_pinned':True,'astra':'EXTERNAL_NOT_RUN','leonardo':'EXTERNAL_NOT_RUN'}
    except (ContractError,ValueError,OSError) as exc:
        # Errors should be stable, non-sensitive codes; no internal path disclosure.
        out={'schema':'MAESTRO_ERROR_V1','status':'HOLD','issue_code':str(exc).split(':')[0]}
    print(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True))
    if args.cmd=='audit-transport': return 0 if out.get('manifest_verified') and not out.get('findings') else 2
    return 0 if (out.get('next_action') in {'READ_ONLY_EVIDENCE_MATCH','BOUND_CANDIDATE_CHECKS_PASSED','OFFLINE_REPLAY_NON_AUTHORIZING'} or
                 args.cmd=='component-check' and out.get('o_prep_v03_pinned')) else 2

if __name__=='__main__':raise SystemExit(main())
