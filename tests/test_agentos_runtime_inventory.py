"""Offline inventory contracts; no hardware probing or model generation."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from dataclasses import asdict

from nerve_awim.cue_engine import ModelProfile
from nerve_awim.cue_evaluation import ModelParity

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import agentos_runtime_inventory as inventory


class RuntimeInventoryTests(unittest.TestCase):
    def binding(self):
        profile = ModelProfile('local', 'model', 'revision', 'tokenizer', 'tok-rev', ('instruction',), 'template')
        model = ModelParity('local', 'model', 'revision', 'tokenizer', 'tok-rev', 'template', 'sampling', 0, 128, 'context', profile.key)
        return {'profile': asdict(profile), 'model': asdict(model), 'adapter_id': 'local',
                'adapter_revision': 'a'*64, 'daily_call_limit':80, 'max_job_calls':77,
                'identity': {'unexpected_private_payload':'never expose'}}

    def test_unconfigured_does_not_inspect_or_probe(self):
        with patch.object(inventory.local, '_config', return_value=None), patch.object(inventory.local, 'inspect_binding') as inspect, patch.object(inventory, 'observe_hardware') as hardware:
            value = inventory.inspect_runtime(object())
        inspect.assert_not_called(); hardware.assert_not_called()
        self.assertEqual(value['runtimes'], [])
        self.assertEqual(value['model_calls'], 0)

    def test_disabled_configuration_can_be_inspected_without_selection(self):
        with patch.object(inventory.local, '_config', return_value={'enabled':False}), patch.object(inventory.local, 'inspect_binding', return_value=self.binding()), patch.object(inventory, 'observe_hardware', return_value={'hardware_observation_digest':'b'*64}):
            value = inventory.inspect_runtime(object())
        self.assertEqual(value['status'], 'observed')
        runtime = value['runtimes'][0]
        self.assertFalse(runtime['research_enabled'])
        self.assertFalse(runtime['eligible_for_automatic_selection'])
        self.assertFalse(value['activation_authorized'])
        self.assertNotIn('private_payload', str(value))
        self.assertIsNone(runtime['measured_cost_usd'])

    def test_binding_drift_rejected_and_error_redacted(self):
        binding = self.binding(); binding['model']['revision'] = 'drift'
        for supplied in (binding, RuntimeError('PRIVATE MODEL RESPONSE')):
            with patch.object(inventory.local, '_config', return_value={'enabled':True}), patch.object(inventory.local, 'inspect_binding', **({'side_effect':supplied} if isinstance(supplied, Exception) else {'return_value':supplied})):
                value = inventory.inspect_runtime(object())
            self.assertEqual(value['status'], 'inspection_unavailable')
            self.assertNotIn('PRIVATE', str(value))

    def test_hardware_unknown_does_not_invent_gpu_or_memory(self):
        with patch.object(inventory.os, 'cpu_count', return_value=None), patch.object(inventory.os, 'sysconf', side_effect=ValueError), patch.object(inventory.platform, 'system', return_value='Darwin'), patch.object(inventory.platform, 'release', return_value='25'), patch.object(inventory.platform, 'machine', return_value='arm64'):
            value = inventory.observe_hardware()
        self.assertIsNone(value['identity']['physical_memory_bytes'])
        self.assertIsNone(value['identity']['logical_cpus'])
        self.assertIsNone(value['accelerator'])
        self.assertFalse(value['identity_attested'])

    def test_resource_snapshot_not_part_of_stable_characteristic_hash(self):
        values={'SC_PAGE_SIZE':4096,'SC_PHYS_PAGES':1024,'SC_AVPHYS_PAGES':512}
        with patch.object(inventory.os, 'sysconf', side_effect=lambda key:values[key]), patch.object(inventory.os, 'cpu_count', return_value=8):
            first=inventory.observe_hardware(); values['SC_AVPHYS_PAGES']=256
            second=inventory.observe_hardware()
        self.assertEqual(first['hardware_observation_digest'],second['hardware_observation_digest'])
        self.assertNotEqual(first['free_physical_memory_bytes'], second['free_physical_memory_bytes'])
        self.assertEqual(first['identity']['physical_memory_bytes'],4194304)
        self.assertIsNone(first['allocatable_memory_bytes'])

    def test_zero_free_pages_remains_measured_zero(self):
        values={'SC_PAGE_SIZE':4096,'SC_PHYS_PAGES':1024,'SC_AVPHYS_PAGES':0}
        with patch.object(inventory.os, 'sysconf', side_effect=lambda key:values[key]):
            value=inventory.observe_hardware()
        self.assertEqual(value['free_physical_memory_bytes'],0)
        self.assertIsNone(value['allocatable_memory_bytes'])


if __name__ == '__main__': unittest.main()
