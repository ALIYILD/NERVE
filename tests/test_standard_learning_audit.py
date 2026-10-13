"""Hand-controlled sensor/action fixtures; no registered episodes are run."""
from copy import deepcopy
import unittest

from nerve_awim.fusion_v12 import LaggedPositionVelocityFilter
from nerve_awim.integrated_v13 import SensorOnlyController
from nerve_awim.single_use_standard import SingleUseStandardController
from nerve_awim.memory_gateway.standard_learning_audit import audit


def fixture(arm, *, recovery=False, observations=None):
    kind = SingleUseStandardController if arm == 'single_use' else SensorOnlyController
    core = kind(learning_rate=0. if arm == 'frozen' else .08)
    observations = observations if observations is not None else {1: (0, .1), 2: (1, .3), 3: (2, .5)}
    trace, events = [], []
    for step in range(80):
        before = core.gain
        sensor = None
        if step in observations:
            timestamp, velocity = observations[step]
            sensor = dict(timestamp=timestamp, velocity=velocity, route='active', accepted=True)
            core.ingest(timestamp-(6 if recovery and step > 6 else 0), velocity=velocity)
        if recovery and step == 6:
            sensor = dict(timestamp=5, velocity=.1, route='recovery', accepted=True)
            events.append(dict(step=6, incident=1, authorised=True, gain_before=core.gain, gain_after=core.gain))
            core.filter = LaggedPositionVelocityFilter(initial_position=.2, initial_velocity=.1)
            if core.drift_model is not None: core.drift_model.processed.clear()
        history = len(core.filter.actions)
        external = recovery and step in (4, 5)
        action = 0 if external else 1
        if not external: core.filter.step(action)
        trace.append(dict(step=step, sensor=sensor, action=action,
            action_source='external_supervisor' if external else 'controller',
            gain_before_observation=before, estimated_gain=core.gain,
            history_before=history, history_after=len(core.filter.actions),
            true_gain=object(), true_velocity=object(), true_position=object(),
            learning_updates=object()))
    return dict(steps=80, initial_gain=.27, final_gain=core.gain, trace=trace,
                recovery_events=events, learning_updates=object())


