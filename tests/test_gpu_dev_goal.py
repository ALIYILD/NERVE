import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
spec=importlib.util.spec_from_file_location('gpu_goal',SCRIPTS/'reconcile_gpu_dev_goal.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)


class GPUDevGoalTests(unittest.TestCase):
    def test_tie_is_verified_but_never_retained_or_promoted(self):
        report={'status':'complete','protocol':{'version':'fixture'},'holdout_accessed':False,
            'promotion_authorized':False,'model_weights_trained':False,'efficacy_established':False,
            'summary':{'verdict':'retain_baseline','prospective_gate_passed':False,
                       'generalization_verdict':'insufficient_power'}}
        digest=hashlib.sha256((json.dumps(report,sort_keys=True,separators=(',',':'))+'\n').encode()).hexdigest()
        calls=[]
        def verify():calls.append(True);return report
        with tempfile.TemporaryDirectory() as state,patch.object(runner.study,'sources',return_value={'fixture':'hash'}):
            goal=runner.build_goal(state,report['protocol'],digest,verify)
            result=goal.run()
            self.assertEqual(result['status'],'complete')
            receipt=result['tasks'][0]['receipt']
            self.assertFalse(receipt['candidate_selected_for_review'])
            self.assertFalse(receipt['retained_skill_selected'])
            self.assertFalse(receipt['promotion_authorized'])
            runner.build_goal(state,report['protocol'],digest,verify).run()
            self.assertEqual(calls,[True])
            with self.assertRaises(ValueError):runner.build_goal(state,{'version':'changed'},digest,verify)

    def test_unverified_or_changed_report_blocks(self):
        with tempfile.TemporaryDirectory() as state,patch.object(runner.study,'sources',return_value={}):
            goal=runner.build_goal(state,{},'0'*64,lambda:{'status':'complete'})
            self.assertEqual(goal.run()['status'],'blocked')
