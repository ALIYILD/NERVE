import tempfile
import unittest
from pathlib import Path
from nerve_awim.adaptation_repository import run_sources,run_repository

class RepositoryAdaptationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.db=str(Path(self.tmp.name)/'state.db')
        self.sources=[('one.py','class Example:\n def method(self): return 1\ndef public(): return 2\n'),('two.py','def outer():\n def hidden(): return 3\n return hidden()\n')]
    def test_real_tool_correction_resume_and_reuse(self):
        result=run_sources(self.db,self.sources,restart=True)
        self.assertTrue(result['success']);self.assertTrue(result['resumed'])
        self.assertEqual([a['tool'] for a in result['attempts']],['regex-inventory','ast-inventory','ast-inventory'])
        self.assertEqual([a['status'] for a in result['attempts']],['failed','verified','verified'])
        self.assertEqual(result['correction_reuse'],1);self.assertEqual(result['receipt_count'],3)
        self.assertEqual(result['outputs'][1]['functions'],['outer'])
        self.assertEqual(result['review_probes'],1);self.assertEqual(result['status'],'completed')
    def test_strong_baseline_is_kept(self):
        result=run_sources(self.db,self.sources,policy='strong-baseline',mode='off')
        self.assertTrue(result['success']);self.assertEqual(len(result['attempts']),2)
        self.assertEqual(result['corrections'],0)
    def test_shadow_and_off_do_not_adapt(self):
        for mode in ('off','shadow'):
            result=run_sources(self.db+mode,self.sources,mode=mode)
            self.assertFalse(result['success']);self.assertEqual(result['corrections'],0)
            self.assertEqual(len(result['attempts']),1)
    def test_source_cannot_execute(self):
        marker=Path(self.tmp.name)/'never-created'
        source=f"open({str(marker)!r},'w').write('bad')\ndef safe(): pass\n"
        result=run_sources(self.db,[('payload.py',source)])
        self.assertTrue(result['success']);self.assertFalse(marker.exists())
    def test_scope_and_size_boundaries(self):
        with self.assertRaises(PermissionError):run_repository(self.db,self.tmp.name,paths=['../outside.py'])
        with self.assertRaises(ValueError):run_sources(self.db,[('large.py',' '*12001)])
    def test_structure_validation_stops_before_execute(self):
        with self.assertRaises(SyntaxError):run_sources(self.db,[('broken.py','def broken(')])
    def test_fabricated_fallback_result_is_rejected(self):
        from unittest.mock import patch
        with patch.dict('nerve_awim.adaptation_repository.TOOLS',{'ast-inventory':lambda source:['invented']}):
            result=run_sources(self.db,self.sources)
        self.assertFalse(result['success']);self.assertEqual(result['status'],'review-required')
        self.assertEqual(result['outputs'],[])
    def test_benchmark_does_not_claim_gain_over_capable_control(self):
        from nerve_awim.adaptation_repository_evaluation import benchmark_repository
        suite={'episodes_digest':'local-test','episodes':[{'id':'fixture','family':'methods','split':'development','files':self.sources,'restart':True}]}
        result=benchmark_repository(suite,split='development')
        self.assertEqual(result['policies']['strong-baseline']['successes'],1)
        self.assertEqual(result['policies']['corrections']['successes'],1)
        self.assertEqual(result['paired_success_difference'],0.)
        self.assertEqual(result['against_fixed_regex']['difference'],1.)
        self.assertTrue(result['hard_gates_passed'])
    def test_normal_repository_run_starts_with_capable_tool(self):
        root=Path(self.tmp.name)/'repo';root.mkdir();file=root/'source.py';file.write_text(self.sources[0][1])
        before=file.read_bytes()
        result=run_repository(self.db,root,paths=['source.py'])
        self.assertTrue(result['success']);self.assertEqual(result['corrections'],0)
        self.assertEqual(result['attempts'][0]['tool'],'ast-inventory')
        self.assertEqual(result['receipt_count'],1);self.assertEqual(file.read_bytes(),before)

    def test_repository_admin_across_processes(self):
        import json
        import os
        import subprocess
        root=Path(__file__).resolve().parents[1]
        state=Path(self.tmp.name)/'cli-state'
        source=Path(self.tmp.name)/'source.py';source.write_text(self.sources[0][1])
        def command(name,*extra,ok=True):
            report=Path(self.tmp.name)/(name+'.json')
            process=subprocess.run([os.sys.executable,str(root/'scripts/agentos_bridge.py'),name,'--state',str(state),'--repository',self.tmp.name,'--report',str(report),*extra],cwd=root,env={**os.environ,'PYTHONPATH':str(root/'src')},capture_output=True,text=True)
            if ok:
                self.assertEqual(process.returncode,0,process.stderr+process.stdout)
                return json.loads(report.read_text())
            self.assertNotEqual(process.returncode,0)
        result=command('adaptation-run','--source','source.py','--task-id','admin-test')
        self.assertTrue(result['success'])
        before=command('adaptation-status','--task-id','admin-test')
        after=command('adaptation-reset','--task-id','admin-test','--reason','operator-reset')
        self.assertEqual(before['action_receipts'],after['action_receipts'])
        self.assertEqual(before['steps'],after['steps'])
        self.assertEqual(after['status'],'completed')
        command('adaptation-status','--task-id','missing',ok=False)
        killed=command('adaptation-kill','--reason','operator-stop')
        self.assertTrue(killed['killed'])
        command('adaptation-run','--source','source.py','--task-id','after-kill',ok=False)

    def test_admin_requires_explicit_existing_scope(self):
        from types import SimpleNamespace
        from nerve_awim.adaptation_cli import dispatch
        args=SimpleNamespace(command='adaptation-status',synthetic=False,repository=None)
        with self.assertRaises(PermissionError):dispatch(args)
        args.repository=Path(self.tmp.name);args.state=Path(self.tmp.name)/'missing';args.task_id='missing'
        with self.assertRaises(FileNotFoundError):dispatch(args)
        args.synthetic=True
        with self.assertRaises(ValueError):dispatch(args)

    def test_repository_roots_isolate_grants_and_kill(self):
        from nerve_awim.adaptation_repository import build_repository
        roots=[Path(self.tmp.name)/name for name in ('a','b')]
        for root in roots:
            root.mkdir();(root/'source.py').write_text(self.sources[0][1])
        first=run_repository(self.db,roots[0],paths=['source.py'],task_id='root-a',initial_tool='regex-inventory',restart=True)
        self.assertTrue(first['success']);self.assertTrue(first['resumed'])
        a=build_repository(self.db,repository_root=roots[0])
        b=build_repository(self.db,repository_root=roots[1])
        with self.assertRaises(PermissionError):
            b['adaptation'].grant(b['operator'],'root-a',b['operator'],subject_scope=b['subject_scope'],review_reference='wrong-root')
        # Even supplying the known subject cannot cross the agent boundary.
        with self.assertRaises(PermissionError):
            b['adaptation'].grant(b['operator'],'root-a',b['operator'],subject_scope=a['subject_scope'],review_reference='wrong-root')
        a['adaptation'].kill_switch(a['operator'],reason='stop-root-a')
        with self.assertRaises(RuntimeError):
            run_repository(self.db,roots[0],paths=['source.py'],task_id='blocked-a')
        second=run_repository(self.db,roots[1],paths=['source.py'],task_id='root-b')
        self.assertTrue(second['success']);self.assertEqual(second['receipt_count'],1)
        with a['engine']._db() as con:
            import json
            stopped=json.loads(con.execute("SELECT state FROM adaptation_tasks WHERE id='blocked-a'").fetchone()[0])
        self.assertEqual(stopped['steps'],0)
        self.assertEqual(stopped['action_receipts'],{})

    def test_repository_alias_keeps_scope_and_kill(self):
        from nerve_awim.adaptation_repository import build_repository,repository_scope
        root=Path(self.tmp.name)/'repo';root.mkdir()
        (root/'source.py').write_text(self.sources[0][1])
        alias=Path(self.tmp.name)/'alias';alias.symlink_to(root,target_is_directory=True)
        self.assertEqual(repository_scope(root),repository_scope(alias))
        run_repository(self.db,root,paths=['source.py'],task_id='alias-task')
        c=build_repository(self.db,repository_root=alias)
        c['adaptation'].grant(c['operator'],'alias-task',c['operator'],subject_scope=c['subject_scope'],review_reference='alias-review')
        self.assertEqual(c['adaptation'].inspect(c['operator'],'alias-task')['status'],'completed')
        c['adaptation'].kill_switch(c['operator'],reason='alias-stop')
        with self.assertRaises(RuntimeError):run_repository(self.db,root,paths=['source.py'])

    def test_legacy_state_cannot_silently_change_namespace(self):
        from nerve_awim.adaptation_repository import build_repository
        run_sources(self.db,self.sources,task_id='legacy-task')
        with self.assertRaisesRegex(PermissionError,'legacy repository state'):
            build_repository(self.db,repository_root=self.tmp.name)
        # Historical receipts remain available through their original API scope.
        c=build_repository(self.db)
        c['adaptation'].grant(c['operator'],'legacy-task',c['operator'],subject_scope='repository',review_reference='legacy-review')
        self.assertEqual(len(c['adaptation'].inspect(c['operator'],'legacy-task')['action_receipts']),3)
        other=str(Path(self.tmp.name)/'legacy-kill.db')
        c=build_repository(other)
        c['adaptation'].kill_switch(c['operator'],reason='legacy-stop')
        with self.assertRaisesRegex(PermissionError,'legacy repository state'):
            build_repository(other,repository_root=self.tmp.name)
