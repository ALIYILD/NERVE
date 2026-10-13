import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.memory_gateway import worldcore_study as study
from nerve_awim.autoresearch_v04 import Proposal
from nerve_awim.worldcore_recursion_v19 import WorldCoreResearchEvolution


def stats(goal=1.):
    return dict(completion=1., abort=0., violations=0.,
                goal_penalized=goal, prediction_penalized=1.)


class FreshWorldCoreStudyTests(unittest.TestCase):
    def test_complete_claims_before_calls_selection_before_holdout_no_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'fresh'
            def evaluator(proposal, seeds):
                with sqlite3.connect(root / 'ledger.sqlite') as db:
                    row = db.execute('SELECT status FROM calls WHERE proposal=?',
                                     (study._json({'name': proposal.name, 'max_missing': proposal.max_missing,
                                                   'risk_aversion': proposal.risk_aversion}),)).fetchone()
                    self.assertEqual(row[0], 'claimed')
                    selection = db.execute('SELECT selection FROM study').fetchone()[0]
                    self.assertEqual(selection is not None, seeds == study.HOLDOUT_SEEDS)
                return stats(.7 if proposal.max_missing > 5 else 1.)
            with patch.object(study, 'evaluate', side_effect=evaluator):
                report = study.run_study(root)
            self.assertEqual(report['status'], 'complete')
            self.assertLessEqual(report['evaluator_calls'], 12)
            self.assertEqual(report['simulation_episodes'], report['evaluator_calls'] * 8)
            self.assertEqual([r['role'] for r in report['calls']][-2:],
                             ['baseline_holdout', 'selected_holdout'])
            self.assertTrue(all(r['status'] == 'complete' for r in report['calls']))
            self.assertEqual(json.loads((root/'report.json').read_text())['status'], 'complete')
            with self.assertRaises(FileExistsError):
                study.run_study(root)

    def test_receipt_validator_rejects_sqlite_and_consistent_report_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'fresh'
            with patch.object(study, 'evaluate', return_value=stats()):
                report = study.run_study(root)
            self.assertEqual(report['result']['selected_recipe'], {'max_missing': 5, 'risk_aversion': .25})
            self.assertEqual(report['calls'][-2]['proposal']['name'], 'baseline-report-only')
            self.assertEqual(report['calls'][-1]['proposal']['name'], 'candidate-report-only')
            with patch.object(study, 'evaluate', side_effect=AssertionError('no simulator rerun')):
                self.assertTrue(study.validate_receipt(root, report, report['protocol']))
            with sqlite3.connect(root/'ledger.sqlite') as db:
                db.execute("UPDATE calls SET status='claimed' WHERE ordinal=1")
            with self.assertRaises(ValueError):
                study.validate_receipt(root, report, report['protocol'])
            with sqlite3.connect(root/'ledger.sqlite') as db:
                db.execute("UPDATE calls SET status='complete' WHERE ordinal=1")
            # Alter all public report copies consistently. Replayed gates still reject.
            report['result']['status'] = 'candidate_for_human_review'
            (root/'report.json').write_text(study._json(report))
            with sqlite3.connect(root/'ledger.sqlite') as db:
                db.execute('UPDATE study SET result=?', (study._json(report),))
            with self.assertRaises(ValueError):
                study.validate_receipt(root, report, report['protocol'])

    def test_receipt_validator_rejects_proposal_and_order_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'fresh'
            with patch.object(study, 'evaluate', return_value=stats()):
                report = study.run_study(root)
            # Consistently edited receipts cannot invent evaluator proposal identities.
            report['calls'][1]['proposal']['name'] = 'invented'
            (root/'report.json').write_text(study._json(report))
            with sqlite3.connect(root/'ledger.sqlite') as db:
                db.execute('UPDATE study SET result=?', (study._json(report),))
                db.execute('UPDATE calls SET proposal=? WHERE ordinal=2',
                           (study._json(report['calls'][1]['proposal']),))
            with self.assertRaises(ValueError):
                study.validate_receipt(root, report, report['protocol'])

    def test_failure_is_consumed_and_prevents_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'fresh'
            with patch.object(study, 'evaluate', side_effect=RuntimeError('synthetic failure')):
                with self.assertRaises(RuntimeError):
                    study.run_study(root)
            with sqlite3.connect(root / 'ledger.sqlite') as db:
                self.assertEqual(db.execute('SELECT status FROM study').fetchone()[0], 'failed')
                self.assertEqual(db.execute('SELECT status FROM calls').fetchall(), [('failed',)])
            with self.assertRaises(FileExistsError):
                study.run_study(root)

    def test_source_drift_after_evaluation_consumes_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'fresh'
            with patch.object(study, '_hashes', side_effect=[{'a':'one'}, {'a':'one'}, {'a':'two'}]), \
                 patch.object(study, 'evaluate', return_value=stats()):
                with self.assertRaisesRegex(RuntimeError, 'source_drift'):
                    study.run_study(root)
            with sqlite3.connect(root / 'ledger.sqlite') as db:
                self.assertEqual(db.execute('SELECT status FROM study').fetchone()[0], 'failed')
                self.assertEqual(db.execute('SELECT status FROM calls').fetchone()[0], 'failed')

    def test_manifest_pins_all_sources_and_simulation_bounds(self):
        value = study.manifest()
        self.assertEqual(value['max_simulation_episodes'], 96)
        self.assertEqual(value['max_steps_per_episode'], 80)
        self.assertTrue(all(len(digest) == 64 for digest in value['source_sha256'].values()))
        self.assertFalse(value['promotion_authorized'])


