import ast
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim import agentos_taskbench as bench


class RepairBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.data=bench.dataset()

    def test_distinct_function_families_and_stable_public_identity(self):
        self.assertEqual({k:len(v) for k,v in self.data.items()},dict(train=2,selection=3,retention=3,final=3))
        tasks=[t for group in self.data.values() for t in group]
        self.assertEqual(len({t.public['family'] for t in tasks}),11)
        self.assertEqual(len({bench.task_hash(t) for t in tasks}),11)
        for task in tasks:
            public=bench.public_task(task)
            self.assertEqual(set(public),{'id','family','source','function','requirements','revision'})
            public['id']='renamed'
            self.assertEqual(bench.task_hash(task),bench.task_hash(public))
            self.assertNotIn('checks',public)
            self.assertNotIn('original',public)
            self.assertNotEqual(public['source'],task.original)

    def test_adversarial_capabilities_and_judge_tampering_rejected(self):
        task=self.data['train'][1]
        patches=[
            'def _counter(value):\n import os\n return os.environ',
            'def _counter(value):\n return open("/etc/passwd").read()',
            'def _counter(value):\n return value.__class__.__mro__',
            'def _counter(value):\n json.dumps = lambda _: \'{"passed":5,"total":5}\'\n return value',
            'def _counter(value):\n return globals()',
            'def _counter(value):\n return __import__("socket")',
            'def _counter(value):\n global json\n return value',
            '@print("side effect")\ndef _counter(value):\n return value',
            'def _counter(value=open("secret")):\n return value',
            'def _counter(value):\n return value\nprint("forged")',
        ]
        with patch.object(bench.subprocess,'Popen',side_effect=AssertionError('must reject before execution')):
            for code in patches:
                with self.subTest(code=code):
                    self.assertEqual(bench.evaluate(task,{'code':code})['category'],'patch_rejected')

    def test_corrupt_patch_contract_rejected(self):
        task=self.data['train'][0]
        invalid=[{'source':task.original}, {'code':task.original,'passed':True},
                 task.original.replace('_normalise_trim(value)', '_normalise_trim(value, extra=None)'),
                 task.original.replace('_normalise_trim(value)', 'other(value)')]
        with patch.object(bench.subprocess,'Popen',side_effect=AssertionError('must reject before execution')):
            for output in invalid:
                with self.subTest(output=output):
                    self.assertEqual(bench.evaluate(task,output)['category'],'patch_rejected')

    @unittest.skipUnless(sys.platform=='darwin','macOS sandbox integration')
    def test_raw_validation_precedes_trimming(self):
        task=self.data['train'][0]
        flawed='def _normalise_trim(value):\n    if not isinstance(value, str):\n        raise ValueError("bad input")\n    stripped=value.strip()\n    if not 1 <= len(stripped) <= 180:\n        raise ValueError("bad length")\n    return stripped.lower()'
        result=bench.evaluate(task,flawed)
        self.assertEqual(result['category'],'behavior_failed',result)
        self.assertEqual((result['tests_passed'],result['tests_total']),(7,9))

    def test_unavailable_sandbox_fails_closed(self):
        task=self.data['train'][0]
        with patch.object(bench.sys,'platform','linux'), patch.object(bench.subprocess,'Popen',side_effect=AssertionError('no fallback execution')):
            result=bench.evaluate(task,bench.reference_solution(task))
        self.assertFalse(result['passed'])
        self.assertEqual(result['category'],'sandbox_unavailable')

    @unittest.skipUnless(sys.platform=='darwin','macOS sandbox integration')
    def test_all_originals_pass_and_all_curated_mutations_fail(self):
        for split,tasks in self.data.items():
            for task in tasks:
                with self.subTest(split=split,function=task.public['function']):
                    reference=bench.evaluate(task,bench.reference_solution(task))
                    self.assertTrue(reference['passed'],reference)
                    node=ast.parse(task.public['source']).body[-1]
                    mutant='\n'.join(task.public['source'].splitlines()[node.lineno-1:node.end_lineno])+'\n'
                    result=bench.evaluate(task,{'code':mutant})
                    self.assertFalse(result['passed'],result)
                    self.assertEqual(result['category'],'behavior_failed',result)

    @unittest.skipUnless(sys.platform=='darwin','macOS sandbox integration')
    def test_nonterminating_patch_killed_by_timeout(self):
        task=self.data['train'][1]
        result=bench.evaluate(task,'def _counter(value):\n while True:\n  pass',timeout=0.2)
        self.assertEqual(result['category'],'timeout',result)

    @unittest.skipUnless(sys.platform=='darwin','macOS sandbox integration')
    def test_kernel_denies_home_reads_and_network_even_for_trusted_probe(self):
        task=self.data['train'][0]
        with tempfile.NamedTemporaryFile(prefix='.nerve-sandbox-probe-',dir=Path.home()) as sentinel:
            probe='''import json,socket
read_denied=network_denied=False
try:
    open(PATH).read()
except PermissionError:
    read_denied=True
try:
    socket.socket().connect(('127.0.0.1',3737))
except PermissionError:
    network_denied=True
print(json.dumps(dict(passed=COUNT if read_denied and network_denied else 0,total=COUNT,memory_limited=False)))
'''.replace('PATH',repr(sentinel.name)).replace('COUNT',str(len(task.checks)))
            with patch.object(bench,'_RUNNER',probe):
                result=bench.evaluate(task,bench.reference_solution(task))
            self.assertTrue(result['passed'],result)
