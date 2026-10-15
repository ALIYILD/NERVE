import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from nerve_awim.adaptation_evaluation import evaluate_candidate
from nerve_awim.arc_evaluation import _db
from nerve_awim.adaptation_replay import load_suite

SUITE=Path(__file__).resolve().parents[1]/'configs/adaptation/suite-v1.json'

class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.db=Path(self.tmp.name)/'eval.db'
        self.report={'overhead_gate_passed':False,'paired_success_difference':.5,'paired_bootstrap_95':[.2,.7]}
    def test_frozen_candidate_and_one_use_holdout(self):
        with patch('nerve_awim.adaptation_evaluation.benchmark',return_value=dict(self.report)):
            result=evaluate_candidate(self.db,candidate='adaptation-v1',suite=SUITE,split='development')
            self.assertEqual(result['candidate_state'],'frozen')
            result=evaluate_candidate(self.db,candidate='adaptation-v1',suite=SUITE,split='heldout')
            self.assertEqual(result['candidate_state'],'rejected'); self.assertFalse(result['activation_authorized'])
            with self.assertRaises(ValueError): evaluate_candidate(self.db,candidate='adaptation-v1',suite=SUITE,split='heldout')
            with self.assertRaises(ValueError): evaluate_candidate(self.db,candidate='adaptation-v2',suite=SUITE,split='development')
    def test_revision_mismatch_fails_closed(self):
        with patch('nerve_awim.adaptation_evaluation.benchmark',return_value=dict(self.report)):
            evaluate_candidate(self.db,candidate='adaptation-v1',suite=SUITE,split='development')
        with patch('nerve_awim.adaptation_evaluation.revision',return_value='changed'):
            with self.assertRaises(ValueError): evaluate_candidate(self.db,candidate='adaptation-v1',suite=SUITE,split='heldout')
    def test_frozen_manifest_and_disjoint_ids(self):
        data=load_suite(SUITE); episodes=data['episodes']
        self.assertGreaterEqual(len(episodes),60); self.assertEqual(len({e['family'] for e in episodes}),6)
        bad=Path(self.tmp.name)/'bad.json'; data['episodes'][0]['heading']='mutated'; bad.write_text(json.dumps(data))
        with self.assertRaises(ValueError): load_suite(bad)
