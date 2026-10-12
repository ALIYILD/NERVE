"""A bounded tie policy prevents repeated-failure lock-in without granting access."""
from pathlib import Path
import sqlite3
import tempfile
import unittest

from nerve_awim.adaptive_memory import OutcomeMemoryRanker
from nerve_awim.memory_gateway import MemoryGateway, MemoryScope
from nerve_awim.memory_gateway.learning import VerifiedOutcomeLearning
from nerve_awim.memory_gateway.automation import AutomaticLearningRun
from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger


class ExplorationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.authority = MemoryAuthority()
        self.host = self.authority.issue('t','a',permissions=('read','propose','approve','delete'))
        self.reader = self.authority.issue('t','a',permissions=('read',))
        self.ledger = TrustedMemoryLedger(Path(self.temp.name)/'memory.sqlite', self.authority)
        self.ids = []
        for value in ('first','second'):
            mid = self.ledger.propose(self.host, context='c', content='sorting '+value, source_id='fixture')
            self.ledger.decide(self.host, mid, approve=True, evaluator_id='host')
            self.ids.append(mid)
        self.rows = [self.ledger.status(self.host, mid) for mid in self.ids]

    def ranker(self, policy):
        return OutcomeMemoryRanker(self.ledger, evaluator=lambda memory,task,output:bool(output),
            evaluator_revision='frozen-v1', window=3, tie_break=policy)

    def observe(self, ranker, mid, n, success=False):
        return ranker.observe(self.host, memory_id=mid, episode_id='episode-'+str(n),
                              task={'fixture':n}, output=success)

    def fail_both(self, ranker):
        for n in range(3):
            self.observe(ranker,self.ids[0],n)
            self.observe(ranker,self.ids[1],n+10)

    def test_opt_in_policy_escapes_equal_failure_trap(self):
        legacy = self.ranker('relevance')
        self.fail_both(legacy)
        chosen = []
        for n in range(3):
            mid = legacy.rank(self.reader,self.rows)[0].memory_id
            chosen.append(mid)
            self.observe(legacy,mid,n+20)
        self.assertEqual(chosen,[self.ids[0]]*3)
        exploring = self.ranker('least_recent')
        self.assertEqual(exploring.rank(self.reader,self.rows)[0].memory_id,self.ids[1])
        self.observe(exploring,self.ids[1],30,True)
        self.assertEqual(exploring.rank(self.reader,self.rows)[0].memory_id,self.ids[1])

    def test_higher_utility_still_wins_and_unseen_ties_keep_relevance(self):
        ranker = self.ranker('least_recent')
        self.assertEqual(ranker.rank(self.reader,self.rows),self.rows)
        self.observe(ranker,self.ids[0],0,True)
        self.assertEqual(ranker.rank(self.reader,list(reversed(self.rows)))[0].memory_id,self.ids[0])
        self.ledger.revoke(self.host,self.ids[0],evaluator_id='host')
        self.assertEqual([r.memory_id for r in ranker.rank(self.reader,self.rows)],[self.ids[1]])
        foreign = self.authority.issue('other','a',permissions=('read',))
        self.assertEqual(ranker.rank(foreign,self.rows),[])

    def test_restart_retains_tie_history_and_new_revision_ignores_it(self):
        ranker = self.ranker('least_recent')
        self.fail_both(ranker)
        self.observe(ranker,self.ids[0],20)
        self.assertEqual(self.ranker('least_recent').rank(self.reader,self.rows)[0].memory_id,self.ids[1])
        changed = OutcomeMemoryRanker(self.ledger,evaluator=lambda *a:True,evaluator_revision='v2',
                                     window=3,tie_break='least_recent')
        self.assertEqual(changed.rank(self.reader,self.rows),self.rows)

    def test_run_cannot_change_tie_policy_after_restart(self):
        scope = MemoryScope('t','a','c')
        gateway = MemoryGateway(self.ledger)
        first = VerifiedOutcomeLearning(gateway,self.host,scope,lambda *a:True,'frozen-v1')
        path = Path(self.temp.name)/'agent.sqlite'
        AutomaticLearningRun(first,self.reader,path,'run')
        second = VerifiedOutcomeLearning(MemoryGateway(self.ledger),self.host,scope,
                                         lambda *a:True,'frozen-v1',tie_break='least_recent')
        with self.assertRaisesRegex(ValueError,'configuration'):
            AutomaticLearningRun(second,self.reader,path,'run')

    def test_unknown_tie_policy_is_rejected(self):
        for value in ('random-code',True,None):
            with self.assertRaises(ValueError):
                self.ranker(value)

    def test_legacy_run_migrates_only_default_policy_without_resetting_budget(self):
        import json
        scope = MemoryScope('t','a','c')
        learning = VerifiedOutcomeLearning(MemoryGateway(self.ledger),self.host,scope,
                                           lambda *a:True,'frozen-v1')
        path = Path(self.temp.name)/'agent.sqlite'
        runner = AutomaticLearningRun(learning,self.reader,path,'old-run',max_episodes=1)
        with sqlite3.connect(self.ledger.path) as con:
            config = json.loads(runner.config)
            config.pop('tie_break')
            con.execute('UPDATE memory_automatic_runs_v1 SET config=?,claimed=1', (json.dumps(config,sort_keys=True),))
        exploring = VerifiedOutcomeLearning(MemoryGateway(self.ledger),self.host,scope,
                                             lambda *a:True,'frozen-v1',tie_break='least_recent')
        with self.assertRaisesRegex(ValueError,'configuration'):
            AutomaticLearningRun(exploring,self.reader,path,'old-run',max_episodes=1)
        reopened = AutomaticLearningRun(learning,self.reader,path,'old-run',max_episodes=1)
        self.assertEqual(reopened.status()['consumed'], 1)
        with sqlite3.connect(self.ledger.path) as con:
            stored = json.loads(con.execute('SELECT config FROM memory_automatic_runs_v1').fetchone()[0])
        self.assertEqual(stored['tie_break'],'relevance')
