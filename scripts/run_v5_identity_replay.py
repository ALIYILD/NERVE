#!/usr/bin/env python3
"""Prepare historical dev-only preflight; never opens a holdout or calls a model."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
import json
from hashlib import sha256
from datetime import datetime, timezone
import run_scientific_family_b_v4_sweden as old

def digest(p): return sha256(p.read_bytes()).hexdigest()
def write(p, value):
    with p.open('x') as f: json.dump(value, f, sort_keys=True, indent=2); f.write('\n')
    p.chmod(0o600)

def prepare(destination):
    destination.mkdir(mode=0o700)
    historical = Path('/Users/aliyildirim/nerve-research-runs/sweden-20261016/final-extracted')
    bundle = []; bindings = {}
    for kind, directory in [('calibration','v4-calibration'),('dev','v4-dev')]:
        base = historical / directory
        reg = json.loads((base/'registration.json').read_text())
        assert reg['kind'] == kind
        assert digest(base/'private-input.json') == reg['input_sha256']
        for name in ['src/nerve_awim/memory_gateway/scientific_family_b_adapter.py',
                     'src/nerve_awim/memory_gateway/scientific_family_b_v4.py']:
            if name in reg['sources']: assert digest(ROOT/name) == reg['sources'][name]
        tasks = json.loads((base/'private-input.json').read_text())
        lookup = {t['task_id']:t for t in tasks}
        schedule = old.schedule(tasks,reg['arms'],reg['candidate_module'],kind)
        assert sha256(old.canonical(schedule).encode()).hexdigest() == reg['schedule_sha256']
        rows = json.loads((base/'private-report.json').read_text())['rows']
        assert [(r['task_id'],r['arm']) for r in rows] == [(r['task_id'],r['arm']) for r in schedule]
        chosen = [(e,r) for e,r in zip(schedule,rows) if kind == 'calibration' or e['arm']=='candidate'][:5 if kind=='calibration' else 10]
        for e,r in chosen:
            p = old.prepare(lookup[e['task_id']],e['arm'],reg['candidate_module'])
            decoded = old.adapter.decode(r['raw_output'],p)
            bundle.append(dict(kind=kind,entry=e,prepared=p,expected_decoded=decoded))
        bindings[kind] = {name:digest(base/name) for name in ['registration.json','private-input.json','private-report.json','aggregate.json']}
    write(destination/'private-requests.json',bundle)
    registration = dict(created_at=datetime.now(timezone.utc).isoformat(),
        purpose='five historical calibration calls then first ten candidate dev rows in registered shuffled order',
        historical_receipts=bindings, private_requests_sha256=digest(destination/'private-requests.json'),
        sources={str(p.relative_to(ROOT)):digest(p) for p in [Path(__file__),ROOT/'scripts/run_scientific_family_b_v4_sweden.py',ROOT/'scripts/run_scientific_runpod_gate.py',*sorted((ROOT/'src/nerve_awim/memory_gateway').glob('scientific*.py'))]},
        pod_id='lvojhtouu5gede', gpu='A40',runtime='0.40.5',model=old.transport.MODEL,model_digest=old.transport.DIGEST,
        latency_band_seconds=[1.5230746129527688,62.35253082308918],
        latency_rule='each of five call latencies inside inclusive historical observed band; zero timeouts',
        timeout_seconds=120, concurrency=1, retries=2,retry_on='timeout only, identical request, journaled',
        comparison='canonical JSON bytes of decoded records, all ten dev items; any mismatch incomplete_infrastructure',
        holdout_access=False, promotion_authorized=False)
    write(destination/'registration.json',registration)
    print(json.dumps(dict(registration_sha256=digest(destination/'registration.json'),calibration_items=5,dev_items=10,dev_model_calls=sum(x['entry']['payload'] is not None for x in bundle if x['kind']=='dev'))))

if __name__ == '__main__': prepare(Path(sys.argv[1]))
