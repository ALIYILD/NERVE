"""Provider-free native identity inspection and unpromotable-cycle preflight."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from nerve_awim.cue_evaluation import DatasetManifest
from nerve_awim.cue_experiment import ExperimentTask
import test_cue_cycle as cycle_fixtures


SPEC = importlib.util.spec_from_file_location('profile_worker_under_test',
    Path(__file__).resolve().parents[1] / 'scripts/agentos_hermes_worker.py')
worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker)


class CueProfileInspectionTests(unittest.TestCase):
    def test_helper_returns_observed_identity_and_never_attests_hosted_alias(self):
        soul = 'PRIVATE_SOUL_SENTINEL'
        result = worker.inspect_native_profile('qa-release', 'fallback:free', 'original:free', soul,
                                               hermes_revision='a' * 40, hermes_worktree_clean=True)
        self.assertEqual(result['model'], 'fallback:free')
        self.assertTrue(result['availability_fallback'])
        self.assertTrue(result['availability_checked'])
        self.assertEqual(result['hermes_revision'], 'a' * 40)
        self.assertEqual(result['template_revision'], worker.template_identity(worker.baseline_system_message(soul)))
        self.assertFalse(result['attested'])
        self.assertEqual(result['supported_modes'], [])
        self.assertEqual(result['transport_modes'], ['instruction'])
        self.assertIsNone(result['revision'])
        self.assertIsNone(result['tokenizer'])
        self.assertIsNone(result['tokenizer_revision'])
        self.assertEqual(result['model_calls'], 0)
        self.assertNotIn(soul, json.dumps(result))

    def test_changed_soul_invalidates_template_identity(self):
        a = worker.inspect_native_profile('qa-release', 'model:free', 'model:free', 'first')
        b = worker.inspect_native_profile('qa-release', 'model:free', 'model:free', 'second')
        self.assertNotEqual(a['template_revision'], b['template_revision'])
        self.assertIsNone(a['hermes_revision'])
        self.assertIsNone(a['hermes_worktree_clean'])

    def test_checkout_failure_stays_unknown(self):
        with patch.object(worker.subprocess, 'check_output', side_effect=OSError('not available')):
            self.assertEqual(worker.inspect_hermes_checkout('/missing'), (None, None))

    def test_checkout_revision_does_not_hide_dirty_source(self):
        with patch.object(worker.subprocess, 'check_output', side_effect=['b' * 40 + '\n', ' M run_agent.py\n']):
            self.assertEqual(worker.inspect_hermes_checkout('/installed'), ('b' * 40, False))

    def invoke_worker(self, request, *, configured='configured:free'):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home = Path(temporary.name)
        root = home / '.hermes/profiles/qa-release'
        root.mkdir(parents=True)
        (root / 'config.yaml').write_text('synthetic fixture read by fake YAML parser')
        (root / 'SOUL.md').write_text('PRIVATE_SOUL_SENTINEL')
        yaml = SimpleNamespace(safe_load=lambda _: {'model': {'default': configured},
            'fallback_providers': ['fallback:free']})
        agent = Mock(side_effect=AssertionError('inspection must not instantiate an agent'))
        output = io.StringIO()
        with patch.object(worker.Path, 'home', return_value=home), \
                patch.object(worker, 'inspect_hermes_checkout', return_value=('c' * 40, True)), \
                patch.dict(sys.modules, {'hermes_yaml': yaml, 'run_agent': SimpleNamespace(AIAgent=agent)}), \
                patch.object(sys, 'stdin', io.StringIO(json.dumps(request))), redirect_stdout(output):
            worker.main()
        agent.assert_not_called()
        return json.loads(output.getvalue())

    def test_provider_free_inspection_precedes_availability_and_credentials(self):
        result = self.invoke_worker({'profile': 'qa-release', 'inspect': True,
                                     'inspect_profile': True, 'available_models': []},
                                    configured='configured-paid-alias')
        self.assertTrue(result['ok'])
        self.assertFalse(result['native_hermes'])
        self.assertEqual(result['tools'], 0)
        self.assertIsNone(result['value'])
        self.assertEqual(result['requested_model'], 'configured-paid-alias')
        self.assertFalse(result['cce_profile']['availability_checked'])
        self.assertFalse(result['cce_profile']['attested'])
        self.assertEqual(result['cce_profile']['model_calls'], 0)
        self.assertNotIn('PRIVATE_SOUL_SENTINEL', json.dumps(result))

    def test_existing_availability_inspect_retains_fallback_resolution(self):
        result = self.invoke_worker({'profile': 'qa-release', 'inspect': True,
                                     'available_models': ['fallback:free']})
        self.assertEqual(result['requested_model'], 'fallback:free')
        self.assertTrue(result['availability_fallback'])
        self.assertTrue(result['cce_profile']['availability_checked'])

    def test_profile_inspection_flag_cannot_request_inference(self):
        with self.assertRaisesRegex(ValueError, 'cannot request inference'):
            self.invoke_worker({'profile': 'qa-release', 'inspect_profile': True})


class CueCyclePreflightTests(unittest.TestCase):
    setUp = cycle_fixtures.CueCycleTests.setUp
    run_cycle = cycle_fixtures.CueCycleTests.run_cycle

    def test_too_small_holdout_rejected_before_reservation_or_provider_spending(self):
        for count in (1, 29):
            with self.subTest(count=count):
                manifest = DatasetManifest(self.manifest.discovery, self.manifest.selection,
                                           self.manifest.holdout[:count])
                tasks = [ExperimentTask(t, 'instruction:' + t, 'right') for t in manifest.holdout]
                with patch.object(self.cce, 'reserve_study') as reserve:
                    with self.assertRaisesRegex(ValueError, 'at least 30 heldout pairs'):
                        self.run_cycle(manifest=manifest, holdout_tasks=tasks)
                reserve.assert_not_called()
                self.assertEqual(self.discovery_payloads, [])
                self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
