#!/usr/bin/env python3
"""One-shot synthetic recovery verification; identity provider is a fixture."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import secrets
from nerve_awim.identity_v26 import VerifiedIdentity
from nerve_awim.recovery_v25 import sign_approval
from nerve_awim.runtime_v28 import NerveResearchRuntime


class SyntheticVerifier:
    def verify(self, token, now):
        if token != 'synthetic-approved':
            return None
        return VerifiedIdentity('synthetic-operator', 'https://synthetic.invalid',
            'research', frozenset({'recovery-supervisor'}), now+100)


def run(directory):
    root=Path(directory)
    root.mkdir(parents=True,exist_ok=False)
    repository=Path(__file__).resolve().parents[1]
    names=['scripts/verify_supervised_recovery.py']+[
        'src/nerve_awim/'+name+'.py' for name in (
            'worldcore_v20','fusion_v12','recovery_v21','recovery_v22',
            'recovery_policy_v23','recovery_v24','recovery_v25','identity_v26',
            'runtime_v28','risk_v17','calibrated_v16','calibration_v15',
            'integrated_v13','drift_v14','adaptive_calibration_v19','coverage_v18')]
    hashes=lambda:{name:sha256((repository/name).read_bytes()).hexdigest() for name in names}
    sources=hashes()
    key=secrets.token_bytes(32)
    runtime=NerveResearchRuntime(verifier=SyntheticVerifier(),
        issuer='https://synthetic.invalid',audience='research',secret=key,
        ledger_path=str(root/'approvals.sqlite'),max_missing=1,recovery_samples=2)
    runtime.sensor_missing()
    stopped=runtime.tick().action is None
    accepted=[runtime.observe_recovery(t,observed_now=t,position=t/10,velocity=.1)
              for t in (1,2)]
    locked=runtime.tick().action is None
    approval=sign_approval(key,'synthetic-operator','supervisor',
        runtime.controller.incident,'synthetic-once',200)
    denied=not runtime.authorise_recovery('invalid',approval,100)
    granted=runtime.authorise_recovery('synthetic-approved',approval,100)
    no_fabricated_actions=runtime.controller.core.filter.actions==[]
    resumed=runtime.tick().action is not None
    try:
        runtime.observe(0,position=.1,velocity=.1)
    except ValueError:
        old_rejected=True
    else:
        old_rejected=False
    runtime.advance_time(3)
    expired=runtime.tick().action is None
    replay_denied=not runtime.authorise_recovery('synthetic-approved',approval,100)
    checks=dict(stopped=stopped,fresh_samples=all(accepted),locked_before_approval=locked,
        invalid_identity_denied=denied,approved=granted,no_fabricated_actions=no_fabricated_actions,
        actual_action_resumed=resumed,old_epoch_rejected=old_rejected,
        later_expiry=expired,approval_replay_denied=replay_denied)
    if sources!=hashes() or not all(checks.values()):
        raise RuntimeError('synthetic recovery verification failed')
    report={'checks':checks,'status':'passed','identity_provider':'synthetic_fixture',
        'source_sha256':sources,'model_weights_trained':False,'deployed':False,
        'scope':'Actual local simulated controller and signed-approval ledger; mock identity provider, no physical device or production authentication.'}
    (root/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',required=True)
    args=parser.parse_args()
    print(run(args.directory)['status'])
