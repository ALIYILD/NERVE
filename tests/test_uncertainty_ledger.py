import tempfile
import unittest
from dataclasses import replace
from nerve_awim.governed_learning_v20 import GovernedLearning,LearningAuthority
from nerve_awim.agent_learning_v12 import RegisteredStrategy,AgentTask
from nerve_awim.uncertainty.contracts import Claim,Resolution,Conflict,OPEN
from nerve_awim.uncertainty.ledger import Ledger,StaleRevision
from nerve_awim.uncertainty.resolution import ResolutionService

class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.now=100.
        self.authority=LearningAuthority();self.actor=self.authority.issue('tenant','agent','runtime');self.operator=self.authority.issue('tenant','agent','operator')
        self.engine=GovernedLearning(self.tmp.name+'/state.db',authority=self.authority,strategies=[RegisteredStrategy('read','read',lambda x:x)],judge=lambda t,v:True,contract_revision='uncertainty-test',baseline_routes={'read':'read'})
        self.engine.bootstrap(self.operator);self.ledger=Ledger(self.engine,clock=lambda:self.now)
    def claim(self,cid,value,**kw):
        task=kw.pop('task_id','task');source=self.ledger.register_source(self.actor,'source-'+cid,{'value':value,'cid':cid},lineage=kw.pop('lineage',None))
        claim=Claim(cid,'tenant',task,kw.pop('subject_ref','record'),kw.pop('predicate','status'),value,**source,**kw)
        self.ledger.add_claim(self.actor,claim);return claim
    def conflict(self):
        self.claim('one',True);self.claim('two',False);return self.ledger.detect(self.actor,'task')[0]
    def resolve(self,c):
        service=ResolutionService(self.ledger,predicates={'primary_record_verified':lambda c,claims,sources,r:sources[0]['id']=='source-one'})
        r=Resolution('resolution',c.conflict_id,c.revision,'primary_record_verified',['one'],['two'],[{'source_ref':'source-one','source_revision':'v1'}],'Primary structured fixture inspected','agent','policy-v1')
        return service.resolve(self.operator,r)
    def test_same_context_one_conflict_duplicate_idempotent(self):
        c=self.conflict();again=self.ledger.detect(self.actor,'task');self.assertEqual([x.conflict_id for x in again],[c.conflict_id])
        before=self.ledger.revision(self.actor,'task');claim=self.ledger.claims(self.actor,'task')[0];self.ledger.add_claim(self.actor,claim);self.assertEqual(before,self.ledger.revision(self.actor,'task'))
    def test_entity_time_units_polarity_reconcile(self):
        self.claim('one',1000,units='mg');self.claim('two',1,units='g');self.assertEqual(self.ledger.detect(self.actor,'task'),[])
        self.claim('three',2,units='g',subject_ref='other');self.claim('four',2,units='g',valid_from=10,valid_to=20)
        # Existing unbounded facts overlap; test nonoverlap separately.
        a=self.claim('a',True,task_id='dates',valid_from=0,valid_to=10)
        self.claim('b',False,task_id='dates',valid_from=10,valid_to=20)
        self.assertEqual(self.ledger.detect(self.actor,'dates'),[])
        self.claim('p',True,task_id='polarity');self.claim('q',False,task_id='polarity',polarity=False)
        self.assertEqual(self.ledger.detect(self.actor,'polarity'),[])
    def test_duplicate_sources_share_lineage(self):
        a=self.ledger.register_source(self.actor,'a',{'same':1},lineage='original')
        b=self.ledger.register_source(self.actor,'b',{'same':1},lineage='copy')
        self.assertEqual(a['source_lineage_id'],b['source_lineage_id'])
        self.assertEqual(b,self.ledger.register_source(self.actor,'b',{'same':1},lineage='copy'))
    def test_cross_scope_and_invented_source(self):
        a=self.claim('a',1);other=self.authority.issue('other','agent','runtime')
        with self.assertRaises(PermissionError):self.ledger.add_claim(other,a)
        with self.assertRaises(PermissionError):self.ledger.add_claim(self.actor,replace(a,claim_id='new',source_ref='invented'))
        with self.assertRaises(ValueError):self.ledger.register_source(self.actor,'source-a',{'changed':True})
    def test_resolution_reopen_revision_and_restart(self):
        c=self.conflict();self.ledger.link(self.actor,'task','decision',['one'],['rule'])
        c=self.ledger.get_conflict(self.actor,c.conflict_id);closed=self.resolve(c)
        self.claim('agrees',True);self.assertEqual(self.ledger.get_conflict(self.actor,c.conflict_id).status,'resolved')
        self.claim('contradicts',False)
        opened=self.ledger.get_conflict(self.actor,c.conflict_id);self.assertEqual(opened.status,'reopened');self.assertGreater(opened.revision,closed.revision)
        with self.assertRaises(StaleRevision):self.ledger.transition(self.actor,c.conflict_id,'investigating',expected_revision=closed.revision)
        restarted=Ledger(self.engine);self.assertEqual(restarted.get_conflict(self.actor,c.conflict_id),opened)
        self.assertIn('conflict_reopened',[x['event'] for x in restarted.events(self.actor,'task')])
    def test_unauthorized_or_evidence_free_resolution(self):
        c=self.conflict();service=ResolutionService(self.ledger,predicates={'reviewed_resolution':lambda *args:True})
        r=Resolution('r',c.conflict_id,c.revision,'reviewed_resolution',['one'],['two'],[],'A model said resolved','agent','policy')
        with self.assertRaises(PermissionError):service.resolve(self.actor,r)
        with self.assertRaises(PermissionError):service.resolve(self.operator,r)
        with self.assertRaises(PermissionError):self.ledger.transition(self.actor,c.conflict_id,'resolved',expected_revision=c.revision)
    def test_links_cannot_silently_drop_dependency(self):
        c=self.conflict();self.ledger.link(self.actor,'task','decision',['one'],['rule'])
        with self.assertRaises(PermissionError):self.ledger.link(self.actor,'task','decision',[])
        self.assertEqual(len(self.ledger.open_conflicts(self.actor,'task','decision')),1)
    def test_source_deletion_preserves_history_and_invalidates_revision(self):
        c=self.conflict();old=self.ledger.revision(self.actor,'task');self.ledger.delete_source(self.operator,'source-one','v1')
        with self.assertRaises(PermissionError):self.ledger.source(self.actor,'source-one','v1')
        self.assertGreater(self.ledger.revision(self.actor,'task'),old);self.assertEqual(len(self.ledger.claims(self.actor,'task')),2)
    def test_migration_preserves_existing_governed_rows(self):
        trainer=self.authority.issue('tenant','agent','trainer');self.engine.learn_from_task(trainer,AgentTask('historic','read',{'a':1}))
        with self.engine._db() as con:before=[tuple(r) for r in con.execute('SELECT * FROM gl_tasks')]
        Ledger(self.engine)
        with self.engine._db() as con:self.assertEqual(before,[tuple(r) for r in con.execute('SELECT * FROM gl_tasks')]);con.execute('UPDATE uc_schema SET version=2')
        with self.assertRaises(ValueError):Ledger(self.engine)
    def test_nonfinite_or_unbounded_contract_rejected(self):
        a=self.claim('a',1)
        for change in ({'normalized_value':float('nan')},{'context':{'blob':'x'*20000}},{'valid_from':True},{'schema_version':'future'}):
            with self.assertRaises(ValueError):replace(a,**change)
    def test_new_source_revision_invalidates_old_reference(self):
        a=self.claim('a',1);old=self.ledger.revision(self.actor,'task')
        self.ledger.register_source(self.actor,'source-a',{'value':2},revision='v2')
        self.assertGreater(self.ledger.revision(self.actor,'task'),old)
        with self.assertRaises(PermissionError):self.ledger.add_claim(self.actor,replace(a,claim_id='stale-copy'))
    def test_resolution_racing_new_evidence_preserves_open_disagreement(self):
        from concurrent.futures import ThreadPoolExecutor
        c=self.conflict()
        def close():
            try:self.resolve(c)
            except StaleRevision:pass
        def introduce():self.claim('new-evidence','unknown')
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda f:f(),[close,introduce]))
        current=self.ledger.get_conflict(self.actor,c.conflict_id)
        self.assertIn(current.status,OPEN);self.assertIn('new-evidence',current.claim_ids)
    def test_duplicate_json_and_malformed_lists_rejected(self):
        a=self.claim('a',1)
        with self.assertRaises(ValueError):Claim.from_json(a.to_json()[:-1]+',"task_id":"other"}')
        c=self.conflict()
        with self.assertRaises(ValueError):replace(c,claim_ids='one')
        with self.assertRaises(ValueError):replace(a,evidence_hash='invented')
    def test_resolution_must_account_for_every_conflicting_claim(self):
        c=self.conflict();self.claim('third','disputed');c=self.ledger.get_conflict(self.actor,c.conflict_id)
        with self.assertRaises(ValueError):self.resolve(c)
        self.assertIn(self.ledger.get_conflict(self.actor,c.conflict_id).status,OPEN)
    def test_unknown_and_nonexclusive_negation_not_false_contradictions(self):
        self.claim('a',None,task_id='unknown');self.claim('b',True,task_id='unknown')
        self.assertEqual(self.ledger.detect(self.actor,'unknown'),[])
        self.claim('c',5,task_id='negated',polarity=False);self.claim('d',6,task_id='negated')
        self.assertEqual(self.ledger.detect(self.actor,'negated'),[])
