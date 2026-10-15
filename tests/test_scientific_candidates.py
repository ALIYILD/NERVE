import copy
from pathlib import Path
import sqlite3
import tempfile
import unittest
from nerve_awim.memory_gateway import scientific_candidates as s
from nerve_awim.memory_gateway.experience_store import ExperienceStore
from nerve_awim.memory_gateway.gateway import MemoryGateway
from nerve_awim.memory_gateway.contracts import MemoryScope
from nerve_awim.memory_v18 import MemoryAuthority,TrustedMemoryLedger


def episode(index,failure='conflict_non_abstaining',stratum='conflict'):
    return dict(episode_id=f'episode-{index}',context_hash='a'*64,agent='model-research',candidate_id='trusted_task',
        policy_version='b'*64,inputs_hash='c'*64,action='registered query',output='wrong output',
        evaluator_verdict='strict_incorrect',format_ok=False,evidence_ok=None,real_world_outcome=None,
        outcome_source='verified-receipt',timestamps=None,source_sha256={'source.py':'d'*64},stratum=stratum,
        failure_class=failure,synthetic_only=True,source_kind='scientific_validation_v1')


class ScientificCandidatesTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.auth=MemoryAuthority();self.actor=self.auth.issue('tenant','agent',permissions=('read','propose'))
        gateway=MemoryGateway(TrustedMemoryLedger(self.root/'memory.sqlite',self.auth))
        self.store=ExperienceStore(self.root/'episodes.sqlite',gateway,MemoryScope('tenant','agent','episodes'))
        self.store.initialize(self.actor)

    def test_measured_conflict_automatically_proposes_hashed_prestep(self):
        self.store.append_many(self.actor,[episode(1),episode(2)])
        before=self.store.path.read_bytes()
        result=s.propose(self.store,self.actor)
        self.assertEqual(result['mode'],'deterministic_failure_rules');self.assertFalse(result['model_research_agent'])
        proposal=result['proposals'][0]
        self.assertTrue(proposal['candidate']['conflict_detection'])
        self.assertEqual(proposal['candidate_sha256'],s._hash(proposal['candidate']))
        self.assertEqual(len(proposal['hypothesis']['cluster']['members']),2)
        self.assertEqual(proposal['hypothesis']['risk_stratum'],'multi-source-agreement')
        self.assertTrue(s.validate_hypothesis(proposal,self.store,self.actor))
        self.assertEqual(s._json(result),s._json(s.propose(self.store,self.actor)))
        self.assertEqual(before,self.store.path.read_bytes());self.assertFalse(result['negative_evidence_enforced'])

    def test_disabled_agent_enumeration_honest_without_model_calls(self):
        self.store.append_many(self.actor,[episode(1)])
        result=s.propose(self.store,self.actor,research_agent_enabled=False)
        self.assertEqual(result['mode'],'enumeration_fallback');self.assertEqual(len(result['proposals']),4)
        self.assertEqual(result['model_calls'],0);self.assertFalse(result['holdout_accessed'])
        for proposal in result['proposals']:self.assertTrue(s.validate_hypothesis(proposal,self.store,self.actor))

    def test_no_failures_empty_off_and_degraded_honest(self):
        self.assertEqual(s.propose(self.store,self.actor)['reason'],'no_failure_data')
        self.store.append_many(self.actor,[episode(1,'none')])
        self.assertEqual(s.propose(self.store,self.actor)['proposals'],[])
        self.store.enabled=False
        self.assertEqual(s.propose(self.store,None)['status'],'off')
        self.store.enabled=True;self.store.path.write_bytes(b'corrupt')
        result=s.propose(self.store,self.actor)
        self.assertEqual(result['status'],'degraded');self.assertEqual(result['proposals'],[])

    def test_budgets_booleans_and_config_types_strict(self):
        for enabled,budget in [(1,4),(False,True),(True,0),(True,5),(None,1)]:
            with self.assertRaises(ValueError):s.propose(self.store,self.actor,research_agent_enabled=enabled,max_proposals=budget)
        for key,value in [('conflict_detection',1),('retrieval_k',True),('prompt_template','arbitrary instructions'),('tool_rule','shell')]:
            config=dict(s.SPACE['conflict_check']);config[key]=value
            with self.assertRaises(ValueError):s.validate_config(config)

    def test_tampered_hypothesis_and_forged_evidence_rejected(self):
        self.store.append_many(self.actor,[episode(1)])
        original=s.propose(self.store,self.actor)['proposals'][0]
        for key,value in [('candidate_sha256','e'*64),('promotion_authorized',True),('model_calls',1)]:
            altered=copy.deepcopy(original);altered[key]=value
            with self.assertRaises(ValueError):s.validate_hypothesis(altered,self.store,self.actor)
        cluster=copy.deepcopy(original['hypothesis']['cluster']);cluster['members'][0]['episode_id']='invented'
        cluster['cluster_sha256']=s._hash({k:v for k,v in cluster.items() if k!='cluster_sha256'})
        altered=s.register_hypothesis(original['candidate'],cluster,store_head=original['store_head'],mode=original['mode'])
        with self.assertRaises(ValueError):s.validate_hypothesis(altered,self.store,self.actor)

    def test_rehashed_wrong_mutation_cannot_claim_failure_rule_provenance(self):
        self.store.append_many(self.actor,[episode(1)])
        original=s.propose(self.store,self.actor)['proposals'][0]
        mismatch=s.register_hypothesis(s.SPACE['format_contract'],original['hypothesis']['cluster'],
                                      store_head=original['store_head'],mode='deterministic_failure_rules')
        with self.assertRaisesRegex(ValueError,'failure_mutation_mapping'):
            s.validate_hypothesis(mismatch,self.store,self.actor)
        enumeration=s.register_hypothesis(s.SPACE['format_contract'],original['hypothesis']['cluster'],
                                         store_head=original['store_head'],mode='enumeration_fallback')
        self.assertTrue(s.validate_hypothesis(enumeration,self.store,self.actor))

    def test_new_evidence_changes_hypothesis_not_candidate_identity(self):
        self.store.append_many(self.actor,[episode(1)])
        old=s.propose(self.store,self.actor)['proposals'][0]
        self.store.append_many(self.actor,[episode(2)])
        new=s.propose(self.store,self.actor)['proposals'][0]
        self.assertEqual(old['candidate_sha256'],new['candidate_sha256'])
        self.assertNotEqual(old['hypothesis_sha256'],new['hypothesis_sha256'])
        with self.assertRaises(ValueError):s.validate_hypothesis(old,self.store,self.actor)

    def test_failure_priority_dedup_and_proposal_budget(self):
        self.store.append_many(self.actor,[episode(1,'format_failure','entity_decoy'),episode(2),episode(3,'supported_abstention','measurement_decoy')])
        result=s.propose(self.store,self.actor,max_proposals=1)
        self.assertEqual(len(result['proposals']),1)
        self.assertEqual(result['proposals'][0]['hypothesis']['mutation'],'conflict_check')
        self.assertEqual(len(s.propose(self.store,self.actor)['proposals']),3)

    def test_foreign_revoked_actor_cannot_read_clusters(self):
        foreign=self.auth.issue('other','agent',permissions=('read',))
        with self.assertRaises(PermissionError):s.propose(self.store,foreign)
        self.auth.revoke(self.actor)
        with self.assertRaises(PermissionError):s.propose(self.store,self.actor)


if __name__=='__main__':unittest.main()
