"""Offline CCE fixtures are contract tests, never model-improvement evidence."""
import json
from pathlib import Path
import unittest
from nerve_awim.cue_learning import GovernedCueCoordinator
from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger
from nerve_awim.uncertainty.ledger import Ledger
from nerve_awim.uncertainty.contracts import Claim
from nerve_awim.uncertainty.adapters import UncertaintyAdapter
import test_cue_learning as fixtures
import test_cue_cycle as cycle_fixtures


class CueUncertaintyTests(unittest.TestCase):
    setUp = fixtures.CueLearningTests.setUp
    propose = fixtures.CueLearningTests.propose
    pairs = fixtures.CueLearningTests.pairs
    passed = fixtures.CueLearningTests.passed
    activate = fixtures.CueLearningTests.activate
    select = fixtures.CueLearningTests.select
    run_cycle = cycle_fixtures.CueCycleTests.run_cycle

    def adapter(self, *, conflict=False):
        self.uc = Ledger(self.engine)
        self.runtime = self.actors['runtime']
        source = self.uc.register_source(self.runtime, 'primary', {'available': True})
        self.uc.add_claim(self.runtime, Claim(claim_id='first',tenant_id='tenant',task_id='cue-evidence',
            subject_ref='fixture',predicate='available',normalized_value=True,**source))
        adapter = UncertaintyAdapter(self.uc,self.runtime,task_id='cue-evidence',dependency_claim_ids=['first'])
        self.cce = GovernedCueCoordinator(self.engine,enabled=True,clock=lambda:self.now,uncertainty=adapter)
        if conflict:self.contradict()
        return adapter

    def contradict(self):
        source = self.uc.register_source(self.runtime,'secondary',{'available':False})
        self.uc.add_claim(self.runtime,Claim(claim_id='second',tenant_id='tenant',task_id='cue-evidence',
            subject_ref='fixture',predicate='available',normalized_value=False,**source))
        self.uc.detect(self.runtime,'cue-evidence')

    def memory(self):
        authority=MemoryAuthority()
        actor=authority.issue('tenant','agent',permissions=('read','propose','approve'))
        return TrustedMemoryLedger(self.engine.path,authority),actor

    def test_rejected_export_stays_pending_and_preserves_open_conflict(self):
        adapter=self.adapter(conflict=True)
        candidate=self.propose()
        self.cce.reject_pending(self.actors['evaluator'],candidate,reason='inconclusive')
        ledger,actor=self.memory()
        memory=self.cce.export_memory(self.actors['auditor'],candidate,ledger,actor)
        record=ledger.status(actor,memory)
        self.assertEqual(record.status,'pending')
        evidence=json.loads(record.content)
        self.assertEqual(evidence['status'],'rejected')
        self.assertEqual(evidence['uncertainty']['open_conflict_count'],1)
        self.assertFalse(evidence['guidance_authority'])
        with self.assertRaises(PermissionError):ledger.retrieve(actor,context='cognitive-cues',query='')
        retrieved=ledger.retrieve(actor,context='cognitive-cues',query='',uncertainty=adapter)
        self.assertEqual(retrieved['records'],[])
        self.assertEqual(retrieved['uncertainty']['open_conflict_count'],1)
        self.assertFalse(retrieved['guidance_authority'])

    def test_restart_cannot_omit_bound_adapter_or_drop_dependency(self):
        adapter=self.adapter()
        candidate=self.propose()
        reloaded=GovernedCueCoordinator(self.engine,enabled=True,clock=lambda:self.now)
        with self.assertRaises(PermissionError):reloaded.select(self.runtime,self.profile,'research',permission_granted=True)
        ledger,actor=self.memory()
        with self.assertRaises(PermissionError):reloaded.export_memory(self.actors['auditor'],candidate,ledger,actor)
        changed=UncertaintyAdapter(self.uc,self.runtime,task_id='cue-evidence',dependency_claim_ids=[],required=False)
        altered=GovernedCueCoordinator(self.engine,enabled=True,uncertainty=changed)
        with self.assertRaises(PermissionError):altered.uncertainty_state(self.runtime,'research')

    def test_new_conflict_blocks_existing_cue_selection_and_activation(self):
        self.adapter()
        candidate=self.passed()
        self.activate(candidate)
        self.assertIsNotNone(self.select().cue)
        self.contradict()
        with self.assertRaises(PermissionError):self.select()
        with self.assertRaises(PermissionError):self.cce.activate(self.actors['operator'],candidate,expected_generation=1,reason='review')

    def test_cross_scope_mapping_denied_before_candidate_creation(self):
        self.adapter()
        outsider=self.authority.issue('foreign','agent','runtime')
        bad=UncertaintyAdapter(self.uc,outsider,task_id='cue-evidence')
        self.cce.uncertainty=bad
        with self.assertRaises(PermissionError):self.propose()
        with self.engine._db() as con:self.assertEqual(con.execute('SELECT COUNT(*) FROM cce_candidates').fetchone()[0],0)

    def test_open_learning_evidence_stops_cycle_before_discovery_or_reservation(self):
        self.adapter(conflict=True)
        with self.assertRaises(PermissionError):self.run_cycle()
        self.assertEqual(self.calls,[])
        self.assertEqual(self.discovery_payloads,[])
        with self.engine._db() as con:self.assertEqual(con.execute('SELECT COUNT(*) FROM cce_studies').fetchone()[0],0)

    def test_discovery_summary_cannot_erase_new_conflict(self):
        self.adapter()
        from nerve_awim.cue_cycle import DiscoveryReceipt
        captured=[]
        def discovery(role,payload,**kwargs):
            captured.append(payload)
            self.contradict()
            return DiscoveryReceipt({'candidates':['Check the answer.']},.01,False)
        result=self.run_cycle(discovery_execute=discovery)
        self.assertIn('uncertainty',captured[0])
        self.assertEqual(result['state'],'blocked')
        self.assertEqual(result['attempted_calls'],1)
        self.assertEqual(self.calls,[])
        self.assertEqual(len(self.uc.conflicts(self.runtime,'cue-evidence',open_only=True)),1)

    def test_cycle_with_supported_evidence_still_obeys_cce_synthetic_gate(self):
        adapter=self.adapter()
        from nerve_awim.cue_cycle import DiscoveryReceipt
        payloads=[]
        def discovery(role,payload,**kwargs):
            payloads.append(payload)
            return DiscoveryReceipt({'candidates':['Check the answer.']},0,True)
        result=self.run_cycle(discovery_execute=discovery,uncertainty=adapter)
        self.assertEqual(result['reason'],'synthetic_discovery')
        self.assertEqual(payloads[0]['uncertainty']['open_conflict_count'],0)
        self.assertFalse(result['activated'])

    def test_revision_change_between_assessment_and_selection_is_rejected(self):
        self.adapter()
        candidate=self.passed();self.activate(candidate)
        from unittest.mock import patch
        original=self.cce.uncertainty_state
        def changed(*args,**kwargs):
            envelope=original(*args,**kwargs)
            self.contradict()
            return envelope
        with patch.object(self.cce,'uncertainty_state',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'changed'):self.select()

    def test_synthetic_holdout_rejection_cannot_become_memory_or_cue_authority(self):
        adapter=self.adapter()
        candidate=self.propose()
        result=self.cce.evaluate(self.actors['evaluator'],candidate,self.pairs(synthetic=True),evaluator_id='independent')
        self.assertFalse(result['decision']['eligible'])
        self.assertEqual(self.cce.status(self.actors['auditor'],candidate)['status'],'rejected')
        with self.assertRaises(PermissionError):self.activate(candidate)
        ledger,actor=self.memory()
        memory=self.cce.export_memory(self.actors['auditor'],candidate,ledger,actor)
        self.assertEqual(ledger.status(actor,memory).status,'pending')
        self.assertIsNone(self.select().cue)
        self.assertEqual(ledger.retrieve(actor,context='cognitive-cues',query='',uncertainty=adapter)['records'],[])


