"""Development-only matched plant cases, including wrong nominal priors.

No registered research streams or acceptance gates are consumed here. True gain
is used only by the synthetic plant, never given to a controller.
"""
from dataclasses import asdict
from pathlib import Path
import secrets
import tempfile

from ..consistent_dynamics import ConsistentDynamicsRuntime
from ..evidence_gated_dynamics import EvidenceGatedRuntime
from ..recovery_epoch_dynamics import RecoveryEpochRuntime
from ..recovery_v25 import sign_approval
from . import recovery_adaptation as fixture

ARMS = ('frozen', 'gated', 'epoch')
PLANTS = {'lower': (.18,)*4, 'nominal': (.27,)*4,
          'higher': (.40,)*4, 'drift': (.27,.48,.15,.40)}


def execute(arm, plant):
    if type(arm) is not str or arm not in ARMS or type(plant) is not str or plant not in PLANTS:
        raise ValueError('registered_development_case_required')
    schedule = fixture._schedule(9)
    secret = secrets.token_bytes(32)
    position = velocity = 0.
    trace, recoveries = [], []
    runtime_type = {'frozen':ConsistentDynamicsRuntime, 'gated':EvidenceGatedRuntime,
                    'epoch':RecoveryEpochRuntime}[arm]
    with tempfile.TemporaryDirectory(prefix='nerve-epoch-development-') as directory:
        kwargs = dict(verifier=fixture.SyntheticVerifier(), issuer=fixture.ISSUER,
            audience=fixture.AUDIENCE, secret=secret, ledger_path=str(Path(directory)/'approvals.sqlite'),
            max_missing=5, recovery_samples=3, evidence_minimum=2, risk_aversion=.25,
            safe_position=6., safe_velocity=2., min_samples=6, target=fixture.TARGET,
            learning_rate=0. if arm == 'frozen' else .08, estimator='drift',
            horizon=3, bound=6., planning_horizon=1, consistent_filter=True, gain=.27)
        runtime = runtime_type(**kwargs)
        controller = runtime.controller
        for step in range(fixture.STEPS):
            sensor = None
            if step:
                noise = schedule[step-1]
                if not noise['dropped']:
                    sensor = dict(timestamp=step-1,position=position+noise['position_noise'],
                                  velocity=velocity+noise['velocity_noise'])
                    if controller.phase == 'active':
                        sensor['accepted'] = runtime.observe(sensor['timestamp'],
                            position=sensor['position'],velocity=sensor['velocity'])
                    else:
                        sensor['accepted'] = runtime.observe_recovery(sensor['timestamp'],
                            observed_now=step-1,position=sensor['position'],velocity=sensor['velocity'])
                        if controller.recovery_ready():
                            old_gain = controller.core.gain
                            approval = sign_approval(secret,'synthetic-supervisor','supervisor',
                                controller.incident,f'epoch-demo-{step}',step)
                            granted = runtime.authorise_recovery('synthetic-host-approval',approval,step-1)
                            recoveries.append(dict(step=step,authorised=granted,
                                gain_before=old_gain,gain_after=controller.core.gain))
                runtime.advance_time(step-1)
            gain = controller.core.gain
            estimate = controller.core.filter.state.velocity
            result = runtime.tick()
            if result.action is None and result.phase == 'active':
                raise RuntimeError('development_controller_infeasible')
            action = 0 if result.action is None else result.action
            prediction = fixture.RETENTION*estimate+gain*action
            # Hidden plant parameter enters only this environment transition.
            actual_gain = PLANTS[plant][step//20]
            velocity = fixture.RETENTION*velocity+actual_gain*action
            position += velocity
            trace.append(dict(step=step,sensor=sensor,command=asdict(result),action=action,
                model_gain=gain,predicted_velocity=prediction,true_gain=actual_gain,
                true_position=position,true_velocity=velocity,
                goal_error=abs(position-fixture.TARGET),prediction_error=abs(prediction-velocity),
                violation=abs(position)>6 or abs(velocity)>2))
    return dict(arm=arm,plant=plant,seed=9,nominal_gain=.27,trace=trace,recoveries=recoveries,
        mean_goal_error=sum(r['goal_error'] for r in trace)/fixture.STEPS,
        mean_prediction_error=sum(r['prediction_error'] for r in trace)/fixture.STEPS,
        violations=sum(r['violation'] for r in trace),
        supervisor_steps=sum(r['command']['action'] is None for r in trace))


def run():
    rows = [execute(arm,plant) for plant in PLANTS for arm in ARMS]
    comparisons = []
    for plant in PLANTS:
        candidate = next(r for r in rows if r['plant']==plant and r['arm']=='epoch')
        for arm in ('frozen','gated'):
            baseline = next(r for r in rows if r['plant']==plant and r['arm']==arm)
            deltas = {key:candidate[key]-baseline[key] for key in
                ('mean_goal_error','mean_prediction_error','violations','supervisor_steps')}
            comparisons.append(dict(plant=plant,baseline=arm,deltas=deltas,
                                    nonregression=all(value<=1e-12 for value in deltas.values())))
    gain = -sum(r['deltas']['mean_goal_error'] for r in comparisons)
    eligible = all(r['nonregression'] for r in comparisons) and gain>1e-5
    return dict(protocol='recovery-epoch-development-v1',rows=rows,episodes=len(rows),
        plant_steps=len(rows)*fixture.STEPS,development_seed=9,
        comparisons=comparisons,eligible_for_registered_study=eligible,
        next_action='register_fresh_control_study' if eligible else 'retain_baselines_and_revise_hypothesis',
        performance_improvement_established=False,candidate_promoted=False,
        model_weights_trained=False,deployed=False)
