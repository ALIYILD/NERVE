"""Real scoped authority and private SQLite; synthetic fixture episodes only."""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from nerve_awim.memory_gateway import experience_store_v2 as s
from nerve_awim.memory_gateway.gateway import MemoryGateway
from nerve_awim.memory_gateway.contracts import MemoryScope
from nerve_awim.memory_v18 import MemoryAuthority,TrustedMemoryLedger


def episode(index):
    return dict(episode_id=f'format-{index}',context_hash='a'*64,agent='model-research',candidate_id='constrained',
        policy_version='b'*64,inputs_hash='c'*64,action='registered query',output='raw result',
        evaluator_verdict='strict_incorrect',format_ok=False,evidence_ok=None,real_world_outcome=None,
        outcome_source='verified-format-receipt',timestamps=None,source_sha256={'source.py':'d'*64},
        stratum='supported-measurement',failure_class='format_failure',synthetic_only=True,
        source_kind='scientific_format_probe_v1',schema_ok=False,source_receipt_sha256='e'*64,source_ordinal=index)


class ExperienceStoreV2Tests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        self.auth=MemoryAuthority();self.actor=self.auth.issue('tenant','agent',permissions=('read','propose'))
        self.scope=MemoryScope('tenant','agent','format-episodes')
        self.gateway=MemoryGateway(TrustedMemoryLedger(self.root/'memory.sqlite',self.auth))
        self.store=s.ExperienceStoreV2(self.root/'episodes.sqlite',self.gateway,self.scope)
        self.store.initialize(self.actor)

    def test_four_rows_original_schema_persisted_and_repeat_unchanged(self):
        rows=[episode(i) for i in range(4)];snapshot=copy.deepcopy(rows)
        self.assertEqual(self.store.append_many(self.actor,rows)['added'],4)
        self.assertEqual(rows,snapshot)
        self.assertEqual(self.store.query(self.actor)['episodes'],rows)
        before=self.store.path.read_bytes();mtime=self.store.path.stat().st_mtime_ns
        restart=s.ExperienceStoreV2(self.store.path,self.gateway,self.scope)
        self.assertEqual(restart.append_many(self.actor,rows)['added'],0)
        self.assertEqual(before,self.store.path.read_bytes());self.assertEqual(mtime,self.store.path.stat().st_mtime_ns)
        with sqlite3.connect(self.store.path) as db:
            payloads=[json.loads(r[0]) for r in db.execute('SELECT payload FROM episodes')]
        self.assertTrue(all(r['source_kind']=='scientific_format_probe_v1' for r in payloads))
        self.assertEqual([r['source_ordinal'] for r in payloads],list(range(4)))

    def test_v1_records_and_wrong_schema_origin_types_rejected(self):
        row=episode(0)
        old={k:v for k,v in row.items() if k in s.legacy.FIELDS};old['source_kind']='scientific_validation_v1'
        with self.assertRaises(ValueError):self.store.append_many(self.actor,[old])
        for key,value in [('schema_ok',1),('source_ordinal',True),('source_ordinal',4),('source_ordinal',-1),
                          ('source_receipt_sha256','bad'),('source_kind','scientific_validation_v1'),
                          ('synthetic_only',False),('real_world_outcome','ACCEPT_AS_IS')]:
            bad=dict(row);bad[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):self.store.append_many(self.actor,[bad])
        self.assertEqual(self.store.status(self.actor)['count'],0)

    def test_existing_v1_store_is_degraded_not_normalized_or_migrated(self):
        path=self.root/'legacy.sqlite';old=s.legacy.ExperienceStore(path,self.gateway,self.scope);old.initialize(self.actor)
        row={k:v for k,v in episode(0).items() if k in s.legacy.FIELDS};row['source_kind']='scientific_validation_v1'
        old.append_many(self.actor,[row]);before=path.read_bytes()
        new=s.ExperienceStoreV2(path,self.gateway,self.scope)
        self.assertEqual(new.status(self.actor)['status'],'degraded')
        with self.assertRaises(ValueError):new.query(self.actor)
        with self.assertRaises(ValueError):new.append_many(self.actor,[episode(1)])
        self.assertEqual(path.read_bytes(),before)

    def test_atomic_conflicting_duplicate_and_bad_batch_rollback(self):
        self.store.append_many(self.actor,[episode(0)])
        changed=episode(0);changed['schema_ok']=True
        with self.assertRaises(ValueError):self.store.append_many(self.actor,[episode(1),changed])
        bad=episode(2);bad['source_ordinal']=5
        with self.assertRaises(ValueError):self.store.append_many(self.actor,[episode(1),bad])
        self.assertEqual(self.store.query(self.actor)['episodes'],[episode(0)])

    def test_tampered_payload_index_tail_and_guards_degraded(self):
        for mutation in ('payload','index','tail','guard'):
            path=self.root/(mutation+'.sqlite');store=s.ExperienceStoreV2(path,self.gateway,self.scope);store.initialize(self.actor)
            store.append_many(self.actor,[episode(0),episode(1)])
            with sqlite3.connect(path) as db:
                if mutation=='tail':
                    db.execute('DROP TRIGGER episodes_no_delete');db.execute('DELETE FROM episodes WHERE sequence=2');db.execute(s.TRIGGERS['episodes_no_delete'])
                else:
                    db.execute('DROP TRIGGER episodes_no_update')
                    if mutation=='payload':db.execute("UPDATE episodes SET payload='{}' WHERE sequence=1")
                    if mutation=='index':db.execute("UPDATE episodes SET candidate_id='other' WHERE sequence=1")
                    if mutation!='guard':db.execute(s.TRIGGERS['episodes_no_update'])
            self.assertEqual(store.status(self.actor)['status'],'degraded')
            with self.assertRaises(ValueError):store.query(self.actor)
            with self.assertRaises(FileExistsError):store.initialize(self.actor)

    def test_authorization_cross_scope_revocation_and_commit_recheck(self):
        foreign=self.auth.issue('other','agent',permissions=('read','propose'))
        with self.assertRaises(PermissionError):self.store.append_many(foreign,[episode(0)])
        wrong=s.ExperienceStoreV2(self.store.path,self.gateway,MemoryScope('tenant','agent','other'))
        with self.assertRaises(ValueError):wrong.query(self.actor)
        original=self.store._validate
        def revoke(db):
            result=original(db);self.auth.revoke(self.actor);return result
        with patch.object(self.store,'_validate',side_effect=revoke):
            with self.assertRaises(PermissionError):self.store.append_many(self.actor,[episode(0)])
        actor=self.auth.issue('tenant','agent',permissions=('read',))
        self.assertEqual(self.store.query(actor)['count'],0)

    def test_private_stable_export_retains_v2_fields(self):
        self.store.append_many(self.actor,[episode(0)])
        path=self.root/'episodes.jsonl';report=self.store.export(self.actor,path)
        before=path.read_bytes();mtime=path.stat().st_mtime_ns
        row=json.loads(before);self.assertEqual(row,episode(0))
        self.assertEqual(path.stat().st_mode&0o777,0o600)
        self.assertFalse(self.store.export(self.actor,path)['rewritten'])
        self.assertEqual(before,path.read_bytes());self.assertEqual(mtime,path.stat().st_mtime_ns)
        self.assertEqual(report['manifest']['count'],1)

    def test_disabled_no_io_and_missing_no_implicit_initialization(self):
        missing=s.ExperienceStoreV2(self.root/'missing.sqlite',self.gateway,self.scope)
        self.assertEqual(missing.append_many(self.actor,[episode(0)])['reason'],'no_data')
        self.assertFalse(missing.path.exists())
        missing.enabled=False
        with patch.object(self.gateway,'_require',side_effect=AssertionError('no IO')):
            self.assertEqual(missing.query(None)['status'],'off')
            self.assertEqual(missing.append_many(None,[])['status'],'off')
            self.assertEqual(missing.initialize(None)['status'],'off')
            self.assertEqual(missing.export(None,self.root/'off.jsonl')['status'],'off')

    def test_concurrent_four_source_rows_preserve_chain(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda i:self.store.append_many(self.actor,[episode(i)]),range(4)))
        self.assertEqual(self.store.status(self.actor)['count'],4)
        self.assertEqual({r['source_ordinal'] for r in self.store.query(self.actor)['episodes']},set(range(4)))


if __name__=='__main__':unittest.main()
