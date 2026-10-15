import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('tier6_reconciliation', Path(__file__).resolve().parents[1]/'scripts/reconcile_tier6_goal.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class Tier6ReconciliationTests(unittest.TestCase):
    def binding(self):
        return {'goal': 'test-dev-gate', 'target_floor': 'canonical three-control gate',
                'split': 'dev', 'controls': ['always_abstain', 'random', 'baseline']}

    def receipt(self, selected=True):
        return {'verified': True, 'candidate_selected_for_review': selected, 'new_model_calls': 0,
                'holdout_accessed': False, 'promotion_authorized': False, 'production_activation_authorized': False}

    def test_evaluate_delegates_once_without_own_scores(self):
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            def evaluate():
                calls.append('canonical-gate')
                return self.receipt()
            goal = runner.build_goal(Path(directory), self.binding(), evaluate)
            self.assertEqual(goal.run()['status'], 'complete')
            runner.build_goal(Path(directory), self.binding(), evaluate).run()
            self.assertEqual(calls, ['canonical-gate'])

    def test_retained_incumbent_cannot_be_overridden(self):
        with tempfile.TemporaryDirectory() as directory:
            goal = runner.build_goal(Path(directory), self.binding(), lambda: self.receipt(False))
            self.assertEqual(goal.run()['status'], 'blocked')

    def test_binding_changes_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            runner.build_goal(Path(directory), self.binding(), self.receipt)
            with self.assertRaises(ValueError):
                runner.build_goal(Path(directory), dict(self.binding(), target_floor='weaker'), self.receipt)

    def test_forbidden_scope_cannot_complete_goal(self):
        for key in ('holdout_accessed', 'promotion_authorized', 'production_activation_authorized'):
            with tempfile.TemporaryDirectory() as directory:
                receipt = dict(self.receipt(), **{key: True})
                goal = runner.build_goal(Path(directory), self.binding(), lambda: receipt)
                self.assertEqual(goal.run()['status'], 'blocked')
