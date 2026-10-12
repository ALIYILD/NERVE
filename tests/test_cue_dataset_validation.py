from dataclasses import replace
import json
import unittest

from nerve_awim.cue_dataset import parse_dataset_json, validate_dataset
from nerve_awim.cue_evaluation import DatasetManifest
from nerve_awim.cue_experiment import ExperimentTask


def fixture():
    return {'schema_version': 1, 'dataset_id': 'validate-v1',
            'source': {'uri': 'fixture:local', 'revision': 'revision-1'},
            'splits': {name: [{'task_id': name + '1', 'family_id': 'family-' + name,
                              'instruction': 'Question ' + name, 'expected': 'Answer ' + name}]
                       for name in ('discovery', 'selection', 'holdout')}}


class DatasetValidationTests(unittest.TestCase):
    def setUp(self):
        self.dataset = parse_dataset_json(json.dumps(fixture()))

    def test_revalidates_valid_content_into_fresh_equal_record(self):
        checked = validate_dataset(self.dataset)
        self.assertEqual(checked, self.dataset)
        self.assertIsNot(checked, self.dataset)
        self.assertIsNot(checked.manifest, self.dataset.manifest)

    def test_forged_digest_source_or_answer_rejected(self):
        task = self.dataset.holdout_tasks[0]
        variants = (replace(self.dataset, digest='f' * 64),
                    replace(self.dataset, source_revision='changed'),
                    replace(self.dataset, source_uri='fixture:changed'),
                    replace(self.dataset, holdout_tasks=(replace(task, expected='changed answer'),)))
        for dataset in variants:
            with self.assertRaises(ValueError):
                validate_dataset(dataset)

    def test_manifest_must_match_actual_order_and_membership(self):
        manifest = DatasetManifest(('different',), self.dataset.manifest.selection, self.dataset.manifest.holdout)
        with self.assertRaises(ValueError):
            validate_dataset(replace(self.dataset, manifest=manifest))
        with self.assertRaises(ValueError):
            validate_dataset(replace(self.dataset, manifest={'discovery': []}))

    def test_missing_duplicate_extra_or_wrong_split_family_mapping_rejected(self):
        families = self.dataset.families
        variants = (families[:-1], families + (families[0],),
                    families + (('unused', 'family-unused', 'holdout'),),
                    (('discovery1', 'family-discovery', 'holdout'),) + families[1:],
                    tuple(reversed(families)),
                    (('discovery1', 'changed-family', 'discovery'),) + families[1:])
        for mapping in variants:
            with self.assertRaises(ValueError):
                validate_dataset(replace(self.dataset, families=mapping))

    def test_mutable_or_unknown_task_and_family_shapes_rejected(self):
        variants = (replace(self.dataset, discovery_tasks=list(self.dataset.discovery_tasks)),
                    replace(self.dataset, discovery_tasks=({'task_id': 'discovery1'},)),
                    replace(self.dataset, families=list(self.dataset.families)),
                    replace(self.dataset, families=(('a', 'b'),) * 3),
                    replace(self.dataset, digest=True))
        for dataset in variants:
            with self.assertRaises(ValueError):
                validate_dataset(dataset)
        with self.assertRaises(ValueError):
            validate_dataset({'digest': self.dataset.digest})

    def test_bypassed_task_constructor_and_cross_split_duplicate_content_rejected(self):
        corrupt = object.__new__(ExperimentTask)
        object.__setattr__(corrupt, 'task_id', 'holdout1')
        object.__setattr__(corrupt, 'instruction', None)
        object.__setattr__(corrupt, 'expected', 'answer')
        with self.assertRaises(ValueError):
            validate_dataset(replace(self.dataset, holdout_tasks=(corrupt,)))
        duplicate = replace(self.dataset.holdout_tasks[0], instruction=self.dataset.discovery_tasks[0].instruction)
        with self.assertRaisesRegex(ValueError, 'duplicate instruction'):
            validate_dataset(replace(self.dataset, holdout_tasks=(duplicate,)))

    def test_family_cross_split_leakage_rejected_before_digest_comparison(self):
        families = tuple((task, 'shared' if split in ('discovery', 'holdout') else family, split)
                         for task, family, split in self.dataset.families)
        with self.assertRaisesRegex(ValueError, 'family crosses'):
            validate_dataset(replace(self.dataset, families=families))

    def test_task_order_and_whitespace_remain_bound(self):
        record = fixture()
        record['splits']['selection'].append({'task_id': 'selection2', 'family_id': 'family-selection',
                                              'instruction': 'second selection', 'expected': 'second answer'})
        dataset = parse_dataset_json(json.dumps(record))
        self.assertEqual(validate_dataset(dataset), dataset)
        with self.assertRaises(ValueError):
            validate_dataset(replace(dataset, selection_tasks=tuple(reversed(dataset.selection_tasks))))
        changed = replace(dataset.holdout_tasks[0], instruction=dataset.holdout_tasks[0].instruction + ' ')
        with self.assertRaises(ValueError):
            validate_dataset(replace(dataset, holdout_tasks=(changed,)))


if __name__ == '__main__':
    unittest.main()
