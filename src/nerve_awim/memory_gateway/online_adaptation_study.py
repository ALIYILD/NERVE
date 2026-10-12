"""Fixed prospective test-then-train study, public synthetic data, no promotion."""
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import random
import re
import sqlite3
import tempfile
from time import perf_counter

from ..agent_bridge_v13 import DemoAgentBridge
from ..memory_v18 import MemoryAuthority, TrustedMemoryLedger
from ..study_statistics_v16 import summarize_pairs
from .automation import AutomaticLearningRun
from .contracts import MemoryScope
from .gateway import MemoryGateway
from .learning import VerifiedOutcomeLearning
from .policy_research_loop import _claim
from .self_study import _digest, _snapshot

SEEDS = tuple(range(7001, 7017))
SCENARIOS = ('stationary', 'abrupt', 'recurrent', 'mixed')
ARMS = ('baseline', 'candidate', 'fixed_lower', 'fixed_trim')
EPISODES = 32
MAX_EXECUTIONS = 8192


def _cases(seed, scenario):
    if type(seed) is not int or scenario not in SCENARIOS:
        raise ValueError('invalid fixture identity')
    rng = random.Random(seed)
    base = bool(rng.randrange(2))
    change = rng.randint(8, 20)
    period, offset = rng.randint(3, 8), rng.randrange(8)
    offset %= period
    result = []
    for index in range(EPISODES):
        trim = (base if scenario == 'stationary' else
                (base if index < change else not base) if scenario == 'abrupt' else
                (base if ((index + offset) // period) % 2 == 0 else not base)
                if scenario == 'recurrent' else (base if rng.randrange(4) != 0 else not base))
        opaque = _digest(['online-adaptation-v4', seed, scenario, index])[:24].upper()
        result.append(({'document': json.dumps({'email': f'  {opaque}@EXAMPLE.TEST  '})}, trim))
    return tuple(result)


def protocol_manifest():
    root = Path(__file__).parent
    names = ('online_adaptation_study.py', 'policy_research_loop.py', 'self_study.py',
             'learning.py', 'automation.py', 'gateway.py', 'policy.py', 'contracts.py',
             'session.py', 'lifecycle.py', '../adaptive_memory.py', '../agent_bridge_v13.py',
             '../memory_v18.py', '../memory_retrieval_v18.py', '../study_statistics_v16.py')
    protocol = {'version': 'online-adaptation-v4', 'seeds': list(SEEDS),
        'scenarios': list(SCENARIOS), 'arms': list(ARMS), 'episodes_per_trial': EPISODES,
        'max_trial_calls': len(SEEDS)*len(SCENARIOS)*len(ARMS),
        'max_tool_executions': MAX_EXECUTIONS,
        'execution_unit': 'two-stage pipeline episode',
        'pipeline_episodes': MAX_EXECUTIONS, 'primitive_tool_invocations': 2*MAX_EXECUTIONS,
        'tool_executions_field': 'compatibility alias for pipeline_episodes',
        'baseline': {'window': 3, 'tie_break': 'relevance', 'discount_half_life': None},
        'candidate': {'window': 3, 'tie_break': 'relevance', 'discount_half_life': 1},
        'seeded_regimes': {'base': 'uniform boolean', 'abrupt_change_point': [8, 20],
            'recurrent_period': [3, 8], 'recurrent_offset': 'randrange(8) modulo period',
            'mixed_base_probability': .75},
        'evaluation': 'score each actual execution before its feedback; only selected memory learns',
        'selection': 'none; one fixed hypothesis, no tuning',
        'recommendation_gate': 'positive total gain and no scenario loss; review only',
        'dataset_sha256': _digest([(seed, scenario, _cases(seed, scenario))
            for seed in SEEDS for scenario in SCENARIOS]),
        'source_sha256': {name: sha256((root/name).read_bytes()).hexdigest() for name in names},
        'public_synthetic_nonsealed': True, 'evaluator_revision': 'online-adaptation-v4',
        'fixture_memory_ids': 'matched IDs and equal created_at=1',
        'promotion_authorized': False}
    return {**protocol, 'protocol_sha256': _digest(protocol)}


def _trial(seed, scenario, arm):
    if arm not in ARMS:
        raise ValueError('unknown fixed study arm')
    cases = _cases(seed, scenario)
    fixed = {'fixed_lower': 'lower-only', 'fixed_trim': 'trim-lower'}.get(arm)
    with tempfile.TemporaryDirectory(prefix='nerve-online-study-') as directory:
        root = Path(directory)
        authority = MemoryAuthority()
        host = authority.issue('synthetic', 'agent', permissions=('read', 'propose', 'approve'))
        reader = authority.issue('synthetic', 'agent', permissions=('read',))
        scope = MemoryScope('synthetic', 'agent', 'online-study')
        gateway = MemoryGateway(TrustedMemoryLedger(root/'memory.sqlite', authority))
        for strategy in ('lower-only', 'trim-lower'):
            mid = gateway.propose(host, scope=scope, source_id='host-fixture', content=json.dumps({
                'schema': 'nerve-demo-strategy-v1', 'task': 'email-normalization',
                'extract': 'json-field', 'normalise': strategy}))
            stable = 'fixture-z-lower' if strategy == 'lower-only' else 'fixture-a-trim'
            with sqlite3.connect(gateway.ledger.path) as con:
                con.execute('UPDATE trusted_memory_v18 SET memory_id=?,created_at=1 WHERE memory_id=?',
                            (stable, mid))
            gateway.decide(host, stable, scope=scope, approve=True, evaluator_id='host-review')
        answers = {_digest(task): json.loads(task['document'])['email'].strip().lower()
                   if trim else json.loads(task['document'])['email'].lower() for task, trim in cases}
        def judge(record, task, output):
            if _digest(task) not in answers:
                raise ValueError('unknown host fixture')
            return output == answers[_digest(task)]
        learning = VerifiedOutcomeLearning(gateway, host, scope, judge, 'online-adaptation-v4',
            window=3, tie_break='relevance', discount_half_life=1 if arm == 'candidate' else None)
        session = replace(learning.session(reader), can_propose=False)
        bridge = DemoAgentBridge(root/'agent.sqlite', memory_session=session, require_verified_memory=True)
        runner = AutomaticLearningRun(learning, reader, root/'agent.sqlite', 'online-study',
            max_episodes=EPISODES, max_failures=EPISODES)
        outcomes, strategies, durations, writes = [], [], [], []
        for index, (task, _) in enumerate(cases):
            before = _snapshot(gateway.ledger.path)['count']
            if before != (0 if fixed else index):
                raise AssertionError('future or duplicate feedback detected')
            started = perf_counter()
            if fixed:
                result = bridge.execute_plan(task_id=f'case-{index}', email_document=task['document'],
                    extract_strategy='json-field', normalise_strategy=fixed)
                success, strategy = judge(None, task, result['result']), fixed
            else:
                result = runner.execute(f'case-{index}', task)
                if result['status'] != 'judged':
                    raise RuntimeError('online execution was not independently judged')
                success, strategy = result['success'], result['strategies']['normalise']
            durations.append((perf_counter()-started)*1000)
            after = _snapshot(gateway.ledger.path)['count']
            if after-before != (0 if fixed else 1):
                raise AssertionError('unexpected outcome feedback writes')
            outcomes.append(success)
            strategies.append(strategy)
            writes.append(after-before)
        return {'seed': seed, 'scenario': scenario, 'arm': arm, 'outcomes': outcomes,
            'strategies': strategies, 'hits': sum(outcomes), 'executions': len(outcomes),
            'feedback_writes': sum(writes), 'episode_feedback_writes': writes,
            'wall_ms': sum(durations), 'payload_sha256': [_digest(task) for task, _ in cases]}


def _validate(row, seed, scenario, arm):
    if not isinstance(row, dict) or any(row.get(k) != v for k, v in
            (('seed', seed), ('scenario', scenario), ('arm', arm))):
        raise ValueError('incorrect trial identity')
    outcomes = row.get('outcomes')
    if not isinstance(outcomes, list) or len(outcomes) != EPISODES or any(type(v) is not bool for v in outcomes):
        raise ValueError('invalid prequential outcomes')
    expected = 0 if arm.startswith('fixed_') else 1
    for key, value in (('hits', sum(outcomes)), ('executions', EPISODES), ('feedback_writes', expected*EPISODES)):
        if type(row.get(key)) is not int or row[key] != value:
            raise ValueError('incorrect execution or feedback budget')
    writes = row.get('episode_feedback_writes')
    if not isinstance(writes, list) or len(writes) != EPISODES or any(type(v) is not int or v != expected for v in writes):
        raise ValueError('invalid per-episode feedback')
    if row.get('payload_sha256') != [_digest(task) for task, _ in _cases(seed, scenario)]:
        raise ValueError('unmatched task payloads')
    if len(json.dumps(row, allow_nan=False)) > 32768:
        raise ValueError('oversized evidence')
    return row


def run_online_adaptation_study(path, run_id):
    return _run(path, run_id, _trial)


def _run(path, run_id, evaluator):
    if not isinstance(run_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', run_id):
        raise ValueError('invalid run identifier')
    manifest = protocol_manifest()
    _claim(path, run_id, manifest)
    calls, rows = 0, {arm: [] for arm in ARMS}
    try:
        for seed in SEEDS:
            for scenario in SCENARIOS:
                for arm in ARMS:
                    if calls*EPISODES >= MAX_EXECUTIONS:
                        raise RuntimeError('study execution budget exhausted')
                    calls += 1
                    row = _validate(evaluator(seed, scenario, arm), seed, scenario, arm)
                    rows[arm].append(row)
        totals = {arm: {scenario: sum(r['hits'] for r in data if r['scenario'] == scenario)
                        for scenario in SCENARIOS} for arm, data in rows.items()}
        deltas = {s: totals['candidate'][s]-totals['baseline'][s] for s in SCENARIOS}
        pairs = []
        for candidate, baseline in zip(rows['candidate'], rows['baseline']):
            for index, (a, b) in enumerate(zip(candidate['outcomes'], baseline['outcomes'])):
                pairs.append({'seed': candidate['seed'], 'format': 'json_email',
                    'task_id': f"{candidate['seed']}-{candidate['scenario']}-{index}",
                    'with_memory': a, 'no_memory': b, 'with_memory_error': False, 'no_memory_error': False})
        report = {'run_id': run_id, 'protocol': manifest, 'rows': rows, 'scenario_hits': totals,
            'arm_hits': {arm: sum(values.values()) for arm, values in totals.items()},
            'tasks_per_arm': len(SEEDS)*len(SCENARIOS)*EPISODES,
            'scenario_tasks_per_arm': len(SEEDS)*EPISODES, 'scenario_deltas': deltas,
            'paired_statistics': summarize_pairs(pairs),
            'statistics_arm_mapping': {'no_memory': 'existing adaptive baseline', 'with_memory': 'fixed discount candidate'},
            'recommendation': 'candidate_for_review' if sum(deltas.values()) > 0 and min(deltas.values()) >= 0 else 'retain_baseline',
            'trial_calls': calls, 'tool_executions': calls*EPISODES,
            'execution_unit': 'two-stage pipeline episode',
            'pipeline_episodes': calls*EPISODES, 'primitive_tool_invocations': 2*calls*EPISODES,
            'tool_executions_field': 'compatibility alias for pipeline_episodes',
            'promotion_authorized': False, 'deployed': False, 'model_weights_trained': False,
            'scope': 'Public synthetic prospective test-then-train; no sealed holdout, weight training or scientific discovery.',
            'replay_protection': 'operator-owned SQLite; not independent test custody', 'cost_usd': None}
        with sqlite3.connect(path) as con:
            con.execute('UPDATE policy_research_runs_v2 SET status=?,report=? WHERE run_id=?',
                        ('complete', json.dumps(report, allow_nan=False), run_id))
        return report
    except BaseException:
        with sqlite3.connect(path) as con:
            con.execute('UPDATE policy_research_runs_v2 SET status=?,report=? WHERE run_id=?',
                        ('failed_consumed', json.dumps({'trial_calls': calls, 'error': 'evaluation_aborted'}), run_id))
        raise
