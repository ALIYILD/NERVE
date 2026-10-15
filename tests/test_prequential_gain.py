"""Real research-controller commands on local fixtures, no registered streams."""
from pathlib import Path
import tempfile
import unittest

from nerve_awim.identity_v26 import VerifiedIdentity
from nerve_awim.prequential_gain import PrequentialGainRuntime
from nerve_awim.recovery_v25 import sign_approval

SECRET = b'synthetic-prequential-test-secret'


class Verifier:
    def verify(self, token, now):
        if token == 'operator':
            return VerifiedIdentity('operator','test','nerve',frozenset({'recovery-supervisor'}),now+20)


class PrequentialGainTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name); self.counter = 0

    def runtime(self, **kwargs):
        self.counter += 1
        defaults = dict(target=100.,bound=1000.,safe_position=1000.,safe_velocity=100.,
                        max_missing=50,recovery_samples=2)
        defaults.update(kwargs)
        return PrequentialGainRuntime(verifier=Verifier(),issuer='test',audience='nerve',
            secret=SECRET,ledger_path=str(self.directory/f'{self.counter}.sqlite'),**defaults)

    def command(self, runtime):
        result = runtime.tick()
        self.assertIn(result.action, (-1,1))
        return runtime.controller.selector_snapshot()['pending'][-1]

    def test_stored_pre_outcome_forecasts_remain_immutable_during_shadow_learning(self):
        runtime = self.runtime(); controller = runtime.controller
        first = self.command(runtime)
        runtime.observe(0,velocity=.1)
        second = self.command(runtime)
        shadow_before = controller.core.drift_model.gain
        runtime.observe(1,velocity=.6)
        snapshot = controller.selector_snapshot()
        self.assertNotEqual(snapshot['shadow_gain'], shadow_before)
        self.assertEqual(snapshot['scores'][-1]['shadow_gain'], second['shadow_gain'])
        self.assertEqual(snapshot['scores'][-1]['learned_forecast'], second['learned_forecast'])
        self.assertEqual(snapshot['scores'][0]['nominal_forecast'], first['nominal_forecast'])
        self.assertEqual(snapshot['selected_gain'], .27)
        self.assertEqual(snapshot['mode'], 'nominal')
        self.assertEqual(controller.core.filter.b, .27)

    def test_four_favorable_scores_switch_to_shadow_and_four_unfavorable_switch_back(self):
        runtime = self.runtime(); controller = runtime.controller
        controller.core.drift_model.gain = .6
        for step in range(4):
            forecast = self.command(runtime)
            runtime.observe(step,velocity=forecast['learned_forecast'])
            if step < 3: self.assertEqual(controller.selector_snapshot()['mode'],'nominal')
        snapshot = controller.selector_snapshot()
        self.assertEqual(snapshot['mode'],'learned')
        self.assertEqual(snapshot['selected_gain'],snapshot['shadow_gain'])
        for step in range(4,8):
            forecast = self.command(runtime)
            runtime.observe(step,velocity=forecast['nominal_forecast'])
            # One non-improving pair disqualifies the window even if the
            # other three gains dominate its summed absolute error.
            self.assertEqual(controller.selector_snapshot()['mode'],'nominal')
            if step == 4:
                scores = controller.selector_snapshot()['scores']
                self.assertLess(sum(row['learned_error'] for row in scores),
                                sum(row['nominal_error'] for row in scores))
        snapshot = controller.selector_snapshot()
        self.assertEqual(snapshot['mode'],'nominal')
        self.assertEqual(snapshot['selected_gain'],.27)
        self.assertEqual(len(snapshot['scores']),4)
        self.assertEqual(snapshot['counts']['resolved'],8)

    def test_ties_keep_nominal(self):
        runtime = self.runtime()
        for step in range(4):
            # Exact constant nominal dynamics produce identical two forecasts.
            forecast = self.command(runtime)
            runtime.observe(step,velocity=forecast['nominal_forecast'])
        snapshot = runtime.controller.selector_snapshot()
        self.assertEqual(snapshot['mode'],'nominal')

    def test_missing_velocity_pending_and_corrections_never_rescore(self):
        runtime = self.runtime(); self.command(runtime)
        runtime.observe(0,position=.1)
        self.assertEqual(len(runtime.controller.selector_snapshot()['pending']),1)
        runtime.observe(0,velocity=.2)
        before = runtime.controller.selector_snapshot()
        runtime.observe(0,velocity=.9)
        self.assertEqual(runtime.controller.selector_snapshot(),before)

    def test_delayed_scores_use_resolution_order_and_original_forecasts(self):
        runtime = self.runtime()
        forecasts = [self.command(runtime) for _ in range(3)]
        runtime.observe(2,velocity=.4); runtime.observe(0,velocity=.1)
        snapshot = runtime.controller.selector_snapshot()
        self.assertEqual([row['timestamp'] for row in snapshot['scores']],[2,0])
        self.assertEqual(snapshot['scores'][0]['learned_forecast'],forecasts[2]['learned_forecast'])
        self.assertEqual([row['timestamp'] for row in snapshot['pending']],[1])

    def test_invalid_ingestion_cannot_score_or_mutate_selector(self):
        runtime = self.runtime(); self.command(runtime)
        before = runtime.controller.selector_snapshot()
        for timestamp, velocity in ((1,.2),(-1,.2),(0,float('nan'))):
            with self.assertRaises(ValueError): runtime.observe(timestamp,velocity=velocity)
            self.assertEqual(runtime.controller.selector_snapshot(),before)

    def test_pending_quota_eviction_is_not_recreated_by_late_observation(self):
        runtime = self.runtime(selector_pending_limit=2)
        for _ in range(3): self.command(runtime)
        snapshot = runtime.controller.selector_snapshot()
        self.assertEqual([row['timestamp'] for row in snapshot['pending']],[1,2])
        self.assertEqual(snapshot['counts']['evicted'],1)
        runtime.observe(0,velocity=.1)
        self.assertEqual(runtime.controller.selector_snapshot()['counts']['resolved'],0)

    def test_expired_pending_and_score_window_cannot_select_stale_gain(self):
        runtime = self.runtime(selector_max_age=4)
        runtime.controller.core.drift_model.gain=.6
        for step in range(4):
            forecast=self.command(runtime)
            runtime.observe(step,velocity=forecast['learned_forecast'])
        self.assertEqual(runtime.controller.selector_snapshot()['mode'],'learned')
        self.command(runtime)
        runtime.advance_time(10)
        snapshot=runtime.controller.selector_snapshot()
        self.assertEqual(snapshot['mode'],'nominal')
        self.assertEqual(snapshot['pending'],[])
        self.assertEqual(snapshot['scores'],[])
        self.assertEqual(snapshot['counts']['expired'],1)
        runtime.observe(4,velocity=.2)
        self.assertEqual(runtime.controller.selector_snapshot()['counts']['resolved'],4)

    def test_signed_recovery_resets_selector_but_preserves_shadow(self):
        runtime=self.runtime(max_missing=1); controller=runtime.controller
        controller.core.drift_model.gain=.6
        self.command(runtime)
        runtime.sensor_missing()
        runtime.observe_recovery(4,observed_now=4,position=.1,velocity=.1)
        runtime.observe_recovery(5,observed_now=5,position=.2,velocity=.1)
        approval=sign_approval(SECRET,'operator','supervisor',controller.incident,'nonce',20)
        before=controller.selector_snapshot()
        self.assertFalse(runtime.authorise_recovery('agent',approval,5))
        self.assertEqual(controller.selector_snapshot(),before)
        with self.assertRaises(PermissionError):
            controller._reseed_observation(5,observed_now=5,position=.2,velocity=.1)
        self.assertTrue(runtime.authorise_recovery('operator',approval,5))
        snapshot=controller.selector_snapshot()
        self.assertEqual(snapshot['shadow_gain'],.6)
        self.assertEqual(snapshot['selected_gain'],.27)
        self.assertEqual(snapshot['pending'],[]);self.assertEqual(snapshot['scores'],[])
        self.assertEqual(snapshot['counts']['recovery_resets'],1)
        forecast=self.command(runtime)
        self.assertEqual(forecast['timestamp'],6)
        self.assertFalse(runtime.authorise_recovery('operator',approval,5))

    def test_returned_snapshots_do_not_alias_mutable_internal_evidence(self):
        runtime=self.runtime();self.command(runtime)
        before=runtime.controller.selector_snapshot()
        changed=runtime.controller.selector_snapshot()
        changed['pending'][0]['learned_forecast']=999
        changed['counts']['resolved']=999
        self.assertEqual(runtime.controller.selector_snapshot(),before)

    def test_constructor_validation_before_ledger_and_custom_nominal(self):
        for kwargs in ({'selector_pending_limit':True},{'selector_pending_limit':129},
                       {'selector_max_age':0},{'learning_rate':0.},{'estimator':'drift'}):
            before=set(self.directory.iterdir())
            with self.assertRaises(ValueError): self.runtime(**kwargs)
            self.assertEqual(set(self.directory.iterdir()),before)
        runtime=self.runtime(gain=.4)
        self.assertEqual(runtime.controller.selector_snapshot()['nominal_gain'],.4)


if __name__=='__main__':unittest.main()