class StandardLearningAuditTests(unittest.TestCase):
    def test_actual_implementations_reconstruct_unique_vs_repeated_applications(self):
        for arm, total, unique in (('frozen', 0, 0), ('legacy', 3, 2), ('single_use', 2, 2)):
            with self.subTest(arm=arm):
                row = fixture(arm)
                result = audit(row, arm)
                self.assertEqual(result['ema_applications'], total)
                self.assertEqual(result['unique_transitions'], unique)
                self.assertEqual(result['repeated_applications'], total-unique)
                self.assertEqual(result['final_gain'], row['final_gain'])
                self.assertEqual(result['epochs'], 1)
                self.assertEqual(len(result['steps']), 80)
        legacy = audit(fixture('legacy'), 'legacy')
        self.assertEqual([a['transition'] for a in legacy['steps'][3]['applications']], [1, 2])
        fixed = audit(fixture('single_use'), 'single_use')
        self.assertEqual([a['transition'] for a in fixed['steps'][3]['applications']], [2])

    def test_truth_and_legacy_counters_are_not_read(self):
        for arm in ('legacy', 'single_use'):
            row = fixture(arm); expected = audit(row, arm)
            row['learning_updates'] = {'untrusted': 1000000}
            for step in row['trace']:
                for key in ('true_gain', 'true_position', 'true_velocity', 'learning_updates'):
                    del step[key]
            self.assertEqual(audit(row, arm), expected)

    def test_original_row_not_mutated(self):
        row = fixture('single_use')
        # Replace opaque sentinels solely to make structural equality meaningful.
        row['learning_updates'] = 0
        for step in row['trace']:
            for key in ('true_gain', 'true_velocity', 'true_position', 'learning_updates'): step[key] = 0
        before = deepcopy(row)
        audit(row, 'single_use')
        self.assertEqual(row, before)

    def test_delayed_pair_arrival_is_still_eligible(self):
        for arm in ('legacy', 'single_use'):
            row = fixture(arm, observations={2: (1, .3), 3: (0, .1)})
            result = audit(row, arm)
            self.assertEqual(result['ema_applications'], 1)
            self.assertEqual(result['steps'][2]['ema_applications'], 0)
            self.assertEqual(result['steps'][3]['applications'][0]['transition'], 1)

    def test_revised_pair_is_fitted_again_only_in_legacy(self):
        observations = {1: (0, .1), 2: (1, .3), 3: (1, .6)}
        for arm, count in (('legacy', 2), ('single_use', 1)):
            result = audit(fixture(arm, observations=observations), arm)
            self.assertEqual(result['ema_applications'], count)
            self.assertEqual(result['unique_transitions'], 1)

    def test_authorized_recovery_resets_local_mapping_not_gain(self):
        observations = {1: (0, .1), 2: (1, .3), 7: (6, .1), 8: (7, .3)}
        for arm in ('frozen', 'legacy', 'single_use'):
            result = audit(fixture(arm, recovery=True, observations=observations), arm)
            self.assertEqual(result['epochs'], 2)
            self.assertEqual(result['steps'][6]['epoch_origin'], 6)
            self.assertEqual(result['steps'][6]['gain_before'], result['steps'][6]['gain_after'])
            if arm != 'frozen':
                self.assertEqual(result['unique_transitions'], 2)
                self.assertEqual(result['steps'][8]['applications'][0]['transition'], 1)
                self.assertEqual(result['steps'][8]['applications'][0]['global_transition'], 7)

    def test_gain_before_estimated_and_final_tampering_rejected(self):
        for key in ('gain_before_observation', 'estimated_gain', 'final_gain'):
            row = fixture('single_use')
            if key == 'final_gain': row[key] = .99
            else: row['trace'][3][key] = .99
            with self.subTest(key=key), self.assertRaises(ValueError): audit(row, 'single_use')

    def test_arm_relabel_cannot_hide_repeated_learning(self):
        with self.assertRaises(ValueError): audit(fixture('legacy'), 'single_use')
        with self.assertRaises(ValueError): audit(fixture('single_use'), 'frozen')

    def test_recovery_authorization_and_gain_tampering_rejected(self):
        for field, value in (('authorised', False), ('authorised', 1), ('gain_after', .9), ('step', 5)):
            row = fixture('single_use', recovery=True)
            row['recovery_events'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): audit(row, 'single_use')

    def test_history_epoch_and_sensor_route_tampering_rejected(self):
        for change in ({'history_before': 99}, {'history_after': True}, {'action': True},
                       {'action_source': 'agent'}):
            row = fixture('single_use'); row['trace'][3].update(change)
            with self.assertRaises(ValueError): audit(row, 'single_use')
        for change in ({'timestamp': 3}, {'timestamp': True}, {'velocity': float('nan')},
                       {'velocity': True}, {'route': 'recovery'}, {'accepted': False}):
            row = fixture('single_use'); row['trace'][2]['sensor'].update(change)
            with self.assertRaises(ValueError): audit(row, 'single_use')

    def test_fixed_roster_initial_gain_and_event_order_enforced(self):
        for change in ('short', 'long', 'step', 'initial', 'duplicate-event', 'unknown-arm'):
            row = fixture('single_use', recovery=True)
            if change == 'short': row['trace'].pop()
            if change == 'long': row['trace'].append(row['trace'][-1])
            if change == 'step': row['trace'][2]['step'] = 4
            if change == 'initial': row['initial_gain'] = True
            if change == 'duplicate-event': row['recovery_events'] *= 2
            with self.subTest(change=change), self.assertRaises(ValueError):
                audit(row, 'unknown' if change == 'unknown-arm' else 'single_use')


if __name__ == '__main__': unittest.main()
