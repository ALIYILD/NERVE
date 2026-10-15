"""Gate tests use already-validated receipt fixtures; no network or inference."""
import copy
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock,patch
from nerve_awim.memory_gateway import scientific_substrate_gate as g


class SubstrateGateTests(unittest.TestCase):
    def setUp(self):
        self.digest='a'*64
        rows=[]
        for i in range(60):
            for arm in g.study.ARMS:
                rows.append(dict(task_id=str(i),arm=arm,model_calls=int(arm=='baseline' or arm=='candidate' and i>=20),
                                 raw_output='ABSTAIN',score={'strict_correct':i<40}))
        self.receipt={'status':'complete','rows':rows,'protocol':{'model':'fixed'}}
        self.store=Mock();self.store.query.return_value=[]
        self.identity=Mock(return_value={'model':'renamed-runtime','digest':self.digest})
        self.kw=dict(study_directory='/fixture/study',expected_digest=self.digest,journal='/fixture/claims',substrate_metadata=self.identity)
        for name,value in [('sources',{'gate':'c'*64})]:
            p=patch.object(g,name,return_value=value);p.start();self.addCleanup(p.stop)
        p=patch.object(g.study,'validate_receipt',return_value=self.receipt);self.validate=p.start();self.addCleanup(p.stop)
        p=patch.object(g.candidates,'propose',return_value={'proposals':[{'fixture':True}]});self.propose=p.start();self.addCleanup(p.stop)

    def test_floor_blocks_generation_despite_model_runtime_rename(self):
        result=g.gated_propose(self.store,object(),**self.kw)
        self.assertEqual(result['status'],'blocked');self.assertEqual(result['proposals'],[])
        self.propose.assert_not_called();self.assertEqual(self.identity.call_count,2)
        self.assertFalse(result['inference_authorized'])

    def test_same_digest_blocks_format_proposals_and_disabled_research(self):
        with patch.object(g.format_feedback,'propose') as generate:
            self.assertEqual(g.gated_format_propose(self.store,object(),**self.kw)['status'],'blocked')
            generate.assert_not_called()
        self.assertEqual(g.gated_propose(self.store,object(),research_agent_enabled=False,**self.kw)['status'],'blocked')
        self.propose.assert_not_called()

    def test_metadata_callback_predecessor_mutation_is_rejected(self):
        def mutate():
            self.validate.side_effect=ValueError('receipt altered')
            return {'model':'renamed','digest':self.digest}
        self.identity.side_effect=mutate
        with self.assertRaisesRegex(ValueError,'receipt altered'):
            g.gated_propose(self.store,object(),**self.kw)
        self.propose.assert_not_called()

    def test_verified_distinct_digest_calls_existing_generator(self):
        self.identity.return_value={'model':'fixed','digest':'b'*64}
        result=g.gated_propose(self.store,object(),**self.kw)
        self.assertEqual(result['status'],'proposed');self.propose.assert_called_once()

    def test_new_digest_requires_valid_stable_host_identity(self):
        self.identity.return_value={'model':'new','digest':'short'}
        with self.assertRaises(ValueError):g.gated_propose(self.store,object(),**self.kw)
        self.propose.assert_not_called()
        self.identity.side_effect=[{'model':'new','digest':'b'*64},{'model':'new','digest':'c'*64}]
        with self.assertRaisesRegex(ValueError,'substrate_or_sources_changed'):
            g.gated_propose(self.store,object(),**self.kw)

    def test_calibration_exception_never_generates_or_authorizes_inference(self):
        result=g.gated_propose(self.store,object(),operation='calibration',**self.kw)
        self.assertEqual(result['calibration']['max_model_calls'],30)
        self.assertEqual(result['calibration']['kind'],'scientific-substrate-calibration-30-v1')
        self.propose.assert_not_called();self.assertFalse(result['inference_authorized'])
        with self.assertRaises(ValueError):g.gated_propose(self.store,object(),operation='prompt-calibration',**self.kw)

    def test_scoped_denial_and_revocation_fail_closed(self):
        self.store.query.side_effect=PermissionError('revoked')
        with self.assertRaises(PermissionError):g.gated_propose(self.store,object(),**self.kw)
        self.validate.assert_not_called();self.propose.assert_not_called()
        self.store.query.side_effect=[[],PermissionError('revoked')]
        with self.assertRaises(PermissionError):g.gated_propose(self.store,object(),**self.kw)

    def test_failed_or_corrupt_receipt_cannot_adjudicate(self):
        self.receipt['status']='failed_consumed'
        with self.assertRaises(ValueError):g.adjudicate('/fixture/study',self.digest,'/fixture/claims')
        self.validate.side_effect=ValueError('corrupt')
        with self.assertRaises(ValueError):g.gated_propose(self.store,object(),**self.kw)
        self.propose.assert_not_called()

    def test_floor_requires_all_model_abstentions_and_same_taskwise_scores(self):
        changed=copy.deepcopy(self.receipt);changed['rows'][0]['raw_output']='1|mg|A0'
        self.validate.return_value=changed
        self.assertEqual(g.adjudicate('/fixture/study',self.digest,'/fixture/claims')['status'],'not_at_floor')
        changed=copy.deepcopy(self.receipt);changed['rows'][0]['score']['strict_correct']=False
        self.validate.return_value=changed
        self.assertEqual(g.adjudicate('/fixture/study',self.digest,'/fixture/claims')['status'],'not_at_floor')

    def test_separate_adjudication_stable_without_history_rewrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'gate'
            first=g.publish_adjudication(root,'/fixture/study',self.digest,'/fixture/claims')
            path=root/'report.json';before=(path.read_bytes(),path.stat().st_mtime_ns)
            self.assertEqual(g.publish_adjudication(root,'/fixture/study',self.digest,'/fixture/claims'),first)
            self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)
            with self.assertRaises(ValueError):g.publish_adjudication('/fixture/study/nested','/fixture/study',self.digest,'/fixture/claims')


if __name__=='__main__':unittest.main()
