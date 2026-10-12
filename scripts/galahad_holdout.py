"""Offline synthetic-only external holdout. Host must protect DB and key paths."""
import argparse
import json
from pathlib import Path

from nerve_awim.memory_gateway.contracts import MemoryScope
from nerve_awim.memory_gateway.gateway import MemoryGateway
from nerve_awim.memory_gateway.holdout import freeze_holdout, evaluate_holdout, read_artifact
from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger
from nerve_awim.recursive_evolution_v19 import RetrievalGenome


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('digest', 'freeze', 'evaluate'))
    parser.add_argument('--claims')
    parser.add_argument('--artifact')
    parser.add_argument('--study-id')
    parser.add_argument('--dataset-sha256')
    parser.add_argument('--selected', type=int, nargs=2, metavar=('TOKEN', 'TRIGRAM'))
    parser.add_argument('--baseline', type=int, nargs=2)
    parser.add_argument('--ledger')
    parser.add_argument('--tenant', default='research')
    parser.add_argument('--agent', default='evaluation')
    parser.add_argument('--context', default='synthetic')
    args = parser.parse_args()
    if args.operation == 'digest':
        if not args.artifact:
            parser.error('--artifact required')
        artifact, digest = read_artifact(args.artifact)
        result = {'study_id': artifact['study_id'], 'dataset_sha256': digest}
    else:
        if not args.claims or not args.study_id:
            parser.error('--claims and --study-id required')
        scope = MemoryScope(args.tenant, args.agent, args.context)
        if args.operation == 'freeze':
            if not args.selected or not args.dataset_sha256:
                parser.error('--selected and --dataset-sha256 required')
            result = freeze_holdout(args.claims, study_id=args.study_id,
                dataset_sha256=args.dataset_sha256, selected=RetrievalGenome(*args.selected),
                baseline=RetrievalGenome(*(args.baseline or (3, 0))), scope=scope)
        else:
            if args.selected is not None or args.baseline is not None:
                parser.error('candidate overrides are forbidden during evaluation')
            if not args.artifact or not args.ledger or not Path(args.ledger).is_file():
                parser.error('--artifact and existing synthetic --ledger required')
            authority = MemoryAuthority()
            actor = authority.issue(args.tenant, args.agent, permissions=('read',))
            gateway = MemoryGateway(TrustedMemoryLedger(args.ledger, authority))
            result = evaluate_holdout(args.claims, args.artifact, study_id=args.study_id,
                                      gateway=gateway, actor=actor, scope=scope)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
