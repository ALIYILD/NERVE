"""Real 700-item development audit, with historical model receipts mocked only."""
from pathlib import Path
from contextlib import redirect_stdout
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.memory_gateway import scientific_candidate_route_audit as audit
from nerve_awim.memory_gateway import scientific_episode_import as importer
from nerve_awim.memory_gateway.inference import LocalInferenceAdapter


def historical_receipt():
    rows=[]
    for index,(task_id,arm) in enumerate(importer.validation.pairs()):
        output=importer.tasks._task(task_id)['expected']
        if importer.tasks.STRATA[task_id]=='conflict' and arm=='trusted_task':output='Poplar|mass|20.1|mg|validation-m'
        elif index==0:output='Answer: '+output
        elif index==2:output='ABSTAIN'
        rows.append(dict(task_id=task_id,arm=arm,raw_output=output,
            score=importer.tasks.judge(output,task_id),evidence={'context_sha256':'a'*64}))
    return {'protocol':{'source_sha256':{'fixture.py':'b'*64}},'rows':rows}


class ScientificCandidateRouteAuditTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.base=Path(temporary.name);self.episodes=self.base/'episodes';self.registered=self.base/'registered'
        self.history=self.base/'history';self.screen=self.base/'screen';self.bank=self.base/'bank';self.output=self.base/'audit'
        validator=patch.object(importer.validation,'validate_receipt',return_value=historical_receipt())
        validator.start();self.addCleanup(validator.stop)
        no_model=patch.object(LocalInferenceAdapter,'_model_response',side_effect=AssertionError('no model calls'))
        self.no_model=no_model.start();self.addCleanup(no_model.stop)
        importer.run(self.episodes,self.base/'validation',self.base/'claims.sqlite','d'*64)
        audit.screening.registration.run(self.registered,self.episodes)
        self.screened=audit.screening.run(self.screen,self.registered,self.history,initialize_history=True)
        self.pin=audit.bank_module.build(self.bank,host_seed='9'*64)['manifest_sha256']
        original_read=audit.bank_module._read
        def dev_only(path,limit):
            if Path(path).name=='holdout.json':raise AssertionError('holdout must stay closed')
            return original_read(path,limit)
        reader=patch.object(audit.bank_module,'_read',side_effect=dev_only)
        self.reader=reader.start();self.addCleanup(reader.stop)

    def run_audit(self):return audit.run(self.output,self.screen,self.bank,self.pin)

    def test_real_700_three_candidates_2100_preparations_no_answer_metadata(self):
        original=audit.execution.prepare;seen=[]
        def inspect(config,query,evidence):
            self.assertIsInstance(query,str)
            for record in evidence:self.assertEqual(set(record),audit.execution.FIELDS)
            prepared=original(config,query,evidence)
            self.assertNotIn('expected',prepared);self.assertNotIn('stratum',prepared)
            self.assertNotIn('task_id',prepared);self.assertNotIn('split',prepared)
            seen.append(prepared)
            return prepared
        with patch.object(audit.execution,'prepare',side_effect=inspect),patch.object(audit.execution,'execute',side_effect=AssertionError('no execution')):
            result=self.run_audit()
        self.assertEqual(len(seen),2100);self.assertEqual(result['development_items'],700)
        self.assertEqual(len(result['candidates']),3)
        self.assertEqual(result['candidates'][0]['routes'],{'model':600,'deterministic_conflict_abstention':100})
        self.assertEqual(result['candidates'][0]['prestep_abstentions_agreeing_with_dev_answer'],100)
        self.assertEqual(result['candidates'][0]['prestep_abstentions_disagreeing_with_dev_answer'],0)
        for candidate in result['candidates'][1:]:self.assertEqual(candidate['routes'],{'model':700})
        self.assertEqual(result['model_calls'],0);self.assertEqual(result['model_predictions'],0)
        self.assertFalse(result['efficacy_established']);self.assertFalse(result['holdout_accessed'])
        self.assertFalse(result['promotion_authorized']);self.no_model.assert_not_called()

    def test_replay_bytes_mtime_and_sources_unchanged(self):
        original={str(p):p.read_bytes() for p in (self.screen/'report.json',self.bank/'dev.json')}
        result=self.run_audit();path=self.output/'report.json';before=(path.read_bytes(),path.stat().st_mtime_ns)
        self.assertEqual(self.run_audit(),result)
        self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)
        self.assertEqual({str(p):p.read_bytes() for p in (self.screen/'report.json',self.bank/'dev.json')},original)
        self.assertEqual(self.output.stat().st_mode & 0o777,0o700)
        self.assertEqual(path.stat().st_mode & 0o777,0o600)

    def test_changed_source_rejected(self):
        with patch.object(audit,'sources',side_effect=[{'source':'a'*64},{'source':'b'*64}]):
            with self.assertRaisesRegex(ValueError,'inputs_changed'):self.run_audit()
        self.assertFalse(self.output.exists())

    def test_changed_screen_report_rejected_without_repair(self):
        path=self.screen/'report.json';path.write_text('{}')
        with self.assertRaises((ValueError,KeyError)):self.run_audit()
        self.assertEqual(path.read_text(),'{}');self.assertFalse(self.output.exists())

    def test_wrong_bank_pin_and_changed_development_rejected(self):
        self.pin='f'*64
        with self.assertRaisesRegex(ValueError,'task_bank_degraded'):self.run_audit()
        self.assertFalse(self.output.exists())
        from hashlib import sha256
        self.pin=sha256((self.bank/'manifest.json').read_bytes()).hexdigest()
        (self.bank/'dev.json').write_text('[]')
        with self.assertRaisesRegex(ValueError,'task_bank_degraded'):self.run_audit()
        self.assertFalse(self.output.exists())

    def test_private_output_and_bank_required(self):
        self.bank.chmod(0o755)
        with self.assertRaisesRegex(ValueError,'task_bank_degraded'):self.run_audit()
        self.bank.chmod(0o700);self.output.mkdir(mode=0o755)
        with self.assertRaisesRegex(ValueError,'private_directory'):self.run_audit()
        self.assertFalse((self.output/'report.json').exists())

    def test_cli_real_audit_no_execution(self):
        spec=importlib.util.spec_from_file_location('route_cli',importer.pilot.ROOT/'scripts/audit_scientific_candidate_routes.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        output=io.StringIO()
        with patch.object(sys,'argv',['audit','--directory',str(self.output),'--screen-directory',str(self.screen),'--bank-directory',str(self.bank),'--manifest-sha256',self.pin]),redirect_stdout(output),patch.object(audit.execution,'execute',side_effect=AssertionError('no execute')):
            module.main()
        report=json.loads(output.getvalue())
        self.assertEqual(report['development_items'],700)
        self.assertEqual(report['model_calls'],0)
        self.assertFalse(report['holdout_accessed'])

    def test_distinct_directories(self):
        for output,screen,bank in ((self.screen,self.screen,self.bank),(self.output,self.bank,self.bank),(self.bank/'nested',self.screen,self.bank)):
            with self.assertRaisesRegex(ValueError,'separate_audit'):audit.run(output,screen,bank,self.pin)


if __name__=='__main__':unittest.main()
