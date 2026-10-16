"""Prospectively registered m14 harmful-rate verification; no L2 grid rerun."""
import gzip
import json
import math
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np
from scipy.stats import beta
import simulate_gate_v3_2_grid as sim

OUT = sim.ROOT / 'docs/galahad/evidence/gate-v3_2-harmful-bound'
PROFILES = ('narrow_64', 'measured', 'broad_75')
N = 100000
SEED = 2026102501
M = 14


def upper(k, n):
    return 1.0 if k == n else float(beta.ppf(.95, k + 1, n - k))


def register():
    OUT.mkdir(exist_ok=False)
    paths = [Path(__file__), sim.Path(sim.__file__), sim.ROOT / 'src/nerve_awim/memory_gateway/scientific_promotion_gate_v3_2.py', sim.ROOT / 'docs/galahad/129-gate-v3_2-coverage-grid.md', sim.OUT / 'registration.json', sim.OUT / 'result.json']
    reg = {
        'schema': 'gate-v3.2-harmful-bound-registration.v1',
        'registered_at': datetime.now(timezone.utc).isoformat(),
        'parent_commit': 'b97aabf', 'parent_grid_rerun': False,
        'reformulation_after_doc': 129,
        'reason': 'Zero observed accepts is not proof of zero risk: zero of 10000 has a one-sided95% exact upper bound about0.03%. User prospectively replaces the failed zero-count target with a bounded rate for new validation.',
        'zero_of_10000_upper': upper(0, 10000),
        'm': M, 'streams_per_profile': N, 'fresh_seed': SEED,
        'profiles_in_order': list(PROFILES), 'scenario': 'harmful',
        'conditional_win_p': .35, 'scope_floor': .08,
        'acceptance': {'maximum_one_sided_95_upper': .0005, 'method': 'Clopper-Pearson beta.ppf(0.95,k+1,n-k); k=n gives1', 'all_profiles_must_pass': True, 'marginal_per_profile_not_simultaneous': True},
        'unchanged_rules': sim.read(sim.OUT / 'registration.json')['sampling'],
        'scope': sim.read(sim.OUT / 'registration.json')['scope'],
        'sources': {str(p.relative_to(sim.ROOT)): sim.h(p) for p in paths},
        'randomness': 'Same fresh seed across profiles; common random numbers, do not pool as independent replications. Fixed100000 denominator per profile; no optional stopping or retuning.',
        'replay': 'First three fresh harmful promotions in registered profile order then ascending stream index, through public scalar Process; retain full reports and item-level phase transitions. If fewer than three exist, report shortfall without changing seed.',
        'model_calls': 0, 'reserve_items_consumed': 0, 'pod_operations': 0,
    }
    sim.write(OUT / 'registration.json', reg)
    print('registered', sim.h(OUT / 'registration.json'), flush=True)


def check_sources(reg):
    for path, digest in reg['sources'].items():
        assert sim.h(sim.ROOT / path) == digest, path


