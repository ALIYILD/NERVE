"""Bounded synthetic drift demonstration using actual registered agent tools.

Host-owned evaluator/fixtures; no model weight training, clinical data or promotion.
"""
import json
from pathlib import Path
import tempfile

from nerve_awim.agent_bridge_v13 import DemoAgentBridge
from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger
from nerve_awim.memory_gateway.gateway import MemoryGateway
from nerve_awim.memory_gateway.contracts import MemoryScope
from nerve_awim.memory_gateway.learning import VerifiedOutcomeLearning


def run():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        authority = MemoryAuthority()
        host = authority.issue('synthetic', 'agent', permissions=('read', 'propose', 'approve', 'delete'))
        reader = authority.issue('synthetic', 'agent', permissions=('read',))
        scope = MemoryScope('synthetic', 'agent', 'string-transformation')
        ledger = TrustedMemoryLedger(root/'verified.sqlite', authority)
        gateway = MemoryGateway(ledger)
        memories = {}
        for strategy in ('lower-only', 'trim-lower'):
            content = json.dumps({'schema': 'nerve-demo-strategy-v1', 'task': 'email-normalization',
                                  'extract': 'json-field', 'normalise': strategy})
            mid = gateway.propose(host, scope=scope, content=content, source_id='host-fixture')
            gateway.decide(host, mid, scope=scope, approve=True, evaluator_id='synthetic-review')
            memories[strategy] = mid
        def judge(memory, task, output):
            value = json.loads(task['document'])['email']
            expected = value.strip().lower() if task['trim'] else value.lower()
            return output == expected
        learning = VerifiedOutcomeLearning(gateway, host, scope, evaluator=judge,
                                           evaluator_revision='synthetic-transform-v1', window=3)
        bridge = DemoAgentBridge(root/'agent.sqlite', memory_session=learning.session(reader))
        observations = 0
        def phase(trim):
            nonlocal observations
            for strategy, mid in memories.items():
                for n in range(3):
                    episode = ('trim' if trim else 'preserve')+'-'+strategy+'-'+str(n)
                    task = {'document': json.dumps({'email': '  '+episode.upper()+'@EXAMPLE.TEST  '}), 'trim': trim}
                    actual = bridge.execute_plan(task_id=episode, email_document=task['document'],
                        extract_strategy='json-field', normalise_strategy=strategy)
                    result = learning.observe(memory_id=mid, episode_id=episode, task=task, output=actual['result'])
                    if result['status'] != 'judged':
                        raise AssertionError('host evaluation did not complete')
                    observations += 1
        document = json.dumps({'email': '  SYNTHETIC@EXAMPLE.TEST  '})
        phase(False)
        before = bridge.run_pipeline(task_id='before', email_document=document)
        phase(True)
        after = bridge.run_pipeline(task_id='after', email_document=document)
        reopened = MemoryGateway(TrustedMemoryLedger(root/'verified.sqlite', authority))
        continued = VerifiedOutcomeLearning(reopened, host, scope, evaluator=judge,
                                             evaluator_revision='synthetic-transform-v1', window=3)
        restarted = DemoAgentBridge(root/'restarted.sqlite', memory_session=continued.session(reader))
        restart = restarted.run_pipeline(task_id='restart', email_document=document)
        assert before['strategies']['normalise'] == 'lower-only'
        assert after['strategies']['normalise'] == restart['strategies']['normalise'] == 'trim-lower'
        assert after['result'] == 'synthetic@example.test'
        gateway.revoke_scope(host, scope=scope, evaluator_id='host-revocation')
        denied = False
        try:
            restarted.run_pipeline(task_id='revoked', email_document=document)
        except PermissionError:
            denied = True
        assert denied
        return {'status': 'passed', 'synthetic_only': True, 'host_evaluations': observations,
                'before_strategy': before['strategies']['normalise'],
                'after_strategy': after['strategies']['normalise'], 'restart_retains_learning': True,
                'revocation_blocks_learned_strategy': denied, 'model_weights_trained': False,
                'deployed': False, 'limitation': 'Constructed deterministic drift fixture, not real-model improvement.'}


if __name__ == '__main__':
    print(json.dumps(run(), indent=2, sort_keys=True))
