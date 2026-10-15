import dataclasses
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from nerve_awim.generation_workspace import GenerationWorkspace
import test_generation_memory as fixtures


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        fixtures.GenerationMemoryTests.setUp(self)
        self.work=GenerationWorkspace(self.store)
        self.mid=fixtures.GenerationMemoryTests.note(self)
        self.sid=fixtures.GenerationMemoryTests.freeze(self,self.mid)
        self.root=Path(self.tmp.name).resolve()/'source';self.root.mkdir()
        self.dest=Path(self.tmp.name).resolve()/'dest';self.dest.mkdir()
        self.source=self.root/'notes.txt';self.source.write_text('Synthetic trial notes.\n')
        self.manifest=dict(review_id='human-review1',files=[dict(path='notes.txt',sha256=sha256(self.source.read_bytes()).hexdigest(),data_class='synthetic')])

    def capture(self):
        return self.work.capture(self.actor,self.scope,snapshot_id=self.sid,source_root=self.root,reviewed_manifest=self.manifest)

    def restore(self,aid,name='next'):
        return self.work.restore(self.actor,self.scope,artifact_id=aid,destination_parent=self.dest,directory_name=name)

    def test_real_process_restart_and_frozen_content(self):
        aid=self.capture();self.source.write_text('Changed after capture')
        script='''import json,sys
from nerve_awim.agentos_learning import AgentOSLearning
from nerve_awim.generation_memory import GenerationMemory,GenerationScope
from nerve_awim.generation_workspace import GenerationWorkspace
h=AgentOSLearning(sys.argv[1]); w=GenerationWorkspace(GenerationMemory(h.ledger))
print(json.dumps(w.restore(h.actor('qa-release'),GenerationScope(**json.loads(sys.argv[2])),artifact_id=sys.argv[3],destination_parent=sys.argv[4],directory_name='next')))'''
        result=subprocess.run([sys.executable,'-c',script,self.tmp.name,json.dumps(dataclasses.asdict(self.scope)),aid,str(self.dest)],check=True,capture_output=True,text=True)
        self.assertEqual(json.loads(result.stdout)['file_count'],1)
        target=self.dest/'next'/'notes.txt'
        self.assertEqual(target.read_text(),'Synthetic trial notes.\n')
        self.assertEqual(target.stat().st_mode & 0o777,0o400)
        self.assertFalse(json.loads(result.stdout)['authorization_granted'])

    def test_drift_and_unprivileged_review_denied(self):
        self.source.write_text('not reviewed')
        with self.assertRaises(ValueError):self.capture()
        reader=self.host.authority.issue('agentos-local','qa-release',permissions=('read','propose'))
        with self.assertRaises(PermissionError):
            self.work.capture(reader,self.scope,snapshot_id=self.sid,source_root=self.root,reviewed_manifest=self.manifest)

    def test_links_traversal_sensitive_paths_and_secret_text_denied(self):
        original=self.source.read_bytes();self.source.unlink()
        outside=Path(self.tmp.name).resolve()/'outside.txt';outside.write_bytes(original)
        self.source.symlink_to(outside)
        with self.assertRaises(OSError):self.capture()
        self.source.unlink();os.link(outside,self.source)
        with self.assertRaises(ValueError):self.capture()
        self.source.unlink();self.source.write_bytes(original)
        for path in ('../outside.txt','/outside.txt','.env','secrets.txt','patient.md'):
            self.manifest['files'][0]['path']=path
            with self.assertRaises(ValueError):self.capture()
        self.manifest['files'][0]['path']='notes.txt';self.source.write_text('password=unsafe')
        self.manifest['files'][0]['sha256']=sha256(self.source.read_bytes()).hexdigest()
        with self.assertRaises(ValueError):self.capture()

    def test_revoked_note_and_artifact_deny_restore(self):
        aid=self.capture()
        self.host.ledger.revoke(self.actor,self.mid,evaluator_id='grader1')
        with self.assertRaises(ValueError):self.restore(aid)
        self.assertEqual(list(self.dest.iterdir()),[])
        # Artifact revocation still works when generation validation cannot pass.
        self.work.revoke(self.actor,self.scope,artifact_id=aid,review_id='review-revoke')
        with self.assertRaises(ValueError):self.restore(aid)

    def test_no_overwrite_and_failed_stage_cleanup(self):
        aid=self.capture();self.restore(aid)
        with self.assertRaises(OSError):self.restore(aid)
        self.assertEqual([p.name for p in self.dest.iterdir()],['next'])
        with patch('nerve_awim.generation_workspace._rename_exclusive',side_effect=OSError('injected failure')):
            with self.assertRaises(OSError):self.restore(aid,'another')
        self.assertEqual([p.name for p in self.dest.iterdir()],['next'])

    def test_artifact_revocation_and_immutable_capture(self):
        import sqlite3
        aid=self.capture()
        with sqlite3.connect(self.host.path) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE generation_artifacts SET payload='{}'")
        self.work.revoke(self.actor,self.scope,artifact_id=aid,review_id='review2')
        with self.assertRaises(ValueError):self.restore(aid)
        self.assertEqual(list(self.dest.iterdir()),[])

    def test_nested_text_restore_and_byte_count_limits(self):
        nested=self.root/'docs';nested.mkdir()
        (nested/'readme.md').write_text('Public synthetic documentation')
        self.manifest['files'][0]=dict(path='docs/readme.md',sha256=sha256((nested/'readme.md').read_bytes()).hexdigest(),data_class='public')
        aid=self.capture();self.restore(aid)
        self.assertEqual((self.dest/'next/docs/readme.md').read_text(),'Public synthetic documentation')
        self.manifest['files']*=9
        with self.assertRaises(ValueError):self.capture()
        self.manifest['files']=self.manifest['files'][:1]
        (nested/'readme.md').write_text('x'*65537)
        self.manifest['files'][0]['sha256']=sha256((nested/'readme.md').read_bytes()).hexdigest()
        with self.assertRaises(ValueError):self.capture()

    def test_scope_and_root_symlink_denied(self):
        aid=self.capture()
        with self.assertRaises(ValueError):
            self.work.restore(self.actor,dataclasses.replace(self.scope,runtime_revision='new'),artifact_id=aid,destination_parent=self.dest,directory_name='next')
        link=Path(self.tmp.name).resolve()/'linked';link.symlink_to(self.dest,target_is_directory=True)
        with self.assertRaises(OSError):
            self.work.restore(self.actor,self.scope,artifact_id=aid,destination_parent=link,directory_name='next')


if __name__=='__main__':unittest.main()
