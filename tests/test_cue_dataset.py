import copy
from dataclasses import FrozenInstanceError
import json
import os
from pathlib import Path
import tempfile
import unittest

from nerve_awim.cue_dataset import load_dataset, parse_dataset_json
from nerve_awim.cue_evaluation import DatasetManifest
from nerve_awim.cue_experiment import ExperimentTask


def fixture():
    return {'schema_version': 1, 'dataset_id': 'benchmark-v1',
            'source': {'uri': 'fixture:offline', 'revision': 'commit-abc123'},
            'splits': {split: [{'task_id': split + '-1', 'family_id': 'family-' + split,
                               'instruction': 'Question: ' + split, 'expected': 'secret-answer-' + split}]
                       for split in ('discovery', 'selection', 'holdout')}}


class CueDatasetTests(unittest.TestCase):
    def parse(self, value=None, **kwargs):
        return parse_dataset_json(json.dumps(fixture() if value is None else value), **kwargs)

    def test_existing_contracts_frozen_fields_and_private_telemetry(self):
        data = self.parse()
        self.assertIsInstance(data.manifest, DatasetManifest)
        self.assertEqual(data.manifest.selection, ('selection-1',))
        self.assertIsInstance(data.holdout_tasks[0], ExperimentTask)
        self.assertEqual(data.holdout_tasks[0].expected, 'secret-answer-holdout')
        self.assertEqual(data.source_revision, 'commit-abc123')
        self.assertNotIn('secret-answer', repr(data))
        self.assertNotIn('Question:', str(data.telemetry()))
        self.assertEqual(data.telemetry()['counts'], {'discovery': 1, 'selection': 1, 'holdout': 1})
        with self.assertRaises(FrozenInstanceError):
            data.digest = 'forged'

    def test_digest_ignores_json_format_but_binds_answers_source_family_and_order(self):
        record = fixture()
        first = parse_dataset_json(json.dumps(record).encode())
        formatted = parse_dataset_json(json.dumps(record, sort_keys=True, indent=4))
        self.assertEqual(first.digest, formatted.digest)
        changes = [copy.deepcopy(record) for _ in range(4)]
        changes[0]['splits']['holdout'][0]['expected'] = 'different'
        changes[1]['source']['revision'] = 'other'
        changes[2]['splits']['holdout'][0]['family_id'] = 'other-family'
        changes[3]['dataset_id'] = 'other'
        for changed in changes:
            self.assertNotEqual(first.digest, self.parse(changed).digest)
        record['splits']['selection'].append({'task_id': 's2', 'family_id': 'family-selection',
                                              'instruction': 'second selected question', 'expected': 'x'})
        ordered = self.parse(record)
        record['splits']['selection'].reverse()
        self.assertNotEqual(ordered.digest, self.parse(record).digest)

    def test_duplicate_instruction_with_different_ids_or_answers_rejected(self):
        record = fixture()
        record['splits']['holdout'][0]['instruction'] = '  Question: discovery\n'
        with self.assertRaisesRegex(ValueError, 'duplicate instruction'):
            self.parse(record)
        record = fixture()
        duplicate = dict(record['splits']['selection'][0], task_id='different-id', expected='different')
        record['splits']['selection'].append(duplicate)
        with self.assertRaisesRegex(ValueError, 'duplicate instruction'):
            self.parse(record)

    def test_family_disjointness_allows_related_training_items_but_not_holdout_leakage(self):
        record = fixture()
        record['splits']['discovery'].append({'task_id': 'd2', 'family_id': 'family-discovery',
                                              'instruction': 'Paraphrased discovery question', 'expected': 'x'})
        self.assertEqual(len(self.parse(record).discovery_tasks), 2)
        record['splits']['holdout'][0]['family_id'] = 'family-discovery'
        with self.assertRaisesRegex(ValueError, 'family crosses'):
            self.parse(record)

    def test_duplicate_json_keys_nonfinite_and_malformed_json_fail_closed(self):
        for raw in ('{"schema_version":1,"schema_version":1}', '{"x":NaN}', '{', '[1]', b'\xff', '"\\ud800"'):
            with self.assertRaises(ValueError):
                parse_dataset_json(raw)

    def test_strict_nested_schema_and_identifier_types(self):
        bad = []
        for key in ('dataset_id', 'source', 'splits'):
            record = fixture(); record.pop(key); bad.append(record)
        record = fixture(); record['schema_version'] = True; bad.append(record)
        record = fixture(); record['unknown'] = True; bad.append(record)
        record = fixture(); record['source']['revision'] = ''; bad.append(record)
        record = fixture(); record['source']['extra'] = 'x'; bad.append(record)
        record = fixture(); record['splits']['holdout'] = []; bad.append(record)
        for key, value in (('task_id', 'bad id'), ('family_id', None), ('expected', {}),
                           ('instruction', ' \n'), ('unexpected', 'value')):
            record = fixture(); record['splits']['selection'][0][key] = value; bad.append(record)
        record = fixture(); record['splits']['holdout'][0]['task_id'] = 'selection-1'; bad.append(record)
        for record in bad:
            with self.assertRaises(ValueError):
                self.parse(record)

    def test_caps_count_utf8_bytes_and_reject_boolean_limits(self):
        raw = json.dumps(fixture())
        with self.assertRaises(ValueError):
            parse_dataset_json(raw, max_bytes=len(raw) - 1)
        for kwargs in ({'max_bytes': True}, {'max_tasks': True}, {'max_tasks': 2}, {'max_tasks': 10001}):
            with self.assertRaises(ValueError):
                self.parse(**kwargs)
        record = fixture()
        record['splits']['discovery'].append({'task_id': 'd2', 'family_id': 'fd2', 'instruction': 'q2', 'expected': 'x'})
        with self.assertRaisesRegex(ValueError, 'task cap'):
            self.parse(record, max_tasks=3)
        record = fixture(); record['splits']['holdout'][0]['instruction'] = '😀' * 17000
        with self.assertRaises(ValueError):
            self.parse(record)

    def test_regular_file_loader_and_fifo_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'dataset.json'
            path.write_text(json.dumps(fixture()))
            self.assertEqual(load_dataset(path).digest, self.parse().digest)
            with self.assertRaises(ValueError):
                load_dataset(path, max_bytes=20)
            fifo = Path(folder) / 'pipe'
            os.mkfifo(fifo)
            with self.assertRaisesRegex(ValueError, 'regular local'):
                load_dataset(fifo)


if __name__ == '__main__':
    unittest.main()
