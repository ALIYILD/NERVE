import copy
from functools import partial
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.evidence_window_dynamics import EvidenceWindowGain, EvidenceWindowRuntime
from nerve_awim.identity_v26 import VerifiedIdentity
from nerve_awim.recovery_v25 import sign_approval
from nerve_awim.memory_gateway import recovery_adaptation as experiment

SECRET = b'synthetic-evidence-window-secret-32'


class Verifier:
    def verify(self, token, now):
        if token == 'valid':
            return VerifiedIdentity('operator', 'test', 'nerve', frozenset({'recovery-supervisor'}), now+100)


class EvidenceWindowTests(unittest.TestCase):
    def runtime(self, directory, **kwargs):
        return EvidenceWindowRuntime(verifier=Verifier(), issuer='test', audience='nerve',
            secret=SECRET, ledger_path=str(Path(directory)/'ledger.sqlite'), estimator='drift',
            max_missing=1, recovery_samples=2, **kwargs)

    def test_exact_weighting_window_order_and_old_evidence_rejection(self):
        model = EvidenceWindowGain(initial=.27, window=2, prior_weight=4.)
        self.assertTrue(model.update(2, 1, 0., .6))
        self.assertAlmostEqual(model.gain, (4*.27+.6)/5)
        self.assertTrue(model.update(3, -1, 0., -.4))
        self.assertAlmostEqual(model.gain, (4*.27+1.)/6)
        before = copy.deepcopy(vars(model))
        self.assertFalse(model.update(1, 1, 0., 1.))
        self.assertEqual(vars(model), before)
        self.assertTrue(model.update(4, 1, 0., .2))
        self.assertEqual(list(model.samples), [(3,.4), (4,.2)])
        self.assertAlmostEqual(model.gain, (4*.27+.6)/6)
        before = copy.deepcopy(vars(model))
        self.assertFalse(model.update(4, 1, 0., 1.))
        self.assertEqual(vars(model), before)

    def test_clipping_and_invalid_inputs_do_not_mutate(self):
        for sample, expected in ((1.3,1.),(-.3,.01)):
            model = EvidenceWindowGain(initial=.27, window=1, prior_weight=.001)
            self.assertTrue(model.update(0, 1, 0., sample))
            self.assertEqual(model.gain, expected)
        model = EvidenceWindowGain()
        for args in ((True,1,0.,.3),(-1,1,0.,.3),(1,True,0.,.3),
                     (1,0,0.,.3),(1,1,float('nan'),.3),(1,1,0.,float('inf')),
                     (1,1,0.,1.31),(1,1,0.,.3,1.)):
            before = copy.deepcopy(vars(model))
            self.assertFalse(model.update(*args))
            self.assertEqual(vars(model), before)

    def test_configuration_strict_and_hook_not_misrepresented_as_rate(self):
        for kwargs in ({'window':True},{'window':0},{'window':65},{'prior_weight':True},
                       {'initial':True},{'prior_weight':0},{'prior_weight':float('nan')}):
            with self.assertRaises(ValueError): EvidenceWindowGain(**kwargs)
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError): self.runtime(temp, forget_on_recovery=1)
            with self.assertRaises(ValueError): self.runtime(temp, learning_rate=.1)

    def test_forgetting_retains_gain_until_genuine_next_sample(self):
        model = EvidenceWindowGain()
        model.update(1,1,0.,.8)
        previous = model.gain
        model.forget_window()
        self.assertEqual(model.gain, previous)
        self.assertEqual(len(model.samples),0)
        self.assertFalse(model.update(1,1,0.,.8))
        model.processed.clear()  # Existing controller does this at epoch reseed.
        self.assertTrue(model.update(1,1,0.,.2))
        self.assertAlmostEqual(model.gain, (4*.27+.2)/5)

    def test_only_successful_authorized_recovery_changes_evidence(self):
        for forget in (False, True):
            with tempfile.TemporaryDirectory() as temp:
                r = self.runtime(temp, forget_on_recovery=forget, planning_horizon=3)
                c = r.controller
                model = c.core.drift_model
                model.update(1,1,0.,.8); c.core.gain=model.gain
                c.core.filter.set_next_gain(model.gain)
                before = copy.deepcopy(vars(model))
                r.sensor_missing()
                r.observe_recovery(1,observed_now=1,position=.1,velocity=.1)
                r.observe_recovery(2,observed_now=2,position=.2,velocity=.2)
                approval = sign_approval(SECRET,'operator','supervisor',c.incident,'nonce',200)
                self.assertFalse(r.authorise_recovery('bad',approval,100))
                self.assertEqual(vars(model),before)
                with self.assertRaises(ValueError):
                    c._reseed_observation(-1,observed_now=-1,position=0.,velocity=0.)
                self.assertEqual(vars(model),before)
                self.assertTrue(r.authorise_recovery('valid',approval,100))
                self.assertEqual(model.gain,before['gain'])
                self.assertEqual(c.core.filter.b,model.gain)
                self.assertEqual(len(model.samples),0 if forget else 1)
                self.assertEqual(model.processed,set())
                self.assertTrue(model.update(1,1,0.,.2))
                expected=(4*.27+.2)/(5) if forget else (4*.27+.8+.2)/6
                self.assertAlmostEqual(model.gain,expected)
                self.assertIsNotNone(r.tick().action)

    def test_runtime_missing_pairs_and_duplicate_observations(self):
        with tempfile.TemporaryDirectory() as temp:
            c = self.runtime(temp).controller
            c.core.filter.step(1); c.core.filter.step(1)
            c.ingest(1,velocity=.8)
            self.assertEqual(len(c.core.drift_model.samples),0)
            c.ingest(0,velocity=.27)
            model = c.core.drift_model
            self.assertEqual(len(model.samples),1)
            self.assertEqual(c.core.filter.b,model.gain)
            before=copy.deepcopy(vars(model))
            c.ingest(0,velocity=.27)
            self.assertEqual(vars(model),before)
            self.assertEqual(c.core.filter.transition_gains,(.27,.27))

    def test_development_smoke_uses_real_learning_recovery_and_original_trace_validator(self):
        for forget in (False, True):
            for horizon in (1,3):
                with patch.object(experiment,'NerveResearchRuntime',partial(EvidenceWindowRuntime,
                        forget_on_recovery=forget, planning_horizon=horizon)):
                    row=experiment.episode(5,'drift',True)
                experiment.validate(row,5,'drift',True)
                self.assertGreater(row['learning_updates'],0)
                self.assertEqual(row['metrics']['successful_recoveries'],1)
                self.assertEqual(row['metrics']['violations'],0)
