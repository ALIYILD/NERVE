import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from nerve_awim.uncertainty import cli

class UncertaintyCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.db=str(Path(self.tmp.name)/'nerve.sqlite3')
    def invoke(self,*args):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):code=cli.main([*args,'--state',self.db])
        return code,json.loads(output.getvalue())
    def demo(self):
        code,value=self.invoke('demo','--offline','--output',str(Path(self.tmp.name)/'demo'))
        self.assertEqual(code,0);return value
    def test_help_for_every_command(self):
        for cmd in ('doctor','demo','inspect','verify','resume','evaluate','freeze','report'):
            with contextlib.redirect_stdout(io.StringIO()),self.assertRaises(SystemExit) as e:cli.main([cmd,'--help'])
            self.assertEqual(e.exception.code,0)
    def test_doctor_truthful_offline(self):
        code,value=self.invoke('doctor','--json')
        self.assertEqual(code,0);self.assertFalse(value['live_provider_verified'])
        self.assertEqual(value['default_mode'],'shadow')
    def test_demo_inspect_resume_preserves_conflict_and_calls(self):
        demo=self.demo();self.assertTrue(demo['conflict_ids'])
        code,task=self.invoke('inspect','--task-id',demo['task_id'])
        self.assertEqual(code,0);self.assertTrue(task['conflicts'])
        before=sum(e['event']=='verification_reserved' for e in task['events'])
        code,resumed=self.invoke('resume','--run-id',demo['run_id'])
        self.assertEqual(code,0);self.assertEqual(resumed['repeated_calls'],0)
        self.assertEqual(resumed['envelope']['open_conflict_ids'],demo['conflict_ids'])
        self.assertTrue(resumed['result']['unresolved'])
        _,after=self.invoke('inspect','--task-id',demo['task_id'])
        self.assertEqual(sum(e['event']=='verification_reserved' for e in after['events']),before)
    def test_verify_inconclusive_exit_and_no_false_resolution(self):
        demo=self.demo()
        code,value=self.invoke('verify','--conflict-id',demo['conflict_ids'][0])
        self.assertEqual(code,4);self.assertEqual(value['boundary'],'unresolved_no_source')
        code,again=self.invoke('verify','--conflict-id',demo['conflict_ids'][0])
        self.assertEqual(code,4);self.assertTrue(again['deduplicated'])
    def test_no_tenant_or_role_grant_flags(self):
        for args in (['doctor','--tenant','other'],['doctor','--role','operator']):
            with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as e:cli.main(args)
            self.assertEqual(e.exception.code,2)
    def test_unknown_record_dependency_exit(self):
        code,_=self.invoke('inspect','--task-id','unknown-task')
        self.assertEqual(code,6)
    def test_exit_code_mapping(self):
        for exc,expected in ((PermissionError('denied'),3),(ValueError('invalid input'),2),
            (ValueError('revision changed'),7),(ValueError('integrity failure'),8),(RuntimeError('unavailable'),6)):
            with patch.object(cli,'execute',side_effect=exc):
                code,_=self.invoke('doctor');self.assertEqual(code,expected)
        with patch.object(cli,'execute',return_value=({'boundary':'unresolved_budget'},5)):
            self.assertEqual(self.invoke('doctor')[0],5)
