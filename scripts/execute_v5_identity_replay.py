"""CPU coordinator; calls Ollama only via SSH on the bound pod."""
import sys,json,subprocess
from pathlib import Path
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import run_scientific_family_b_v4_sweden as old
from run_v5_identity_replay import write,digest
BASE=Path('/Users/aliyildirim/nerve-research-runs/v5-identity-replay-20261016')
SSH=['ssh','-p','22011','-i','/Users/aliyildirim/.ssh/id_ed25519','-o','BatchMode=yes','-o','ConnectTimeout=15','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=3','root@194.68.245.37','python3','/workspace/v5_remote_call.py']

def remote(action,data=None):
    r=subprocess.run(SSH+[action],input=None if data is None else json.dumps(data),capture_output=True,text=True,timeout=600,check=True)
    return json.loads(r.stdout)

def run():
    reg=json.loads((BASE/'registration.json').read_text())
    amendment=json.loads((BASE/'pod-amendment.json').read_text())
    assert digest(BASE/'registration.json')==amendment['registration_sha256']
    assert digest(BASE/'private-requests.json')==reg['private_requests_sha256']
    for name,h in amendment['execution_sources'].items():assert digest(ROOT/name)==h
    identity=remote('identity');write(BASE/'identity.json',identity)
    assert identity['pod_id']==amendment['pod_id'] and identity['model_digest']==reg['model_digest']
    requests=json.loads((BASE/'private-requests.json').read_text());results=[];latencies=[];differences=[];failure=None
    for i,x in enumerate(requests):
        e=x['entry'];raw='ABSTAIN'
        if e['payload'] is not None:
            body=old.canonical(e['payload'])
            timeout=120 if x['kind']=='calibration' else 3*max(latencies)
            for retry in range(3):
                write(BASE/f'claim-{i:02}-{retry}.json',dict(body_sha256=sha256(body.encode()).hexdigest(),timeout=timeout))
                result=remote('call',dict(body=body,timeout=timeout))
                write(BASE/f'attempt-{i:02}-{retry}.json',result)
                if result['status']=='ok':break
            if result['status']!='ok':failure='timeout';break
            raw,usage,finish=old.transport.decode(result['wire'])
            if x['kind']=='calibration':latencies.append(result['elapsed_seconds'])
        try:decoded=old.adapter.decode(raw,x['prepared'])
        except Exception as exc:decoded={'decode_error':type(exc).__name__}
        match=old.canonical(decoded)==old.canonical(x['expected_decoded'])
        row=dict(index=i,kind=x['kind'],match=match,decoded=decoded,expected=x['expected_decoded'])
        write(BASE/f'replay-{i:02}.json',row);results.append(row)
        if x['kind']=='dev' and not match:
            differences.append(row);failure='decoded_record_mismatch';break
        print(json.dumps(dict(index=i,kind=x['kind'],match=match)),flush=True)
        if i==4 and (len(latencies)!=5 or not all(reg['latency_band_seconds'][0]<=v<=reg['latency_band_seconds'][1] for v in latencies)):
            failure='latency_outside_recorded_band';break
    report=dict(status='incomplete_infrastructure' if failure else 'passed',reason=failure,identity=identity,
        calibration_latencies_seconds=latencies,dev_items_compared=sum(r['kind']=='dev' for r in results),
        dev_matches=sum(r['kind']=='dev' and r['match'] for r in results),diff= differences,
        registration_sha256=digest(BASE/'registration.json'),amendment_sha256=digest(BASE/'pod-amendment.json'),
        model_calls=len(list(BASE.glob('attempt-*.json'))),holdout_items_consumed=0)
    write(BASE/'report.json',report);print(json.dumps(report),flush=True)
if __name__=='__main__':run()
