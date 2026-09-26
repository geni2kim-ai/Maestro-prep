"""Local read-only CLI for Maestro-Prep v0.1 candidate. No connector or network calls."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .coordinator import ContractError, read_json, decide, vendor_module, verify_generic_file


def main(argv=None):
    p=argparse.ArgumentParser(prog='maestro-prep',description='Candidate-only orchestration. No runtime authority.')
    sub=p.add_subparsers(dest='cmd',required=True)
    d=sub.add_parser('decide',help='evaluate a locally byte-bound work unit')
    for key in ('work','lock','o-signal','receipt-index','evidence-root'):
        d.add_argument('--'+key,required=True)
    for key in ('astra-skill','astra-plan-receipt','leonardo-route'):
        d.add_argument('--'+key)
    a=sub.add_parser('audit-file',help='read-only file hash check, independent of Astra')
    a.add_argument('--file',required=True);a.add_argument('--sha256',required=True)
    f=sub.add_parser('audit-transport',help='invoke the pinned public generic transported archive auditor')
    f.add_argument('--zip',required=True)
    sub.add_parser('component-check',help='check pinned vendored O-Prep source bytes')
    args=p.parse_args(argv)
    try:
        if args.cmd=='decide':
            out=decide(read_json(Path(args.work)),read_json(Path(args.lock)),read_json(Path(args.o_signal)),
                Path(args.receipt_index),Path(args.evidence_root),astra_skill_path=Path(args.astra_skill) if args.astra_skill else None,
                astra_plan_receipt_rel=args.astra_plan_receipt,leonardo_route_rel=args.leonardo_route)
        elif args.cmd=='audit-file': out=verify_generic_file(Path(args.file),args.sha256)
        elif args.cmd=='audit-transport': out=vendor_module().audit_transport_bundle(args.zip)
        else:
            vendor_module();out={'schema':'MAESTRO_COMPONENT_CHECK_V1','o_prep_v03_pinned':True,'astra':'EXTERNAL_NOT_RUN','leonardo':'EXTERNAL_NOT_RUN'}
    except (ContractError,ValueError,OSError) as exc:
        # Errors should be stable, non-sensitive codes; no internal path disclosure.
        out={'schema':'MAESTRO_ERROR_V1','status':'HOLD','issue_code':str(exc).split(':')[0]}
    print(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True))
    if args.cmd=='audit-transport': return 0 if out.get('manifest_verified') and not out.get('findings') else 2
    return 0 if (out.get('next_action') in {'READ_ONLY_EVIDENCE_MATCH','BOUND_CANDIDATE_CHECKS_PASSED'} or
                 args.cmd=='component-check' and out.get('o_prep_v03_pinned')) else 2

if __name__=='__main__':raise SystemExit(main())
