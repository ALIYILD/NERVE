"""Observation-time discounted evidence remains opt-in, scoped and durable."""
import json
from pathlib import Path
import sqlite3
import unittest

import test_memory_exploration as fixtures
from nerve_awim.adaptive_memory import OutcomeMemoryRanker
from nerve_awim.memory_gateway import MemoryGateway, MemoryScope
from nerve_awim.memory_gateway.learning import VerifiedOutcomeLearning
from nerve_awim.memory_gateway.automation import AutomaticLearningRun


class DiscountTests(unittest.TestCase):
    setUp = fixtures.ExplorationTests.setUp
    observe = fixtures.ExplorationTests.observe

    def ranker(self, half=None, **kwargs):
        return OutcomeMemoryRanker(self.ledger, evaluator=lambda m,t,o: bool(o),
            evaluator_revision='frozen-v1', window=10, discount_half_life=half, **kwargs)

    def test_recent_successes_recover_from_old_failures_without_changing_default(self):
        ranker = self.ranker(1)
        for n, success in enumerate([False, False, False, True, True]):
            self.observe(ranker, self.ids[0], n, success)
        # Undiscounted Beta mean is 3/7, below unseen B's neutral .5.
        self.assertEqual(self.ranker().rank(self.reader, self.rows)[0].memory_id, self.ids[1])
        # Recent successes outweigh historical failures with observation discounting.
        self.assertEqual(ranker.rank(self.reader, self.rows)[0].memory_id, self.ids[0])
        self.assertEqual(self.ranker(1).rank(self.reader, self.rows)[0].memory_id, self.ids[0])
        self.ledger.revoke(self.host, self.ids[0], evaluator_id='host')
        self.assertEqual(ranker.rank(self.reader, self.rows), [self.rows[1]])

    def test_recent_failures_overrule_older_successes(self):
        ranker = self.ranker(1)
        for n, success in enumerate([True, True, True, False, False]):
            self.observe(ranker, self.ids[0], n, success)
        self.assertEqual(self.ranker().rank(self.reader, self.rows)[0].memory_id, self.ids[0])
        self.assertEqual(ranker.rank(self.reader, self.rows)[0].memory_id, self.ids[1])

    def test_foreign_tenant_agent_context_and_revision_do_not_age_samples(self):
        ranker = self.ranker(3)
        for n in range(3):
            self.observe(ranker, self.ids[0], n, True)
        for tenant, agent, context in [('other', 'a', 'c'), ('t', 'other', 'c'), ('t', 'a', 'other')]:
            host = self.authority.issue(tenant, agent, permissions=('read', 'propose', 'approve'))
            mid = self.ledger.propose(host, context=context, content='sorting foreign', source_id='fixture')
            self.ledger.decide(host, mid, approve=True, evaluator_id='host')
            for n in range(30):
                ranker.observe(host, memory_id=mid, episode_id=f'{tenant}-{agent}-{context}-{n}',
                               task={'foreign': [tenant, agent, context, n]}, output=True)
        other_revision = OutcomeMemoryRanker(self.ledger, evaluator=lambda *a: True,
                                            evaluator_revision='other-v1')
        for n in range(30, 60):
            self.observe(other_revision, self.ids[1], n, True)
        self.observe(ranker, self.ids[1], 100, True)
        # A has three successes aged by only one matching observation, still > B.
        self.assertEqual(ranker.rank(self.reader, self.rows)[0].memory_id, self.ids[0])
        foreign_reader = self.authority.issue('other', 'a', permissions=('read',))
        self.assertEqual(ranker.rank(foreign_reader, self.rows), [])

    def test_failed_evaluator_does_not_age_samples(self):
        ranker = self.ranker(3)
        for n in range(3):
            self.observe(ranker, self.ids[0], n, True)
        failed = OutcomeMemoryRanker(self.ledger, evaluator=lambda *a: None,
                                     evaluator_revision='frozen-v1')
        for n in range(10, 40):
            self.observe(failed, self.ids[1], n, True)
        self.observe(ranker, self.ids[1], 100, True)
        self.assertEqual(ranker.rank(self.reader, self.rows)[0].memory_id, self.ids[0])

    def test_window_stays_bounded_and_unseen_ties_keep_relevance(self):
        ranker = self.ranker(100)
        self.assertEqual(ranker.rank(self.reader, self.rows), self.rows)
        for n in range(20):
            self.observe(ranker, self.ids[0], n, n < 10)
        # Ten old successes outside the configured window cannot retain priority.
        self.assertEqual(ranker.rank(self.reader, self.rows)[0].memory_id, self.ids[1])

    def test_invalid_half_life_rejected(self):
        for value in (True, False, 0, -1, 101, 3.0, '3', float('nan')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.ranker(value)

    def test_decay_and_discount_are_mutually_exclusive(self):
        with self.assertRaisesRegex(ValueError, 'choose either'):
            self.ranker(3, decay_half_life=3)

    def test_legacy_run_only_migrates_default_and_retains_consumed_budget(self):
        scope = MemoryScope('t', 'a', 'c')
        path = Path(self.temp.name) / 'agent.sqlite'
        old = VerifiedOutcomeLearning(MemoryGateway(self.ledger), self.host, scope, lambda *a: True, 'v')
        runner = AutomaticLearningRun(old, self.reader, path, 'legacy')
        with sqlite3.connect(self.ledger.path) as con:
            config = json.loads(runner.config)
            config.pop('discount_half_life')
            con.execute('UPDATE memory_automatic_runs_v1 SET config=?,claimed=2', (json.dumps(config),))
        changed = VerifiedOutcomeLearning(MemoryGateway(self.ledger), self.host, scope,
                                          lambda *a: True, 'v', discount_half_life=3)
        with self.assertRaisesRegex(ValueError, 'configuration'):
            AutomaticLearningRun(changed, self.reader, path, 'legacy')
        reopened = AutomaticLearningRun(old, self.reader, path, 'legacy')
        self.assertEqual(reopened.status()['consumed'], 2)
        with sqlite3.connect(self.ledger.path) as con:
            config = json.loads(con.execute('SELECT config FROM memory_automatic_runs_v1').fetchone()[0])
        self.assertIsNone(config['discount_half_life'])
        AutomaticLearningRun(changed, self.reader, path, 'new-discounted')
        self.assertEqual(AutomaticLearningRun(changed, self.reader, path, 'new-discounted').status()['consumed'], 0)
        with self.assertRaisesRegex(ValueError, 'configuration'):
            AutomaticLearningRun(old, self.reader, path, 'new-discounted')
