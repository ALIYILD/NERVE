"""CCE host governance, persistent evidence and existing memory integration."""
from dataclasses import replace
import tempfile
from pathlib import Path
import unittest

from nerve_awim.agent_learning_v12 import RegisteredStrategy
from nerve_awim.governed_learning_v20 import GovernedLearning, LearningAuthority
from nerve_awim.cue_engine import Cue, ModelProfile
from nerve_awim.cue_evaluation import DatasetManifest, ModelParity, Observation, PairedResult
from nerve_awim.cue_learning import GovernedCueCoordinator
from nerve_awim.memory_v18 import TrustedMemoryLedger, MemoryAuthority


class CueLearningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.authority = LearningAuthority()
        self.actors = {r: self.authority.issue('tenant', 'agent', r)
                       for r in ('trainer', 'evaluator', 'operator', 'runtime', 'auditor')}
        self.engine = GovernedLearning(Path(self.temp.name) / 'db.sqlite', authority=self.authority,
            strategies=[RegisteredStrategy('baseline', 'research', lambda x: x)],
            judge=lambda task, value: True, contract_revision='test-v1', baseline_routes={'research': 'baseline'})
        self.engine.bootstrap(self.actors['operator'])
        self.now = 1000
        self.cce = GovernedCueCoordinator(self.engine, enabled=True, clock=lambda: self.now)
        self.profile = ModelProfile('fixture', 'model', 'r1', 'tok', 't1', ('instruction',), 'template-v1')
        self.cue = Cue('check', 1, 'Check the answer.', 'instruction', self.profile.key, ('research',), 'fixture')
        self.manifest = DatasetManifest(('d',), ('s',), tuple('h'+str(i) for i in range(30)))
        self.model = ModelParity('fixture', 'model', 'r1', 'tok', 't1', 'template-hash', 'sampling-hash', .6, 100, 'context-hash', self.profile.key)

    def propose(self):
        return self.cce.propose(self.actors['trainer'], self.cue, self.profile, 'research',
            self.manifest, generator_id='generator', model_config=self.model)

    def pairs(self, *, synthetic=False):
        # Fabricated UNIT TEST inputs exercise the trust contract, never exported
        # as live evidence. Production host must authenticate all measurements.
        return tuple(PairedResult(
            Observation(t, self.model, False, True, .1, 10, .01, t+'b', synthetic, '', 'baseline'),
            Observation(t, self.model, True, True, 1., 9, .009, t+'c', synthetic, self.cue.content_hash, 'candidate')) for t in self.manifest.holdout)

    def passed(self):
        candidate = self.propose()
        result = self.cce.evaluate(self.actors['evaluator'], candidate, self.pairs(), evaluator_id='independent')
        self.assertTrue(result['decision']['eligible'])
        return candidate

    def activate(self, candidate):
        return self.cce.activate(self.actors['operator'], candidate, expected_generation=0, reason='review', valid_for=100)

    def select(self):
        return self.cce.select(self.actors['runtime'], self.profile, 'research', permission_granted=True)

    def test_persistent_approved_route_expiry_and_no_effect_on_tool_release(self):
        original = self.engine.status(self.actors['runtime'])['active_release']
        candidate = self.passed()
        self.assertIsNone(self.select().cue)
        self.activate(candidate)
        self.assertEqual(self.select().cue.cue_id, 'check')
        self.cce = GovernedCueCoordinator(self.engine, enabled=True, clock=lambda: self.now)
        self.assertIsNotNone(self.select().cue)
        self.now += 101
        self.assertIsNone(self.select().cue)
        self.assertEqual(original, self.engine.status(self.actors['runtime'])['active_release'])

    def test_synthetic_evidence_never_activates(self):
        candidate = self.propose()
        result = self.cce.evaluate(self.actors['evaluator'], candidate, self.pairs(synthetic=True), evaluator_id='independent')
        self.assertIn('live_evidence_required', result['decision']['reasons'])
        with self.assertRaises(PermissionError): self.activate(candidate)

    def test_scope_role_and_forged_capability(self):
        candidate = self.passed()
        for role in ('trainer', 'evaluator', 'runtime', 'auditor'):
            with self.assertRaises(PermissionError):
                self.cce.activate(self.actors[role], candidate, expected_generation=0, reason='fake')
        foreign = self.authority.issue('other', 'agent', 'operator')
        with self.assertRaises(LookupError): self.cce.status(foreign, candidate)
        forged = replace(self.actors['trainer'], role='operator')
        with self.assertRaises(PermissionError): self.cce.revoke(forged, candidate, reason='fake')

    def test_one_evaluation_fresh_holdout_and_preregistered_model(self):
        candidate = self.propose()
        changed = tuple(PairedResult(replace(p.baseline, model=replace(self.model, temperature=.9)),
            replace(p.candidate, model=replace(self.model, temperature=.9))) for p in self.pairs())
        with self.assertRaises(ValueError): self.cce.evaluate(self.actors['evaluator'], candidate, changed, evaluator_id='independent')
        self.cce.evaluate(self.actors['evaluator'], candidate, self.pairs(), evaluator_id='independent')
        with self.assertRaises(ValueError): self.cce.evaluate(self.actors['evaluator'], candidate, self.pairs(), evaluator_id='independent')
        with self.assertRaises(ValueError): self.propose()

    def test_wrong_generator_identity_and_approval_race(self):
        candidate = self.propose()
        result = self.cce.evaluate(self.actors['evaluator'], candidate, self.pairs(), evaluator_id='generator')
        self.assertFalse(result['decision']['eligible'])
        with self.assertRaises(PermissionError): self.activate(candidate)

    def test_feedback_revokes_and_duplicate_feedback_rejected(self):
        candidate = self.passed(); self.activate(candidate)
        self.cce.feedback(self.actors['evaluator'], candidate, episode_id='outcome-1', safe=False, correct=True)
        self.assertIsNone(self.select().cue)
        self.assertEqual(self.cce.status(self.actors['auditor'], candidate)['status'], 'revoked')
        with self.assertRaises(PermissionError): self.activate(candidate)

    def test_default_off_and_clinical_and_permission_controls(self):
        candidate = self.passed(); self.activate(candidate)
        for kwargs in ({'clinical': True, 'permission_granted': True}, {'risk': 'high', 'permission_granted': True}, {}):
            self.assertIsNone(self.cce.select(self.actors['runtime'], self.profile, 'research', **kwargs).cue)
        self.cce = GovernedCueCoordinator(self.engine)
        self.assertIsNone(self.select().cue)

    def test_memory_export_is_pending_and_contains_no_cue_text(self):
        candidate = self.passed()
        authority = MemoryAuthority()
        actor = authority.issue('tenant', 'agent')
        ledger = TrustedMemoryLedger(self.engine.path, authority)
        memory_id = self.cce.export_memory(self.actors['auditor'], candidate, ledger, actor)
        record = ledger.status(actor, memory_id)
        self.assertEqual(record.status, 'pending')
        self.assertNotIn(self.cue.text, record.content)

    def test_persisted_version_immutable_even_with_fresh_holdout(self):
        self.propose()
        self.cue = replace(self.cue, text='Changed same version.')
        self.manifest = replace(self.manifest, holdout=tuple('new'+str(i) for i in range(30)))
        with self.assertRaises(ValueError): self.propose()

    def test_passed_evidence_expires_before_operator_approval(self):
        candidate = self.passed()
        self.now += 604801
        with self.assertRaises(ValueError): self.activate(candidate)

    def test_study_reservation_is_scoped_and_single_use(self):
        reservation = self.cce.reserve_study(self.actors['trainer'], self.manifest)
        with self.assertRaises(ValueError): self.cce.reserve_study(self.actors['trainer'], self.manifest)
        candidate = self.cce.propose(self.actors['trainer'], self.cue, self.profile, 'research',
            self.manifest, generator_id='generator', model_config=self.model, reservation=reservation)
        self.assertEqual(self.cce.status(self.actors['auditor'], candidate)['status'], 'pending')
        with self.assertRaises(ValueError):
            self.cce.propose(self.actors['trainer'], replace(self.cue, version=2), self.profile, 'research',
                self.manifest, generator_id='generator', model_config=self.model, reservation=reservation)


if __name__ == '__main__': unittest.main()
