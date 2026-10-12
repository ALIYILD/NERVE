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
