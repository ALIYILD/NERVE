"""Generation host/CLI boundaries reuse the memory authority without approval."""
from contextlib import redirect_stdout
from dataclasses import asdict
import io
import json
from hashlib import sha256
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import agentos_bridge as bridge
from nerve_awim.agentos_learning import AgentOSLearning
from nerve_awim.generation_memory import GenerationScope


class GenerationBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.host=AgentOSLearning(self.tmp.name)
        self.scope=asdict(GenerationScope('qa-release','setup','local','v1','runtime1','model1','template1','judge1'))
        self.request=dict(scope=self.scope,text='Verify the endpoint contract before adjusting dependencies.',
                          category='observation',data_class='synthetic',source_id='episode-1',valid_until=int(time.time())+3600)

    def cli(self,action,request,profile='qa-release'):
        path=Path(self.tmp.name)/'input.json'
        path.write_text(json.dumps(request))
        args=['bridge','generation-'+action,'--state',self.tmp.name,'--task',str(path)]
        if profile is not None:
            args.extend(['--profile',profile])
        with patch.object(sys,'argv',args),patch.object(bridge,'native') as native,redirect_stdout(io.StringIO()) as out:
            bridge.main()
        native.assert_not_called()
        return json.loads(out.getvalue())

    def test_cli_pending_approval_restart_and_redacted_inspection(self):
        result=self.cli('propose',self.request)
        self.assertEqual(result['status'],'pending')
        self.assertFalse(result['activation_authorized'])
        mid=result['memory_id']
        freeze=dict(scope=self.scope,memory_ids=[mid],parent_id=None,valid_until=self.request['valid_until'])
        with self.assertRaises(ValueError):
            self.cli('freeze',freeze)
        actor=self.host.actor('qa-release')
        self.host.ledger.decide(actor,mid,approve=True,evaluator_id=self.scope['evaluator_revision'],score=1)
        frozen=self.cli('freeze',freeze)
        query=dict(scope=self.scope,snapshot_id=frozen['snapshot_id'])
        metadata=self.cli('inspect',query)
        self.assertNotIn(self.request['text'],json.dumps(metadata))
        handoff=self.cli('handoff',query)
        self.assertEqual(handoff['notes'][0]['note']['text'],self.request['text'])
        self.assertFalse(handoff['authorization_granted'])
        self.assertEqual(handoff['provider_calls'],0)
        self.host.ledger.revoke(actor,mid,evaluator_id='independent-test')
        with self.assertRaises(ValueError):
            self.cli('handoff',query)
        with sqlite3.connect(self.host.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM nerve_calls').fetchone()[0],0)
        self.assertEqual(self.host.recall('qa-release'),[])

    def test_exact_inputs_and_profile_are_required_without_approval_surface(self):
        for request in ({**self.request,'approved':True},{**self.request,'scope':[]},{'scope':self.scope}):
            with self.assertRaises((ValueError,TypeError)):
                self.cli('propose',request)
        with self.assertRaises(PermissionError):
            self.cli('propose',self.request,profile='research')
        with self.assertRaises(ValueError):
            self.cli('propose',self.request,profile=None)
        with self.assertRaises(ValueError):
            self.host.generation_memory('qa-release','approve',self.request)

    def test_temporary_capability_is_revoked_even_on_failure(self):
        before=len(self.host.authority._issued)
        self.host.generation_memory('qa-release','propose',self.request)
        self.assertEqual(len(self.host.authority._issued),before)
        with self.assertRaises(ValueError):
            self.host.generation_memory('qa-release','freeze',dict(scope=self.scope,memory_ids=[],parent_id=None,valid_until=self.request['valid_until']))
        self.assertEqual(len(self.host.authority._issued),before)

    def test_workspace_restore_cli_uses_reviewed_snapshot_without_overwrite(self):
        from nerve_awim.generation_memory import GenerationMemory
        from nerve_awim.generation_workspace import GenerationWorkspace
        actor=self.host.actor('qa-release')
        memory=GenerationMemory(self.host.ledger)
        scope=GenerationScope(**self.scope)
        mid=self.host.generation_memory('qa-release','propose',self.request)['memory_id']
        self.host.ledger.decide(actor,mid,approve=True,evaluator_id=scope.evaluator_revision)
        snapshot=memory.freeze(actor,scope,memory_ids=[mid],valid_until=self.request['valid_until'])
        root=Path(self.tmp.name).resolve()
        content=b'Public synthetic setup notes.\n'
        (root/'notes.md').write_bytes(content)
        artifacts=GenerationWorkspace(memory)
        ident=artifacts.capture(actor,scope,snapshot_id=snapshot,source_root=root,
            reviewed_manifest={'review_id':'host-test','files':[{'path':'notes.md',
                'sha256':sha256(content).hexdigest(),'data_class':'synthetic'}]})
        request=dict(scope=self.scope,artifact_id=ident,destination_parent=str(root),directory_name='next')
        result=self.cli('workspace-restore',request)
        self.assertFalse(result['activation_authorized'])
        self.assertEqual((root/'next/notes.md').read_bytes(),content)
        with self.assertRaises(OSError):
            self.cli('workspace-restore',request)


if __name__=='__main__':
    unittest.main()
