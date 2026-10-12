import ast
import sys
import unittest
from nerve_awim import agentos_taskbench as bench
from nerve_awim import agentos_taskbench_v3 as v3
from nerve_awim import agentos_taskbench_v2 as v2
from nerve_awim import agentos_maintenance_policy as policy
from copy import deepcopy


class OperationalRepairCohortTests(unittest.TestCase):
    def test_fixed_split_and_new_families(self):
        data=v3.dataset()
        self.assertEqual({k:len(v) for k,v in data.items()},dict(train=2,selection=3,retention=3,final=3))
        tasks=[t for group in data.values() for t in group]
        previous={t.public['family'] for data in (bench.dataset(),v2.dataset()) for group in data.values() for t in group}
        families={t.public['family'] for t in tasks}
        self.assertEqual(len(families),11)
        self.assertFalse(previous & families)
        self.assertEqual(len({bench.task_hash(t) for t in tasks}),11)
        for task in tasks:
            with self.subTest(function=task.public['function']):
                self.assertGreaterEqual(len(task.checks),4)
                self.assertNotIn('checks',bench.public_task(task))
                self.assertEqual(bench.validate_patch(task,bench.reference_solution(task)),task.original)
                self.assertNotEqual(task.public['source'],task.preamble+task.original)

    def test_identity_stable_and_public_copy_isolated(self):
        a=v3.dataset(); b=v3.dataset()
        for phase in a:
            for x,y in zip(a[phase],b[phase]):
                self.assertEqual(bench.task_hash(x),bench.task_hash(y))
                exposed=bench.public_task(x)
                exposed['requirements']='changed'
                self.assertNotEqual(exposed,x.public)

    def test_observed_timeout_recovery_and_blocked_successors(self):
        # Adapted shape of Oct3 QA recovery; timings are normalized, not raw logs.
        runs = [dict(id='a',task_id='qa',started_at=0,finished_at=248,status='timed_out'),
                dict(id='b',task_id='qa',started_at=300,finished_at=488,status='reclaimed'),
                dict(id='c',task_id='qa',started_at=500,finished_at=680,status='done')]
        saved = deepcopy(runs)
        self.assertEqual(policy.timeout_diagnosis(runs[0],240),'watchdog_window')
        self.assertEqual(policy.retry_chain_summary('qa',runs),dict(state='recovered',attempts=3,timeouts=1))
        self.assertEqual(policy.latest_run_by_task(runs)['qa']['id'],'c')
        self.assertEqual(runs,saved)
        # Oct5-style auditor timeout exhausts max_retries=1 (one consecutive failure).
        attempt = dict(id='r',task_id='audit',started_at=0,finished_at=243,status='timed_out')
        self.assertEqual(policy.retry_disposition(dict(id='audit',max_consecutive_failures=1,consecutive_failures=1),[attempt],300,0),'exhausted')
        auditor = dict(id='audit',status='blocked',run_id='r')
        child = dict(id='qa',status='todo',depends_on=['audit'])
        self.assertEqual(policy.dependency_readiness(child,[auditor]),'waiting')
        self.assertEqual(policy.successor_release(child,[auditor],[]),['audit'])
        self.assertEqual(policy.mission_admission([auditor,child],dict(task_ids=[])),'blocked')

    def test_completion_cannot_be_proved_by_previous_attempt_receipt(self):
        task = dict(id='audit',status='done',run_id='new',expected_artifact='scheduling.json')
        run = dict(id='new',task_id='audit',started_at=100)
        receipt = dict(task_id='audit',run_id='old',written_at=90,path='scheduling.json',validated=True)
        self.assertEqual(policy.artifact_receipt_status(task,run,receipt),'wrong_attempt')
        self.assertEqual(policy.mission_terminal_state(['audit'],[task],[receipt]),'unverified')
        self.assertEqual(policy.successor_release(dict(depends_on=['audit']),[task],[receipt]),['audit'])

    def test_every_mutation_changes_a_named_operational_mechanism(self):
        # All are new policy functions actually usable by the maintenance report.
        tasks=[t for group in v3.dataset().values() for t in group]
        for task in tasks:
            self.assertTrue(callable(getattr(policy,task.public['function'])))
            self.assertEqual(task.preamble,'')
        finals={t.public['function'] for t in v3.dataset()['final']}
        self.assertEqual(finals,{'retry_chain_summary','mission_terminal_state','successor_release'})

    @unittest.skipUnless(sys.platform=='darwin','macOS sandbox integration')
    def test_all_references_pass_and_mutants_fail(self):
        for phase,tasks in v3.dataset().items():
            for task in tasks:
                with self.subTest(phase=phase,function=task.public['function']):
                    original=bench.evaluate(task,bench.reference_solution(task))
                    self.assertTrue(original['passed'],original)
                    node=ast.parse(task.public['source']).body[-1]
                    mutant='\n'.join(task.public['source'].splitlines()[node.lineno-1:node.end_lineno])+'\n'
                    verdict=bench.evaluate(task,{'code':mutant})
                    self.assertEqual(verdict['category'],'behavior_failed',verdict)


if __name__=='__main__':
    unittest.main()
