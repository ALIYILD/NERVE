import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from nerve_awim.memory_gateway import research_campaign as campaign


def fixture(seed, scenario, arm, timeout):
    hits = 20 if arm == 'candidate' else 16
    outcomes = [i < hits for i in range(campaign.study.EPISODES)]
    writes = 0 if arm.startswith('fixed_') else 1
    return {'seed': seed, 'scenario': scenario, 'arm': arm, 'outcomes': outcomes,
            'hits': sum(outcomes), 'executions': 32, 'feedback_writes': writes*32,
            'episode_feedback_writes': [writes]*32,
            'payload_sha256': [campaign.study._digest(task) for task, _ in campaign.study._cases(seed, scenario)]}


class ResearchCampaignTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db, self.out, self.stop = [self.root/n for n in ('ledger.sqlite', 'report.json', 'STOP')]

    def run_campaign(self, **kwargs):
        args = dict(run_id='fixture', deadline=datetime.now(timezone.utc)+timedelta(minutes=5),
                    stop_file=self.stop, cycles=1, seeds_per_cycle=1, first_seed=10000,
                    executor=fixture)
        args.update(kwargs)
        return campaign._run(self.db, self.out, **args)

    def test_complete_exact_budget_scoring_and_atomic_evidence(self):
        report = self.run_campaign()
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(len(report['trials']), 16)
        self.assertEqual(len(report['cycle_summaries']), 1)
        self.assertEqual(report['cycle_summaries'][0]['scenario_deltas']['stationary'], 4)
        self.assertEqual(report['claimed_pipeline_episodes'], 512)
        self.assertEqual(report['completed_pipeline_episodes'], 512)
        self.assertEqual(report['recommendation'], 'candidate_for_review')
        self.assertFalse(report['promotion_authorized'])
        self.assertIn('fresh learner', report['learning_scope'])
        self.assertEqual(json.loads(self.out.read_text()), report)
        with sqlite3.connect(self.db) as db:
            self.assertEqual(json.loads(db.execute('SELECT report FROM research_campaign_runs').fetchone()[0]), report)
            self.assertEqual(db.execute("SELECT count(*) FROM research_campaign_trials WHERE status='complete'").fetchone()[0], 16)

    def test_claim_before_execution_and_failure_consumed(self):
        def fail(seed, scenario, arm, timeout):
            with sqlite3.connect(self.db) as db:
                self.assertEqual(db.execute('SELECT status FROM research_campaign_trials').fetchone()[0], 'pending')
            raise RuntimeError('sensitive detail must not be exported')
        report = self.run_campaign(executor=fail)
        self.assertEqual(report['status'], 'failed_consumed')
        self.assertEqual(report['claimed_pipeline_episodes'], 32)
        self.assertEqual(report['completed_pipeline_episodes'], 0)
        self.assertNotIn('sensitive', self.out.read_text())
        self.assertNotIn('scenario_hits', report)
        self.out.unlink()
        with self.assertRaises(ValueError):
            self.run_campaign(run_id='another')

    def test_deadline_and_stop_claim_no_trials(self):
        report = self.run_campaign(deadline=datetime.now(timezone.utc)-timedelta(seconds=1))
        self.assertEqual(report['status'], 'deadline_consumed')
        self.assertEqual(report['trials'], [])
        self.out.unlink()
        self.stop.touch()
        report = self.run_campaign(run_id='stop', first_seed=11000)
        self.assertEqual(report['status'], 'stopped_consumed')
        self.assertEqual(report['trials'], [])

    def test_stop_between_trials(self):
        def execute(*args):
            result = fixture(*args)
            self.stop.touch()
            return result
        report = self.run_campaign(executor=execute)
        self.assertEqual(report['status'], 'stopped_consumed')
        self.assertEqual(report['completed_pipeline_episodes'], 32)
        self.assertNotIn('scenario_hits', report)

    def test_drift_consumes_trial_without_scoring(self):
        original = campaign._current_sources
        calls = [0]
        def sources(protocol):
            result = original(protocol)
            calls[0] += 1
            if calls[0] >= 2:
                result['research_campaign.py'] = 'changed'
            return result
        with patch.object(campaign, '_current_sources', side_effect=sources):
            report = self.run_campaign()
        self.assertEqual(report['status'], 'failed_consumed')
        self.assertEqual(report['completed_pipeline_episodes'], 0)
        self.assertEqual(report['trials'][0]['status'], 'failed_consumed')

    def test_interrupt_is_retained_and_reraised(self):
        def interrupt(*args):
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.run_campaign(executor=interrupt)
        report = json.loads(self.out.read_text())
        self.assertEqual(report['status'], 'failed_consumed')
        self.assertEqual(report['error'], 'interrupted')

    def test_exclusive_ledger_ownership(self):
        with campaign._ownership(self.db):
            with self.assertRaises(RuntimeError):
                self.run_campaign()

    def test_exclusive_output_ownership(self):
        with campaign._ownership(self.out):
            with self.assertRaises(RuntimeError):
                self.run_campaign()

    def test_real_spawn_trial(self):
        row = campaign._execute(15000, 'stationary', 'baseline', 15)
        campaign.study._validate(row, 15000, 'stationary', 'baseline')
        self.assertEqual(row['executions'], 32)

    def test_subprocess_timeout_terminates_and_closes(self):
        context = MagicMock()
        reader, writer, process = MagicMock(), MagicMock(), MagicMock()
        context.Pipe.return_value = (reader, writer)
        context.Process.return_value = process
        process.pid = 123
        process.is_alive.side_effect = [True, True]
        reader.poll.return_value = False
        with patch.object(campaign.multiprocessing, 'get_context', return_value=context):
            with self.assertRaises(TimeoutError):
                campaign._execute(10000, 'stationary', 'baseline', 1)
        process.start.assert_called_once()
        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        reader.close.assert_called_once()
        self.assertTrue(writer.close.called)
        self.assertEqual(process.join.call_count, 2)

    def test_crashed_pending_trial_is_consumed_not_replayed(self):
        report = self.run_campaign()
        report['status'] = 'running'
        report['trials'][0]['status'] = 'pending'
        with sqlite3.connect(self.db) as db:
            db.execute('UPDATE research_campaign_runs SET status=?,report=?', ('running', json.dumps(report)))
            db.execute("UPDATE research_campaign_trials SET status='pending' WHERE arm='baseline'")
        self.out.unlink()
        with self.assertRaises(ValueError):
            self.run_campaign()
        with sqlite3.connect(self.db) as db:
            status, raw = db.execute('SELECT status,report FROM research_campaign_runs').fetchone()
            self.assertEqual(status, 'interrupted_consumed')
            self.assertEqual(json.loads(raw)['trials'][0]['status'], 'interrupted_consumed')
            self.assertEqual(db.execute("SELECT count(*) FROM research_campaign_trials WHERE status='pending'").fetchone()[0], 0)

    def test_reject_invalid_budgets_and_paths(self):
        for kwargs in ({'cycles': 33}, {'cycles': True}, {'seeds_per_cycle': 5},
                       {'first_seed': 7001}, {'trial_timeout': 301}, {'cycle_interval': 1801},
                       {'deadline': datetime.now()}, {'stop_file': self.out},
                       {'stop_file': Path(str(self.db)+'.lock')},
                       {'trial_timeout': float('nan')}, {'cycle_interval': float('inf')}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.run_campaign(**kwargs)
        self.assertEqual(campaign._manifest(32, 4, 10000, 60)['max_pipeline_episodes'], 65536)

    def test_timeout_failure_retained(self):
        def timeout(*args):
            raise TimeoutError()
        report = self.run_campaign(executor=timeout)
        self.assertEqual(report['error'], 'trial_timeout')
        self.assertEqual(len(report['trials']), 1)

    def test_invalid_evidence_cannot_score(self):
        def invalid(*args):
            row = fixture(*args)
            row['hits'] = 32
            return row
        report = self.run_campaign(executor=invalid)
        self.assertEqual(report['status'], 'failed_consumed')
        self.assertNotIn('scenario_hits', report)

    def test_cycle_wait_is_stop_interruptible(self):
        def sleep(seconds):
            persisted = json.loads(self.out.read_text())
            self.assertEqual(len(persisted['cycle_summaries']), 1)
            self.assertEqual(persisted['cycle_summaries'][0]['recommendation'], 'candidate_for_review')
            self.assertEqual(persisted['recommendation'], 'incomplete_no_recommendation')
            self.assertLessEqual(seconds, 1)
            self.stop.touch()
        with patch.object(campaign.time, 'sleep', side_effect=sleep):
            report = self.run_campaign(cycles=2, cycle_interval=1800)
        self.assertEqual(report['status'], 'stopped_consumed')
        self.assertEqual(report['completed_cycles'], 1)
        self.assertEqual(len(report['trials']), 16)

    def test_partial_cycle_has_no_summary(self):
        calls = [0]
        def execute(*args):
            calls[0] += 1
            if calls[0] == 18:
                self.stop.touch()
            return fixture(*args)
        report = self.run_campaign(cycles=2, executor=execute)
        self.assertEqual(report['status'], 'stopped_consumed')
        self.assertEqual(len(report['trials']), 18)
        self.assertEqual([row['cycle'] for row in report['cycle_summaries']], [1])
        self.assertEqual(report['recommendation'], 'incomplete_no_recommendation')
        self.assertNotIn('scenario_hits', report)

    def test_no_gain_retains_baseline(self):
        def equal(seed, scenario, arm, timeout):
            row = fixture(seed, scenario, arm, timeout)
            row['outcomes'] = [i < 16 for i in range(32)]
            row['hits'] = 16
            return row
        self.assertEqual(self.run_campaign(executor=equal)['recommendation'], 'retain_baseline')


if __name__ == '__main__':
    unittest.main()
