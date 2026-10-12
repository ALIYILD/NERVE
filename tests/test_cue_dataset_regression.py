from dataclasses import replace
from hashlib import sha256
import json
import unittest

from nerve_awim.cue_dataset import FrozenCueDataset, parse_dataset_json, validate_dataset


def record(version=2):
    splits = ('discovery', 'selection', 'holdout', 'regression') if version == 2 else ('discovery', 'selection', 'holdout')
    return {'schema_version': version, 'dataset_id': 'schema-fixture',
            'source': {'uri': 'fixture:local', 'revision': 'rev1'},
            'splits': {split: [{'task_id': split + '1', 'family_id': 'family-' + split,
                               'instruction': 'Question ' + split, 'expected': 'Answer ' + split}]
                       for split in splits}}


def parse(value):
    return parse_dataset_json(json.dumps(value))


class RegressionDatasetTests(unittest.TestCase):
    def test_schema_two_builds_four_frozen_partitions_and_private_counts(self):
        dataset = parse(record())
        self.assertEqual(dataset.schema_version, 2)
        self.assertEqual(dataset.manifest.regression, ('regression1',))
        self.assertEqual(dataset.regression_tasks[0].expected, 'Answer regression')
        self.assertEqual(dataset.telemetry()['counts'], {'discovery': 1, 'selection': 1, 'holdout': 1, 'regression': 1})
        self.assertEqual(dataset.telemetry()['schema_version'], 2)
        self.assertNotIn('Answer regression', repr(dataset))
        self.assertEqual(validate_dataset(dataset), dataset)

    def test_schema_one_preserves_original_digest_and_positional_constructor(self):
        source = record(1)
        expected = sha256(json.dumps(source, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
        dataset = parse(source)
        self.assertEqual(dataset.digest, expected)
        self.assertEqual(dataset.regression_tasks, ())
        self.assertEqual(dataset.manifest.regression, ())
        legacy = FrozenCueDataset(dataset.dataset_id, dataset.source_uri, dataset.source_revision,
                                  dataset.digest, dataset.manifest, dataset.discovery_tasks,
                                  dataset.selection_tasks, dataset.holdout_tasks, dataset.families)
        self.assertEqual(legacy, dataset)
        self.assertEqual(validate_dataset(legacy), dataset)
        self.assertEqual(set(dataset.telemetry()['counts']), {'discovery', 'selection', 'holdout'})

    def test_version_exactly_controls_required_nonempty_splits(self):
        missing = record(); missing['splits'].pop('regression')
        empty = record(); empty['splits']['regression'] = []
        old_extra = record(); old_extra['schema_version'] = 1
        extra = record(); extra['splits']['test'] = extra['splits']['regression']
        for malformed in (missing, empty, old_extra, extra):
            with self.assertRaises(ValueError):
                parse(malformed)
        for version in (True, 0, 3, '2'):
            malformed = record(); malformed['schema_version'] = version
            with self.assertRaises(ValueError):
                parse(malformed)

    def test_regression_id_content_and_family_cannot_leak_from_other_splits(self):
        for field, value in (('task_id', 'holdout1'), ('instruction', ' Question selection '),
                             ('family_id', 'family-discovery')):
            source = record(); source['splits']['regression'][0][field] = value
            with self.assertRaises(ValueError):
                parse(source)

    def test_regression_content_and_version_are_bound_to_digest(self):
        dataset = parse(record())
        source = record(); source['splits']['regression'][0]['expected'] += ' changed'
        self.assertNotEqual(parse(source).digest, dataset.digest)
        self.assertNotEqual(parse(record(1)).digest, dataset.digest)
        altered = replace(dataset.regression_tasks[0], expected='forged answer')
        for forged in (replace(dataset, regression_tasks=(altered,)),
                       replace(dataset, regression_tasks=()),
                       replace(dataset, regression_tasks=list(dataset.regression_tasks)),
                       replace(dataset, schema_version=1),
                       replace(dataset, manifest=replace(dataset.manifest, regression=('other',)))):
            with self.assertRaises(ValueError):
                validate_dataset(forged)

    def test_schema_one_cannot_hide_regression_content_in_direct_dataclass(self):
        legacy, modern = parse(record(1)), parse(record())
        with self.assertRaises(ValueError):
            validate_dataset(replace(legacy, regression_tasks=modern.regression_tasks))
        with self.assertRaises(ValueError):
            validate_dataset(replace(legacy, manifest=modern.manifest))

    def test_regression_counts_toward_global_size_and_task_caps(self):
        with self.assertRaisesRegex(ValueError, 'task cap'):
            parse_dataset_json(json.dumps(record()), max_tasks=3)
        source = record()
        source['splits']['regression'][0]['instruction'] = 'x' * 65537
        with self.assertRaises(ValueError):
            parse(source)

    def test_regression_family_mapping_must_be_complete_and_in_canonical_order(self):
        dataset = parse(record())
        for forged in (replace(dataset, families=dataset.families[:-1]),
                       replace(dataset, families=dataset.families + (dataset.families[-1],)),
                       replace(dataset, families=tuple(reversed(dataset.families)))):
            with self.assertRaises(ValueError):
                validate_dataset(forged)


if __name__ == '__main__':
    unittest.main()
