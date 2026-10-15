"""Real episode importer/store and proposal registry; mock historical receipt only."""
from pathlib import Path
from contextlib import redirect_stdout
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.memory_gateway import scientific_candidate_registration as registration
from nerve_awim.memory_gateway import scientific_episode_import as importer
from nerve_awim.memory_gateway.inference import LocalInferenceAdapter


def receipt():
    rows=[]
    for task_id,arm in importer.validation.pairs():
        output=importer.tasks._task(task_id)['expected']
        if importer.tasks.STRATA[task_id]=='conflict' and arm=='trusted_task':
            output='Poplar|mass|20.1|mg|validation-m'
        rows.append(dict(task_id=task_id,arm=arm,raw_output=output,
                         score=importer.tasks.judge(output,task_id),
                         evidence={'context_sha256':'a'*64}))
    return {'protocol':{'source_sha256':{'fixture.py':'b'*64}},'rows':rows}


class ScientificCandidateRegistrationTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.base=Path(temporary.name);self.episodes=self.base/'episodes';self.output=self.base/'registration'
        validator=patch.object(importer.validation,'validate_receipt',return_value=receipt())
        self.validator=validator.start();self.addCleanup(validator.stop)
        no_inference=patch.object(LocalInferenceAdapter,'_model_response',side_effect=AssertionError('no inference permitted'))
        self.inference=no_inference.start();self.addCleanup(no_inference.stop)

    def imported(self):
        return importer.run(self.episodes,self.base/'validation',self.base/'journal.sqlite','d'*64)

    def run_registration(self,**kwargs):return registration.run(self.output,self.episodes,**kwargs)

    def test_missing_or_incomplete_import_is_not_created(self):
        with self.assertRaises((ValueError,OSError)):self.run_registration()
        self.assertFalse(self.episodes.exists());self.assertFalse(self.output.exists())
        self.episodes.mkdir(mode=0o700);(self.episodes/'report.json').write_text('{}')
        before=(self.episodes/'report.json').read_bytes()
        with self.assertRaises((ValueError,OSError)):self.run_registration()
        self.assertEqual((self.episodes/'report.json').read_bytes(),before)
        self.assertFalse((self.episodes/'experiences.sqlite').exists())
        self.validator.assert_not_called()

    def test_registration_restart_stable_and_no_inference(self):
        self.imported()
        original={p.name:p.read_bytes() for p in self.episodes.iterdir() if p.is_file()}
        result=self.run_registration();path=self.output/'report.json';before=(path.read_bytes(),path.stat().st_mtime_ns)
        self.assertEqual(self.run_registration(),result)
        self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)
        self.assertEqual({p.name:p.read_bytes() for p in self.episodes.iterdir() if p.is_file()},original)
        self.assertEqual(result['new_model_calls'],0);self.assertFalse(result['evaluated'])
        self.assertFalse(result['promotion_authorized']);self.assertFalse(result['holdout_opened'])
        proposal=result['generation']['proposals'][0]
        self.assertEqual(proposal['hypothesis']['mutation'],'conflict_check')
        self.assertEqual(len(proposal['hypothesis']['cluster']['members']),2)
        self.assertEqual(self.output.stat().st_mode & 0o777,0o700)
        self.assertEqual(path.stat().st_mode & 0o777,0o600)
        self.inference.assert_not_called()

    def test_disabled_research_is_honest_enumeration(self):
        self.imported();result=self.run_registration(research_agent_enabled=False)
        self.assertEqual(result['generation']['mode'],'enumeration_fallback')
        self.assertFalse(result['generation']['model_research_agent'])
        self.assertEqual(len(result['generation']['proposals']),4)
        self.assertFalse(result['generation']['negative_evidence_enforced'])
        self.inference.assert_not_called()

    def test_changed_configuration_and_output_rejected(self):
        self.imported();self.run_registration();path=self.output/'report.json';before=path.read_bytes()
        with self.assertRaises(ValueError):self.run_registration(research_agent_enabled=False)
        self.assertEqual(path.read_bytes(),before)
        path.write_bytes(b'changed')
        with self.assertRaises(ValueError):self.run_registration()
        self.assertEqual(path.read_bytes(),b'changed')

    def test_missing_source_store_not_reinitialized(self):
        self.imported();path=self.episodes/'experiences.sqlite';path.unlink()
        with patch.object(importer.ExperienceStore,'initialize',side_effect=AssertionError('no reset')):
            with self.assertRaises((ValueError,OSError)):self.run_registration()
        self.assertFalse(path.exists());self.assertFalse(self.output.exists())

    def test_corrupt_original_kept_and_no_output(self):
        self.imported();path=self.episodes/'experiences.sqlite';path.write_bytes(b'corrupt')
        with self.assertRaises(Exception):self.run_registration()
        self.assertEqual(path.read_bytes(),b'corrupt');self.assertFalse(self.output.exists())

    def test_source_changes_fail_before_publication(self):
        self.imported()
        with patch.object(registration,'sources',side_effect=[{'source':'a'*64},{'source':'b'*64}]):
            with self.assertRaisesRegex(ValueError,'inputs_changed'):self.run_registration()
        self.assertFalse(self.output.exists())

    def test_public_output_directory_rejected(self):
        self.imported();self.output.mkdir(mode=0o755)
        with self.assertRaisesRegex(ValueError,'private_registration_directory'):self.run_registration()
        self.assertFalse((self.output/'report.json').exists())

    def test_cli_uses_real_registration_with_disabled_enumeration(self):
        self.imported()
        spec=importlib.util.spec_from_file_location('scientific_candidate_cli',importer.pilot.ROOT/'scripts/register_scientific_candidates.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        stdout=io.StringIO()
        with patch.object(sys,'argv',['register','--directory',str(self.output),'--episode-directory',str(self.episodes),'--disable-research-agent','--max-proposals','2']),redirect_stdout(stdout):
            module.main()
        report=json.loads(stdout.getvalue())
        self.assertEqual(report['generation']['mode'],'enumeration_fallback')
        self.assertEqual(len(report['generation']['proposals']),2)
        self.inference.assert_not_called()

    def test_invalid_configuration_rejected_before_source_access(self):
        for kwargs in ({'research_agent_enabled':1},{'max_proposals':True},{'max_proposals':0},{'max_proposals':5},{'max_proposals':17}):
            with self.assertRaises(ValueError):self.run_registration(**kwargs)
        self.validator.assert_not_called();self.assertFalse(self.output.exists())


if __name__=='__main__':unittest.main()
