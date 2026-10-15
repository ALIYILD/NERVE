#!/usr/bin/env python3
"""Synthetic trusted-host demonstration of verified research outcome memory."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger
from nerve_awim.memory_gateway import MemoryGateway, MemoryScope, MemoryRequest
from nerve_awim.memory_gateway.research_outcome_memory import ResearchOutcomeMemory

SCOPE=MemoryScope('synthetic-research','scientific-coordinator','verified-experiments')


def readback(root):
    if not (root/'memory.sqlite').is_file():
        raise ValueError('missing_research_memory')
    authority=MemoryAuthority()
    reader=authority.issue(SCOPE.tenant_id,SCOPE.agent_id,permissions=('read',))
    gateway=MemoryGateway(TrustedMemoryLedger(root/'memory.sqlite',authority))
    result=gateway.retrieve(reader,MemoryRequest(SCOPE,'verified_synthetic_research_outcome'))
    return {'records':len(result.records),'memory_ids':[r.memory_id for r in result.records],
            'recommendations':[json.loads(r.content)['recommendation'] for r in result.records],
            'candidate_promoted':any(json.loads(r.content)['candidate_promoted'] for r in result.records)}


def run(root, study, claims, supervisor):
    root.mkdir(parents=True,exist_ok=False)
    authority=MemoryAuthority()
    proposer=authority.issue(SCOPE.tenant_id,SCOPE.agent_id,permissions=('read','propose'))
    reviewer=authority.issue(SCOPE.tenant_id,SCOPE.agent_id,permissions=('read','approve'))
    reader=authority.issue(SCOPE.tenant_id,SCOPE.agent_id,permissions=('read',))
    gateway=MemoryGateway(TrustedMemoryLedger(root/'memory.sqlite',authority))
    bridge=ResearchOutcomeMemory(gateway)
    mid=bridge.propose(proposer,SCOPE,study,claims,supervisor)
    pending=len(gateway.retrieve(reader,MemoryRequest(SCOPE,'verified_synthetic_research_outcome')).records)
    if pending:raise RuntimeError('pending_research_memory_leaked')
    bridge.review(reviewer,SCOPE,mid,study,claims,supervisor)
    process=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--directory',str(root),
                            '--verify-existing'],check=True,capture_output=True,text=True,timeout=30)
    restarted=json.loads(process.stdout)
    if restarted['memory_ids'] != [mid] or restarted['candidate_promoted']:
        raise RuntimeError('restart_memory_mismatch')
    foreign=authority.issue('other-research-tenant',SCOPE.agent_id,permissions=('read',))
    try:
        gateway.retrieve(foreign,MemoryRequest(SCOPE,'verified_synthetic_research_outcome'))
    except PermissionError:
        isolation=True
    else:
        raise RuntimeError('cross_tenant_memory_leak')
    report={'status':'passed','memory_id':mid,'pending_records_returned':pending,
            'fresh_process_readback':restarted,'cross_tenant_denied':isolation,
            'new_plant_episodes':0,'candidate_promoted':False,'model_weights_trained':False,
            'host_authentication':'local research capabilities; not network authentication'}
    (root/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',required=True)
    parser.add_argument('--study');parser.add_argument('--claims');parser.add_argument('--supervisor')
    parser.add_argument('--verify-existing',action='store_true')
    args=parser.parse_args()
    if args.verify_existing:
        print(json.dumps(readback(Path(args.directory))))
    else:
        if not all((args.study,args.claims,args.supervisor)):
            parser.error('--study, --claims and --supervisor are required for ingestion')
        print(run(Path(args.directory),args.study,args.claims,args.supervisor)['status'])
