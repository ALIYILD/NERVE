"""Historical receipt validation mocked; actual store, authority and export used."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.memory_gateway import scientific_episode_import as importer


def receipt():
    rows=[]
    for task_id, arm in importer.validation.pairs():
        task=importer.tasks._task(task_id)
        output=task['expected']
        if importer.tasks.STRATA[task_id]=='conflict' and arm=='trusted_task':
            output='Poplar|mass|20.1|mg|validation-m'
        rows.append(dict(task_id=task_id, arm=arm, raw_output=output,
                         score=importer.tasks.judge(output,task_id),
                         evidence={'context_sha256':'a'*64}))
    return {'protocol':{'source_sha256':{'frozen.py':'b'*64}}, 'rows':rows}


class ScientificEpisodeImportTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.base=Path(temporary.name);self.output=self.base/'import'
        self.validation=self.base/'validation';self.journal=self.base/'claims.sqlite'
        self.report=receipt()

    def run_import(self):
        with patch.object(importer.validation,'validate_receipt',return_value=self.report) as validator:
            result=importer.run(self.output,self.validation,self.journal,'d'*64)
        self.assertEqual(validator.call_count,3)
        validator.assert_called_with(self.validation,'d'*64,self.journal)
        return result

    def store(self):
        gateway,_,_,_,reader=importer.pilot._state(self.output/'authority.sqlite')
        return importer.ExperienceStore(self.output/'experiences.sqlite',gateway,importer.SCOPE),reader

    def test_disabled_has_no_io_or_validation(self):
        with patch.object(importer,'sources',side_effect=AssertionError('no sources')),patch.object(importer.validation,'validate_receipt',side_effect=AssertionError('no receipt')):
            result=importer.run(self.output,self.validation,self.journal,'bad',disabled=True)
        self.assertEqual(result,{'status':'off','reason':'disabled','new_model_calls':0})
        self.assertFalse(self.output.exists())

    def test_missing_completed_receipt_creates_nothing(self):
        with self.assertRaises(ValueError):
            importer.run(self.output,self.validation,self.journal,'d'*64)
        self.assertFalse(self.output.exists());self.assertFalse(self.validation.exists())

    def test_repeat_exact_export_and_two_conflicts(self):
        result=self.run_import();self.assertEqual(result['episode_count'],16)
        files={p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in (self.output/'episodes.jsonl',self.output/'report.json')}
        self.assertEqual(self.run_import(),result)
        for name,expected in files.items():
            path=self.output/name;self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),expected)
        store,reader=self.store()
        rows=store.query(reader,failure_class='conflict_non_abstaining')['episodes']
        self.assertEqual(len(rows),2);self.assertTrue(all(r['candidate_id']=='trusted_task' for r in rows))
        all_rows=store.query(reader)['episodes']
        self.assertTrue(all(r['timestamps'] is None and r['real_world_outcome'] is None for r in all_rows))
        self.assertFalse(result['rewards_written']);self.assertFalse(result['approved_knowledge_written'])

    def test_correct_answer_with_prose_not_declared_false_fact(self):
        row=self.report['rows'][0]
        row['raw_output']='Answer: '+importer.tasks._task(row['task_id'])['expected']
        row['score']=importer.tasks.judge(row['raw_output'],row['task_id'])
        self.run_import();store,reader=self.store()
        matches=[r for r in store.query(reader)['episodes'] if r['output']==row['raw_output']]
        self.assertEqual(len(matches),1)
        self.assertIsNone(matches[0]['evidence_ok']);self.assertFalse(matches[0]['format_ok'])
        self.assertEqual(matches[0]['evaluator_verdict'],'strict_incorrect')
        self.assertEqual(matches[0]['failure_class'],'format_failure')

    def test_roster_and_score_tampering_rejected_before_io(self):
        original=deepcopy(self.report)
        self.report['rows'].pop()
        with self.assertRaisesRegex(ValueError,'roster'):self.run_import()
        self.report=original;self.report['rows'][0]['score']['strict_correct']=False
        with self.assertRaisesRegex(ValueError,'score'):self.run_import()
        self.assertFalse(self.output.exists())

    def test_corrupt_existing_store_never_reset(self):
        self.run_import();path=self.output/'experiences.sqlite';path.write_bytes(b'corrupt')
        with self.assertRaises(Exception):self.run_import()
        self.assertEqual(path.read_bytes(),b'corrupt')

    def test_changed_receipt_cannot_append_to_same_destination(self):
        self.run_import();store,reader=self.store();before=store.query(reader)
        self.report['extra']='changed'
        with self.assertRaisesRegex(ValueError,'report_changed'):self.run_import()
        self.assertEqual(store.query(reader),before)

    def test_interrupted_report_cannot_rebind_existing_rows(self):
        self.run_import();store,reader=self.store();before=store.query(reader)
        (self.output/'report.json').unlink()
        self.report['different_receipt']=True
        with self.assertRaisesRegex(ValueError,'roster_changed'):self.run_import()
        self.assertEqual(store.query(reader),before)
        self.report.pop('different_receipt')
        self.run_import()
        self.assertEqual(store.query(reader),before)

    def test_changed_export_rejected_without_rewrite(self):
        self.run_import();path=self.output/'episodes.jsonl'
        path.write_bytes(b'changed')
        with self.assertRaises(ValueError):self.run_import()
        self.assertEqual(path.read_bytes(),b'changed')

    def test_deleted_store_is_not_rebuilt(self):
        self.run_import();path=self.output/'experiences.sqlite';path.unlink()
        exported=(self.output/'episodes.jsonl').read_bytes()
        with patch.object(importer.ExperienceStore,'initialize',side_effect=AssertionError('no initialize')):
            with self.assertRaisesRegex(ValueError,'missing_degraded'):self.run_import()
        self.assertFalse(path.exists())
        self.assertEqual((self.output/'episodes.jsonl').read_bytes(),exported)

    def test_disabled_requires_boolean(self):
        for value in (0,1,'yes',None):
            with self.assertRaisesRegex(ValueError,'boolean_disabled'):
                importer.run(self.output,self.validation,self.journal,'d'*64,disabled=value)
        self.assertFalse(self.output.exists())

    def test_final_receipt_change_prevents_complete_report(self):
        changed=deepcopy(self.report);changed['revoked']=True
        with patch.object(importer.validation,'validate_receipt',side_effect=[self.report,changed]):
            with self.assertRaisesRegex(ValueError,'receipt_changed'):
                importer.run(self.output,self.validation,self.journal,'d'*64)
        self.assertFalse((self.output/'report.json').exists())
        self.assertTrue((self.output/'experiences.sqlite').exists())
        self.assertFalse((self.output/'episodes.jsonl').exists())

    def test_private_directory_and_report_modes(self):
        self.run_import()
        self.assertEqual(self.output.stat().st_mode & 0o777,0o700)
        self.assertEqual((self.output/'report.json').stat().st_mode & 0o777,0o600)
        self.output.chmod(0o755)
        with self.assertRaisesRegex(ValueError,'private_import_directory'):self.run_import()
        self.output.chmod(0o700)
        (self.output/'report.json').chmod(0o644)
        with self.assertRaisesRegex(ValueError,'private_regular_report'):self.run_import()

    def test_final_validation_after_export_blocks_report(self):
        changed=deepcopy(self.report);changed['revoked']=True
        with patch.object(importer.validation,'validate_receipt',side_effect=[self.report,self.report,changed]):
            with self.assertRaisesRegex(ValueError,'receipt_changed'):
                importer.run(self.output,self.validation,self.journal,'d'*64)
        self.assertFalse((self.output/'report.json').exists())

    def test_interrupted_pending_report_resumes_without_rewriting_evidence(self):
        with patch.object(importer.os,'replace',side_effect=InterruptedError('injected before replace')):
            with self.assertRaises(InterruptedError):self.run_import()
        pending=self.output/'report.pending'
        self.assertTrue(pending.exists());self.assertFalse((self.output/'report.json').exists())
        names=('experiences.sqlite','episodes.jsonl','episodes.jsonl.manifest.json')
        before={name:((self.output/name).read_bytes(),(self.output/name).stat().st_mtime_ns) for name in names}
        expected=pending.read_bytes()
        self.run_import()
        self.assertFalse(pending.exists());self.assertEqual((self.output/'report.json').read_bytes(),expected)
        for name,value in before.items():
            path=self.output/name;self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),value)

    def test_pending_report_rejects_corrupt_public_or_symlink(self):
        payload={'status':'complete'}
        path=self.base/'report.json';pending=path.with_suffix('.pending')
        pending.write_bytes(b'corrupt');pending.chmod(0o600)
        with self.assertRaisesRegex(ValueError,'pending_import_report_changed'):importer._save_exact(path,payload)
        pending.write_text(importer.canonical(payload)+'\n');pending.chmod(0o644)
        with self.assertRaisesRegex(ValueError,'private_regular_pending'):importer._save_exact(path,payload)
        pending.unlink();target=self.base/'target';target.write_text(importer.canonical(payload)+'\n');target.chmod(0o600)
        pending.symlink_to(target)
        with self.assertRaisesRegex(ValueError,'private_regular_pending'):importer._save_exact(path,payload)
        self.assertFalse(path.exists());self.assertTrue(pending.is_symlink())

    def test_policy_identity_includes_model_digest(self):
        pins={'test.py':'a'*64}
        before=importer.episodes(self.report,pins)
        self.report['protocol']['expected_digest']='f'*64
        after=importer.episodes(self.report,pins)
        self.assertNotEqual(before[0]['policy_version'],after[0]['policy_version'])

    def test_changed_sources_stop_before_initialization(self):
        with patch.object(importer,'sources',side_effect=[{'one':'a'*64},{'one':'b'*64}]),patch.object(importer.validation,'validate_receipt',return_value=self.report):
            with self.assertRaisesRegex(ValueError,'source_code_changed'):
                importer.run(self.output,self.validation,self.journal,'d'*64)
        self.assertFalse(self.output.exists())


if __name__=='__main__':unittest.main()
