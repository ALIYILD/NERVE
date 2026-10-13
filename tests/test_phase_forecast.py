import unittest
from nerve_awim.phase_forecast import PhaseAwareForecaster
from nerve_awim.identity_v26 import VerifiedIdentity


class Verifier:
    def verify(self, token, now):
        if token=='host':
            return VerifiedIdentity('host','test','forecast',frozenset({'actual-action-observer'}),now+1)


class PhaseForecastTests(unittest.TestCase):
    def make(self,**kwargs):
        return PhaseAwareForecaster(verifier=Verifier(),issuer='test',audience='forecast',subjects=frozenset({'host'}),**kwargs)

    def test_fixed_source_rule_preserves_controller_and_continuous_observer(self):
        router=self.make()
        first=router.record_action('host',now=0,step=0,action=1,gain=.27,source='controller',controller_velocity=.123)
        self.assertEqual(first.velocity,.123)
        second=router.record_action('host',now=1,step=1,action=0,gain=.27,source='external_supervisor')
        self.assertAlmostEqual(second.velocity,.82*.27)
        self.assertEqual(second.source,'external_supervisor')
        third=router.record_action('host',now=2,step=2,action=-1,gain=.27,source='controller',controller_velocity=-.25)
        self.assertEqual(third.velocity,-.25)

    def test_invalid_or_unauthorized_route_is_atomic(self):
        for token,kwargs in [('bad',{}),('host',{'source':'agent'}),('host',{'controller_velocity':True}),
                             ('host',{'controller_velocity':float('nan')}),
                             ('host',{'source':'external_supervisor'})]:
            router=self.make();before=router.snapshot()
            args=dict(now=0,step=0,action=1,gain=.27,source='controller',controller_velocity=.2)
            args.update(kwargs)
            with self.assertRaises((PermissionError,ValueError)):router.record_action(token,**args)
            self.assertEqual(router.snapshot(),before)

    def test_unknown_history_cannot_return_external_stale_forecast(self):
        router=self.make()
        router.record_unknown('host',now=0,step=0)
        result=router.record_action('host',now=1,step=1,action=0,gain=.27,source='external_supervisor')
        self.assertIsNone(result.velocity)
        router.observe('host',now=2,step=1,position=.5,velocity=.2)
        result=router.record_action('host',now=2,step=2,action=0,gain=.27,source='external_supervisor')
        self.assertAlmostEqual(result.velocity,.164)

    def test_valid_controller_forecast_is_distinct_from_unknown_observer(self):
        router=self.make()
        router.record_unknown('host',now=0,step=0)
        result=router.record_action('host',now=1,step=1,action=1,gain=.27,source='controller',controller_velocity=.4)
        self.assertEqual(result.velocity,.4)
        self.assertFalse(router.snapshot()['known'])

    def test_missing_controller_prediction_and_replayed_report_rejected(self):
        router=self.make()
        with self.assertRaises(ValueError):
            router.record_action('host',now=0,step=0,action=1,gain=.27,source='controller')
        router.record_action('host',now=0,step=0,action=1,gain=.27,source='controller',controller_velocity=.2)
        with self.assertRaises(ValueError):
            router.record_action('host',now=0,step=0,action=1,gain=.27,source='external_supervisor')

    def test_history_budget_exhaustion_has_no_external_fallback(self):
        router=self.make(max_history=1)
        router.record_action('host',now=0,step=0,action=1,gain=.27,source='external_supervisor')
        result=router.record_action('host',now=1,step=1,action=0,gain=.27,source='external_supervisor')
        self.assertIsNone(result.velocity)
        self.assertEqual(result.status,'history_budget_exhausted')
