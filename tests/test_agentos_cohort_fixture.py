"""Integrity checks for the separately reviewed v2 simulated evidence cohort."""
from hashlib import sha256
import json
from pathlib import Path
import unittest

from nerve_awim.agentos_audit_cohort import canonical_identity, cohort
from nerve_awim.agentos_audit_evidence import expected_decision
from nerve_awim.agentos_audit_fixtures import development_cases

EVIDENCE = Path(__file__).resolve().parents[1] / 'docs' / 'evidence'
FIXTURE = EVIDENCE / 'agentos-audit-composition-v2.json'
REVIEW = EVIDENCE / 'agentos-audit-composition-v2-review.json'


class FreshCohortFixtureTests(unittest.TestCase):
    def setUp(self):
        self.value = json.loads(FIXTURE.read_text())
        self.rows = [row for rows in self.value['splits'].values() for row in rows]

    def test_fixture_shape_and_host_authored_gold(self):
        self.assertEqual(set(self.value), {'scope', 'id', 'limitation', 'splits'})
        self.assertEqual(self.value['id'], 'audit-composition-20261012-v2')
        self.assertEqual(self.value['scope'], 'agentos-audit-composition-v1')
        self.assertEqual({phase: len(rows) for phase, rows in self.value['splits'].items()},
                         {'train': 2, 'selection': 4, 'retention': 4, 'final': 6})
        for row in self.rows:
            with self.subTest(case=row['id']):
                self.assertEqual(set(row), {'id', 'family', 'bundle', 'expected'})
                self.assertIs(row['bundle']['simulated'], True)
                self.assertEqual(row['expected'], expected_decision(row['bundle']))

    def test_no_cross_split_or_prior_canonical_reuse(self):
        previous = development_cases() + [row for rows in cohort()['splits'].values() for row in rows]
        previous_ids = {canonical_identity(row) for row in previous}
        identities = {canonical_identity(row) for row in self.rows}
        self.assertEqual(len(identities), 16)
        self.assertFalse(identities & previous_ids)
        for field in ('id', 'family'):
            self.assertEqual(len({row[field] for row in self.rows}), 16)
            self.assertFalse({row[field] for row in self.rows} & {row[field] for row in previous})

    def test_review_binds_exact_fixture_and_all_rationales(self):
        review = json.loads(REVIEW.read_text())
        self.assertEqual(review['cohort_sha256'], sha256(FIXTURE.read_bytes()).hexdigest())
        self.assertEqual(review['cohort_id'], self.value['id'])
        rationales = {row['id']: row for row in review['cases']}
        self.assertEqual(set(rationales), {row['id'] for row in self.rows})
        for row in self.rows:
            rationale = rationales[row['id']]
            self.assertEqual(rationale['expected_decision'], row['expected']['decision'])
            self.assertEqual(rationale['applicable_roots'],
                             [citation['source_id'] for citation in row['expected']['citations']])
            self.assertTrue(rationale['rationale'])
        self.assertIn('not independent production evidence', self.value['limitation'])
        self.assertEqual(review['model_calls'], 0)

    def test_evaluation_splits_do_not_reward_single_constant_decision(self):
        for phase in ('selection', 'retention', 'final'):
            with self.subTest(phase=phase):
                self.assertEqual({row['expected']['decision'] for row in self.value['splits'][phase]},
                                 {'supported', 'contradicted', 'unknown'})
        unknown = [row for row in self.rows if row['expected']['decision'] == 'unknown']
        self.assertTrue(any(row['expected']['citations'] for row in unknown))
        self.assertTrue(any(not row['expected']['citations'] for row in unknown))


if __name__ == '__main__':
    unittest.main()
