"""Preregistered public synthetic study of NERVE's existing memory window.

No model training, sealed test set, deployment, or general-science claim. Every
arm executes the same allowlisted tools 25 times; only adaptive prefixes learn.
"""
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import random
import sqlite3
import tempfile
from time import perf_counter

from ..agent_bridge_v13 import DemoAgentBridge
from ..memory_v18 import MemoryAuthority, TrustedMemoryLedger
from .automation import AutomaticLearningRun
from .contracts import MemoryScope
from .gateway import MemoryGateway
from .learning import VerifiedOutcomeLearning

WINDOWS = (3, 10, 20)
BASELINE_WINDOW = 3
TIE_BREAKS = ('relevance', 'least_recent')
CANDIDATES = tuple((w, t) for w in WINDOWS for t in TIE_BREAKS)
BASELINE_KEY = '3:relevance'
SPLITS = (('train', (101, 102)), ('validation', (201, 202)),
          ('holdout', (301, 302, 303, 304, 305)))
SCENARIOS = ('stationary', 'abrupt', 'recurrent', 'mixed')
FEEDBACK_COUNT = 20
PROBE_COUNT = 5


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                             allow_nan=False).encode()).hexdigest()


def _cases(seed, scenario):
    if type(seed) is not int or seed not in {s for _, seeds in SPLITS for s in seeds}:
        raise ValueError('preregistered seed required')
    if scenario not in SCENARIOS:
        raise ValueError('preregistered scenario required')
    rng = random.Random(seed)
    # Seed varies task regimes, not merely synthetic identifiers. Ranges are
    # frozen before heldout execution; no outcomes influence generation.
    base = bool(rng.randrange(2))
    change_point = rng.randint(8, 14)
    period, offset = rng.randint(3, 6), rng.randrange(6)
    offset %= period
    cases = []
    for index in range(FEEDBACK_COUNT + PROBE_COUNT):
        trim = (base if scenario == 'stationary' else
                (base if index < change_point else not base) if scenario == 'abrupt' else
                (base if ((index + offset) // period) % 2 == 0 else not base)
                if scenario == 'recurrent' else (base if rng.randrange(4) != 0 else not base))
        opaque_id = _digest([seed, scenario, index])[:24].upper()
        document = json.dumps({'email': f'  {opaque_id}@EXAMPLE.TEST  '})
        # Truth belongs to this host fixture, never the bridge input.
        cases.append(({'document': document}, trim))
    return tuple(cases)


def protocol_manifest():
    splits = {}
    for split, seeds in SPLITS:
        splits[split] = {'seeds': list(seeds), 'payload_sha256': [
            _digest(task) for seed in seeds for scenario in SCENARIOS
            for task, _ in _cases(seed, scenario)]}
    protocol = {'version': 1, 'windows': list(WINDOWS), 'tie_breaks': list(TIE_BREAKS), 'baseline_window': BASELINE_WINDOW,
        'scenarios': list(SCENARIOS),
        'seeded_regimes': {'base': 'uniform boolean', 'abrupt_change_point': [8, 14],
            'recurrent_period': [3, 6], 'recurrent_offset': 'randrange(6) modulo period',
            'mixed_base_probability': 0.75},
        'feedback_executions': FEEDBACK_COUNT,
        'frozen_probe_executions': PROBE_COUNT, 'splits': splits,
        'selection': 'validation probe hits; ties retain 3/relevance then smallest window and preregistered tie-break order',
        'dataset_sha256': _digest([(seed, scenario, _cases(seed, scenario))
            for _, seeds in SPLITS for seed in seeds for scenario in SCENARIOS]),
        'fixture_memory_ids': 'deterministic temporary SQLite IDs and equal created_at=1 ensure matched lexical ties',
        'public_synthetic_nonsealed': True, 'evaluator_revision': 'self-study-transform-v1'}
    return {**protocol, 'protocol_sha256': _digest(protocol)}


def _snapshot(path):
    with sqlite3.connect(path) as con:
        rows = con.execute('SELECT * FROM memory_utility ORDER BY sequence').fetchall()
    return {'count': len(rows), 'sha256': _digest(rows)}


def _trial(seed, scenario, window=None, fixed=None, tie_break='relevance'):
    if tie_break not in TIE_BREAKS:
        raise ValueError('preregistered tie-break required')
    invalid = ((window not in WINDOWS or type(window) is not int) if fixed is None else
               (window is not None or fixed not in ('lower-only', 'trim-lower')))
    if invalid:
        raise ValueError('one preregistered adaptive window or fixed strategy required')
    cases = _cases(seed, scenario)
    with tempfile.TemporaryDirectory(prefix='nerve-self-study-') as directory:
        root = Path(directory)
        authority = MemoryAuthority()
        host = authority.issue('synthetic', 'agent', permissions=('read', 'propose', 'approve'))
        reader = authority.issue('synthetic', 'agent', permissions=('read',))
        scope = MemoryScope('synthetic', 'agent', 'self-study')
        gateway = MemoryGateway(TrustedMemoryLedger(root/'memory.sqlite', authority))
        for strategy in ('lower-only', 'trim-lower'):
            mid = gateway.propose(host, scope=scope, source_id='host-fixture', content=json.dumps({
                'schema': 'nerve-demo-strategy-v1', 'task': 'email-normalization',
                'extract': 'json-field', 'normalise': strategy}))
            # Synthetic fixture setup only: equal lexical scores otherwise tie on
            # random UUIDs, confounding paired policies and reproducibility.
            stable_id = 'fixture-z-lower' if strategy == 'lower-only' else 'fixture-a-trim'
            with sqlite3.connect(gateway.ledger.path) as con:
                con.execute('UPDATE trusted_memory_v18 SET memory_id=?,created_at=1 WHERE memory_id=?',
                            (stable_id, mid))
            gateway.decide(host, stable_id, scope=scope, approve=True, evaluator_id='host-review')
        answers = {_digest(task): json.loads(task['document'])['email'].strip().lower()
                   if trim else json.loads(task['document'])['email'].lower()
                   for task, trim in cases}
        def judge(record, task, output):
            digest = _digest(task)
            if digest not in answers:
                raise ValueError('unknown host fixture')
            return output == answers[digest]
        learning = VerifiedOutcomeLearning(gateway, host, scope, judge,
            'self-study-transform-v1', window=window or BASELINE_WINDOW, tie_break=tie_break)
        session = replace(learning.session(reader), can_propose=False)
        bridge = DemoAgentBridge(root/'agent.sqlite', memory_session=session,
                                 require_verified_memory=True)
        runner = AutomaticLearningRun(learning, reader, root/'agent.sqlite', 'study',
                                      max_episodes=FEEDBACK_COUNT, max_failures=FEEDBACK_COUNT)
        outcomes, strategies, durations = [], [], []
        before = None
        for index, (task, _) in enumerate(cases):
            if index == FEEDBACK_COUNT:
                before = _snapshot(gateway.ledger.path)
            started = perf_counter()
            if fixed is not None:
                result = bridge.execute_plan(task_id=f'case-{index}', email_document=task['document'],
                    extract_strategy='json-field', normalise_strategy=fixed)
                success, strategy = judge(None, task, result['result']), fixed
            elif index < FEEDBACK_COUNT:
                result = runner.execute(f'case-{index}', task)
                if result['status'] != 'judged':
                    raise RuntimeError('synthetic feedback trial did not complete')
                success, strategy = result['success'], result['strategies']['normalise']
            else:
                result = bridge.run_pipeline(task_id=f'case-{index}', email_document=task['document'])
                success = judge(None, task, result['result'])
                strategy = result['strategies']['normalise']
            durations.append((perf_counter() - started) * 1000)
            outcomes.append(success)
            strategies.append(strategy)
        after = _snapshot(gateway.ledger.path)
        if before != after:
            raise AssertionError('frozen probes modified outcome memory')
        if after['count'] != (FEEDBACK_COUNT if fixed is None else 0):
            raise AssertionError('unequal or unexpected feedback consumption')
        return {'seed': seed, 'scenario': scenario, 'window': window, 'tie_break': tie_break, 'fixed_strategy': fixed,
            'feedback_outcomes': outcomes[:FEEDBACK_COUNT], 'probe_outcomes': outcomes[FEEDBACK_COUNT:],
            'feedback_strategies': strategies[:FEEDBACK_COUNT], 'probe_strategies': strategies[FEEDBACK_COUNT:],
            'probe_hits': sum(outcomes[FEEDBACK_COUNT:]), 'executions': len(outcomes),
            'feedback_executions': FEEDBACK_COUNT, 'probe_executions': PROBE_COUNT,
            'feedback_writes': after['count'], 'probe_feedback_writes': 0,
            'frozen_probe_state_unchanged': before == after,
            'strategy_switches': sum(a != b for a, b in zip(strategies, strategies[1:])),
            'feedback_wall_ms': sum(durations[:FEEDBACK_COUNT]),
            'probe_wall_ms': sum(durations[FEEDBACK_COUNT:]),
            'payload_sha256': [_digest(task) for task, _ in cases]}


def _select(validation):
    totals = {f'{window}:{tie}': sum(row['probe_hits'] for row in validation[f'{window}:{tie}'])
              for window, tie in CANDIDATES}
    selected = min(CANDIDATES, key=lambda item: (-totals[f'{item[0]}:{item[1]}'],
                   item != (BASELINE_WINDOW, 'relevance'), item[0], TIE_BREAKS.index(item[1])))
    return selected, totals


def run_self_study():
    """Run one fixed study, with no caller tuning parameters or holdout feedback."""
    manifest = protocol_manifest()
    candidate_results = {}
    for split, seeds in SPLITS[:2]:
        candidate_results[split] = {f'{window}:{tie}': [_trial(seed, scenario, window=window, tie_break=tie)
            for seed in seeds for scenario in SCENARIOS] for window, tie in CANDIDATES}
    selected, totals = _select(candidate_results['validation'])
    # Selection is frozen BEFORE any holdout arm is instantiated/executed.
    selection_hash = _digest({'protocol': manifest['protocol_sha256'], 'window': selected,
                              'validation_hits': totals})
    holdout = {}
    for name, window, fixed in (('selected', selected[0], None), ('baseline', BASELINE_WINDOW, None),
                               ('fixed_lower', None, 'lower-only'), ('fixed_trim', None, 'trim-lower')):
        holdout[name] = [_trial(seed, scenario, window=window, fixed=fixed,
                        tie_break=selected[1] if name == 'selected' else 'relevance')
                        for seed in SPLITS[2][1] for scenario in SCENARIOS]
    paired = {}
    chosen = [hit for row in holdout['selected'] for hit in row['probe_outcomes']]
    for name in ('baseline', 'fixed_lower', 'fixed_trim'):
        control = [hit for row in holdout[name] for hit in row['probe_outcomes']]
        paired[name] = {'wins': sum(a and not b for a, b in zip(chosen, control)),
                        'losses': sum(b and not a for a, b in zip(chosen, control)),
                        'tasks': len(chosen)}
    paired_rows = []
    scenario_deltas = {scenario: 0 for scenario in SCENARIOS}
    for candidate, baseline in zip(holdout['selected'], holdout['baseline']):
        for index, (a, b) in enumerate(zip(candidate['probe_outcomes'], baseline['probe_outcomes'])):
            paired_rows.append({'seed': candidate['seed'], 'scenario': candidate['scenario'],
                'task_id': f"{candidate['seed']}-{candidate['scenario']}-{index}",
                'candidate_success': a, 'baseline_success': b,
                'candidate_error': False, 'baseline_error': False})
            scenario_deltas[candidate['scenario']] += int(a)-int(b)
    recommend = (selected != (BASELINE_WINDOW, 'relevance')
                 and sum(scenario_deltas.values()) > 0 and min(scenario_deltas.values()) >= 0)
    return {'paired_rows': paired_rows, 'scenario_deltas': scenario_deltas,
        'recommendation': 'candidate_for_review' if recommend else 'retain_baseline',
        'protocol': manifest, 'candidate_results': candidate_results,
        'selected_window': selected[0], 'selected_tie_break': selected[1], 'baseline_window': BASELINE_WINDOW,
        'validation_probe_hits': totals, 'selection_sha256': selection_hash,
        'selection_frozen_before_holdout': True, 'holdout': holdout, 'paired': paired,
        'holdout_probe_feedback_written': False, 'promotion_authorized': False,
        'deployed': False, 'model_weights_trained': False, 'cost_usd': None,
        'scope': 'Public synthetic deterministic fixture; CPU wall time, not model latency or scientific discovery.',
        'holdout_protocol': 'Disjoint heldout episodes include a fixed online feedback prefix; final five probes never teach the policy.'}
