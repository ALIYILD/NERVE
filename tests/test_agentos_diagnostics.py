import copy
import json
from pathlib import Path
import unittest

from nerve_awim.agentos_diagnostics import diagnose


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.receipt = json.loads((Path(__file__).resolve().parents[1] /
            'docs/evidence/agentos-repository-repair-v1.json').read_text())

    def test_archived_ceiling_and_training_rejection(self):
        before = copy.deepcopy(self.receipt)
        result = diagnose(self.receipt)
        self.assertEqual(result['cohort'], 'v1')
        self.assertEqual(result['diagnosis'], 'selection_ceiling_tie')
        self.assertEqual(result['training'], dict(tasks=2, hits=1,
            category_counts={'passed': 1, 'patch_rejected': 1}))
        self.assertEqual(result['phases_unopened'], ['retention', 'final'])
        self.assertFalse(result['candidate_promoted'])
        self.assertIsNone(result['native_cost_usd'])
        self.assertEqual(len(result['next_actions']), 2)
        self.assertEqual(self.receipt, before)
        self.assertNotIn('MAX_COUNTER', json.dumps(result))

    def test_v2_receipt(self):
        path = Path(__file__).resolve().parents[1] / 'docs/evidence/agentos-repository-repair-v2.json'
        if not path.exists():
            self.skipTest('v2 archive not installed')
        result = diagnose(json.loads(path.read_text()))
        self.assertEqual(result['cohort'], 'v2')
        self.assertEqual(result['training']['category_counts'], {'patch_rejected': 2})
        self.assertEqual(result['training']['hits'], 0)
        self.assertTrue(result['selection_ceiling'])

    def test_malformed_evidence_fails_closed(self):
        for mutate in (
            lambda r: r.update(result=None),
            lambda r: r['result']['selection'].update(tasks=True),
            lambda r: r['result']['selection'].update(lesson_hits=2),
            lambda r: r['result']['retention'].update(tasks=1),
            lambda r: r['artifacts'].append(copy.deepcopy(r['artifacts'][0])),
            lambda r: r['artifacts'][0]['check'].update(category=[]),
            lambda r: r['result'].update(lesson_id='invented'),
            lambda r: r['result'].update(general_improvement_proven=True),
            lambda r: r['artifacts'].pop(),
        ):
            with self.subTest(mutate=mutate):
                receipt = copy.deepcopy(self.receipt)
                mutate(receipt)
                with self.assertRaises(ValueError):
                    diagnose(receipt)

    def test_failure_is_not_tie_or_unopened_holdout(self):
        self.receipt['result'] = {'status': 'failed', 'reason': 'TimeoutError'}
        result = diagnose(self.receipt)
        self.assertEqual(result['diagnosis'], 'failed')
        self.assertFalse(result['selection_ceiling'])
        self.assertEqual(result['phases_unknown'], ['selection', 'retention', 'final'])
        self.assertEqual(result['phases_unopened'], [])
        self.assertFalse(result['candidate_promoted'])

    def test_incomplete(self):
        self.receipt['result'] = {'status': 'running'}
        self.assertEqual(diagnose(self.receipt)['diagnosis'], 'incomplete')

    def test_saturated_baseline_with_loss_is_regression(self):
        item = next(a for a in self.receipt['artifacts'] if a['phase']=='selection' and a['arm']=='lesson')
        item['check'].update(passed=False, category='behavior_failed', tests_passed=0)
        self.receipt['result']['selection'].update(lesson_hits=2, losses=1)
        result = diagnose(self.receipt)
        self.assertEqual(result['diagnosis'], 'regression')
        self.assertTrue(result['selection_ceiling'])

    def test_scoped_gain_never_claims_general_improvement(self):
        receipt = self.receipt
        receipt['artifacts'] = [a for a in receipt['artifacts'] if a['phase']=='train']
        for phase in ('selection', 'retention', 'final'):
            base = phase == 'retention'
            receipt['result'][phase] = dict(evaluated=True, tasks=1, baseline_hits=int(base),
                                           lesson_hits=1, wins=int(not base), losses=0)
            for arm, passed in (('baseline', base), ('lesson', True)):
                receipt['artifacts'].append(dict(task_id=phase, phase=phase, arm=arm,
                    check=dict(passed=passed, category='passed' if passed else 'behavior_failed',
                               tests_passed=int(passed), tests_total=1, scope=receipt['scope'])))
        receipt['result'].update(status='observed_gain', lesson_id='lesson-example')
        result = diagnose(receipt)
        self.assertEqual(result['diagnosis'], 'observed_scoped_gain')
        self.assertTrue(result['candidate_promoted'])
        self.assertFalse(result['general_improvement_proven'])
        self.assertIn('unproven', result['summary'])
        receipt['result']['selection']['wins'] = 0
        with self.assertRaises(ValueError):
            diagnose(receipt)


if __name__ == '__main__':
    unittest.main()
