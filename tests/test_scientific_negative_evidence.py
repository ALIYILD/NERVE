"""Fabricated adjudications exist only in isolated temporary test fixtures."""
from concurrent.futures import ThreadPoolExecutor
import copy
from pathlib import Path
import sqlite3
import tempfile
import unittest
from nerve_awim.memory_gateway import scientific_negative_evidence as s
from nerve_awim.memory_gateway import scientific_candidates as candidates
from nerve_awim.memory_gateway.experience_store import ExperienceStore
from nerve_awim.memory_gateway.gateway import MemoryGateway
from nerve_awim.memory_gateway.contracts import MemoryScope
from nerve_awim.memory_v18 import MemoryAuthority,TrustedMemoryLedger


def episode(index,output='wrong output'):
    return dict(episode_id=f'episode-{index}',context_hash='a'*64,agent='model-research',candidate_id='trusted_task',
        policy_version='b'*64,inputs_hash='c'*64,action='registered query',output=output,
        evaluator_verdict='strict_incorrect',format_ok=False,evidence_ok=None,real_world_outcome=None,
        outcome_source='verified-receipt',timestamps=None,source_sha256={'source.py':'d'*64},stratum='conflict',
        failure_class='conflict_non_abstaining',synthetic_only=True,source_kind='scientific_validation_v1')


def receipt(proposal):
    report=dict(schema='scientific_rejection_report_v1',candidate_sha256=proposal['candidate_sha256'],
        hypothesis_sha256=proposal['hypothesis_sha256'],verdict='evaluated_rejected',metrics={'synthetic_fixture_correct':0})
    return dict(candidate_sha256=proposal['candidate_sha256'],hypothesis_sha256=proposal['hypothesis_sha256'],
        verdict='evaluated_rejected',evaluator_id='test-host',model_digest='e'*64,task_bank_sha256='f'*64,
        reason='Synthetic unit-test rejection fixture; no actual evaluated candidate.',study_report=report,study_report_sha256=s._hash(report))


class ScientificNegativeEvidenceTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        self.auth=MemoryAuthority();self.actor=self.auth.issue('tenant','agent',permissions=('read','propose','approve'))
        self.reader=self.auth.issue('tenant','agent',permissions=('read',))
        self.gateway=MemoryGateway(TrustedMemoryLedger(self.root/'memory.sqlite',self.auth))
        self.scope=MemoryScope('tenant','agent','rejections')
        self.store=ExperienceStore(self.root/'episodes.sqlite',self.gateway,MemoryScope('tenant','agent','episodes'))
        self.store.initialize(self.actor);self.store.append_many(self.actor,[episode(1)])
        self.journal=s.NegativeEvidenceJournal(self.root/'rejections.sqlite',self.gateway,self.scope,self.store)
        self.journal.initialize(self.actor)

    def proposal(self):return candidates.propose(self.store,self.actor)['proposals'][0]
    def reject(self,proposal=None):
        proposal=self.proposal() if proposal is None else proposal
        return self.journal.record_rejection(self.actor,proposal,receipt(proposal))

    def test_exact_rejection_and_task_bank_change_do_not_bypass(self):
        p=self.proposal();self.reject(p)
        for bank in (None,'1'*64):
            result=self.journal.filter(self.reader,[p],task_bank_sha256=bank)
            self.assertEqual(result['allowed'],[]);self.assertEqual(len(result['blocked']),1)
            self.assertFalse(result['new_bank_exception_verified'])

    def test_idempotent_persisted_replay_no_rewrite(self):
        p=self.proposal();first=self.reject(p)
        before=self.journal.path.read_bytes();mtime=self.journal.path.stat().st_mtime_ns
        restarted=s.NegativeEvidenceJournal(self.journal.path,self.gateway,self.scope,self.store)
        repeat=restarted.record_rejection(self.actor,p,receipt(p))
        self.assertFalse(repeat['added']);self.assertEqual(first['receipt_id'],repeat['receipt_id'])
        self.assertEqual(before,self.journal.path.read_bytes());self.assertEqual(mtime,self.journal.path.stat().st_mtime_ns)

    def test_semantically_renamed_evidence_cannot_bypass(self):
        self.reject()
        renamed=episode(2);renamed['timestamps']={'imported':123};renamed['source_sha256']={'renamed.py':'1'*64}
        renamed['candidate_id']='renamed';renamed['policy_version']='2'*64
        self.store.append_many(self.actor,[renamed])
        result=self.journal.filter(self.reader,[self.proposal()])
        self.assertEqual(result['allowed'],[])

    def test_new_members_or_hash_changes_in_existing_cluster_do_not_waive(self):
        self.reject()
        changed=episode(2,'new incorrect measurement');changed['inputs_hash']='1'*64;changed['context_hash']='2'*64
        self.store.append_many(self.actor,[changed])
        self.assertEqual(self.journal.filter(self.reader,[self.proposal()])['allowed'],[])

    def test_old_alternative_cluster_is_not_new_evidence(self):
        row=episode(2);row['stratum']='entity-decoy';row['failure_class']='format_failure'
        self.store.append_many(self.actor,[row]);self.reject()
        cluster=next(c for c in candidates._clusters(self.store.query(self.reader)['episodes']) if c['stratum']=='entity-decoy')
        p=candidates.register_hypothesis(candidates.SPACE['conflict_check'],cluster,
            store_head=self.store.query(self.reader)['head'],mode='enumeration_fallback')
        self.assertEqual(self.journal.filter(self.reader,[p])['allowed'],[])

    def test_new_cluster_key_allows_registered_enumeration(self):
        self.reject()
        row=episode(2);row['stratum']='entity-decoy';row['failure_class']='format_failure'
        self.store.append_many(self.actor,[row])
        clusters=candidates._clusters(self.store.query(self.reader)['episodes'])
        cluster=next(c for c in clusters if c['stratum']=='entity-decoy')
        p=candidates.register_hypothesis(candidates.SPACE['conflict_check'],cluster,
            store_head=self.store.query(self.reader)['head'],mode='enumeration_fallback')
        self.assertEqual(len(self.journal.filter(self.reader,[p])['allowed']),1)
        self.reject(p)
        # Must satisfy every matching rejection; new to the first is old to the second.
        result=self.journal.filter(self.reader,[p])
        self.assertEqual(result['allowed'],[])
        self.assertEqual(len(result['blocked'][0]['matched_receipt_ids']),1)

    def test_typed_field_distance_one_without_registering_invalid_candidate(self):
        original=dict(candidates.SPACE['conflict_check']);neighbor=dict(original)
        neighbor['conflict_detection']=False
        self.assertEqual(s.candidate_distance(original,neighbor),1)
        self.assertEqual(s.candidate_distance(original,original),0)
        with self.assertRaises(ValueError):candidates.validate_config(neighbor)
        invalid=dict(original);invalid['conflict_detection']=1
        with self.assertRaises(ValueError):s.candidate_distance(original,invalid)
        configurations=list(candidates.SPACE.values())
        for i,left in enumerate(configurations):
            for right in configurations[i+1:]:self.assertGreaterEqual(s.candidate_distance(left,right),2)

    def test_filter_binds_snapshot_even_when_unrelated_rejection_does_not_block(self):
        p=self.proposal();before=self.journal.filter(self.reader,[p])
        unrelated=candidates.register_hypothesis(candidates.SPACE['format_contract'],p['hypothesis']['cluster'],
            store_head=p['store_head'],mode='enumeration_fallback')
        self.reject(unrelated)
        after=self.journal.filter(self.reader,[p])
        self.assertEqual(before['allowed'],after['allowed'])
        self.assertNotEqual(before['journal_head'],after['journal_head'])
        self.assertEqual(after['rejection_count'],before['rejection_count']+1)

    def test_invalid_or_non_efficacy_receipts_rejected(self):
        p=self.proposal()
        for mutation in ('insufficient_power','transport_failed','identity','report','reporthash'):
            r=receipt(p)
            if mutation in ('insufficient_power','transport_failed'):r['verdict']=mutation
            elif mutation=='identity':r['candidate_sha256']='0'*64
            elif mutation=='report':r['study_report']['verdict']='insufficient_power';r['study_report_sha256']=s._hash(r['study_report'])
            else:r['study_report_sha256']='0'*64
            with self.assertRaises(ValueError):self.journal.record_rejection(self.actor,p,r)
        self.assertEqual(self.journal.inspect(self.reader)['count'],0)

    def test_missing_and_corrupt_journal_allow_nothing(self):
        p=self.proposal()
        absent=s.NegativeEvidenceJournal(self.root/'absent.sqlite',self.gateway,self.scope,self.store)
        self.assertEqual(absent.filter(self.reader,[p])['allowed'],[])
        self.assertFalse(absent.path.exists())
        self.journal.path.write_bytes(b'corrupt')
        self.assertEqual(self.journal.filter(self.reader,[p])['status'],'degraded')
        with self.assertRaises(FileExistsError):self.journal.initialize(self.actor)

    def test_integrity_tail_and_scope_binding(self):
        self.reject()
        other=s.NegativeEvidenceJournal(self.journal.path,self.gateway,MemoryScope('tenant','agent','other'),self.store)
        self.assertEqual(other.filter(self.reader,[self.proposal()])['status'],'degraded')
        with sqlite3.connect(self.journal.path) as db:
            db.execute('DROP TRIGGER reject_no_delete');db.execute('DELETE FROM rejections');db.execute(s.TRIGGERS['reject_no_delete'])
        self.assertEqual(self.journal.inspect(self.reader)['status'],'degraded')

    def test_authorization_revocation_and_concurrent_idempotent_writes(self):
        p=self.proposal()
        with self.assertRaises(PermissionError):self.journal.record_rejection(self.reader,p,receipt(p))
        foreign=self.auth.issue('other','agent',permissions=('read','approve'))
        with self.assertRaises(PermissionError):self.journal.filter(foreign,[p])
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(lambda _:self.reject(p),range(4)))
        self.assertEqual(sum(row['added'] for row in results),1)
        self.assertEqual(self.journal.inspect(self.reader)['count'],1)
        self.auth.revoke(self.reader)
        with self.assertRaises(PermissionError):self.journal.inspect(self.reader)


if __name__=='__main__':unittest.main()
