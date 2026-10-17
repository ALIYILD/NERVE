"""Zero-inference staged workflow and deterministic 200-proposal simulation."""
from collections import Counter, defaultdict
from hashlib import sha256
import json
import math
from pathlib import Path
import random
import statistics
import tempfile

from .contracts import CAPACITY, digest, route, canonical
from .gate import Gate
from .evidence import ResponseCache, RepairPlanner, probe_status, review_readiness
from .evaluator import diagnose, verify_domain, score


def simulation_registration(index, *, seed=20261015, alpha=.00025, budget=100):
    cap = {k: 0 for k in CAPACITY}; cap['model_digest'] = 'synthetic-no-model'
    return dict(study_id=f'simulation-{index}', model=dict(identifier='synthetic', checkpoint_digest='no-model', quantisation='none', runtime='python'),
        prompts=['synthetic paired Bernoulli outcomes'], schemas=[{'type': 'boolean'}],
        sampling=dict(temperature=0, top_p=1, seeds=[seed], token_limit=1), transport=dict(timeout=1, retry_limit=0),
        bank=dict(manifest='synthetic-bank-v1', split='synthetic', fresh_items=True),
        exclusions=dict(malformed='fail', refused='fail', timeout='incomplete_infrastructure'),
        outcomes=dict(primary='paired strict correctness', secondary=['items consumed'], interpretation='simulation only'),
        mode='exploratory', pilot_history=dict(drafts=0, calibrations=0, dev_studies=0, findings='fixed synthetic design'),
        robustness=dict(variants=[], order_seeds=[seed], stateful=False), holdout_unread_attestation=True,
        candidate=f'candidate-{index}', incumbent='deployed-synthetic-incumbent', capacity=cap, incumbent_capacity=cap,
        prices={k: 0 for k in CAPACITY}, gate=dict(alpha=alpha, bet=.5, item_budget=budget, minimum_net_wins=3,
        futility_e=.05, strata=['synthetic'], order_seed=seed), rollback='retain_incumbent', tier='A')


def simulate(directory, *, seed=20261015):
    """Fixed design, no tuning to achieved acceptance/consumption targets."""
    rng = random.Random(seed)
    harmful = set(rng.sample(range(200), 40))
    # Independent fresh paired outcomes for each proposal; identical stream per comparator.
    streams = [[rng.random() < (.45 if i in harmful else .85) for _ in range(100)] for i in range(200)]
    gate = Gate(Path(directory)/'gate', key=sha256(b'public synthetic test key; not for real evidence').digest())
    seq_bad = naive_bad = seq_items = 0
    verdicts = Counter()
    for i, stream in enumerate(streams):
        r = simulation_registration(i, seed=seed)
        gate.start(r)
        # Naive repeated fixed-n testing at 20,40,...,100 without alpha correction.
        # This is an explicitly specified comparator, not a reconstruction of NERVE's slice gate.
        naive = any(sum(stream[:n]) - n/2 > 1.645 * math.sqrt(n/4) for n in range(20, 101, 20))
        naive_bad += int(i in harmful and naive)
        for j, win in enumerate(stream):
            if gate.report(r['study_id'])['verdict'] != 'running': break
            item = f'{i}:{j}'
            if gate.claim(r['study_id'], item, 'synthetic') == 'dispatch_once':
                gate.record(r['study_id'], item, candidate=win, incumbent=not win,
                    controls={'always_abstain': not win, 'random': not win}, violations=[], measured_capacity=r['capacity'])
        result = gate.report(r['study_id'])
        seq_items += result['items']; verdicts[result['verdict']] += 1
        seq_bad += int(i in harmful and result['verdict'] == 'exploratory_only')
    original = canonical([gate.report(f'simulation-{i}') for i in range(200)])
    gate.close()
    gate = Gate(Path(directory)/'gate', key=sha256(b'public synthetic test key; not for real evidence').digest())
    replay = canonical([gate.report(f'simulation-{i}') for i in range(200)])
    gate.close()
    return dict(kind='NERVE synthetic demonstration; not an exact Lewis replication', seed=seed, proposals=200,
        harmful_proposals=40, naive=dict(harmful_accepted=naive_bad, harmful_accept_rate=naive_bad/40, items=20000),
        sequential=dict(harmful_accepted=seq_bad, harmful_accept_rate=seq_bad/40, items=seq_items, verdicts=dict(verdicts)),
        target_met=seq_bad/40 < .01 and seq_items < 20000, byte_identical_restart=original == replay,
        model_calls=0, holdout_accessed=False, promotion_authorized=False,
        limitations=['No empirical result establishes a universal 1% bound.',
                      'Comparator uses repeated prefix looks; neither comparator adapts candidates to prior data.',
                      'Alpha spending controls error only when each test is conditionally valid.'])


