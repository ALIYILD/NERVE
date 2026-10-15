"""Regression evidence is measured and admitted before any sealed holdout call."""
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

import test_cue_cycle as fixtures
from nerve_awim.agentos_learning import AgentOSLearning
from nerve_awim.cue_dataset import parse_dataset_json
from nerve_awim.cue_experiment import ExperimentTask, ProviderReceipt
from nerve_awim.cue_host import CueHost


class CueRegressionCycleTests(unittest.TestCase):
    setUp = fixtures.CueCycleTests.setUp
    run_cycle = fixtures.CueCycleTests.run_cycle

    def run_regression_cycle(self, *, fail=False, missing_confidence=False, **changes):
        self.seen=[]
        manifest=replace(self.manifest,regression=('regression1',))
        def provider(request):
            self.seen.append((request.task_id,request.arm))
            regression=request.task_id=='regression1'
            correct=(not fail or request.arm=='baseline') if regression else request.arm=='candidate'
            confidence=None if regression and missing_confidence else float(correct)
            return ProviderReceipt('right' if correct else 'wrong',confidence,request.model,
                .009 if request.arm=='candidate' else .01,request.task_id+request.arm,
                False,False,request.cue_digest,request.arm)
        values=dict(manifest=manifest,regression_tasks=[ExperimentTask('regression1','retained question','right')],
                    provider=provider,max_calls=65)
        values.update(changes)
        return self.run_cycle(**values)

    def test_regression_admitted_before_holdout_then_awaits_approval(self):
        result=self.run_regression_cycle()
        self.assertEqual(result['state'],'awaiting_approval')
        self.assertEqual(result['attempted_calls'],65)
        self.assertIsNotNone(result['regression_digest'])
        self.assertEqual([task for task,arm in self.seen[:4]],['s','s','regression1','regression1'])
        self.assertEqual(self.cce.status(self.actors['auditor'],result['candidate'])['status'],'passed')
        self.assertFalse(result['activated'])

    def test_failed_regression_stops_before_holdout_and_seals_candidate(self):
        result=self.run_regression_cycle(fail=True)
        self.assertEqual(result['state'],'rejected')
        self.assertEqual(result['reason'],'regression_gate_failed')
        self.assertEqual(result['attempted_calls'],5)
        self.assertIsNone(result['holdout_digest'])
        self.assertEqual({task for task,arm in self.seen},{'s','regression1'})
        self.assertEqual(self.cce.status(self.actors['auditor'],result['candidate'])['status'],'rejected')

    def test_unknown_regression_calibration_cannot_reach_holdout(self):
        result=self.run_regression_cycle(missing_confidence=True)
        self.assertEqual(result['reason'],'regression_gate_failed')
        self.assertEqual(result['attempted_calls'],5)
        self.assertIsNone(result['holdout_digest'])

    def test_missing_regression_or_insufficient_budget_fails_before_reservation(self):
        for changes in ({'regression_tasks':[]},{'max_calls':63},{'max_cost_usd':.73}):
            with self.subTest(changes=changes), patch.object(self.cce,'reserve_study') as reserve:
                with self.assertRaises(ValueError):self.run_regression_cycle(**changes)
                reserve.assert_not_called()
                self.assertEqual(self.seen,[])
                self.assertEqual(self.discovery_payloads,[])

    def test_schema2_dataset_bound_cycle_persists_both_gates(self):
        partitions={'discovery':self.manifest.discovery,'selection':self.manifest.selection,
                    'holdout':self.manifest.holdout,'regression':('regression1',)}
        record={'schema_version':2,'dataset_id':'retained-capabilities',
                'source':{'uri':'fixture:retained','revision':'v1'},
                'splits':{split:[{'task_id':task,'family_id':split+'-family',
                    'instruction':'instruction:'+task,'expected':'right'} for task in tasks]
                    for split,tasks in partitions.items()}}
        dataset=parse_dataset_json(json.dumps(record))
        result=self.run_regression_cycle(dataset=dataset,manifest=dataset.manifest,
            selection_tasks=dataset.selection_tasks,holdout_tasks=dataset.holdout_tasks,
            regression_tasks=dataset.regression_tasks)
        self.assertEqual(result['state'],'awaiting_approval')
        self.assertEqual(result['dataset_digest'],dataset.digest)
        self.assertEqual(result['attempted_calls'],65)
        status=self.cce.status(self.actors['auditor'],result['candidate'])
        self.assertTrue(status['dataset']['bound'])
        self.assertEqual(status['dataset']['digest'],dataset.digest)
        self.assertTrue(status['regression']['required'])
        self.assertTrue(status['regression']['evaluation']['decision']['eligible'])
        self.assertEqual(status['regression']['evaluation']['report']['split'],'regression')
        self.assertTrue(status['evaluation']['decision']['eligible'])
        self.assertEqual([task for task,arm in self.seen[:4]],['s','s','regression1','regression1'])
        self.assertTrue(all(task in dataset.manifest.holdout for task,arm in self.seen[4:]))

    def test_host_dataset_wrapper_supplies_regression_and_refuses_override(self):
        record={'schema_version':2,'dataset_id':'frozen','source':{'uri':'fixture:test','revision':'v1'},
            'splits':{split:[{'task_id':split+str(i),'family_id':split+str(i),
                'instruction':'question '+split+str(i),'expected':'right'}
                for i in range(30 if split=='holdout' else 1)]
                for split in ('discovery','selection','regression','holdout')}}
        dataset=parse_dataset_json(json.dumps(record))
        host=CueHost(AgentOSLearning(self.temp.name))
        with patch.object(host,'run_cycle',return_value={'state':'fixture'}) as cycle:
            host.run_dataset_cycle('worker',dataset,permission_granted=True)
            self.assertEqual(cycle.call_args.kwargs['regression_tasks'],dataset.regression_tasks)
            self.assertEqual(cycle.call_args.kwargs['manifest'],dataset.manifest)
            with self.assertRaises(ValueError):
                host.run_dataset_cycle('worker',dataset,permission_granted=True,regression_tasks=[])
            self.assertEqual(cycle.call_count,1)


if __name__=='__main__':unittest.main()
