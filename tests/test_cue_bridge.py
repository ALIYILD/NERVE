"""Installed bridge contracts without starting Hermes or calling a provider."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from nerve_awim.agentos_learning import AgentOSLearning, expected_handoff


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('cce_bridge_under_test', ROOT / 'scripts/agentos_bridge.py')
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


def task():
    return {'id': 'host-observed-1', 'exit_code': 0, 'artifact_exists': True,
            'qa_passed': True, 'memory_written': False}


class CueBridgeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.host = AgentOSLearning(self.directory)

    def test_real_status_cli_needs_no_provider_and_does_not_bootstrap_cues(self):
        # Exercise the actual command parser and state path in a clean process.
        # No credentials or installed Hermes are needed by this local command.
        env = {k: v for k, v in os.environ.items()
               if k in ('PATH', 'HOME', 'LANG', 'LC_ALL', 'TMPDIR')}
        process = subprocess.run(
            [sys.executable, str(ROOT / 'scripts/agentos_bridge.py'), 'cce-status',
             '--state', str(self.directory)],
            env=env, text=True, capture_output=True, timeout=20)
        self.assertEqual(process.returncode, 0, process.stderr)
        status = json.loads(process.stdout)
        self.assertEqual(status, {'enabled': False, 'reason': 'not_configured', 'profiles': {}})
        self.assertEqual(json.loads((self.directory / 'cce-status.json').read_text()), status)
        with sqlite3.connect(self.host.path) as db:
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            calls = db.execute('SELECT COUNT(*) FROM nerve_calls').fetchone()[0]
        self.assertNotIn('cce_candidates', tables)
        self.assertNotIn('gl_state', tables)
        self.assertEqual(calls, 0)

    def test_research_batch_preserves_native_call_contract(self):
        observed = task()
        values = {observed['id']: expected_handoff(observed)}
        with patch.object(bridge, 'native', return_value={'value': values, 'native_hermes': True}) as native:
            output, receipt = bridge.batch(self.host, 'qa-release', [observed], 'Verified lesson.')
        self.assertEqual(output, values)
        self.assertEqual(native.call_args.kwargs, {})
        self.assertIn('Verified lesson.', native.call_args.args[2])
        self.assertNotIn('value', receipt)

    def test_operational_batch_passes_explicit_context(self):
        observed = task()
        with patch.object(bridge, 'native', return_value={'value': {observed['id']: {}}}) as native:
            bridge.batch(self.host, 'qa-release', [observed], cue_context='handoff')
        self.assertEqual(native.call_args.kwargs, {'cue_context': 'handoff'})

    def native_fixture(self, *, operational=True, inspect=False, worker_selected=False):
        (self.directory / 'free-models.json').write_text(json.dumps(['fixture:free']))
        envelope = {'cue': {'text': 'PRIVATE_CUE_SENTINEL'}, 'profile': {'model': 'fixture:free'}}
        host_receipt = {'candidate': 'approved-1', 'envelope_prepared': True,
                        'reason': 'awaiting_worker_attestation'}
        worker_receipt = {'selected': worker_selected,
                          'reason': 'instruction_applied' if worker_selected else 'model_mismatch',
                          'approval_id': 'approved-1' if worker_selected else None}
        process = Mock(returncode=0)
        process.communicate.return_value = (json.dumps({'ok': True, 'value': {}, 'cce': worker_receipt}), '')
        with patch('nerve_awim.cue_host.CueHost') as host_type, \
                patch.object(bridge.subprocess, 'check_output', side_effect=['["/mock/launcher"]', '/mock/python\n']) as resolve, \
                patch.object(bridge.subprocess, 'Popen', return_value=process) as popen:
            host_type.return_value.prepare.return_value = {'envelope': envelope, 'receipt': host_receipt}
            result = bridge.native(self.host, 'qa-release', 'PRIVATE_TASK_SENTINEL',
                                   inspect=inspect, **({'cue_context': 'handoff'} if operational else {}))
            prepare_calls = host_type.return_value.prepare.call_args_list
        self.assertEqual(resolve.call_count, 2)
        self.assertIn(str(ROOT / 'scripts/agentos_hermes_worker.py'), popen.call_args.args[0])
        self.assertEqual(process.communicate.call_args.kwargs['timeout'], 90)
        return result, json.loads(process.communicate.call_args.args[0]), prepare_calls, envelope

    def test_native_carries_envelope_but_persists_only_actual_worker_receipt(self):
        result, request, calls, envelope = self.native_fixture(worker_selected=False)
        self.assertEqual(request['cce'], envelope)
        self.assertEqual(calls[0].args, ('qa-release', 'handoff'))
        self.assertEqual(calls[0].kwargs, {'permission_granted': True})
        self.assertTrue(result['cce_host']['envelope_prepared'])
        self.assertFalse(result['cce']['selected'])
        evidence = (self.directory / 'latest-cce-native.json').read_text()
        self.assertFalse(json.loads(evidence)['cue_applied'])
        self.assertNotIn('PRIVATE_CUE_SENTINEL', evidence)
        self.assertNotIn('PRIVATE_TASK_SENTINEL', evidence)
        self.assertNotIn('PRIVATE_CUE_SENTINEL', json.dumps(result))

    def test_native_records_worker_confirmed_application(self):
        self.native_fixture(worker_selected=True)
        self.assertTrue(json.loads((self.directory / 'latest-cce-native.json').read_text())['cue_applied'])

    def test_research_and_inspection_do_not_prepare_or_send_cues(self):
        for operational, inspect in ((False, False), (True, True)):
            with self.subTest(operational=operational, inspect=inspect):
                result, request, calls, _ = self.native_fixture(operational=operational, inspect=inspect)
                self.assertEqual(calls, [])
                self.assertNotIn('cce', request)
                self.assertNotIn('cce_host', result)
        self.assertFalse((self.directory / 'latest-cce-native.json').exists())

    def test_unknown_operational_context_denied_before_process_or_provider(self):
        with patch.object(bridge.subprocess, 'check_output') as resolve, \
                patch.object(bridge.subprocess, 'Popen') as popen:
            with self.assertRaises(PermissionError):
                bridge.native(self.host, 'qa-release', 'task', cue_context='clinical')
        resolve.assert_not_called()
        popen.assert_not_called()

    def invoke_operation(self, command, *, worker_selected=False):
        observed = task()
        path = self.directory / 'task.json'
        path.write_text(json.dumps(observed))
        info = {'cce_host': {'envelope_prepared': True, 'candidate': 'approved-1'},
                'cce': {'selected': worker_selected, 'approval_id': 'approved-1'}}
        with patch.object(sys, 'argv', ['agentos_bridge.py', command, '--state', str(self.directory),
                                      '--profile', 'qa-release', '--task', str(path)]), \
                patch.object(bridge, 'batch', return_value=({observed['id']: expected_handoff(observed)}, info)) as batch, \
                patch.object(bridge, 'publish'), \
                patch.object(bridge, 'recover_interrupted_repository'), \
                patch('nerve_awim.cue_host.CueHost') as host_type, redirect_stdout(io.StringIO()):
            host_type.return_value.feedback.return_value = {'status': 'approved'}
            host_type.return_value.export_memory.return_value = 'memory-1'
            bridge.main()
            return (batch.call_args, host_type.return_value.feedback.call_args_list,
                    host_type.return_value.export_memory.call_args_list)

    def test_only_operational_run_requests_context_and_host_proposal_is_not_feedback(self):
        for command in ('probe', 'run'):
            with self.subTest(command=command):
                batch_call, feedback, exports = self.invoke_operation(command)
                self.assertEqual(batch_call.kwargs, {'cue_context': 'handoff'} if command == 'run' else {})
                self.assertEqual(feedback, [])
                self.assertEqual(exports, [])
                self.assertNotIn('cce_feedback', json.loads((self.directory / 'latest-native.json').read_text()))

    def test_worker_applied_cue_receives_independent_host_feedback(self):
        _, feedback, exports = self.invoke_operation('run', worker_selected=True)
        self.assertEqual(len(feedback), 1)
        self.assertEqual(feedback[0].args, ('qa-release', 'approved-1'))
        self.assertEqual(feedback[0].kwargs, {'episode_id': task()['id'], 'safe': True, 'correct': True})
        self.assertEqual(len(exports), 1)
        self.assertEqual(exports[0].args, ('qa-release', 'approved-1'))
        receipt = json.loads((self.directory / 'latest-native.json').read_text())
        self.assertEqual(receipt['cce_feedback'], {'status': 'approved', 'memory_id': 'memory-1'})

    def test_replayed_operational_observation_does_not_repeat_feedback_or_memory(self):
        _, first_feedback, first_exports = self.invoke_operation('run', worker_selected=True)
        _, replay_feedback, replay_exports = self.invoke_operation('run', worker_selected=True)
        self.assertEqual(len(first_feedback), 1)
        self.assertEqual(len(first_exports), 1)
        self.assertEqual(replay_feedback, [])
        self.assertEqual(replay_exports, [])
        receipt = json.loads((self.directory / 'latest-native.json').read_text())
        self.assertTrue(receipt['evaluation']['duplicate'])
        self.assertNotIn('cce_feedback', receipt)


if __name__ == '__main__':
    unittest.main()
