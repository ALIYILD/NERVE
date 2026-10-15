"""Timing harness contracts; no repository-wide test run from these fixtures."""
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

PATH=Path(__file__).resolve().parents[1]/'scripts/timed_test_runner.py'
SPEC=importlib.util.spec_from_file_location('nerve_timed_test_runner',PATH)
s=importlib.util.module_from_spec(SPEC);sys.modules[SPEC.name]=s;SPEC.loader.exec_module(s)


class TimedTestRunnerTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)

    def test_exact_ids_frozen_even_if_test_overwrites_id_attribute(self):
        class Fixture(unittest.TestCase):
            def test_mutation(self):self.id='changed by test'
        fixture=Fixture('test_mutation');expected=fixture.id();path=self.root/'timings.json'
        with patch.object(s,'discover',return_value=([fixture],.01)):
            code=s.run('profile',path,None,stream=io.StringIO())
        report=json.loads(path.read_text())
        self.assertEqual(code,0);self.assertEqual(report['discovered_ids'],[expected])
        self.assertEqual(report['tests'][0]['id'],expected);self.assertTrue(report['complete_coverage'])
        self.assertGreaterEqual(report['tests'][0]['seconds'],0)
        self.assertIn(str(s.ROOT/'src'),os.environ['PYTHONPATH'].split(os.pathsep))

    def test_skips_failures_subtests_and_fixture_overhead_recorded(self):
        class Fixture(unittest.TestCase):
            @unittest.skip('intentional fixture')
            def test_skip(self):pass
            def test_subtest(self):
                with self.subTest(case='negative'):self.fail('intentional fixture')
        tests=[Fixture('test_skip'),Fixture('test_subtest')];path=self.root/'timings.json'
        with patch.object(s,'discover',return_value=(tests,.01)):
            code=s.run('profile',path,None,stream=io.StringIO())
        report=json.loads(path.read_text())
        self.assertEqual(code,1);self.assertEqual(report['skipped'],1);self.assertTrue(report['complete_coverage'])
        self.assertEqual({r['outcome'] for r in report['tests']},{'skipped','failed_subtest'})
        self.assertGreaterEqual(report['fixture_and_runner_seconds'],0)

    def test_module_partition_covers_all_ids_and_new_modules_default_fast(self):
        class A(unittest.TestCase):
            def runTest(self):pass
        class B(A):pass
        A.__module__='slow_fixture';B.__module__='new_fixture'
        tests=[A(),B()];manifest={'version':'unittest-tiers-v1','slow_modules':['slow_fixture']}
        self.assertEqual(s.partition(tests,'slow',manifest),tests[:1])
        self.assertEqual(s.partition(tests,'fast',manifest),tests[1:])
        self.assertEqual(s.partition(tests,'profile',None),tests)

    def profile(self):
        source=self.root/'fixture.py';source.write_text('# fixture\n')
        tests=[dict(id=module+'.Case.test',module=module,seconds=seconds,outcome='passed')
               for module,seconds in [('slow',200.0),('medium',60.0),('short',30.0)]]
        ids=[row['id'] for row in tests]
        report=dict(version=s.VERSION,tier='profile',successful=True,complete_coverage=True,failures=0,errors=0,
            unexpected_successes=0,selected_ids=ids,discovered_ids=ids,tests=tests,runner_sha256=s.digest(PATH),
            module_sources={'fixture':{'path':str(source),'sha256':s.digest(source)}},
            discovery_seconds=2,fixture_and_runner_seconds=8,skipped=0)
        path=self.root/'profile.json';path.write_text(json.dumps(report));return path,report

    def test_freeze_uses_measured_module_cost_and_justified_timeout(self):
        path,report=self.profile();target=self.root/'tiers.json'
        result=s.freeze(path,target)
        self.assertEqual(result['slow_modules'],['slow'])
        self.assertEqual(result['fast_estimated_seconds'],100)
        self.assertEqual(result['slow_timeout_seconds'],375)
        self.assertEqual(result['profile_sha256'],s.digest(path))
        self.assertEqual(result['new_modules_default'],'fast')

    def test_incomplete_failed_duplicate_or_changed_profile_cannot_freeze(self):
        for change in ('incomplete','failure','duplicate','changed'):
            path,report=self.profile()
            if change=='incomplete':report['tests'].pop()
            elif change=='failure':report['successful']=False
            elif change=='duplicate':report['discovered_ids'].append(report['discovered_ids'][0])
            else:(self.root/'fixture.py').write_text('# changed\n')
            path.write_text(json.dumps(report))
            with self.assertRaises(ValueError):s.freeze(path,self.root/'tiers.json')

    def test_discovery_import_does_not_execute_suite_or_main(self):
        spec=importlib.util.spec_from_file_location('spawn_import_fixture',PATH)
        module=importlib.util.module_from_spec(spec)
        with patch.object(unittest.TextTestRunner,'run',side_effect=AssertionError('import must not run')):
            spec.loader.exec_module(module)
        self.assertTrue(callable(module.main))


if __name__=='__main__':unittest.main()
