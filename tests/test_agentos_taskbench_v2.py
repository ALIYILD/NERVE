import ast
import sys
import unittest
from nerve_awim import agentos_taskbench as bench
from nerve_awim import agentos_taskbench_v2 as v2


class SecondRepairCohortTests(unittest.TestCase):
    def test_fixed_split_and_new_families(self):
        data=v2.dataset()
        self.assertEqual({k:len(v) for k,v in data.items()},dict(train=2,selection=3,retention=3,final=3))
        tasks=[t for group in data.values() for t in group]
        previous={t.public['family'] for group in bench.dataset().values() for t in group}
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
        a=v2.dataset(); b=v2.dataset()
        for phase in a:
            for x,y in zip(a[phase],b[phase]):
                self.assertEqual(bench.task_hash(x),bench.task_hash(y))
                exposed=bench.public_task(x)
                exposed['requirements']='changed'
                self.assertNotEqual(exposed,x.public)

    @unittest.skipUnless(sys.platform=='darwin','macOS sandbox integration')
    def test_all_references_pass_and_mutants_fail(self):
        for phase,tasks in v2.dataset().items():
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
