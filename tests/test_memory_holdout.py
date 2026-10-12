import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from nerve_awim.memory_gateway.evaluation import GatewayMemoryObjective
from nerve_awim.memory_gateway.holdout import freeze_holdout, evaluate_holdout, read_artifact
from nerve_awim.recursive_evolution_v19 import RetrievalGenome


class HoldoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.obj = GatewayMemoryObjective()
        self.addCleanup(self.obj.close)
        self.db = Path(self.tmp.name) / 'claims.sqlite'
        self.artifact = Path(self.tmp.name) / 'external.json'
        self.data = {'version': 1, 'study_id': 'study1', 'cases': [
            {'query': 'optical calibration', 'expected_source_id': 'calibration'},
            {'query': 'qwertynonsense', 'expected_source_id': None}]}
        self.artifact.write_text(json.dumps(self.data))

    def freeze(self):
        return freeze_holdout(self.db, study_id='study1', dataset_sha256=read_artifact(self.artifact)[1],
            selected=RetrievalGenome(2, 1), baseline=RetrievalGenome(), scope=self.obj.scope)

    def evaluate(self):
        return evaluate_holdout(self.db, self.artifact, study_id='study1', gateway=self.obj.gateway,
                                actor=self.obj.actor, scope=self.obj.scope)

    def test_fixed_comparison_and_restart_replay(self):
        self.freeze()
        result = self.evaluate()
        self.assertEqual(result['hits'], {'selected': 2, 'baseline': 2})
        self.assertFalse(result['deployed'])
        self.assertNotIn('cases', json.dumps(result['hits']))
        command = [sys.executable, 'scripts/galahad_holdout.py', 'evaluate', '--claims', str(self.db),
                   '--artifact', str(self.artifact), '--study-id', 'study1', '--ledger', str(self.obj.ledger.path)]
        proc = subprocess.run(command, env={**os.environ, 'PYTHONPATH': 'src'}, capture_output=True,
                              text=True, timeout=10)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('no unused frozen study', proc.stderr)

    def test_changed_genome_and_renamed_dataset_cannot_refreeze(self):
        self.freeze()
        for study, genome in [('study1', RetrievalGenome(5, 1)), ('renamed', RetrievalGenome())]:
            with self.assertRaises(ValueError):
                freeze_holdout(self.db, study_id=study, dataset_sha256=read_artifact(self.artifact)[1],
                               selected=genome, baseline=RetrievalGenome(), scope=self.obj.scope)

    def test_artifact_tamper_consumes_run_before_answers(self):
        self.freeze()
        self.data['cases'][0]['expected_source_id'] = 'noise1'
        self.artifact.write_text(json.dumps(self.data))
        with self.assertRaisesRegex(ValueError, 'artifact changed'):
            self.evaluate()
        with self.assertRaisesRegex(ValueError, 'no unused'):
            self.evaluate()

    def test_binding_corruption_consumes_run(self):
        self.freeze()
        with sqlite3.connect(self.db) as con:
            con.execute("UPDATE holdout_claims SET binding='{}'")
        with self.assertRaisesRegex(ValueError, 'binding corrupted'):
            self.evaluate()
        with self.assertRaisesRegex(ValueError, 'no unused'):
            self.evaluate()

    def test_failure_is_one_use_and_no_tuning_callback(self):
        self.freeze()
        original = self.obj.gateway.retrieve
        self.obj.gateway.retrieve = lambda *a: (_ for _ in ()).throw(RuntimeError('failure'))
        with self.assertRaises(RuntimeError):
            self.evaluate()
        self.obj.gateway.retrieve = original
        with self.assertRaisesRegex(ValueError, 'no unused'):
            self.evaluate()

    def test_bounded_strict_json(self):
        invalid = [' ' * 65537, '{"version":1,"version":1}',
                   json.dumps({**self.data, 'execute': 'arbitrary'}),
                   json.dumps({**self.data, 'cases': self.data['cases'] * 51}),
                   json.dumps({**self.data, 'cases': [{'query': 'a'*257, 'expected_source_id': None}]})]
        for raw in invalid:
            self.artifact.write_text(raw)
            with self.assertRaises(ValueError):
                read_artifact(self.artifact)

    def test_digest_normalises_whitespace_order_and_study_name(self):
        first = read_artifact(self.artifact)[1]
        self.data['cases'].reverse()
        self.data['study_id'] = 'another'
        self.artifact.write_text(json.dumps(self.data, indent=4))
        self.assertEqual(first, read_artifact(self.artifact)[1])

    def test_revoked_actor_denied_without_consuming_study(self):
        self.freeze()
        self.obj.gateway.revoke_actor(self.obj.actor)
        with self.assertRaises(PermissionError):
            self.evaluate()
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute('SELECT status FROM holdout_claims').fetchone()[0], 'frozen')

    def test_separate_cli_freeze_and_evaluate(self):
        common = [sys.executable, 'scripts/galahad_holdout.py']
        freeze = subprocess.run(common + ['freeze', '--claims', str(self.db), '--study-id', 'study1',
            '--dataset-sha256', read_artifact(self.artifact)[1], '--selected', '2', '1'],
            env={**os.environ, 'PYTHONPATH': 'src'}, capture_output=True, text=True, timeout=10)
        self.assertEqual(freeze.returncode, 0, freeze.stderr)
        evaluate = subprocess.run(common + ['evaluate', '--claims', str(self.db), '--study-id', 'study1',
            '--artifact', str(self.artifact), '--ledger', str(self.obj.ledger.path)],
            env={**os.environ, 'PYTHONPATH': 'src'}, capture_output=True, text=True, timeout=10)
        self.assertEqual(evaluate.returncode, 0, evaluate.stderr)
        self.assertEqual(json.loads(evaluate.stdout)['hits'], {'selected': 2, 'baseline': 2})

    def test_claim_capacity_is_bounded(self):
        self.freeze()
        with sqlite3.connect(self.db) as con:
            con.executemany('INSERT INTO holdout_claims VALUES (?,?,?,?,?)',
                ((str(n), str(n), '{}', 'hash', 'consumed') for n in range(9999)))
        with self.assertRaisesRegex(ValueError, 'capacity'):
            freeze_holdout(self.db, study_id='new', dataset_sha256='0'*64,
                selected=RetrievalGenome(), baseline=RetrievalGenome(), scope=self.obj.scope)

    def test_wrong_scope_cannot_consume_another_frozen_study(self):
        self.freeze()
        with self.assertRaisesRegex(PermissionError, 'frozen scope denied'):
            evaluate_holdout(self.db, self.artifact, study_id='study1', gateway=self.obj.gateway,
                             actor=self.obj.foreign, scope=self.obj.foreign_scope)
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute('SELECT status FROM holdout_claims').fetchone()[0], 'frozen')
        self.assertEqual(self.evaluate()['hits'], {'selected': 2, 'baseline': 2})

    def test_cli_evaluate_rejects_candidate_overrides_without_consumption(self):
        self.freeze()
        for option in ('--selected', '--baseline'):
            proc = subprocess.run([sys.executable, 'scripts/galahad_holdout.py', 'evaluate',
                '--claims', str(self.db), '--study-id', 'study1', '--artifact', str(self.artifact),
                '--ledger', str(self.obj.ledger.path), option, '3', '0'],
                env={**os.environ, 'PYTHONPATH': 'src'}, capture_output=True, text=True, timeout=10)
            self.assertEqual(proc.returncode, 2)
            self.assertIn('candidate overrides are forbidden', proc.stderr)
        self.assertEqual(self.evaluate()['hits'], {'selected': 2, 'baseline': 2})
