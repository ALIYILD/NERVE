#!/usr/bin/env python3
"""Bound registered historical preflight to an explicitly inventoried pod."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import execute_v5_identity_replay as original
from run_v5_identity_replay import digest,write
BASE=Path('/Users/aliyildirim/nerve-research-runs/overnight-identity-20261017')
def main():
    original.BASE=BASE
    original.SSH=['ssh','-p','22188','-i','/Users/aliyildirim/.ssh/id_ed25519','-o','BatchMode=yes','-o','ConnectTimeout=15','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=3','root@194.68.245.37','python3','/workspace/v5_remote_call.py']
    if sys.argv[1]=='register':
        write(BASE/'pod-amendment.json',{'registration_sha256':digest(BASE/'registration.json'),'pod_id':'5xndo7i7s5r9zn','connection':{'host':'194.68.245.37','port':22188},'reason':'live MCP connection binding before calls','execution_sources':{'scripts/overnight_identity_replay.py':digest(Path(__file__)),'scripts/execute_v5_identity_replay.py':digest(Path(original.__file__))}})
    elif sys.argv[1]=='run':
        state=Path('/Users/aliyildirim/nerve-orchestration')
        for name in ['pod-A.lock','pod-B.lock']:
            lock=json.loads((state/name).read_text());assert lock['window']=='W0' and lock['pod_id']=='5xndo7i7s5r9zn'
        if (state/'inference-revoked.json').exists():raise RuntimeError('inference revoked')
        original.run()
    else:raise ValueError('register or run')
if __name__=='__main__': main()