def replay(reg, results):
    chosen = []
    for profile in PROFILES:
        row = results[profile]
        path = sim.ROOT / row['receipt']['path']
        assert sim.h(path) == row['receipt']['sha256']
        raw = gzip.decompress(path.read_bytes())
        assert sim.sha256(raw).hexdigest() == row['receipt']['raw_sha256']
        records = json.loads(raw)
        assert len(records) == N and sum(x['promoted'] for x in records) == row['accepted']
        for record in records:
            if record['promoted'] and len(chosen) < 3:
                chosen.append((profile, record))
    audits = []
    for profile in PROFILES:
        targets = [record for name, record in chosen if name == profile]
        if not targets:
            continue
        rates, probs, _ = sim.fixture(profile, 'harmful')
        processes = {r['stream']: sim.gate.Process(m=M, risk_stratum='dissenter', planned_discordant_p=.85, order_offset=r['stream'] % 9, declared_primary_discordance=reg['scope']['fixture_primary_discordance'][profile], scope_profile=profile, scope_evidence_sha256=sim.h(OUT / 'registration.json')) for r in targets}
        traces = {i: [] for i in processes}
        rng = np.random.default_rng(SEED)
        for step in range(max(sum(r['counts']) for r in targets)):
            u = rng.random((N, 4))
            for i, process in processes.items():
                if process.phase in ('risk', 'done'):
                    continue
                stratum = process.next_stratum(); j = sim.gate.STRATA.index(stratum)
                if stratum in sim.gate.SAFETY:
                    c = b = True
                else:
                    d = u[i, 0] < rates[i, j]; win = u[i, 1] < probs[i, j]; both = u[i, 2] < .88
                    c = bool(win if d else both); b = bool(not win if d else both)
                before = process.phase
                process.update(item_id=str(process.items), stratum=stratum, candidate=c, incumbent=b, abstain=stratum in sim.gate.SAFETY)
                traces[i].append({'item': process.items, 'phase_before': before, 'phase_after': process.phase, 'stratum': stratum, 'candidate': c, 'incumbent': b, 'log_e': process.log_e, 'verdict': process.verdict})
        for record in targets:
            i = record['stream']; process = processes[i]
            while process.next_stratum() is not None:
                assert process.phase == 'risk'
                stratum = process.next_stratum()
                process.update(item_id=str(process.items), stratum=stratum, candidate=True, incumbent=True, abstain=True)
                traces[i].append({'item': process.items, 'phase_before': 'risk', 'phase_after': process.phase, 'stratum': stratum, 'candidate': True, 'incumbent': True, 'log_e': process.log_e, 'verdict': process.verdict})
            assert process.verdict == 'promote_proposal' and process.items == record['items']
            assert [process.counts[s] for s in sim.gate.STRATA] == record['counts']
            assert [process.net[s] for s in sim.gate.STRATA] == record['net']
            assert [process.discordance[s] for s in sim.gate.STRATA] == record['discordance']
            audits.append({'profile': profile, 'stream': i, 'matched': True, 'route': process.reason, 'report': process.report(), 'counts': process.counts, 'coverage_routes': {s: 'm_discordances' if process.discordance[s] >= M else 'zero_in_first60_terminal_bound' for s in sim.gate.ANSWER}, 'trace': traces[i]})
    return audits


def run():
    reg = sim.read(OUT / 'registration.json'); check_sources(reg)
    assert reg['fresh_seed'] == SEED and reg['streams_per_profile'] == N and reg['m'] == M
    sim.N = N; sim.OUT = OUT
    results = {}
    for profile in PROFILES:
        rates, probs, bad = sim.fixture(profile, 'harmful')
        row = sim.simulate('fresh-m14-' + profile + '-harmful', rates, probs, bad, SEED, M)
        row['upper_95'] = upper(row['accepted'], N)
        row['bound_passed'] = row['upper_95'] <= .0005
        sim.write(OUT / (profile + '-result.json'), row)
        results[profile] = row
    audits = replay(reg, results)
    sim.write(OUT / 'three-harmful-promotion-replays.json', {'cases': audits, 'requested': 3, 'replayed': len(audits), 'model_calls': 0})
    check_sources(reg)
    result = {'registration_sha256': sim.h(OUT / 'registration.json'), 'results': results, 'all_bounds_passed': all(r['bound_passed'] for r in results.values()), 'replayed': len(audits), 'model_calls': 0, 'reserve_items_consumed': 0, 'payload_prepared': False}
    sim.write(OUT / 'result.json', result)
    print(json.dumps({k: {'count': v['accepted'], 'n': N, 'rate': v['accept_rate'], 'upper_95': v['upper_95']} for k, v in results.items()}), flush=True)


if __name__ == '__main__':
    def deny(*args, **kwargs):
        raise RuntimeError('CPU-only verification; network prohibited')
    with patch.object(socket.socket, 'connect', deny), patch.object(socket.socket, 'connect_ex', deny), patch.object(socket, 'create_connection', deny):
        if sys.argv[1] == 'register':
            register()
        elif sys.argv[1] == 'run':
            run()
        else:
            raise ValueError('register or run required')
