import copy
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from nerve_awim.memory_gateway import scientific_policy_gate_v2 as gate


class PolicyGateV2Tests(unittest.TestCase):
    def setUp(self):
        self.old={'status':'model_at_floor','verdict':'model_at_floor','study_directory':'/fixture/devstudy','model_digest':'a'*64,'model':'fixture'}
        protocol=dict(model='fixture',expected_digest='a'*64,journal='/fixture/claims',bank_directory='/fixture/bank',manifest_sha256='b'*64,
                      predecessor_directory='/fixture/v1',predecessor_journal='/fixture/v1claims')
        self.receipt=dict(status='complete',protocol=protocol,rows=[dict(arm=arm,response={'raw_output':'ABSTAIN' if arm=='compact' else 'value'},score={'declared_abstention':arm=='compact'}) for arm in ('compact','original','forced_answer') for _ in range(10)])
        def read(path):
            if str(path)=='/fixture/v2/report.json':return copy.deepcopy(self.receipt)
            if str(path)=='/fixture/devstudy/report.json':return {'protocol':dict(expected_digest='a'*64,journal='/fixture/devclaims',paths={})}
            return copy.deepcopy(self.old)
        for target,name,kwargs in [(gate,'sources',{'return_value':{'gate':'pinned'}}),(gate,'_read',{'side_effect':read}),
                (gate.calibration,'validate_receipt',{'side_effect':lambda *a,**k:copy.deepcopy(self.receipt)}),
                (gate.predecessor,'adjudicate',{'side_effect':lambda *a,**k:copy.deepcopy(self.old)})]:
            p=patch.object(target,name,**kwargs);p.start();self.addCleanup(p.stop)

    def test_reclassification_is_policy_not_digest_block(self):
        result=gate.adjudicate('/fixture/v2')
        self.assertEqual(result['verdict'],'prompt_induced_abstention')
        self.assertEqual(result['blocked_policy'],'compact_with_abstain')
        self.assertFalse(result['model_digest_blocked']);self.assertTrue(result['proposals_unblocked'])
        self.assertNotIn('model_digest',result)

    def test_new_v3_proposal_allowed_with_prediction_not_promotion(self):
        r=gate.register_proposal('/fixture/v2')
        self.assertEqual(r['permission']['status'],'allowed')
        self.assertIn('decoy',r['prediction']);self.assertFalse(r['promotion_authorized'])
        self.assertFalse(r['evaluated']);self.assertFalse(r['permission']['inference_authorized'])

    def test_bad_policy_only_permitted_as_baseline(self):
        self.assertEqual(gate.authorize('compact_with_abstain','/fixture/v2')['status'],'blocked')
        self.assertEqual(gate.authorize('compact_with_abstain','/fixture/v2',purpose='development_baseline')['status'],'allowed')

    def test_original_retired_for_proposals_and_new_comparisons(self):
        for purpose in ('proposal','development_baseline'):
            result=gate.authorize('original_json','/fixture/v2',purpose=purpose)
            self.assertEqual(result['status'],'blocked');self.assertEqual(result['reason'],'retired_original_prompt')

    def test_unknown_policy_or_purpose_is_not_unrestricted_unblock(self):
        for name,purpose in [('arbitrary','proposal'),('candidate_v3','deploy')]:
            with self.assertRaises(ValueError):gate.authorize(name,'/fixture/v2',purpose=purpose)

    def test_incomplete_or_changed_calibration_cannot_reclassify(self):
        self.receipt['status']='failed_consumed'
        with self.assertRaises(ValueError):gate.adjudicate('/fixture/v2')
        self.receipt['status']='complete';self.receipt['rows'][0]['response']['raw_output']='answer'
        with self.assertRaises(ValueError):gate.adjudicate('/fixture/v2')

    def test_different_substrate_does_not_reclassify_prompt(self):
        self.old['model_digest']='c'*64
        with self.assertRaisesRegex(ValueError,'same_substrate'):gate.adjudicate('/fixture/v2')

    def test_missing_prior_floor_or_changed_pins_fails(self):
        self.old['verdict']='other'
        with self.assertRaises(ValueError):gate.adjudicate('/fixture/v2')
        self.old['verdict']='model_at_floor'
        with patch.object(gate,'sources',side_effect=[{'a':1},{'a':2}]):
            with self.assertRaises(ValueError):gate.adjudicate('/fixture/v2')

    def test_publication_is_distinct_stable_and_read_only_to_old(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'new';first=gate.publish(root,'/fixture/v2');path=root/'report.json'
            before=(path.read_bytes(),path.stat().st_mtime_ns)
            self.assertEqual(gate.publish(root,'/fixture/v2'),first)
            self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)
        with self.assertRaises(ValueError):gate.publish('/fixture/v2','/fixture/v2')


if __name__=='__main__':unittest.main()
