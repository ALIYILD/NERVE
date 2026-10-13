"""Bounded sensor-only duplicate-learning and authorized-epoch fixtures."""
from dataclasses import asdict
from pathlib import Path
import secrets
import tempfile

from ..integrated_v13 import SensorOnlyController
from ..single_use_standard import SingleUseStandardController, SingleUseStandardRuntime
from ..recovery_v25 import sign_approval
from .recovery_adaptation import SyntheticVerifier, ISSUER, AUDIENCE


def _controller(kind):
    controller = kind(learning_rate=.5,estimator='standard')
    controller.filter.step(1); controller.filter.step(1)
    return controller


def _snapshot(controller):
    return {'gain':controller.gain,'accepted_transitions':sorted(controller.drift_model.processed)
            if controller.drift_model is not None else None,'sensor_packets':controller.observation_count,
            'filter_state':asdict(controller.filter.state)}


def duplicate_fixture():
    legacy = _controller(SensorOnlyController); corrected = _controller(SingleUseStandardController)
    for controller in (legacy,corrected):
        controller.ingest(0,velocity=.1); controller.ingest(1,velocity=.3)
    initial = {'legacy':_snapshot(legacy),'corrected':_snapshot(corrected)}
    repeats = []
    for count in range(1,4):
        legacy.ingest(1,velocity=.3); corrected.ingest(1,velocity=.3)
        repeats.append({'duplicate_packets':count,'legacy':_snapshot(legacy),'corrected':_snapshot(corrected)})
    if initial['legacy']['gain'] != initial['corrected']['gain']:
        raise ValueError('first_update_equivalence_failed')
    if any(r['corrected']['gain'] != initial['corrected']['gain'] for r in repeats):
        raise ValueError('duplicate_learning_detected')
    before = _snapshot(corrected)
    corrected.ingest(1,velocity=.4)
    after = _snapshot(corrected)
    if before['gain'] != after['gain'] or before['filter_state'] == after['filter_state']:
        raise ValueError('sensor_revision_semantics_failed')
    return {'forced_actions':[1,1],'initial_observations':[[0,.1],[1,.3]],
            'initial':initial,'repeats':repeats,'revision':{'observation':[1,.4],'before':before,'after':after},
            'revision_policy':'Filter correction allowed; previously accepted transition is not learned again.'}


def delayed_fixture():
    controller = _controller(SingleUseStandardController)
    controller.ingest(1,velocity=.3); missing = _snapshot(controller)
    controller.ingest(0,velocity=.1); resolved = _snapshot(controller)
    controller.ingest(0,velocity=.1); repeated = _snapshot(controller)
    if missing['accepted_transitions'] or resolved['accepted_transitions'] != [1] or resolved['gain'] != repeated['gain']:
        raise ValueError('delayed_pair_consumption_failed')
    return {'delivery':[[1,.3],[0,.1],[0,.1]],'missing_predecessor':missing,'resolved':resolved,'repeated':repeated}


def order_fixture():
    results = []
    for order in ((0,1,2),(1,2,0)):
        controller = _controller(SingleUseStandardController); controller.filter.step(1)
        values = (.1,.3,.7)
        for index in order: controller.ingest(index,velocity=values[index])
        results.append({'delivery_order':list(order),'result':_snapshot(controller)})
    return {'cases':results,'order_invariance_claimed':False,
            'policy':'EMA follows first usable pair order, not chronological refitting.'}


def recovery_fixture():
    secret = secrets.token_bytes(32)
    with tempfile.TemporaryDirectory(prefix='nerve-single-use-learning-') as temp:
        runtime = SingleUseStandardRuntime(verifier=SyntheticVerifier(),issuer=ISSUER,audience=AUDIENCE,
            secret=secret,ledger_path=str(Path(temp)/'approval.sqlite'),learning_rate=.5,estimator='standard',
            target=4.,horizon=1,risk_aversion=0.,max_missing=5,recovery_samples=2,evidence_minimum=2)
        epochs = []
        for epoch in range(2):
            origin = runtime.controller.epoch_origin
            actions = [runtime.tick().action,runtime.tick().action]
            if actions != [1,1]: raise ValueError('unexpected_fixture_actions')
            runtime.observe(origin,velocity=.1); runtime.observe(origin+1,velocity=.3)
            first = _snapshot(runtime.controller.core)
            runtime.observe(origin+1,velocity=.3); duplicate = _snapshot(runtime.controller.core)
            if first['accepted_transitions'] != [1] or first['gain'] != duplicate['gain']:
                raise ValueError('epoch_consumption_failed')
            epochs.append({'epoch':epoch,'origin':origin,'actions':actions,'first':first,'duplicate':duplicate})
            if epoch == 0:
                runtime.advance_time(6)
                if runtime.tick().action is not None: raise ValueError('missing_recovery_abstention')
                for timestamp,position in ((7,.1),(8,.2)):
                    if not runtime.observe_recovery(timestamp,observed_now=timestamp,position=position,velocity=.1):
                        raise ValueError('recovery_observation_rejected')
                approval = sign_approval(secret,'synthetic-supervisor','supervisor',runtime.controller.incident,'single-use-epoch',9)
                rejected = runtime.authorise_recovery('invalid',approval,8)
                if rejected: raise ValueError('invalid_identity_accepted')
                gain_before = runtime.controller.core.gain
                granted = runtime.authorise_recovery('synthetic-host-approval',approval,8)
                gain_after = runtime.controller.core.gain
                processed_after = sorted(runtime.controller.core.drift_model.processed)
                if not granted or gain_before != gain_after or processed_after:
                    raise ValueError('authorized_epoch_reset_failed')
                recovery = {'invalid_identity_granted':rejected,'authorized':granted,
                    'gain_before':gain_before,'gain_after':gain_after,'processed_after':processed_after,
                    'epoch_origin':runtime.controller.epoch_origin}
        return {'epochs':epochs,'recovery':recovery,'accepted_updates_total':sum(len(e['first']['accepted_transitions']) for e in epochs)}


def run_demo():
    return {'protocol':'single-use-learning-development-demo-v1','status':'complete',
            'duplicates':duplicate_fixture(),'delayed':delayed_fixture(),'delivery_order':order_fixture(),
            'runtime_recovery':recovery_fixture(),'registered_streams_used':False,
            'performance_improvement_claimed':False,'model_weights_trained':False,'candidate_promoted':False,
            'scope':'Synthetic sensor/action mechanism fixtures. Standard EMA duplicate-consumption correction; no discovery, control-performance or deployment claim.'}
