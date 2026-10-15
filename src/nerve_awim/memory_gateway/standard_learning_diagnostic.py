"""Verified retrospective prediction decomposition, without plant execution."""
import gzip
from hashlib import sha256
import json
import math
from pathlib import Path

from . import standard_learning_demo as demo

MAX_COMPRESSED = 4*1024*1024
MAX_EXPANDED = 16*1024*1024
EXTRA_SOURCES = ('src/nerve_awim/memory_gateway/standard_learning_diagnostic.py',
                 'scripts/diagnose_standard_learning.py')


def _require(condition):
    if not condition: raise ValueError('invalid_standard_learning_diagnostic_evidence')


def _sources():
    pins = demo.sources()
    pins.update({name: sha256((demo.ROOT/name).read_bytes()).hexdigest() for name in EXTRA_SOURCES})
    return pins


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError('duplicate_json_key')
        result[key] = value
    return result


def _read(path):
    with Path(path).open('rb') as stream: raw = stream.read(MAX_COMPRESSED+1)
    _require(len(raw) <= MAX_COMPRESSED)
    import io
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream: expanded = stream.read(MAX_EXPANDED+1)
    _require(len(expanded) <= MAX_EXPANDED)
    return raw, json.loads(expanded, object_pairs_hook=_unique)


def validate(report):
    """Full recorded physical and learning checks; never execute a child."""
    expected_keys = {'protocol','status','source_sha256','rows','episodes','plant_steps',
        'screen','development_screen_passed','registered_streams_used','heldout_outcomes_analyzed',
        'performance_improvement_claimed','candidate_promoted','model_weights_trained',
        'recommendation','scope'}
    _require(type(report) is dict and set(report) == expected_keys)
    _require(report['protocol'] == 'standard-learning-development-comparison-v1' and report['status'] == 'complete')
    _require(type(report['episodes']) is int and report['episodes'] == 6)
    _require(type(report['plant_steps']) is int and report['plant_steps'] == 480)
    for field in ('registered_streams_used','heldout_outcomes_analyzed','performance_improvement_claimed',
                  'candidate_promoted','model_weights_trained'):
        _require(report[field] is False)
    pins = demo.sources()
    _require(len(pins) == 21 and report['source_sha256'] == pins)
    rows = report['rows']
    _require(type(rows) is list and len(rows) == 6)
    expected = [(scenario,arm) for scenario in demo.SCENARIOS for arm in demo.ARMS]
    for row, (scenario,arm) in zip(rows, expected):
        _require(type(row) is dict and set(row) == {'arm','episode','audit','elapsed_seconds','source_sha256'})
        _require(row['arm'] == arm and row['source_sha256'] == pins)
        elapsed = row['elapsed_seconds']
        _require(type(elapsed) in (int,float) and math.isfinite(elapsed) and elapsed >= 0)
        demo.episode.validate(row['episode'],9,scenario,arm != 'frozen')
        _require(demo.episode._same(row['audit'],demo.auditor.audit(row['episode'],arm)))
    screen = demo.compare(rows)
    _require(demo.episode._same(report['screen'],screen))
    _require(type(report['development_screen_passed']) is bool and report['development_screen_passed'] == screen['passed'])
    _require(report['recommendation'] == ('register_fresh_study' if screen['passed'] else 'retain_baseline_and_diagnose'))


def _mean(rows, key):
    return sum(row[key] for row in rows)/len(rows) if rows else None


def analyze(report):
    validate(report)
    summaries, counterfactuals, cases = [], [], []
    for row in report['rows']:
        episode, arm = row['episode'], row['arm']
        scenario = episode['scenario']
        recovery = next((event['step'] for event in episode['recovery_events'] if event['authorised']), None)
        previous_velocity = 0.
        steps = []
        for item in episode['trace']:
            state = demo.episode.RETENTION*(item['estimated_velocity']-previous_velocity)
            gain = (item['estimated_gain']-item['true_gain'])*item['action']
            signed = item['predicted_velocity']-item['true_velocity']
            residual = signed-(state+gain)
            _require(abs(residual) <= 1e-12)
            _require(abs(abs(signed)-item['prediction_error']) <= 1e-12)
            nominal = (demo.episode.RETENTION*item['estimated_velocity']
                       + demo.episode.INITIAL_GAIN*item['action'])
            steps.append({'step':item['step'],'source':item['action_source'],
                'recovery_period':'post_recovery' if recovery is not None and item['step'] >= recovery else 'pre_recovery',
                'action_group':'zero' if item['action'] == 0 else 'nonzero',
                'state_term':state,'gain_term':gain,'signed_error':signed,
                'absolute_error':abs(signed),'absolute_state_term':abs(state),
                'absolute_gain_term':abs(gain),'cancellation':abs(state)+abs(gain)-abs(signed),
                'identity_residual':residual,'nominal_absolute_error':abs(nominal-item['true_velocity'])})
            previous_velocity = item['true_velocity']
        for source in ('all','controller','external_supervisor'):
            selected = [item for item in steps if source == 'all' or item['source'] == source]
            summaries.append({'scenario':scenario,'arm':arm,'source':source,'steps':len(selected),
                **{key:_mean(selected,key) for key in ('state_term','gain_term','signed_error',
                    'absolute_error','absolute_state_term','absolute_gain_term','cancellation')},
                'max_absolute_identity_residual':max((abs(item['identity_residual']) for item in selected),default=0.)})
        if arm == 'single_use':
            for period in ('pre_recovery','post_recovery'):
                for action_group in ('zero','nonzero'):
                    selected = [item for item in steps if item['recovery_period'] == period and item['action_group'] == action_group]
                    learned, nominal = _mean(selected,'absolute_error'), _mean(selected,'nominal_absolute_error')
                    counterfactuals.append({'scenario':scenario,'arm':arm,'recovery_period':period,
                        'action_group':action_group,'steps':len(selected),'learned_mae':learned,
                        'nominal_mae':nominal,'learned_minus_nominal':None if learned is None else learned-nominal})
        cases.append({'scenario':scenario,'arm':arm,'steps':steps})
    return {'protocol':'standard-learning-prediction-diagnostic-v1','status':'complete',
        'episodes_analyzed':6,'recorded_steps_analyzed':480,'decomposition':summaries,
        'fixed_state_action_gain_counterfactuals':counterfactuals,'cases':cases,
        'recommendation':'investigate_state_estimation_and_gain_effects_without_automatic_configuration_change',
        'new_episodes':0,'heldout_outcomes_analyzed':False,'candidate_promoted':False,
        'control_improvement_established':False,'model_weights_trained':False,
        'scope':'Retrospective development-only scoring uses recorded physical truth. Signed terms add; absolute component means are not additive error shares. Nominal-gain forecasts hold recorded states and actions fixed, not counterfactual control trajectories.'}


def run(path):
    pins = _sources()
    before, report = _read(path)
    result = analyze(report)
    after, _ = _read(path)
    if before != after: raise ValueError('diagnostic_source_artifact_changed')
    if pins != _sources(): raise ValueError('diagnostic_source_code_changed')
    result['source_artifact_sha256'] = sha256(before).hexdigest()
    result['source_sha256'] = pins
    return result
