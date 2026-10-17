import copy
import tempfile
import unittest
from pathlib import Path
from nerve_awim.memory_gateway import overnight_autoresearch as ar
from nerve_awim.memory_gateway.experience_study_store_v2 import ExperienceStudyStoreV2,build_episode
from nerve_awim.memory_gateway.contracts import MemoryScope
from nerve_awim.memory_gateway.gateway import MemoryGateway
from nerve_awim.memory_v18 import MemoryAuthority,TrustedMemoryLedger

class OvernightTests(unittest.TestCase):
    def rows(self):
        return [dict(task_id=str(i),candidate=i<80,incumbent=i<74,
                     random=i<25,**{'always-abstain':False,'safety_error':False}) for i in range(100)]
    def test_keep_boundaries_and_controls(self):
        rows=self.rows();self.assertTrue(ar.decide(rows)['kept'])
        for change in ('safety','loss','control','missing','duplicate','bool'):
            r=copy.deepcopy(rows)
            if change=='safety':r[1]['safety_error']=True
            elif change=='loss':
                for i in (80,81):r[i]['incumbent']=True
            elif change=='control':
                for row in r:row['random']=row['candidate']
            elif change=='missing':r.pop()
            elif change=='duplicate':r[1]['task_id']='0'
            else:r[1]['candidate']=1
            if change in ('missing','duplicate','bool'):
                with self.assertRaises(ValueError):ar.decide(r)
            else:self.assertFalse(ar.decide(r)['kept'])
    def test_rejection_survives_cluster_growth(self):
        snap=dict(head='a'*64,source_sha256='b'*64,episodes=[dict(episode_id='one',stratum='unit-mismatch',failure_class='format_failure')])
        p=ar.propose(snap)[0]
        snap['episodes'].append(dict(episode_id='two',stratum='unit-mismatch',failure_class='format_failure'))
        self.assertEqual(ar.propose(snap,[p['rejection_key']]),[])
    def test_study_store_provenance_roundtrip_and_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);authority=MemoryAuthority();actor=authority.issue('synthetic-science','model-research',permissions=('read','propose'))
            gateway=MemoryGateway(TrustedMemoryLedger(root/'auth.sqlite',authority))
            store=ExperienceStudyStoreV2(root/'store.sqlite',gateway,MemoryScope('synthetic-science','model-research','study-episodes'))
            store.initialize(actor)
            row=dict(task_id='dev-1',stratum='unit-mismatch',candidate_id='v4',raw_output='ABSTAIN',strict_correct=False,format_ok=True,failure_class='supported_abstention',inputs_hash='a'*64)
            e=build_episode(row=row,source_receipt_sha256='b'*64,registration_sha256='c'*64,model_digest='d'*64,domain='scientific-B',ordinal=100)
            self.assertEqual(store.append_many(actor,[e])['added'],1)
            self.assertEqual(store.append_many(actor,[e])['added'],0)
            self.assertEqual(store.query(actor)['episodes'],[e])
            for key,value in [('split','reserve'),('source_kind','scientific_format_probe_v1'),('real_world_outcome','accepted'),('model_digest','short')]:
                bad=dict(e);bad[key]=value
                with self.assertRaises(ValueError):store.append_many(actor,[bad])
            conflict=dict(e);conflict['output']='different'
            with self.assertRaises(ValueError):store.append_many(actor,[conflict])
            self.assertEqual(store.status(actor)['count'],1)
