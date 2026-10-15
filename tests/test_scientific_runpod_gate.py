import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('runpod_gate',Path(__file__).resolve().parents[1]/'scripts/run_scientific_runpod_gate.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class RunpodGateTests(unittest.TestCase):
    def test_local_inference_denied(self):
        with patch.object(m.platform,'system',return_value='Darwin'):
            with self.assertRaisesRegex(RuntimeError,'inference_requires_registered_runpod'):m.network('/v1/chat/completions',b'{}')
    def test_timeout_retries_identical_bytes_and_journals(self):
        calls=[]
        def request(path,body,timeout):
            calls.append((path,body,timeout))
            if len(calls)<3:raise TimeoutError()
            return b'wire'
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch.object(m,'network',side_effect=request),patch.object(m,'decode',return_value=('ok',{},'stop')):
                self.assertEqual(m.attempt(root,0,{'seed':20261015},12),('ok',{},'stop'))
            self.assertEqual(len(calls),3);self.assertTrue(all(x==calls[0] for x in calls))
            self.assertEqual([m.read(root/f'attempt-000-{i}-result.json')['status'] for i in range(3)],['timeout','timeout','complete'])
    def test_non_timeout_never_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(m,'network',side_effect=ValueError('bad')) as call:
                with self.assertRaises(ValueError):m.attempt(Path(directory),0,{},12)
                self.assertEqual(call.call_count,1)
    def test_max_three_attempts(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(m,'network',side_effect=TimeoutError()) as call:
                with self.assertRaises(TimeoutError):m.attempt(Path(directory),0,{},12)
                self.assertEqual(call.call_count,3)
    def test_incomplete_cannot_promote(self):
        self.assertEqual(m.aggregate([],False)['verdict'],'incomplete_infrastructure')
    def test_wilson_edges(self):
        self.assertAlmostEqual(m.wilson(20,20)[0],0.8388748419471806)
        self.assertAlmostEqual(m.wilson(0,20)[1],0.16112515805281938)

class RegistrationBoundaryTests(unittest.TestCase):
    def fixtures(self,directory):
        root=Path(directory);ref=root/'reference';(ref/'receipt').mkdir(parents=True)
        reg={'identity':{'model':{'digest':m.DIGEST}},'seed':20261015,'sources':{}}
        m.write(ref/'registration.json',reg)
        report={'status':'complete','rows':[{'elapsed_seconds':1,'model_calls':int(i<160)} for i in range(400)],'model_calls':160,'registration_sha256':m.digest((ref/'registration.json').read_bytes())}
        m.write(ref/'receipt/report.json',report)
        manifest=ref/'manifest.json';m.write(manifest,{'name':'slice2','content_sha256':'fixed'})
        m.write(ref/'partition-preregistration.json',{'slices':{'slice2':{'manifest_sha256':m.digest(manifest.read_bytes())}}})
        return root,ref,manifest
    def test_wrong_manifest_rejected_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root,ref,manifest=self.fixtures(directory)
            manifest.write_text('{"name":"reserve"}')
            with patch.object(m,'network',side_effect=AssertionError('network forbidden')):
                with self.assertRaisesRegex(ValueError,'original_slice2_manifest'):m.register(root/'out','slice2',ref,manifest,root/'dry')
    def test_source_mismatch_rejected_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root,ref,manifest=self.fixtures(directory)
            reg=m.read(ref/'registration.json');reg['sources']={'source/src/nerve_awim/__init__.py':'wrong'}
            (ref/'registration.json').write_text(m.canonical(reg)+'\n')
            report=m.read(ref/'receipt/report.json');report['registration_sha256']=m.digest((ref/'registration.json').read_bytes());(ref/'receipt/report.json').write_text(m.canonical(report)+'\n')
            with patch.object(m,'network',side_effect=AssertionError('network forbidden')):
                with self.assertRaisesRegex(ValueError,'development_source_changed'):m.register(root/'out','slice2',ref,manifest,root/'dry')
    def test_unqualified_dry_rejected_before_consumption(self):
        with tempfile.TemporaryDirectory() as directory:
            root,ref,manifest=self.fixtures(directory)
            with patch.object(m,'verify',return_value={'dry_admission_passed':False}),patch.object(m,'network',side_effect=AssertionError('network forbidden')):
                with self.assertRaisesRegex(ValueError,'dry_not_qualified'):m.register(root/'out','slice2',ref,manifest,root/'dry')
            self.assertFalse((root/'out').exists())
