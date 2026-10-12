"""Synthetic gateway objective for the existing bounded v1.9 research loop.

Fixtures are public and inspectable, not cryptographically sealed. The final
holdout phase permits exactly the selected/baseline comparison; it cannot be
reopened for training on the same objective instance. No policy is deployed.
"""
from pathlib import Path
import tempfile

from ..memory_v18 import MemoryAuthority, TrustedMemoryLedger
from ..recursive_evolution_v19 import (DOCS, DATASETS, EvalScore, RetrievalGenome,
                                      RecursiveEvolutionLoop, select)
from .contracts import MemoryRequest, MemoryScope
from .gateway import MemoryGateway


class GatewayMemoryObjective:
    def __init__(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.authority = MemoryAuthority()
        self.actor = self.authority.issue('research', 'evaluation', permissions=('read', 'propose', 'approve'))
        self.foreign = self.authority.issue('foreign', 'evaluation', permissions=('read',))
        self.scope = MemoryScope('research', 'evaluation', 'synthetic')
        self.foreign_scope = MemoryScope('foreign', 'evaluation', 'synthetic')
        self.ledger = TrustedMemoryLedger(Path(self._temporary.name) / 'memory.sqlite', self.authority)
        self.gateway = MemoryGateway(self.ledger)
        for name, content in DOCS.items():
            mid = self.gateway.propose(self.actor, scope=self.scope,
                content='fixture ' + content, source_id=name, kind='semantic')
            self.gateway.decide(self.actor, mid, scope=self.scope, approve=True,
                                evaluator_id='frozen-synthetic-v1', score=1.0)
        self.calls = []
        self._holdout_calls = 0

    def close(self):
        self._temporary.cleanup()

    def corpus(self, foreign=False):
        # Equal broad prefilter for all genomes: every fixture contains this
        # synthetic marker. Candidate weights rank only authorised source text.
        scope, actor = (self.foreign_scope, self.foreign) if foreign else (self.scope, self.actor)
        result = self.gateway.retrieve(actor, MemoryRequest(scope, 'fixture', limit=20))
        return {record.source_id: record.content for record in result.records}

    def evaluate(self, genome, split):
        if type(genome) is not RetrievalGenome or split not in DATASETS:
            raise ValueError('fixed genome and split required')
        if split == 'holdout':
            if self._holdout_calls >= 2:
                raise RuntimeError('holdout comparison already consumed')
            self._holdout_calls += 1
        elif self._holdout_calls:
            raise RuntimeError('selection is closed after holdout')
        self.calls.append(split)
        documents = self.corpus()
        leaks = len(self.corpus(foreign=True))
        cases = DATASETS[split]
        hits = sum(select(query, documents, genome) == label for query, label in cases)
        return EvalScore(hits / len(cases), hits, len(cases), leaks)


def run_gateway_research(*, generations=3, seed=19):
    objective = GatewayMemoryObjective()
    try:
        report = RecursiveEvolutionLoop(objective=objective, generations=generations,
                                       offspring=4, seed=seed, patience=3).run()
        report.update(gateway_verified=True, runtime_kv_tested=False,
                      deployed=False, fixture='public synthetic v1.9 retrieval cases',
                      holdout_sealed=False, evaluation_calls=len(objective.calls))
        return report
    finally:
        objective.close()
