"""Independent offline check of every preflight response against registered dev records."""
import sys,json,socket
from pathlib import Path
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import run_scientific_family_b_v4_sweden as old
from run_v5_identity_replay import digest,write
def forbidden(*a,**kw):raise RuntimeError('offline_replay_network_forbidden')
socket.socket=forbidden
base=Path('/Users/aliyildirim/nerve-research-runs/v5-identity-replay-20261016')
reg=json.loads((base/'registration.json').read_text())
amend=json.loads((base/'pod-amendment.json').read_text())
assert digest(base/'registration.json')==amend['registration_sha256']
for name,h in {**reg['sources'],**amend['execution_sources']}.items():assert digest(ROOT/name)==h
assert digest(base/'private-requests.json')==reg['private_requests_sha256']
requests=json.loads((base/'private-requests.json').read_text())
dev_matches=0;latencies=[]
for i,x in enumerate(requests):
    raw='ABSTAIN'
    if x['entry']['payload'] is not None:
        body=old.canonical(x['entry']['payload'])
        paths=sorted(base.glob(f'attempt-{i:02}-*.json'));assert paths
        for p in paths:
            claim=json.loads((base/p.name.replace('attempt-','claim-')).read_text())
            assert claim['body_sha256']==sha256(body.encode()).hexdigest()
            attempt=json.loads(p.read_text())
        assert attempt['status']=='ok'
        raw=old.transport.decode(attempt['wire'])[0]
        if x['kind']=='calibration':latencies.append(attempt['elapsed_seconds'])
    decoded=old.adapter.decode(raw,x['prepared'])
    row=json.loads((base/f'replay-{i:02}.json').read_text())
    assert old.canonical(decoded)==old.canonical(row['decoded'])
    match=old.canonical(decoded)==old.canonical(x['expected_decoded'])
    assert row['match']==match
    if x['kind']=='dev':assert match;dev_matches+=1
assert dev_matches==10 and len(latencies)==5
assert all(reg['latency_band_seconds'][0]<=v<=reg['latency_band_seconds'][1] for v in latencies)
report=json.loads((base/'report.json').read_text())
assert report['status']=='passed' and report['dev_matches']==dev_matches and report['calibration_latencies_seconds']==latencies
receipt=dict(verified=True,dev_records_byte_identical=10,calibration_calls_verified=5,new_model_calls=0,
    network_disabled=True,registration_sha256=digest(base/'registration.json'),report_sha256=digest(base/'report.json'),
    replay_source_sha256=digest(Path(__file__)))
write(base/'offline-replay.json',receipt);print(json.dumps(receipt))
