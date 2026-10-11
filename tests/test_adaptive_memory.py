import sqlite3
import unittest
import test_memory_retrieval_v18 as fixtures
from nerve_awim.adaptive_memory import OutcomeMemoryRanker
from nerve_awim.memory_retrieval_v18 import SecureMemoryRetriever


class AdaptiveMemoryTests(unittest.TestCase):
    setUp = fixtures.SemanticMemoryV18Tests.setUp
    new = fixtures.SemanticMemoryV18Tests.new

    def ranker(self, evaluator=lambda memory, task, output: output == task['expected'], revision='test-v1'):
        return OutcomeMemoryRanker(self.host, evaluator=evaluator, evaluator_revision=revision, window=3)

    def observe(self, ranker, mid, n, success=True, actor=None):
        return ranker.observe(actor or self.reviewer, memory_id=mid, episode_id='episode-'+str(n),
                              task={'expected': n}, output=n if success else -100)

    def test_learns_recent_outcomes_and_adapts_without_changing_approval(self):
        a, b = self.new('sorting rule a'), self.new('sorting rule b')
        ranker = self.ranker()
        for n in range(3):
            self.observe(ranker, a, n)
            self.observe(ranker, b, n+10, False)
        facade = SecureMemoryRetriever(self.host, utility=ranker)
        self.assertEqual(facade.retrieve(self.writer, context='planning', query='sorting', mode='adaptive')[0].memory_id, a)
        for n in range(3):
            self.observe(ranker, a, n+20, False)
            self.observe(ranker, b, n+30)
        self.assertEqual(facade.retrieve(self.writer, context='planning', query='sorting', mode='adaptive')[0].memory_id, b)
        self.assertEqual(self.host.status(self.writer, a).status, 'approved')

    def test_rewards_require_host_capability_and_fresh_episode(self):
        mid, ranker = self.new('sorting rule'), self.ranker()
        with self.assertRaises(PermissionError):
            self.observe(ranker, mid, 0, actor=self.writer)
        self.observe(ranker, mid, 0)
        with self.assertRaises(sqlite3.IntegrityError):
            self.observe(ranker, mid, 0)
        with self.assertRaises(sqlite3.IntegrityError):
            ranker.observe(self.reviewer, memory_id=mid, episode_id='renamed', task={'expected': 0}, output=0)

    def test_failed_judge_is_consumed_without_reward(self):
        mid, ranker = self.new('sorting rule'), self.ranker(lambda *args: 'yes')
        self.assertEqual(self.observe(ranker, mid, 0), {'status': 'evaluator_failed', 'success': None})
        with sqlite3.connect(self.host.path) as con:
            self.assertEqual(con.execute('SELECT success FROM memory_utility').fetchone(), (None,))

    def test_revocation_during_judging_cannot_award_or_retrieve(self):
        mid = self.new('sorting rule')
        def evaluator(*args):
            self.host.revoke(self.reviewer, mid, evaluator_id='test')
            return True
        ranker = self.ranker(evaluator)
        record = self.host.status(self.writer, mid)
        self.assertEqual(self.observe(ranker, mid, 0)['status'], 'memory_unavailable')
        self.assertEqual(ranker.rank(self.writer, [record]), [])

    def test_revision_isolates_evidence_and_restart_retains_it(self):
        a, b = self.new('sorting rule a'), self.new('sorting rule b')
        self.observe(self.ranker(), a, 0)
        candidates = [self.host.status(self.writer, b), self.host.status(self.writer, a)]
        self.assertEqual(self.ranker().rank(self.writer, candidates)[0].memory_id, a)
        self.assertEqual(self.ranker(revision='test-v2').rank(self.writer, candidates)[0].memory_id, b)

    def test_pending_and_other_scope_are_not_retrieved(self):
        mid = self.new('sorting rule')
        pending = self.new('sorting pending', approved=False)
        ranker = self.ranker()
        with self.assertRaises(ValueError):
            self.observe(ranker, pending, 0)
        facade = SecureMemoryRetriever(self.host, utility=ranker)
        self.assertEqual(facade.retrieve(self.other_agent, context='planning', query='sorting', mode='adaptive'), [])
        self.assertEqual(facade.retrieve(self.writer, context='planning', query='unrelated', mode='adaptive'), [])
        self.assertEqual(facade.retrieve(self.writer, context='planning', query='sorting', mode='adaptive')[0].memory_id, mid)
