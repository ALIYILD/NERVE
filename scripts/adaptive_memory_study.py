"""Deterministic capable-control smoke study, not evidence of LLM improvement."""
import json
from pathlib import Path
import tempfile

from nerve_awim.adaptive_memory import OutcomeMemoryRanker
from nerve_awim.learning_study import Episode, run_study
from nerve_awim.memory_retrieval_v18 import SecureMemoryRetriever
from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger


def run():
    with tempfile.TemporaryDirectory() as folder:
        class Arm:
            def __init__(self, name):
                self.name, self.used = name, None
                authority = MemoryAuthority()
                self.ledger = TrustedMemoryLedger(Path(folder)/(name+'.db'), authority)
                self.actor = authority.issue('synthetic', 'sorting', permissions=('read', 'propose', 'approve'))
                mid = self.ledger.propose(self.actor, context='sorting', content='Sort numbers using the requested direction.', source_id='fixture')
                self.ledger.decide(self.actor, mid, approve=True, evaluator_id='fixture-review', score=1.)
                self.utility = OutcomeMemoryRanker(self.ledger, evaluator=lambda memory, task, output:
                    output == sorted(task['numbers'], reverse=task['descending']), evaluator_revision='sorting-fixture-v1')
                self.retriever = SecureMemoryRetriever(self.ledger, utility=self.utility)

            def predict(self, task):
                self.used = None
                if self.name != 'no_memory':
                    rows = self.retriever.retrieve(self.actor, context='sorting', query='sort numbers',
                        mode='adaptive' if self.name == 'adaptive' else 'lexical', limit=1)
                    self.used = rows[0].memory_id if rows else None
                # Capable fixed control: memory is not required to solve this task.
                return sorted(task['numbers'], reverse=task['descending'])

            def learn(self, task, output, success, episode_id):
                if self.name == 'adaptive' and self.used is not None:
                    self.utility.observe(self.actor, memory_id=self.used, episode_id=episode_id,
                                         task=task, output=output)

        episodes = []
        for n in range(16):
            descending = n % 2 == 1
            values = [n*4+2, n*4, n*4+1]
            expected = [n*4+2, n*4+1, n*4] if descending else [n*4, n*4+1, n*4+2]
            episodes.append(Episode('case-'+str(n), 'train' if n < 6 else 'evaluation',
                                    {'numbers': values, 'descending': descending}, expected))
        result = run_study(episodes, arm_factory=Arm, judge=lambda task, output, expected: output == expected)
        result['fixture'] = 'capable deterministic sorting control; not a real-model benchmark'
        return result


if __name__ == '__main__':
    print(json.dumps(run(), indent=2, sort_keys=True))