def wilson(success, total):
    if not total: return None
    z = 1.959963984540054; p = success/total; d = 1 + z*z/total
    center = (p + z*z/(2*total))/d
    half = z*math.sqrt(p*(1-p)/total + z*z/(4*total*total))/d
    return [center-half, center+half]


def audit_v3(receipt_path, dev_path, output_directory):
    """Back-apply output checks to completed development evidence, never promote."""
    from ..memory_gateway import scientific_candidate_v3 as v3
    receipt_path, dev_path = Path(receipt_path), Path(dev_path)
    receipt = json.loads(receipt_path.read_text())
    if sha256(dev_path.read_bytes()).hexdigest() != receipt['protocol']['inputs']['development_sha256']:
        raise ValueError('registered_development_bytes_changed')
    repository = Path(__file__).resolve().parents[3]
    for name, expected in receipt['protocol']['sources'].items():
        source = (repository/name).resolve()
        if not source.is_relative_to(repository) or sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError('historical_evaluator_source_changed')
    tasks = json.loads(dev_path.read_text())
    if any(t.get('split') != 'dev' or not t['task_id'].startswith('dev-') for t in tasks):
        raise PermissionError('development_only')
    if receipt.get('status') != 'complete' or receipt.get('holdout_accessed') is not False:
        raise ValueError('completed_development_receipt_required')
    by_id = {t['task_id']: t for t in tasks}
    roster = {r['task_id']: r for r in receipt['protocol']['roster']}
    cache = ResponseCache(Path(output_directory)/'responses')
    histogram, violations, per_stratum = Counter(), Counter(), defaultdict(list)
    timings, tokens, calls = [], Counter(), 0
    rows = [r for r in receipt['rows'] if r['arm'] == 'candidate']
    if len({r['task_id'] for r in rows}) != len(roster): raise ValueError('complete_unique_candidate_rows_required')
    disagreements = 0
    for row in rows:
        task = by_id[row['task_id']]
        if task['content_sha256'] != row['task_content_sha256'] or roster[row['task_id']]['content_sha256'] != task['content_sha256']:
            raise ValueError('development_task_identity_changed')
        prepared = v3.prepare(task['query'], task['evidence'])
        try: output = v3.decode(row['raw_output'], prepared)
        except ValueError: output = None
        labels = diagnose(task, output)
        histogram.update(labels)
        violations.update(verify_domain(task, output, abstention_rule=prepared['gate_reason']))
        strict = score(task, output)
        disagreements += int(strict != row['score']['strict_correct'])
        per_stratum[row['stratum']].append(strict)
        calls += row['model_calls']; timings.append(row['elapsed_seconds']); tokens.update(row['usage'] or {})
        cache.put(dict(model_digest=receipt['protocol']['expected_digest'],
            prompt={'system': prepared['system'], 'user': prepared['user'], 'schema': prepared['schema']},
            params={'seed': row['model_sampling_seed'], 'temperature': 0, 'max_output_tokens': 128},
            replicate=row['task_id']), dict(raw_output=row['raw_output'], usage=row['usage'], route=row['route']))
    accuracy = {s: {'correct': sum(v), 'n': len(v), 'wilson95': wilson(sum(v), len(v))} for s,v in sorted(per_stratum.items())}
    planner = RepairPlanner(Path(output_directory)/'repairs.sqlite')
    try: repair = planner.propose('retrospective-v3:'+sha256(receipt_path.read_bytes()).hexdigest(), dict(histogram))
    finally: planner.db.close()
    return dict(status='development_audit_complete', confirmatory=False,
        receipt_sha256=sha256(receipt_path.read_bytes()).hexdigest(),
        development_sha256=sha256(dev_path.read_bytes()).hexdigest(),
        five_axes=dict(accuracy=accuracy, efficiency=dict(model_calls=calls, tokens=dict(tokens),
            median_latency=statistics.median(timings), max_latency=max(timings), capacity_delta='not registered in historical study'),
            robustness=dict(seed_order_variance='not measured', worst_stratum=min(sum(v)/len(v) for v in per_stratum.values())),
            safety=dict(domain_verifier_violations=dict(violations), abstention_precision='not separately registered'),
            ux='deferred: clinician edit distance and acceptance not measured'),
        failure_histogram=dict(histogram), next_repair=repair, scorer_disagreements=disagreements,
        cache_manifest=cache.manifest(), evidence_readiness=review_readiness('B', {}), white_box=probe_status(),
        new_model_calls=0, holdout_accessed=False, promotion_authorized=False,
        limitation='Retrospective development audit; no new efficacy or confirmatory claim.')