class WorldCoreHoldoutContractTests(unittest.TestCase):
    def test_invalid_seed_contracts(self):
        for bad in ((), [], (True,), (-1,), (2**32,), (1, 1), tuple(range(65))):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                WorldCoreResearchEvolution(validation_seeds=bad)
        with self.assertRaises(ValueError):
            WorldCoreResearchEvolution(validation_seeds=(1,), holdout_seeds=(1,))
        with self.assertRaises(ValueError):
            WorldCoreResearchEvolution(on_selection='not callable')

    def test_holdout_tie_or_goal_regression_blocks_recommendation(self):
        for holdout_goal in (1., 1.1):
            def evaluator(proposal, seeds):
                if proposal.max_missing == 5:
                    return stats()
                return stats(.7 if seeds == (1,) else holdout_goal)
            loop = WorldCoreResearchEvolution(generations=1, offspring=1,
                    validation_seeds=(1,), holdout_seeds=(2,), evaluator=evaluator)
            loop.mutation = lambda parent, rng, name: Proposal(name, 6, .25)
            result = loop.run()
            self.assertEqual(result['status'], 'no_deployable_improvement')
            self.assertFalse(result['holdout_strict_goal_improvement'])

    def test_selection_hook_is_before_holdout_and_cannot_mutate_lineage(self):
        frozen = []
        def selected(value):
            frozen.append(value['selected_recipe'].copy())
            value['lineage'].clear()
            value['selected_recipe']['max_missing'] = 12
        def evaluator(proposal, seeds):
            self.assertEqual(bool(frozen), seeds == (2,))
            return stats(.7 if proposal.max_missing > 5 else 1.)
        loop = WorldCoreResearchEvolution(generations=1, offspring=1,
                validation_seeds=(1,), holdout_seeds=(2,), evaluator=evaluator,
                on_selection=selected)
        loop.mutation = lambda parent, rng, name: Proposal(name, 6, .25)
        result = loop.run()
        self.assertEqual(result['selected_recipe']['max_missing'], 6)
        self.assertEqual(len(result['lineage']), 1)
        self.assertEqual(result['status'], 'candidate_for_human_review')


if __name__ == '__main__':
    unittest.main()
