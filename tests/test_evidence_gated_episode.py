import copy
import unittest
from unittest.mock import patch
from nerve_awim.memory_gateway import evidence_gated_episode as worker


class EvidenceGatedEpisodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = {arm: worker.execute(8,'drift',arm) for arm in worker.ARMS}

    def test_all_arms_valid_and_matched_schedules(self):
        schedules=set()
        for arm,row in self.rows.items():
            worker.validate(row,8,'drift',arm)
            schedules.add(row['episode']['schedule_sha256'])
            self.assertEqual(row['episode']['metrics']['successful_recoveries'],1)
            self.assertEqual(row['episode']['metrics']['violations'],0)
        self.assertEqual(len(schedules),1)

    def test_sensor_reconstructed_learning_rejects_gain_and_window_tampering(self):
        for field,value in (('gain',.99),('samples',[[1,.99]]),('evidence_resets',77),('gain_changes',999),('last_threshold',99.)):
            row=copy.deepcopy(self.rows['gated_forget_h1'])
            row['learning_evidence'][60][field]=value
            with self.assertRaisesRegex(ValueError,'learning_evidence_mismatch'):
                worker.validate(row,8,'drift','gated_forget_h1')

    def test_arm_relabelling_cannot_hide_recovery_policy(self):
        row=copy.deepcopy(self.rows['gated_retain_h1'])
        row['arm']='gated_forget_h1'
        with self.assertRaisesRegex(ValueError,'learning_evidence_mismatch'):
            worker.validate(row,8,'drift','gated_forget_h1')

    def test_controls_match_original_runner(self):
        for arm in worker.ARMS[:4]:
            baseline=worker.controls.execute(8,'drift',arm)
            self.assertEqual(self.rows[arm]['episode'],baseline['episode'])
            self.assertIsNone(self.rows[arm]['learning_evidence'])

    def test_update_counts_must_match_reconstructed_learning(self):
        row=copy.deepcopy(self.rows['gated_forget_h1'])
        self.assertGreater(row['episode']['learning_updates'],0)
        for step in row['episode']['trace']:step['learning_updates']=0
        row['episode']['learning_updates']=0
        with self.assertRaisesRegex(ValueError,'learning_evidence_mismatch'):
            worker.validate(row,8,'drift','gated_forget_h1')

    def test_invalid_inputs_and_exception_restore_bindings(self):
        runtime,product=worker.episode.NerveResearchRuntime,worker.consistent_dynamics.product
        with self.assertRaises(ValueError):worker.execute(8,'drift','unknown')
        with patch.object(worker.episode,'episode',side_effect=RuntimeError('fixture')):
            with self.assertRaises(RuntimeError):worker.execute(8,'drift','gated_forget_h3')
        self.assertIs(worker.episode.NerveResearchRuntime,runtime)
        self.assertIs(worker.consistent_dynamics.product,product)

    def test_boolean_planner_count_and_invalid_elapsed_rejected(self):
        for key,value in (('planning_sequences',False),('elapsed_seconds',True),('elapsed_seconds',float('nan'))):
            row=copy.deepcopy(self.rows['gated_forget_h1']);row[key]=value
            with self.assertRaises(ValueError):worker.validate(row,8,'drift','gated_forget_h1')

    def test_evidence_consumption_and_gain_changes_are_distinct(self):
        for arm in worker.ARMS[4:]:
            row = self.rows[arm]
            changes = row['learning_evidence'][-1]['gain_changes']
            self.assertGreaterEqual(changes, 0)
            self.assertLessEqual(changes, row['episode']['learning_updates'])
            self.assertGreater(row['episode']['learning_updates'], 0)
            self.assertEqual(row['learning_evidence'][0]['gain_changes'], 0)
