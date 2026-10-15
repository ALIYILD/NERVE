"""Actual importer, registration and rejection journal; no model inference."""
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from contextlib import redirect_stdout
import unittest
from unittest.mock import patch

from nerve_awim.memory_gateway import scientific_candidate_screening as screening
from nerve_awim.memory_gateway import scientific_episode_import as importer
from nerve_awim.memory_gateway.inference import LocalInferenceAdapter


def historical_receipt():
    rows=[]
    for task_id,arm in importer.validation.pairs():
        output=importer.tasks._task(task_id)['expected']
        if importer.tasks.STRATA[task_id]=='conflict' and arm=='trusted_task':
            output='Poplar|mass|20.1|mg|validation-m'
        rows.append(dict(task_id=task_id,arm=arm,raw_output=output,
            score=importer.tasks.judge(output,task_id),evidence={'context_sha256':'a'*64}))
    return {'protocol':{'source_sha256':{'fixture.py':'b'*64}},'rows':rows}


class ScientificCandidateScreeningTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.base=Path(temporary.name);self.episodes=self.base/'episodes';self.registered=self.base/'registered'
        self.history=self.base/'history';self.output=self.base/'screen'
        validator=patch.object(importer.validation,'validate_receipt',return_value=historical_receipt())
        validator.start();self.addCleanup(validator.stop)
        transport=patch.object(LocalInferenceAdapter,'_model_response',side_effect=AssertionError('no inference'))
        self.transport=transport.start();self.addCleanup(transport.stop)
        importer.run(self.episodes,self.base/'validation',self.base/'claims.sqlite','d'*64)
        self.registration=screening.registration.run(self.registered,self.episodes)

    def run_screen(self,initialize=False):
        return screening.run(self.output,self.registered,self.history,initialize_history=initialize)

    def test_explicit_empty_history_allows_only_unevaluated_proposals_and_restart(self):
        result=self.run_screen(True)
        self.assertEqual(result['status'],'screened')
        self.assertEqual(result['decision']['allowed'],self.registration['generation']['proposals'])
        self.assertEqual(result['decision']['blocked'],[])
        self.assertFalse(result['evaluated']);self.assertFalse(result['promotion_authorized'])
        self.assertFalse(result['holdout_accessed']);self.assertEqual(result['rejection_receipts_created'],0)
        self.assertEqual(result['new_model_calls'],0)
        paths=[self.history/'rejections.sqlite',self.history/'identity.json',self.output/'report.json']
        before={str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in paths}
        self.assertEqual(self.run_screen(),result)
        self.assertEqual({str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in paths},before)
        self.assertEqual(self.output.stat().st_mode & 0o777,0o700)
        self.assertEqual((self.output/'report.json').stat().st_mode & 0o777,0o600)
        self.transport.assert_not_called()

    def test_no_implicit_initialization(self):
        with self.assertRaises(ValueError):self.run_screen()
        self.assertFalse(self.history.exists());self.assertFalse(self.output.exists())
        self.history.mkdir(mode=0o700)
        result=self.run_screen()
        self.assertEqual(result['status'],'blocked');self.assertEqual(result['decision']['allowed'],[])
        self.assertFalse((self.history/'rejections.sqlite').exists())

    def test_deleted_history_with_identity_never_reinitialized(self):
        self.run_screen(True);path=self.history/'rejections.sqlite';path.unlink()
        before=(self.output/'report.json').read_bytes()
        with patch.object(screening.NegativeEvidenceJournal,'initialize',side_effect=AssertionError('no reset')):
            with self.assertRaisesRegex(ValueError,'missing_degraded'):self.run_screen(True)
        self.assertFalse(path.exists());self.assertEqual((self.output/'report.json').read_bytes(),before)

    def test_corrupt_history_fails_closed_without_overwrite(self):
        self.run_screen(True);path=self.history/'rejections.sqlite';path.write_bytes(b'corrupt')
        self.output=self.base/'screen-corrupt'
        result=self.run_screen()
        self.assertEqual(result['status'],'blocked');self.assertEqual(result['decision']['allowed'],[])
        self.assertTrue(result['decision']['blocked']);self.assertEqual(path.read_bytes(),b'corrupt')

    def test_wrong_history_scope_blocks_all_proposals(self):
        self.run_screen(True)
        with sqlite3.connect(self.history/'rejections.sqlite') as db:
            db.execute("UPDATE metadata SET scope=? WHERE id=1",(json.dumps({'tenant_id':'other','agent_id':'other','context':'other'}),))
        self.output=self.base/'screen-scope'
        result=self.run_screen()
        self.assertEqual(result['status'],'blocked');self.assertEqual(result['decision']['allowed'],[])

    def test_changed_report_not_overwritten(self):
        self.run_screen(True);path=self.output/'report.json';path.write_bytes(b'changed')
        with self.assertRaises(ValueError):self.run_screen()
        self.assertEqual(path.read_bytes(),b'changed')

    def test_changed_registration_rejected_before_history(self):
        path=self.registered/'report.json';report=json.loads(path.read_text())
        report['generation']['mode']='enumeration_fallback';path.write_text(importer.canonical(report)+'\n')
        before=path.read_bytes()
        with self.assertRaises(ValueError):self.run_screen(True)
        self.assertFalse(self.history.exists());self.assertFalse(self.output.exists())
        self.assertEqual(path.read_bytes(),before)

    def test_source_change_blocks_publication(self):
        with patch.object(screening,'sources',side_effect=[{'source':'a'*64},{'source':'b'*64}]):
            with self.assertRaisesRegex(ValueError,'inputs_changed'):self.run_screen(True)
        self.assertFalse(self.output.exists())

    def test_private_history_and_output_required(self):
        self.history.mkdir(mode=0o755)
        with self.assertRaisesRegex(ValueError,'private_directory'):self.run_screen(True)
        self.history.chmod(0o700);self.output.mkdir(mode=0o755)
        with self.assertRaisesRegex(ValueError,'private_directory'):self.run_screen(True)
        self.assertFalse((self.output/'report.json').exists())

    def test_distinct_directories_and_boolean_required(self):
        for output,history in ((self.registered,self.history),(self.output,self.registered),(self.output,self.output),(self.output,self.episodes),(self.output,self.episodes/'nested')):
            with self.assertRaises(ValueError):screening.run(output,self.registered,history,initialize_history=True)
        for value in (1,0,None,'yes'):
            with self.assertRaises(ValueError):screening.run(self.output,self.registered,self.history,initialize_history=value)
        self.assertFalse(self.history.exists())

    def test_cli_real_explicit_initialization(self):
        spec=importlib.util.spec_from_file_location('screening_cli',importer.pilot.ROOT/'scripts/screen_scientific_candidates.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        output=io.StringIO()
        with patch.object(sys,'argv',['screen','--directory',str(self.output),'--registration-directory',str(self.registered),'--history-directory',str(self.history),'--initialize-history']),redirect_stdout(output):
            module.main()
        self.assertEqual(json.loads(output.getvalue())['status'],'screened')
        self.transport.assert_not_called()


if __name__=='__main__':unittest.main()
