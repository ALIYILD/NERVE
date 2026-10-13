import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.memory_gateway import research_orchestrator as graph
from test_online_optimisation import fixture


class ResearchOrchestratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.TemporaryDirectory()
        cls.original = Path(cls.shared.name) / 'original.sqlite'
        cls.report = graph.online._run(cls.original, 'fixture', fixture)

    @classmethod
    def tearDownClass(cls):
        cls.shared.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / 'input.sqlite'
        shutil.copyfile(self.original, self.db)
        self.output = self.root / 'input.json'
        self.output.write_text(json.dumps(self.report))

    def verify(self):
        return graph.verify_online(self.db, self.output, 'fixture')

    def run_graph(self, execute):
        return graph._run(self.root / 'graph', self.db, self.output, 'fixture', execute)

    def test_valid_receipt(self):
        self.assertEqual(self.verify()['status'], 'completed_candidate_for_review')

    def test_export_tamper(self):
        report = json.loads(self.output.read_text())
        report['trial_calls'] = 351
        self.output.write_text(json.dumps(report))
        with self.assertRaises(ValueError):
            self.verify()

    def test_journal_fail_closed(self):
        for mutation in ("DELETE FROM policy_research_trials_v2 WHERE trial_index=3", "UPDATE policy_research_trials_v2 SET status='pending' WHERE trial_index=3", "UPDATE policy_research_trials_v2 SET seed=99 WHERE trial_index=3", "UPDATE policy_research_datasets_v2 SET run_id='other'"):
            with self.subTest(mutation=mutation):
                shutil.copyfile(self.original, self.db)
                with sqlite3.connect(self.db) as db:
                    db.execute(mutation)
                with self.assertRaises(ValueError):
                    self.verify()

    def test_consistent_false_count_rejected(self):
        report = json.loads(self.output.read_text())
        report['pipeline_episodes'] = True
        self.output.write_text(json.dumps(report))
        with sqlite3.connect(self.db) as db:
            db.execute('UPDATE policy_research_runs_v2 SET report=?', (json.dumps(report),))
        with self.assertRaises(ValueError):
            self.verify()

    def test_no_dispatch_on_invalid_receipt(self):
        self.output.write_text('{}')
        calls = []
        with self.assertRaises(ValueError):
            self.run_graph(lambda path: calls.append(path))
        self.assertEqual(calls, [])
        with sqlite3.connect(self.root / 'graph/orchestrator.sqlite') as db:
            self.assertEqual(db.execute('SELECT status FROM nodes').fetchall(), [('failed_consumed',)])

    def test_claim_precedes_dispatch_and_failure_not_replayed(self):
        calls = []
        def fail(path):
            calls.append(path)
            with sqlite3.connect(self.root / 'graph/orchestrator.sqlite') as db:
                self.assertEqual(db.execute("SELECT status FROM nodes WHERE name='worldcore'").fetchone()[0], 'claimed')
            raise TimeoutError('fixture timeout')
        with self.assertRaises(TimeoutError):
            self.run_graph(fail)
        with self.assertRaises(FileExistsError):
            self.run_graph(fail)
        self.assertEqual(len(calls), 1)
        with sqlite3.connect(self.root / 'graph/orchestrator.sqlite') as db:
            self.assertEqual(db.execute("SELECT status FROM nodes WHERE name='worldcore'").fetchone()[0], 'failed_consumed')

    def test_rejected_predecessor_is_terminal_not_improvement(self):
        receipt = {'status': 'completed_rejected', 'recommendation': 'retain_baseline'}
        def child(path):
            path.mkdir()
            report = {'protocol': graph.worldcore.manifest(), 'status': 'complete', 'result': {'status': 'no_deployable_improvement'}}
            with sqlite3.connect(path / 'ledger.sqlite') as db:
                db.execute('CREATE TABLE study(id INTEGER, status TEXT, result TEXT)')
                db.execute('INSERT INTO study VALUES (1, ?, ?)', ('complete', json.dumps(report)))
            return report
        with patch.object(graph, 'verify_online', return_value=receipt), patch.object(graph.worldcore, 'validate_receipt', create=True):
            result = self.run_graph(child)
        self.assertEqual(result['online']['status'], 'completed_rejected')
        self.assertFalse(result['goal_achieved'])
        self.assertFalse(result['deployed'])

    def test_source_drift_after_child_consumes_claim(self):
        with patch.object(graph, 'verify_online', return_value={'status': 'completed_rejected'}), patch.object(graph, '_sources', side_effect=[{'a': 'a'}, {'a': 'a'}, {'a': 'b'}]):
            with self.assertRaises(ValueError):
                self.run_graph(lambda path: {})
        self.assertEqual(json.loads((self.root / 'graph/failure.json').read_text())['node'], 'worldcore')

    def test_symlink_root_refused(self):
        (self.root / 'graph').symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(FileExistsError):
            self.run_graph(lambda path: self.fail('must not execute'))

    def test_contradictory_lineage_rejected(self):
        report = json.loads(self.output.read_text())
        report['cycles'][0]['decisions'][0]['reasons'] = []
        selection = {'protocol_sha256': report['protocol']['protocol_sha256'], 'selected': report['selected'], 'cycles_sha256': graph.loop._digest(report['cycles'])}
        report['selection_sha256'] = graph.loop._digest(selection)
        self.output.write_text(json.dumps(report))
        with sqlite3.connect(self.db) as db:
            db.execute('UPDATE policy_research_runs_v2 SET report=?', (json.dumps(report),))
            db.execute('UPDATE policy_research_cycles_v2 SET evidence=? WHERE generation=1', (json.dumps(report['cycles'][0]),))
        with self.assertRaises(ValueError):
            self.verify()

    def test_process_timeout_terminates_and_kills(self):
        from unittest.mock import MagicMock
        process = MagicMock()
        process.pid = 123
        process.is_alive.return_value = True
        context = MagicMock()
        context.Process.return_value = process
        with patch.object(graph.multiprocessing, 'get_context', return_value=context):
            with self.assertRaises(TimeoutError):
                graph._execute(self.root / 'child')
        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        self.assertEqual(process.join.call_args_list[0].args, (120,))

    def test_process_crash_rejected(self):
        from unittest.mock import MagicMock
        process = MagicMock()
        process.pid = 123
        process.is_alive.return_value = False
        process.exitcode = 1
        context = MagicMock()
        context.Process.return_value = process
        with patch.object(graph.multiprocessing, 'get_context', return_value=context):
            with self.assertRaises(RuntimeError):
                graph._execute(self.root / 'child')
