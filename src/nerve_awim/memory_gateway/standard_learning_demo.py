"""Fixed seed-9 standard-learning development comparison; no promotion."""
from hashlib import sha256
import multiprocessing
import math
from pathlib import Path
import time

from ..runtime_v28 import NerveResearchRuntime
from ..single_use_standard import SingleUseStandardRuntime
from . import recovery_adaptation as episode
from . import standard_learning_audit as auditor

ARMS = ('frozen','legacy','single_use')
SCENARIOS = ('stationary','drift')
ROOT = Path(__file__).resolve().parents[3]
SOURCES = ('src/nerve_awim/integrated_v13.py','src/nerve_awim/fusion_v12.py',
    'src/nerve_awim/drift_v14.py','src/nerve_awim/runtime_v28.py',
    'src/nerve_awim/identity_v26.py','src/nerve_awim/recovery_v25.py',
    'src/nerve_awim/recovery_v24.py','src/nerve_awim/recovery_v22.py',
    'src/nerve_awim/recovery_v21.py','src/nerve_awim/recovery_policy_v23.py',
    'src/nerve_awim/worldcore_v20.py','src/nerve_awim/risk_v17.py',
    'src/nerve_awim/calibrated_v16.py','src/nerve_awim/calibration_v15.py',
    'src/nerve_awim/adaptive_calibration_v19.py','src/nerve_awim/coverage_v18.py',
    'src/nerve_awim/single_use_standard.py',
    'src/nerve_awim/memory_gateway/recovery_adaptation.py',
    'src/nerve_awim/memory_gateway/standard_learning_audit.py',
    'src/nerve_awim/memory_gateway/standard_learning_demo.py',
    'scripts/demo_standard_learning.py')


def sources():
    return {name:sha256((ROOT/name).read_bytes()).hexdigest() for name in SOURCES}


def _identity(arm,scenario):
    if type(arm) is not str or arm not in ARMS or type(scenario) is not str or scenario not in SCENARIOS:
        raise ValueError('invalid_development_identity')


def _child(connection,arm,scenario):
    """Constructor binding occurs only in an isolated single-thread child."""
    original = episode.NerveResearchRuntime
    try:
        _identity(arm,scenario); pins = sources(); start = time.monotonic()
        def runtime(**kwargs):
            kwargs['estimator'] = 'standard'
            expected = 0. if arm == 'frozen' else .08
            if kwargs['learning_rate'] != expected: raise ValueError('learning_rate_mismatch')
            constructor = SingleUseStandardRuntime if arm == 'single_use' else NerveResearchRuntime
            return constructor(**kwargs)
        episode.NerveResearchRuntime = runtime
        row = episode.episode(9,scenario,arm != 'frozen')
        evidence = auditor.audit(row,arm)
        if sources() != pins: raise ValueError('source_drift')
        connection.send(('ok',{'arm':arm,'episode':row,'audit':evidence,
                               'elapsed_seconds':time.monotonic()-start,'source_sha256':pins}))
    except BaseException as exc:
        connection.send(('failed',type(exc).__name__))
    finally:
        episode.NerveResearchRuntime = original
        connection.close()


def _execute(arm,scenario,timeout=30):
    _identity(arm,scenario)
    context = multiprocessing.get_context('spawn'); reader,writer = context.Pipe(duplex=False)
    child = context.Process(target=_child,args=(writer,arm,scenario))
    try:
        child.start(); writer.close()
        if not reader.poll(timeout): raise TimeoutError('development_episode_timeout')
        status,result = reader.recv()
        if status != 'ok': raise RuntimeError('development_episode_failed:'+result)
        return result
    finally:
        if child.pid is not None:
            if child.is_alive(): child.terminate()
            child.join(1)
            if child.is_alive(): child.kill(); child.join(1)
        reader.close(); writer.close()


