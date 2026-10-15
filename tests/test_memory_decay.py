"""Scoped, opt-in decay with immutable run configuration and legacy compatibility."""
import json
import sqlite3
from pathlib import Path
import unittest
import test_memory_exploration as fixtures
from nerve_awim.adaptive_memory import OutcomeMemoryRanker
from nerve_awim.memory_gateway import MemoryGateway, MemoryScope
from nerve_awim.memory_gateway.learning import VerifiedOutcomeLearning
from nerve_awim.memory_gateway.automation import AutomaticLearningRun


class DecayTests(unittest.TestCase):
    setUp = fixtures.ExplorationTests.setUp
    observe = fixtures.ExplorationTests.observe
    ranker = fixtures.ExplorationTests.ranker
    def make_decay(self, half=3):
        return OutcomeMemoryRanker(self.ledger,evaluator=lambda m,t,o:bool(o),
            evaluator_revision='frozen-v1',window=3,decay_half_life=half)

    def test_stale_failure_decays_toward_neutral_and_default_is_unchanged(self):
        ranker = self.make_decay()
        for n in range(3):
            self.observe(ranker,self.ids[1],n)
        for n in range(3,6):
            self.observe(ranker,self.ids[0],n)
        self.assertEqual(self.ranker('relevance').rank(self.reader,self.rows)[0].memory_id,self.ids[0])
        self.assertEqual(ranker.rank(self.reader,self.rows)[0].memory_id,self.ids[1])
        self.assertEqual(self.make_decay().rank(self.reader,self.rows)[0].memory_id,self.ids[1])

    def test_other_context_and_revision_do_not_age_outcomes(self):
        ranker = self.make_decay(1)
        for n in range(3):
            self.observe(ranker,self.ids[0],n,False)
            self.observe(ranker,self.ids[1],n+10,False)
        # First memory is older; both utilities stay fixed as foreign feedback arrives.
        before = [r.memory_id for r in ranker.rank(self.reader,self.rows)]
        foreign = self.ledger.propose(self.host,context='different',content='sorting other',source_id='fixture')
        self.ledger.decide(self.host,foreign,approve=True,evaluator_id='host')
        for n in range(20,25):
            self.observe(ranker,foreign,n,True)
        newer = OutcomeMemoryRanker(self.ledger,evaluator=lambda *a:True,evaluator_revision='v2',window=3)
        for n in range(30,35):
            self.observe(newer,self.ids[1],n,True)
        self.assertEqual([r.memory_id for r in ranker.rank(self.reader,self.rows)],before)
        # Directly exercise tied own-history values: external sequences alone cannot break a tie.
        with sqlite3.connect(self.ledger.path) as con:
            con.execute("UPDATE memory_utility SET success=1 WHERE revision='frozen-v1' AND memory IN (?,?)",self.ids)
        order = [r.memory_id for r in ranker.rank(self.reader,self.rows)]
        for n in range(40,45):
            self.observe(ranker,foreign,n,True)
        self.assertEqual([r.memory_id for r in ranker.rank(self.reader,self.rows)],order)

    def test_invalid_decay_and_run_policy_change_rejected(self):
        for value in (True,0,-1,101,3.0,'3'):
            with self.assertRaises(ValueError):
                self.make_decay(value)
        scope=MemoryScope('t','a','c');path=Path(self.temp.name)/'agent.sqlite'
        old=VerifiedOutcomeLearning(MemoryGateway(self.ledger),self.host,scope,lambda *a:True,'v')
        runner=AutomaticLearningRun(old,self.reader,path,'old')
        with sqlite3.connect(self.ledger.path) as con:
            config=json.loads(runner.config);config.pop('decay_half_life');config.pop('tie_break')
            con.execute('UPDATE memory_automatic_runs_v1 SET config=?,claimed=2',(json.dumps(config),))
        changed=VerifiedOutcomeLearning(MemoryGateway(self.ledger),self.host,scope,lambda *a:True,'v',decay_half_life=3)
        with self.assertRaises(ValueError):
            AutomaticLearningRun(changed,self.reader,path,'old')
        self.assertEqual(AutomaticLearningRun(old,self.reader,path,'old').status()['consumed'],2)

    def test_foreign_feedback_cannot_accelerate_decay_before_own_new_observation(self):
        ranker=self.make_decay(3)
        for n in range(3):
            self.observe(ranker,self.ids[0],n,True)
        foreign=self.ledger.propose(self.host,context='other',content='sorting other',source_id='fixture')
        self.ledger.decide(self.host,foreign,approve=True,evaluator_id='host')
        for n in range(3,33):
            self.observe(ranker,foreign,n,True)
        self.observe(ranker,self.ids[1],33,True)
        # Only ONE same-context episode ages A: .5+(.8-.5)*2**(-1/3) > 2/3.
        # Counting foreign sequence gaps would incorrectly demote A below B.
        self.assertEqual(ranker.rank(self.reader,self.rows)[0].memory_id,self.ids[0])
