import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('observer_demo',Path(__file__).resolve().parents[1]/'scripts/demo_actual_action_observer.py')
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


class ActualActionObserverDemoTests(unittest.TestCase):
    def test_known_action_propagation_does_not_resume_suspended_control(self):
        result = demo.run()
        self.assertEqual(result['steps'],16)
        self.assertEqual(result['external_steps'],11)
        self.assertEqual(result['external_observer_mae'],0.)
        self.assertGreater(result['external_legacy_mae'],0.)
        self.assertFalse(result['automatic_recovery'])
        for row in result['rows']:
            self.assertTrue(row['controller_unchanged_by_observer'])
            if row['source']=='external_supervisor':
                self.assertNotEqual(row['phase'],'active')
                self.assertEqual(row['action'],0)
        self.assertFalse(result['candidate_promoted'])
        self.assertFalse(result['model_weights_trained'])
