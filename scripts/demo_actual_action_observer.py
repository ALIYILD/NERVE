#!/usr/bin/env python3
"""Synthetic, known-model observation during suspended control; not a benchmark."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import secrets
import tempfile

from nerve_awim.actual_action_observer import ActualActionObserver
from nerve_awim.identity_v26 import VerifiedIdentity
from nerve_awim.runtime_v28 import NerveResearchRuntime


class SyntheticVerifier:
    def verify(self, token, now):
        if token == 'synthetic-action-reporter':
            return VerifiedIdentity('synthetic-host','synthetic','observer-demo',
                                    frozenset({'actual-action-observer'}), now+1)


def run():
    verifier = SyntheticVerifier()
    observer = ActualActionObserver(verifier=verifier,issuer='synthetic',
        audience='observer-demo',subjects=frozenset({'synthetic-host'}))
    rows = []
    position = velocity = 0.
    with tempfile.TemporaryDirectory(prefix='nerve-observer-demo-') as temp:
        runtime = NerveResearchRuntime(verifier=verifier,issuer='synthetic',
            audience='observer-demo',secret=secrets.token_bytes(32),
            ledger_path=str(Path(temp)/'approvals.sqlite'),max_missing=2,
            recovery_samples=2,learning_rate=0.,target=1.2)
        for step in range(16):
            if step:
                if step < 4:
                    runtime.observe(step-1,position=position,velocity=velocity)
                    observer.observe('synthetic-action-reporter',now=step,
                                     step=step-1,position=position,velocity=velocity)
                runtime.advance_time(step-1)
            old_velocity = runtime.controller.core.filter.state.velocity
            result = runtime.tick()
            action = result.action if result.action is not None else 0
            # Simulated host confirms the actual applied command after execution.
            velocity = .82*velocity+.27*action
            position += velocity
            controller_before = (runtime.controller.phase,runtime.controller.incident,
                                 tuple(runtime.controller.core.filter.actions),
                                 runtime.controller.core.filter.state)
            observed = observer.record_action('synthetic-action-reporter',now=step,
                step=step,action=action,gain=runtime.controller.core.gain)
            controller_after = (runtime.controller.phase,runtime.controller.incident,
                                tuple(runtime.controller.core.filter.actions),
                                runtime.controller.core.filter.state)
            if controller_before != controller_after:
                raise RuntimeError('observer_mutated_controller')
            rows.append({'step':step,'action':action,'phase':result.phase,
                         'source':'controller' if result.action is not None else 'external_supervisor',
                         'observer':asdict(observed),'true_velocity':velocity,
                         'observer_absolute_error':abs(observed.velocity-velocity),
                         'legacy_absolute_error':abs(.82*old_velocity+.27*action-velocity),
                         'controller_unchanged_by_observer':True})
        external = [row for row in rows if row['source']=='external_supervisor']
        if not external or any(row['phase']=='active' for row in external):
            raise RuntimeError('missing_suspended_control_evidence')
        return {'status':'passed','protocol':'actual-action-observer-demo-v1','steps':len(rows),
                'external_steps':len(external),'rows':rows,
                'external_observer_mae':sum(r['observer_absolute_error'] for r in external)/len(external),
                'external_legacy_mae':sum(r['legacy_absolute_error'] for r in external)/len(external),
                'automatic_recovery':False,'candidate_promoted':False,
                'model_weights_trained':False,
                'scope':'Single deterministic noiseless known-model mechanism demo; no comparative learning claim.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',required=True)
    args = parser.parse_args()
    root = Path(args.directory); root.mkdir(parents=True,exist_ok=False)
    report = run()
    (root/'report.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='rows'},sort_keys=True))
