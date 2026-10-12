"""Native boundary tests: subprocesses mocked, no provider or network access."""
import json
import unittest
from unittest.mock import Mock, patch
import test_cue_host as fixtures
from test_cue_bridge import bridge
from nerve_awim.uncertainty.ledger import Ledger
from nerve_awim.uncertainty.contracts import Claim
from nerve_awim.uncertainty.adapters import UncertaintyAdapter


class NativeUncertaintyTests(unittest.TestCase):
    setUp = fixtures.CueHostTests.setUp
    configure = fixtures.CueHostTests.configure
    approve = fixtures.CueHostTests.approve

    def prepare(self):
        self.approve()
        self.ledger = Ledger(self.adapter._engine)
        self.actor = self.adapter._actor('worker', 'runtime')
        self.claim('primary', True)
        self.uncertainty = UncertaintyAdapter(self.ledger, self.actor, task_id='native-task', dependency_claim_ids=['primary'])
        (self.host.directory/'free-models.json').write_text('["fixture:free"]')

    def claim(self, name, value):
        source = self.ledger.register_source(self.actor, name, {'available': value})
        self.ledger.add_claim(self.actor, Claim(claim_id=name, tenant_id=self.actor.tenant,
            task_id='native-task', subject_ref='fixture', predicate='available', normalized_value=value, **source))
        self.ledger.detect(self.actor, 'native-task')

    def invoke(self, during=None):
        process = Mock(returncode=0)
        def communicate(*args, **kwargs):
            if during: during()
            return json.dumps({'ok': True, 'value': {'summary': 'certain'}, 'uncertainty': {'open_conflict_ids': []}}), ''
        process.communicate.side_effect = communicate
        with patch.object(bridge.subprocess, 'check_output', side_effect=['["/mock/launcher"]', '/mock/python']), patch.object(bridge.subprocess, 'Popen', return_value=process):
            result = bridge.native(self.host, 'worker', 'fixture', cue_context='handoff', uncertainty=self.uncertainty)
        return result, json.loads(process.communicate.call_args.args[0])

    def test_request_companion_preserves_strict_cce_and_host_overwrites_provider_state(self):
        self.prepare()
        result, request = self.invoke()
        self.assertEqual(set(request['cce']), {'profile', 'cue', 'task_type', 'approval_expires'})
        self.assertIn('uncertainty-handoff-v1', request['prompt'])
        self.assertEqual(result['uncertainty']['task_id'], 'native-task')
        self.assertEqual(result['uncertainty']['evidence_refs'], ['primary'])
        self.assertFalse(result['guidance_authority'])

    def test_provider_summary_cannot_erase_conflict_added_in_flight(self):
        self.prepare()
        with self.assertRaises(PermissionError): self.invoke(lambda: self.claim('secondary', False))
        self.assertEqual(len(self.ledger.open_conflicts(self.actor, 'native-task')), 1)

    def test_restart_omission_even_without_cue_context_denied_before_provider(self):
        self.prepare()
        self.invoke()
        with patch.object(bridge.subprocess, 'check_output') as process:
            with self.assertRaises(PermissionError): bridge.native(self.host, 'worker', 'fixture')
        process.assert_not_called()

    def test_initial_conflict_denied_without_provider(self):
        self.prepare()
        self.claim('secondary', False)
        with patch.object(bridge.subprocess, 'check_output') as process:
            with self.assertRaises(PermissionError): bridge.native(self.host, 'worker', 'fixture', uncertainty=self.uncertainty)
        process.assert_not_called()