import test_cue_host as host_fixtures
class CueHostUncertaintyTests(unittest.TestCase):
    setUp=host_fixtures.CueHostTests.setUp
    configure=host_fixtures.CueHostTests.configure
    approve=host_fixtures.CueHostTests.approve

    def test_native_preparation_preserves_state_and_omission_does_not_fallback(self):
        candidate=self.approve()
        uc=Ledger(self.adapter._engine)
        actor=self.adapter._actor('worker','runtime')
        source=uc.register_source(actor,'host-source',{'available':True})
        uc.add_claim(actor,Claim(claim_id='host-claim',tenant_id=actor.tenant,task_id='host-task',
            subject_ref='worker',predicate='available',normalized_value=True,**source))
        uncertainty=UncertaintyAdapter(uc,actor,task_id='host-task',dependency_claim_ids=['host-claim'])
        self.adapter.uncertainty=uncertainty
        prepared=self.adapter.prepare('worker','handoff',permission_granted=True)
        self.assertEqual(prepared['uncertainty']['task_id'],'host-task')
        self.assertEqual(prepared['uncertainty']['open_conflict_count'],0)
        from nerve_awim.cue_host import CueHost
        with self.assertRaises(PermissionError):CueHost(self.host).prepare('worker','handoff',permission_granted=True)
        source=uc.register_source(actor,'host-disagreement',{'available':False})
        uc.add_claim(actor,Claim(claim_id='host-conflict-claim',tenant_id=actor.tenant,task_id='host-task',
            subject_ref='worker',predicate='available',normalized_value=False,**source))
        uc.detect(actor,'host-task')
        with self.assertRaises(PermissionError):self.adapter.prepare('worker','handoff',permission_granted=True)
