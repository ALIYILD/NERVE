import copy
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from nerve_awim.memory_gateway.experience_store import ExperienceStore,TRIGGERS
from nerve_awim.memory_gateway.gateway import MemoryGateway
from nerve_awim.memory_gateway.contracts import MemoryScope
from nerve_awim.memory_v18 import MemoryAuthority,TrustedMemoryLedger


def episode(index):
    return dict(episode_id=f'episode-{index}',context_hash='a'*64,agent='model-research',candidate_id='trusted_task',
        policy_version='b'*64,inputs_hash='c'*64,action='registered synthetic query',output='ABSTAIN',
        evaluator_verdict='strict_correct',format_ok=True,evidence_ok=True,real_world_outcome=None,
        outcome_source='verified-receipt',timestamps=None,source_sha256={'source.py':'d'*64},
        stratum='conflict',failure_class='none',synthetic_only=True,source_kind='scientific_validation_v1')


class ExperienceStoreTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        self.auth=MemoryAuthority();self.actor=self.auth.issue('tenant','agent',permissions=('read','propose'))
        self.scope=MemoryScope('tenant','agent','episodes')
        self.gateway=MemoryGateway(TrustedMemoryLedger(self.root/'memory.sqlite',self.auth))
        self.store=ExperienceStore(self.root/'episodes.sqlite',self.gateway,self.scope)
        self.store.initialize(self.actor)

    def test_atomic_batch_exact_replay_and_filtered_queries(self):
        rows=[episode(i) for i in range(16)];rows[0]['failure_class']='conflict_non_abstaining'
        result=self.store.append_many(self.actor,rows);self.assertEqual(result['added'],16)
        before=self.store.path.read_bytes();mtime=self.store.path.stat().st_mtime_ns
        repeat=self.store.append_many(self.actor,rows);self.assertEqual(repeat['added'],0)
        self.assertEqual(before,self.store.path.read_bytes());self.assertEqual(mtime,self.store.path.stat().st_mtime_ns)
        selected=self.store.query(self.actor,stratum='conflict',candidate_id='trusted_task',failure_class='conflict_non_abstaining')
        self.assertEqual(selected['episodes'],rows[:1])
        self.assertEqual(self.store.status(self.actor)['count'],16)

    def test_conflicting_duplicate_rolls_back_entire_batch(self):
        self.store.append_many(self.actor,[episode(1)])
        bad=episode(1);bad['output']='changed'
        with self.assertRaisesRegex(ValueError,'conflicting'):self.store.append_many(self.actor,[episode(2),bad])
        self.assertEqual(self.store.query(self.actor)['episodes'],[episode(1)])

    def test_append_only_sql_triggers(self):
        self.store.append_many(self.actor,[episode(1)])
        with sqlite3.connect(self.store.path) as db:
            for sql in ('DELETE FROM episodes','UPDATE episodes SET payload=payload'):
                with self.assertRaises(sqlite3.IntegrityError):db.execute(sql)

    def test_deleted_tail_modified_payload_and_missing_tables_degraded(self):
        for mutation in ('delete','modify','missing'):
            with self.subTest(mutation=mutation):
                store=ExperienceStore(self.root/(mutation+'.sqlite'),self.gateway,self.scope);store.initialize(self.actor)
                store.append_many(self.actor,[episode(1),episode(2)])
                with sqlite3.connect(store.path) as db:
                    if mutation=='missing':db.execute('DROP TABLE metadata')
                    else:
                        name='episodes_no_delete' if mutation=='delete' else 'episodes_no_update'
                        db.execute('DROP TRIGGER '+name)
                        db.execute('DELETE FROM episodes WHERE sequence=2' if mutation=='delete' else "UPDATE episodes SET payload='{}' WHERE sequence=1")
                        db.execute(TRIGGERS[name])
                self.assertEqual(store.status(self.actor)['status'],'degraded')
                with self.assertRaises((ValueError,sqlite3.Error)):store.query(self.actor)
                with self.assertRaises((ValueError,sqlite3.Error)):store.append_many(self.actor,[episode(3)])
                with self.assertRaises(FileExistsError):store.initialize(self.actor)

    def test_deeply_nested_corrupt_json_reports_degraded_and_refuses_access(self):
        self.store.append_many(self.actor,[episode(1)])
        with sqlite3.connect(self.store.path) as db:
            db.execute('DROP TRIGGER episodes_no_update')
            db.execute('UPDATE episodes SET payload=?',('['*2000+'0'+']'*2000,))
            db.execute(TRIGGERS['episodes_no_update'])
        before=self.store.path.read_bytes()
        self.assertEqual(self.store.status(self.actor)['status'],'degraded')
        with self.assertRaisesRegex(ValueError,'^(malformed_episode_payload|exact_episode_schema_required)$'):self.store.query(self.actor)
        with self.assertRaisesRegex(ValueError,'^(malformed_episode_payload|exact_episode_schema_required)$'):self.store.append_many(self.actor,[episode(2)])
        self.assertEqual(before,self.store.path.read_bytes())

    def test_corrupt_file_never_reinitializes(self):
        self.store.path.write_bytes(b'broken sqlite')
        self.assertEqual(self.store.status(self.actor)['status'],'degraded')
        with self.assertRaises(FileExistsError):self.store.initialize(self.actor)
        self.assertEqual(self.store.path.read_bytes(),b'broken sqlite')

    def test_concurrent_appends_preserve_single_hash_chain(self):
        def write(i):return self.store.append_many(self.actor,[episode(i)])
        with ThreadPoolExecutor(max_workers=4) as executor:list(executor.map(write,range(16)))
        self.assertEqual(self.store.status(self.actor)['count'],16)
        self.assertEqual({r['episode_id'] for r in self.store.query(self.actor)['episodes']},{f'episode-{i}' for i in range(16)})

    def test_disabled_never_reads_writes_or_checks_database_authority(self):
        disabled=ExperienceStore(self.root/'absent.sqlite',self.gateway,self.scope,enabled=False)
        with patch.object(self.gateway,'_require',side_effect=AssertionError('IO forbidden')):
            for call in (lambda:disabled.initialize(None),lambda:disabled.append_many(None,[]),lambda:disabled.query(None),lambda:disabled.status(None),lambda:disabled.export(None,self.root/'export.jsonl')):
                self.assertEqual(call()['status'],'off')
        self.assertFalse(disabled.path.exists());self.assertFalse((self.root/'export.jsonl').exists())

    def test_missing_no_data_requires_explicit_initialize(self):
        store=ExperienceStore(self.root/'missing.sqlite',self.gateway,self.scope)
        for result in (store.status(self.actor),store.query(self.actor),store.append_many(self.actor,[episode(1)])):
            self.assertEqual(result['reason'],'no_data')
        self.assertFalse(store.path.exists())

    def test_auth_cross_scope_revocation_and_readonly(self):
        foreign=self.auth.issue('other','agent',permissions=('read','propose'))
        with self.assertRaises(PermissionError):self.store.query(foreign)
        reader=self.auth.issue('tenant','agent',permissions=('read',))
        with self.assertRaises(PermissionError):self.store.append_many(reader,[episode(1)])
        other=ExperienceStore(self.store.path,self.gateway,MemoryScope('tenant','agent','other'))
        with self.assertRaises(ValueError):other.query(self.actor)
        self.auth.revoke(self.actor)
        with self.assertRaises(PermissionError):self.store.query(self.actor)

    def test_schema_bounds_and_unknown_historical_evidence(self):
        row=episode(1);row['evidence_ok']=None;row['format_ok']=False
        self.store.append_many(self.actor,[row])
        for key,value in [('synthetic_only',False),('source_kind','clinical'),('real_world_outcome','ACCEPT_AS_IS'),('output','x'*16385),('format_ok',1)]:
            bad=episode(2);bad[key]=value
            with self.assertRaises(ValueError):self.store.append_many(self.actor,[bad])
        self.assertEqual(self.store.query(self.actor)['count'],1)

    def test_export_rejects_incomplete_symlink_or_public_artifacts(self):
        self.store.append_many(self.actor,[episode(1)])
        path=self.root/'partial.jsonl';path.write_text('partial')
        with self.assertRaises(ValueError):self.store.export(self.actor,path)
        path=self.root/'private.jsonl';self.store.export(self.actor,path)
        path.chmod(0o644)
        with self.assertRaises(ValueError):self.store.export(self.actor,path)
        path.chmod(0o600);link=self.root/'linked.jsonl';link.symlink_to(path)
        Path(str(link)+'.manifest.json').symlink_to(Path(str(path)+'.manifest.json'))
        with self.assertRaises(ValueError):self.store.export(self.actor,link)

    def test_interrupted_manifest_publication_reconciles_only_exact_payload(self):
        self.store.append_many(self.actor,[episode(1)])
        path=self.root/'interrupted.jsonl';side=Path(str(path)+'.manifest.json')
        original=os.open
        def interrupt(target,*args,**kwargs):
            if Path(target)==side:raise KeyboardInterrupt()
            return original(target,*args,**kwargs)
        journal=self.store.path.read_bytes()
        with patch('nerve_awim.memory_gateway.experience_store.os.open',side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):self.store.export(self.actor,path)
        before=path.read_bytes();mtime=path.stat().st_mtime_ns
        restarted=ExperienceStore(self.store.path,self.gateway,self.scope)
        result=restarted.export(self.actor,path)
        self.assertTrue(result['reconciled']);self.assertFalse(result['rewritten'])
        self.assertEqual(before,path.read_bytes());self.assertEqual(mtime,path.stat().st_mtime_ns)
        self.assertEqual(journal,self.store.path.read_bytes())
        self.assertFalse(restarted.export(self.actor,path)['rewritten'])
        good=self.root/'good.jsonl';restarted.export(self.actor,good)
        self.assertEqual(side.read_bytes(),Path(str(good)+'.manifest.json').read_bytes())

    def test_status_rechecks_revocation_after_validation(self):
        original=self.store._validate
        def revoke(db):
            result=original(db);self.auth.revoke(self.actor);return result
        with patch.object(self.store,'_validate',side_effect=revoke):
            with self.assertRaises(PermissionError):self.store.status(self.actor)

    def test_export_stable_private_hash_manifest_no_overwrite(self):
        self.store.append_many(self.actor,[episode(1),episode(2)])
        path=self.root/'export.jsonl';first=self.store.export(self.actor,path)
        before=path.read_bytes();mtime=path.stat().st_mtime_ns
        second=self.store.export(self.actor,path)
        self.assertFalse(second['rewritten']);self.assertEqual(first['manifest'],second['manifest'])
        self.assertEqual(before,path.read_bytes());self.assertEqual(mtime,path.stat().st_mtime_ns)
        self.assertEqual(path.stat().st_mode&0o777,0o600)
        self.assertEqual(Path(str(path)+'.manifest.json').stat().st_mode&0o777,0o600)
        self.store.append_many(self.actor,[episode(3)])
        with self.assertRaises(ValueError):self.store.export(self.actor,path)
        self.assertEqual(before,path.read_bytes())


if __name__=='__main__':unittest.main()
