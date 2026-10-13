"""Bridge commands delegate to existing host adapters, without implicit opt-in."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import agentos_bridge as bridge
import agentos_runtime_inventory as inventory


class GenerationDispatchBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def call(self,argv):
        with patch.object(sys,'argv',['bridge',*argv,'--state',self.tmp.name]),redirect_stdout(io.StringIO()) as output:
            bridge.main()
        return json.loads(output.getvalue())

    def test_inventory_does_not_inspect_or_generate_when_not_configured(self):
        with patch.object(inventory.local,'inspect_binding',side_effect=AssertionError('no local model access')):
            result=self.call(['runtime-inventory'])
        self.assertEqual(result['model_calls'],0)
        self.assertFalse(result['selection_performed'])
        self.assertFalse(result['activation_authorized'])

    def test_local_run_requires_explicit_profile_and_exact_request(self):
        with self.assertRaises(ValueError):
            self.call(['generation-local-scope'])
        path=Path(self.tmp.name)/'task.json'
        path.write_text(json.dumps({'snapshot_id':'a'*64,'task':{},'approve':True}))
        with self.assertRaises(ValueError):
            self.call(['generation-local-run','--profile','local-handoff-research','--task',str(path)])

    def test_local_dispatch_preserves_false_opt_in(self):
        import agentos_generation_local as local
        path=Path(self.tmp.name)/'task.json'
        path.write_text(json.dumps({'snapshot_id':'a'*64,'task':{}}))
        with patch.object(local,'run',return_value={'provider_calls':0}) as run:
            self.call(['generation-local-run','--profile','local-handoff-research','--task',str(path)])
        self.assertFalse(run.call_args.kwargs['allow_local_inference'])


if __name__=='__main__':
    unittest.main()
