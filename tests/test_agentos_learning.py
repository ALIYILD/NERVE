import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

from nerve_awim.agentos_learning import AgentOSLearning, CONTEXT, expected_handoff, judge_handoff


def task(n=0, **changes):
    return dict(id='task-' + str(n), exit_code=0, artifact_exists=True,
                qa_passed=True, memory_written=False, **{}) | changes


class AgentOSLearningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.host = AgentOSLearning(self.tmp.name)

    def lesson(self, text='Require independent evidence.'):
        actor = self.host.actor('hermes')
        mid = self.host.ledger.propose(actor, context=CONTEXT, content=text, source_id='test')
        self.host.ledger.decide(actor, mid, approve=True, evaluator_id='test', score=1)
        return mid

    def count(self, table):
        with sqlite3.connect(self.host.path) as db:
            return db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]

    def test_host_judge_ignores_supplied_expected_and_false_success(self):
        evidence = task(exit_code=1, memory_written=None)
        self.assertEqual(expected_handoff(evidence), dict(status='failed', passed=False, memory_saved=False))
        claim = dict(status='done', passed=True, memory_saved=True)
        self.assertFalse(judge_handoff(evidence, claim, claim))
        self.assertEqual(expected_handoff(task(qa_passed=None))['status'], 'unknown')
        self.assertFalse(judge_handoff(task(), dict(status='done', passed=1, memory_saved=False)))
        with self.assertRaises(ValueError):
            expected_handoff(task(exit_code=True))

    def test_receipts_persist_and_replay_cannot_change_reward(self):
        mid = self.lesson()
        first = self.host.observe('hermes', task(), expected_handoff(task()), lesson=mid)
        restarted = AgentOSLearning(self.tmp.name)
        replay = restarted.observe('hermes', task(), {}, lesson=mid)
        self.assertFalse(first['duplicate'])
        self.assertEqual(replay, dict(id=first['id'], duplicate=True, success=True))
        self.assertEqual(self.count('nerve_runs'), 1)
        self.assertEqual(self.count('memory_utility'), 1)

    def test_failures_lower_rank_and_three_of_recent_five_revoke(self):
        mid = self.lesson('Potentially useful lesson.')
        neutral = self.lesson('Untried lesson.')
        self.host.observe('hermes', task(0), expected_handoff(task(0)), lesson=mid)
        self.assertEqual(self.host.recall('hermes')[0].memory_id, mid)
        for n in (1, 2):
            self.host.observe('hermes', task(n), {}, lesson=mid)
        self.assertEqual(self.host.recall('hermes')[0].memory_id, neutral)
        self.host.observe('hermes', task(3), expected_handoff(task(3)), lesson=mid)
        self.host.observe('hermes', task(4), {}, lesson=mid)
        self.assertEqual(self.host.ledger.status(self.host.actor('hermes'), mid).status, 'revoked')
        self.assertNotIn(mid, [m.memory_id for m in self.host.recall('hermes')])
        self.assertTrue(self.host.observe('hermes', task(4), {}, lesson=mid)['duplicate'])
        with self.assertRaises(ValueError):
            self.host.observe('hermes', task(5), {}, lesson=mid)

    def test_expired_and_other_profile_lessons_cannot_reward_or_recall(self):
        mid = self.lesson()
        self.assertEqual(self.host.recall('other'), [])
        with self.assertRaises(LookupError):
            self.host.observe('other', task(), {}, lesson=mid)
        with sqlite3.connect(self.host.path) as db:
            db.execute('UPDATE trusted_memory_v18 SET valid_until=1 WHERE memory_id=?', (mid,))
        self.assertEqual(self.host.recall('hermes'), [])
        with self.assertRaises(ValueError):
            self.host.observe('hermes', task(), {}, lesson=mid)
        self.assertEqual(self.count('nerve_runs'), 0)

    def test_concurrent_duplicate_has_exactly_one_receipt_and_reward(self):
        mid = self.lesson()
        def observe(_):
            return AgentOSLearning(self.tmp.name).observe('hermes', task(), expected_handoff(task()), lesson=mid)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(observe, range(8)))
        self.assertEqual(sum(not r['duplicate'] for r in results), 1)
        self.assertEqual(self.count('nerve_runs'), 1)
        self.assertEqual(self.count('memory_utility'), 1)

    def test_receipt_rolls_back_if_reward_write_fails(self):
        mid = self.lesson()
        self.host.recall('hermes')  # Initialise ranker schema.
        with sqlite3.connect(self.host.path) as db:
            db.execute("CREATE TRIGGER fail_reward BEFORE INSERT ON memory_utility BEGIN SELECT RAISE(ABORT,'injected'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.host.observe('hermes', task(), expected_handoff(task()), lesson=mid)
        self.assertEqual(self.count('nerve_runs'), 0)
        with sqlite3.connect(self.host.path) as db:
            db.execute('DROP TRIGGER fail_reward')
        self.assertFalse(self.host.observe('hermes', task(), expected_handoff(task()), lesson=mid)['duplicate'])

    def report(self):
        return dict(status='observed_final_gain', selected_lesson='Report unknown without QA.',
                    final=dict(tasks=5, wins=1, losses=0, baseline_hits=4, lesson_hits=5))

    def test_no_gain_and_regressions_never_accept(self):
        self.assertIsNone(self.host.accept_study('hermes', 'study', dict(status='no_verified_improvement')))
        report = self.report()
        report['final'].update(wins=0, baseline_hits=5)
        self.assertIsNone(self.host.accept_study('hermes', 'study', report))
        report['final'].update(wins=2, losses=1, baseline_hits=3, lesson_hits=4)
        self.assertIsNone(self.host.accept_study('hermes', 'study', report))
        self.assertEqual(self.count('trusted_memory_v18'), 0)

    def test_accept_requires_consistent_report_reserved_final_and_is_idempotent(self):
        report = self.report()
        with self.assertRaises(ValueError):
            self.host.accept_study('hermes', 'study', report)
        self.host.reserve_holdout('study', [task(i, exit_code=i) for i in range(5)])
        malformed = self.report()
        malformed['final']['lesson_hits'] = 99
        with self.assertRaises(ValueError):
            self.host.accept_study('hermes', 'study', malformed)
        mid = self.host.accept_study('hermes', 'study', report)
        self.assertEqual(AgentOSLearning(self.tmp.name).accept_study('hermes', 'study', report), mid)
        self.assertEqual(self.count('trusted_memory_v18'), 1)
        self.assertEqual(self.count('nerve_lessons'), 1)
        self.assertEqual(self.host.recall('hermes')[0].memory_id, mid)
        report['selected_lesson'] = 'Different lesson'
        with self.assertRaises(ValueError):
            self.host.accept_study('hermes', 'study', report)

    def test_holdout_reservation_is_atomic_and_cannot_reuse_after_restart(self):
        self.host.reserve_holdout('study', [task(1)])
        with self.assertRaises(sqlite3.IntegrityError):
            AgentOSLearning(self.tmp.name).reserve_holdout('other-study', [task(2, exit_code=1), task(1)])
        self.assertEqual(self.count('nerve_holdouts'), 1)

    def test_daily_reservations_are_durable_and_bounded(self):
        self.host.reserve_calls('hermes-free', 10)
        with self.assertRaises(RuntimeError):
            AgentOSLearning(self.tmp.name).reserve_calls('hermes-free', 3)
        self.assertEqual(self.count('nerve_calls'), 10)
        with self.assertRaises(ValueError):
            self.host.reserve_calls('claude', 1)

    def test_verified_missions_are_deduplicated_without_claiming_learning(self):
        self.assertTrue(self.host.ingest_mission('run-1', 'hermes', success=False, duration=3, source='host-qa'))
        self.assertFalse(self.host.ingest_mission('run-1', 'hermes', success=True, duration=1, source='host-qa'))
        status = AgentOSLearning(self.tmp.name).status()
        self.assertEqual(status['missions'][0]['passed'], 0)
        self.assertEqual(status['memories'], {})
        self.assertFalse(status['automatic_paid_calls'])
        with self.assertRaises(ValueError):
            self.host.ingest_mission('run-2', 'hermes', success=True, duration=float('nan'), source='host-qa')

    def test_routing_requires_three_outcomes_and_preserves_incumbent_ties(self):
        candidates = ['incumbent', 'challenger']
        self.assertEqual(self.host.recommend_profiles(candidates)['recommended'], 'incumbent')
        for n in range(2):
            self.host.ingest_mission('candidate-' + str(n), 'challenger', success=True, duration=1, source='qa')
        self.assertEqual(self.host.recommend_profiles(candidates)['recommended'], 'incumbent')
        self.host.ingest_mission('candidate-2', 'challenger', success=True, duration=1, source='qa')
        recommendation = self.host.recommend_profiles(candidates)
        self.assertEqual(recommendation['recommended'], 'challenger')
        self.assertEqual(recommendation['ranked'][0]['score'], 0.8)
        for n in range(3):
            self.host.ingest_mission('incumbent-' + str(n), 'incumbent', success=True, duration=1, source='qa')
        self.assertEqual(self.host.recommend_profiles(candidates)['recommended'], 'incumbent')
        with self.assertRaises(ValueError):
            self.host.recommend_profiles(candidates, incumbent='unknown')

    def test_routing_adapts_to_recent_window_and_excludes_unsupplied_roles(self):
        for n in range(25):
            self.host.ingest_mission('old-' + str(n), 'a', success=True, duration=1, source='qa')
        for n in range(20):
            self.host.ingest_mission('new-' + str(n), 'a', success=False, duration=1, source='qa')
        for n in range(3):
            self.host.ingest_mission('other-' + str(n), 'b', success=True, duration=1, source='qa')
        host = AgentOSLearning(self.tmp.name)
        result = host.recommend_profiles(['a', 'b'])
        self.assertEqual(result['recommended'], 'b')
        a = next(r for r in result['ranked'] if r['profile'] == 'a')
        self.assertEqual((a['samples'], a['passed']), (20, 0))
        self.assertEqual(host.recommend_profiles(['a'])['recommended'], 'a')

    def test_holdouts_cannot_be_reused_by_changing_task_id(self):
        self.host.reserve_holdout('study', [task(0)])
        with self.assertRaises(sqlite3.IntegrityError):
            self.host.reserve_holdout('renamed-study', [task(999)])
        self.assertEqual(self.host.reserved_evidence(), {self.host.evidence_hash(task(123))})
