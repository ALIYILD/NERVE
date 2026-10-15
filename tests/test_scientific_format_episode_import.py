"""Mock existing receipt validation; real v2 journal, scoped authority and export."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from nerve_awim.memory_gateway import scientific_format_episode_import as importer

DIGEST='d'*64


def receipt():
    config=dict(importer.study.candidates.SPACE['conflict_check'])
    rows=[]
    for task_id,constrained in importer.study.PAIRS:
        task=importer.study.tasks()[task_id]
        if constrained:
            shape=dict(task['expected']);shape['status']='abstain';shape['entity']='nonempty'
            output=importer.canonical(shape)
        else:output='Some prose describing the evidence.'
        rows.append(dict(task_id=task_id,constrained=constrained,response={'raw_output':output},
            score=importer.study.score(output,task_id),
            arm_config_sha256=importer.digest({'base_candidate_config':config,'constrained':constrained,'model_digest':DIGEST})))
    return dict(status='complete',protocol={'config':config,'expected_digest':DIGEST},rows=rows)


class ScientificFormatEpisodeImportTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.base=Path(temporary.name);self.root=self.base/'import';self.study=self.base/'study';self.journal=self.base/'study.sqlite'
        self.report=receipt()

    def run_import(self):
        with patch.object(importer.study,'validate_receipt',return_value=self.report) as validator,patch.object(importer.study,'run',side_effect=AssertionError('no dispatch')):
            result=importer.run(self.root,self.study,self.journal,DIGEST)
        self.assertEqual(validator.call_count,3)
        return result

    def stored(self):
        gateway,_,_,_,reader=importer.pilot._state(self.root/'authority.sqlite')
        store=importer.ExperienceStoreV2(self.root/'experiences.sqlite',gateway,importer.SCOPE)
        return store,reader

    def test_exact_four_rows_distinct_failures_no_factual_assertion(self):
        report=self.run_import();store,reader=self.stored();rows=store.query(reader)['episodes']
        self.assertEqual(report['episode_count'],4)
        self.assertEqual(len(store.query(reader,failure_class='schema_shape_failure')['episodes']),2)
        self.assertEqual(len(store.query(reader,failure_class='abstention_contract_failure')['episodes']),2)
        self.assertEqual([r['source_ordinal'] for r in rows],[0,1,2,3])
        for row,original in zip(rows,self.report['rows']):
            self.assertEqual(row['output'],original['response']['raw_output'])
            self.assertIsNone(row['evidence_ok']);self.assertIsNone(row['timestamps']);self.assertIsNone(row['real_world_outcome'])
            self.assertEqual(row['policy_version'],original['arm_config_sha256'])
            self.assertEqual(row['source_receipt_sha256'],importer.digest(self.report))
        self.assertEqual(report['new_model_calls'],0);self.assertFalse(report['rewards_written'])

    def test_repeat_export_bytes_and_mtime_unchanged(self):
        report=self.run_import();paths=[self.root/name for name in ('experiences.sqlite','episodes.jsonl','episodes.jsonl.manifest.json','report.json')]
        before={str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in paths}
        self.assertEqual(self.run_import(),report)
        self.assertEqual({str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in paths},before)

    def test_disabled_no_io_or_validation(self):
        with patch.object(importer,'sources',side_effect=AssertionError('no source IO')),patch.object(importer.study,'validate_receipt',side_effect=AssertionError('no validation')):
            self.assertEqual(importer.run(self.root,self.study,self.journal,'bad',disabled=True)['status'],'off')
        self.assertFalse(self.root.exists())

    def test_missing_receipt_never_dispatches_or_creates(self):
        with patch.object(importer.study,'run',side_effect=AssertionError('no dispatch')),patch.object(importer.study.transport,'run',side_effect=AssertionError('no transport')):
            with self.assertRaises(ValueError):importer.run(self.root,self.study,self.journal,DIGEST)
        self.assertFalse(self.study.exists());self.assertFalse(self.root.exists())

    def test_roster_score_and_policy_mutations_rejected(self):
        original=deepcopy(self.report)
        for mutate in (lambda r:r['rows'].pop(),lambda r:r['rows'][0]['score'].update(schema_valid=1),lambda r:r['rows'][0].update(arm_config_sha256='f'*64),lambda r:r.update(status='failed_consumed')):
            self.report=deepcopy(original);mutate(self.report)
            with self.assertRaises(ValueError):self.run_import()
        self.assertFalse(self.root.exists())

    def test_revocation_before_export_leaves_no_complete_artifacts(self):
        with patch.object(importer.study,'validate_receipt',side_effect=[self.report,PermissionError('revoked')]):
            with self.assertRaises(PermissionError):importer.run(self.root,self.study,self.journal,DIGEST)
        self.assertFalse((self.root/'episodes.jsonl').exists());self.assertFalse((self.root/'report.json').exists())

    def test_deleted_database_and_corrupt_database_never_reset(self):
        self.run_import();path=self.root/'experiences.sqlite';original=path.read_bytes();path.unlink()
        with patch.object(importer.ExperienceStoreV2,'initialize',side_effect=AssertionError('no reset')):
            with self.assertRaisesRegex(ValueError,'missing_degraded'):self.run_import()
        self.assertFalse(path.exists());path.write_bytes(b'corrupt');path.chmod(0o600)
        with self.assertRaises(Exception):self.run_import()
        self.assertEqual(path.read_bytes(),b'corrupt')

    def test_changed_receipt_cannot_append(self):
        self.run_import();store,reader=self.stored();before=store.query(reader)
        self.report['different']=True
        with self.assertRaises(ValueError):self.run_import()
        self.assertEqual(store.query(reader),before)

    def test_source_drift_blocks_store_creation(self):
        with patch.object(importer,'sources',side_effect=[{'a':'a'*64},{'a':'b'*64}]),patch.object(importer.study,'validate_receipt',return_value=self.report):
            with self.assertRaisesRegex(ValueError,'source_code_changed'):importer.run(self.root,self.study,self.journal,DIGEST)
        self.assertFalse(self.root.exists())

    def test_private_output_and_valid_supported_abstention(self):
        for row in self.report['rows']:
            row['response']['raw_output']=importer.canonical(importer.study.execution.ABSTAIN)
            row['score']=importer.study.score(row['response']['raw_output'],row['task_id'])
        self.run_import();store,reader=self.stored()
        self.assertEqual(len(store.query(reader,failure_class='supported_abstention')['episodes']),2)
        self.assertEqual(len(store.query(reader,failure_class='none')['episodes']),2)
        self.assertEqual(self.root.stat().st_mode & 0o777,0o700)
        self.assertEqual((self.root/'report.json').stat().st_mode & 0o777,0o600)


if __name__=='__main__':unittest.main()
