import json
from hashlib import sha256
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.memory_gateway import research_supervisor as supervisor


def config(temp):
    return {key: str(Path(temp)/(key+'.sqlite' if key.endswith('claims') else key)) for key in supervisor.PATH_KEYS}


def result(node):
    if node in ('recovery', 'factorial'):
        return {'recommendation': 'retain_baseline'}
    return {'next_action': ('register_objective_aligned_candidate_study' if node == 'adaptation_diagnosis'
                            else 'register_observation_aware_adaptation_study')}


def write(root, paths, node):
    artifact = supervisor._artifact(root, paths, node)
    artifact.parent.mkdir(parents=True)
    artifact.write_text(json.dumps(result(node)))


def validate(root, paths, node):
    raw = supervisor._artifact(root, paths, node).read_bytes()
    return json.loads(raw), sha256(raw).hexdigest()


class ResearchSupervisorTests(unittest.TestCase):
    def setUp(self):
        for target, replacement in (('_execute', write), ('_validate', validate)):
            mock = patch.object(supervisor, target, side_effect=replacement)
            setattr(self, target, mock.start()); self.addCleanup(mock.stop)

    def test_dispatch_claims_then_resume_without_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/'coordinator'
            paths = config(temp)
            def claimed(root, paths, node):
                with sqlite3.connect(root/'supervisor.sqlite') as db:
                    self.assertEqual(db.execute('SELECT status FROM nodes WHERE name=?', (node,)).fetchone()[0], 'claimed')
                write(root, paths, node)
            self._execute.side_effect = claimed
            first = supervisor.run(root, paths)
            self.assertEqual(self._execute.call_count, 4)
            self.assertEqual(first['status'], 'new_registered_experiment_required')
            self.assertFalse(first['goal_achieved'])
            self._execute.reset_mock()
            self.assertEqual(supervisor.run(root, paths), first)
            self._execute.assert_not_called()

    def test_adoption_of_completed_stages_only_executes_missing_node(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/'coordinator'; paths = config(temp)
            for node in supervisor.NODES[:3]: write(root, paths, node)
            report = supervisor.run(root, paths)
            self.assertEqual(self._execute.call_count, 1)
            self.assertEqual([r['origin'] for r in report['completed_nodes']], ['adopted']*3+['executed'])

    def test_partial_stage_is_consumed_not_restarted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/'coordinator'; paths = config(temp)
            Path(paths['recovery']).mkdir()
            with self.assertRaises(FileNotFoundError): supervisor.run(root, paths)
            self._execute.assert_not_called()
            with self.assertRaisesRegex(RuntimeError, 'failed_consumed'): supervisor.run(root, paths)
            self._execute.assert_not_called()

    def test_interrupted_claim_accepts_complete_receipt_but_never_dispatches(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/'coordinator'; paths = config(temp)
            supervisor.run(root, paths)
            with sqlite3.connect(root/'supervisor.sqlite') as db:
                db.execute("UPDATE nodes SET status='claimed',digest=NULL WHERE name='factorial'")
            self._execute.reset_mock()
            report = supervisor.run(root, paths)
            self.assertEqual(len(report['completed_nodes']), 4)
            self._execute.assert_not_called()

    def test_changed_completed_artifact_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/'coordinator'; paths = config(temp)
            supervisor.run(root, paths)
            Path(paths['recovery'], 'report.json').write_text(json.dumps({'recommendation': 'changed'}))
            with self.assertRaisesRegex(ValueError, 'completed_node_changed'): supervisor.run(root, paths)

    def test_protocol_change_and_concurrent_runner_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/'coordinator'; paths = config(temp)
            supervisor.run(root, paths)
            with supervisor._exclusive(root):
                with self.assertRaisesRegex(RuntimeError, 'already_running'): supervisor.run(root, paths)
            paths['factorial_claims'] += 'other'
            with self.assertRaisesRegex(ValueError, 'protocol_changed'): supervisor.run(root, paths)

    def test_positive_candidate_stops_for_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/'coordinator'; paths = config(temp)
            write(root, paths, 'recovery')
            Path(paths['recovery'], 'report.json').write_text(json.dumps({'recommendation': 'candidate_for_review'}))
            report = supervisor.run(root, paths)
            self.assertEqual(report['status'], 'candidate_requires_independent_review')
            self._execute.assert_not_called()

    def test_unknown_journal_status_cannot_be_reconciled(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/'coordinator'; paths = config(temp)
            supervisor.run(root, paths)
            with sqlite3.connect(root/'supervisor.sqlite') as db:
                db.execute("UPDATE nodes SET status='invented' WHERE name='recovery'")
            self._execute.reset_mock()
            with self.assertRaisesRegex(ValueError, 'invalid_node_journal_state'):
                supervisor.run(root, paths)
            self._execute.assert_not_called()

    def test_explicit_shared_paths_required_and_symlink_root_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/'coordinator'
            with self.assertRaises(ValueError): supervisor.run(root, None)
            target = Path(temp)/'actual'; target.mkdir()
            link = Path(temp)/'linked'; link.symlink_to(target)
            with self.assertRaisesRegex(ValueError, 'symlink'): supervisor.run(link, config(temp))
