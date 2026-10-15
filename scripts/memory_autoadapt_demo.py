"""Automatic, bounded synthetic learning from actual registered-tool outcomes."""
import json
from pathlib import Path
import tempfile

from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger
from nerve_awim.memory_gateway.gateway import MemoryGateway
from nerve_awim.memory_gateway.contracts import MemoryScope
from nerve_awim.memory_gateway.learning import VerifiedOutcomeLearning
from nerve_awim.memory_gateway.automation import AutomaticLearningRun


def run():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        authority = MemoryAuthority()
        host = authority.issue('synthetic', 'agent', permissions=('read', 'propose', 'approve', 'delete'))
        reader = authority.issue('synthetic', 'agent', permissions=('read',))
        scope = MemoryScope('synthetic', 'agent', 'automatic-transform')
        ledger = TrustedMemoryLedger(root/'verified.sqlite', authority)
        gateway = MemoryGateway(ledger)
        for strategy in ('lower-only', 'trim-lower'):
            content = json.dumps({'schema':'nerve-demo-strategy-v1','task':'email-normalization',
                                  'extract':'json-field','normalise':strategy})
            mid = gateway.propose(host, scope=scope, content=content, source_id='host-fixture')
            gateway.decide(host, mid, scope=scope, approve=True, evaluator_id='host-review')
        def judge(memory, task, output):
            value = json.loads(task['document'])['email']
            return output == (value.strip().lower() if task['trim'] else value.lower())
        def make(gateway):
            learning = VerifiedOutcomeLearning(gateway, host, scope, evaluator=judge,
                evaluator_revision='frozen-transform-v1', window=3)
            return AutomaticLearningRun(learning, reader, root/'agent.sqlite', 'automatic-demo',
                                        max_episodes=16, max_failures=4)
        runner = make(gateway)
        outcomes = []
        for index in range(16):
            if index == 8:
                runner = make(MemoryGateway(TrustedMemoryLedger(root/'verified.sqlite', authority)))
            task = {'document':json.dumps({'email':'  AUTO'+str(index)+'@EXAMPLE.TEST  '}),
                    'trim':index < 8}
            outcomes.append(runner.execute('episode-'+str(index), task))
        first, last = outcomes[7], outcomes[-1]
        assert first['success'] is True and last['success'] is True
        assert first['strategies']['normalise'] == 'trim-lower'
        assert last['strategies']['normalise'] == 'lower-only'
        # The host does not select strategies or separately call observe().
        # Reopening and replay cannot reset consumption or execute old tasks.
        replay_denied = False
        try:
            runner.execute('episode-0', {'document':json.dumps({'email':'  AUTO0@EXAMPLE.TEST  '}),'trim':True})
        except (ValueError, RuntimeError):
            replay_denied = True
        assert replay_denied
        return {'status':'passed','episodes':16,'host_selected_strategies':False,
                'automatic_outcome_feedback':True,'reopened_between_phases':True,
                'first_phase_final_strategy':first['strategies']['normalise'],
                'second_phase_final_strategy':last['strategies']['normalise'],
                'successes':sum(item['success'] is True for item in outcomes),
                'observed_failures':sum(item['success'] is False for item in outcomes),
                'replay_or_exhausted_run_denied':replay_denied,
                'outcomes':outcomes,'synthetic_only':True,'deployed':False,
                'model_weights_trained':False,
                'limitation':'Constructed deterministic drift; no general-model improvement claim.'}


if __name__ == '__main__':
    print(json.dumps(run(), indent=2, sort_keys=True))