def compare(rows):
    expected = {(scenario,arm) for scenario in SCENARIOS for arm in ARMS}
    indexed = {}
    for row in rows:
        identity = row['episode']['scenario'],row['arm']
        if identity not in expected or identity in indexed: raise ValueError('invalid_development_roster')
        if row['episode']['seed'] != 9 or type(row['episode']['seed']) is not int:
            raise ValueError('development_seed_required')
        metrics = row['episode']['metrics']
        for key in ('mean_goal_error','mean_prediction_error'):
            if type(metrics[key]) not in (int,float) or not math.isfinite(metrics[key]) or metrics[key] < 0:
                raise ValueError('invalid_development_metric')
        for key in ('violations','supervisor_steps'):
            if type(metrics[key]) is not int or not 0 <= metrics[key] <= 80:
                raise ValueError('invalid_development_metric')
        indexed[identity] = row
    if set(indexed) != expected: raise ValueError('incomplete_development_roster')
    comparisons = []
    for control in ('frozen','legacy'):
        strata = []
        for scenario in SCENARIOS:
            candidate = indexed[scenario,'single_use']['episode']['metrics']
            baseline = indexed[scenario,control]['episode']['metrics']
            metrics = {key:{'candidate':candidate[key],'control':baseline[key],
                            'delta':candidate[key]-baseline[key]}
                       for key in ('mean_goal_error','mean_prediction_error','violations','supervisor_steps')}
            passed = (candidate['violations'] == 0 and
                      all(values['delta'] <= (1e-12 if key.startswith('mean_') else 0) for key,values in metrics.items()))
            strata.append({'scenario':scenario,'metrics':metrics,'nonregression':passed})
        goal_gain = -sum(s['metrics']['mean_goal_error']['delta'] for s in strata)
        comparisons.append({'control':control,'strata':strata,'sum_goal_gain':goal_gain,
                            'passed':all(s['nonregression'] for s in strata) and goal_gain > 1e-5})
    return {'passed':all(c['passed'] for c in comparisons),'comparisons':comparisons,
            'scope':'Fixed development fixture screen only; no held-out or population improvement claim.'}


def run_demo():
    pins = sources(); rows = []; start = time.monotonic()
    for scenario in SCENARIOS:
        for arm in ARMS:
            remaining = 180-(time.monotonic()-start)
            if remaining <= 0: raise TimeoutError('development_budget_exhausted')
            if sources() != pins: raise ValueError('source_drift')
            row = _execute(arm,scenario,min(30,remaining))
            if type(row) is not dict or set(row) != {'arm','episode','audit','elapsed_seconds','source_sha256'}:
                raise ValueError('invalid_worker_result')
            if type(row['elapsed_seconds']) not in (int,float) or not math.isfinite(row['elapsed_seconds']) or row['elapsed_seconds'] < 0:
                raise ValueError('invalid_worker_elapsed')
            if row['source_sha256'] != pins or row['arm'] != arm:
                raise ValueError('worker_source_or_arm_mismatch')
            episode.validate(row['episode'],9,scenario,arm != 'frozen')
            if not episode._same(row['audit'],auditor.audit(row['episode'],arm)): raise ValueError('audit_mismatch')
            rows.append(row)
    if sources() != pins or time.monotonic()-start > 180: raise ValueError('source_or_budget_changed')
    screen = compare(rows)
    return {'protocol':'standard-learning-development-comparison-v1','status':'complete',
            'source_sha256':pins,'rows':rows,'episodes':6,'plant_steps':480,
            'screen':screen,'development_screen_passed':screen['passed'],
            'registered_streams_used':False,'heldout_outcomes_analyzed':False,
            'performance_improvement_claimed':False,'candidate_promoted':False,
            'model_weights_trained':False,
            'recommendation':'register_fresh_study' if screen['passed'] else 'retain_baseline_and_diagnose',
            'scope':'Six seed-9 development episodes; duplicate-consumption correctness is separate from goal or prediction performance.'}
