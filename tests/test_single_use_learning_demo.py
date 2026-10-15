import unittest
from nerve_awim.memory_gateway.single_use_learning_demo import run_demo


class SingleUseLearningDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.report = run_demo()

    def test_legacy_once_and_corrected_once_match_but_duplicates_diverge(self):
        result = self.report['duplicates']
        self.assertEqual(result['initial']['legacy']['gain'],.244)
        self.assertEqual(result['initial']['corrected']['gain'],.244)
        for row,expected in zip(result['repeats'],(.231,.2245,.22125)):
            self.assertAlmostEqual(row['legacy']['gain'],expected)
            self.assertEqual(row['corrected']['gain'],.244)
            self.assertEqual(row['corrected']['accepted_transitions'],[1])
        self.assertEqual(result['repeats'][-1]['corrected']['sensor_packets'],5)

    def test_revised_sensor_changes_filter_without_reusing_pair(self):
        revision = self.report['duplicates']['revision']
        self.assertEqual(revision['before']['gain'],revision['after']['gain'])
        self.assertEqual(revision['after']['accepted_transitions'],[1])
        self.assertNotEqual(revision['before']['filter_state'],revision['after']['filter_state'])

    def test_delayed_missing_pair_qualifies_once_when_predecessor_arrives(self):
        result = self.report['delayed']
        self.assertEqual(result['missing_predecessor']['gain'],.27)
        self.assertEqual(result['missing_predecessor']['accepted_transitions'],[])
        self.assertEqual(result['resolved']['gain'],.244)
        self.assertEqual(result['resolved']['accepted_transitions'],[1])
        self.assertEqual(result['resolved']['gain'],result['repeated']['gain'])

    def test_ema_delivery_order_is_not_claimed_commutative(self):
        result = self.report['delivery_order']
        self.assertFalse(result['order_invariance_claimed'])
        first,second = result['cases']
        self.assertEqual(first['result']['accepted_transitions'],[1,2])
        self.assertEqual(second['result']['accepted_transitions'],[1,2])
        self.assertAlmostEqual(first['result']['gain'],.349)
        self.assertAlmostEqual(second['result']['gain'],.29)

    def test_real_runtime_authorized_recovery_preserves_gain_and_resets_local_epoch(self):
        result = self.report['runtime_recovery']; recovery = result['recovery']
        self.assertFalse(recovery['invalid_identity_granted'])
        self.assertTrue(recovery['authorized'])
        self.assertEqual(recovery['gain_before'],recovery['gain_after'])
        self.assertEqual(recovery['gain_after'],.244)
        self.assertEqual(recovery['processed_after'],[])
        self.assertEqual([e['origin'] for e in result['epochs']],[0,9])
        self.assertEqual(result['accepted_updates_total'],2)
        for epoch in result['epochs']:
            self.assertEqual(epoch['actions'],[1,1])
            self.assertEqual(epoch['first']['accepted_transitions'],[1])
            self.assertEqual(epoch['first']['gain'],epoch['duplicate']['gain'])
        self.assertAlmostEqual(result['epochs'][1]['first']['gain'],.231)

    def test_scope_remains_mechanism_proof(self):
        for key in ('registered_streams_used','performance_improvement_claimed','model_weights_trained','candidate_promoted'):
            self.assertIs(self.report[key],False)
