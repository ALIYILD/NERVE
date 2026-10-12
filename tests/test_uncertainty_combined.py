"""Combined real ARC/adaptation/uncertainty tests, enabled when adaptation is imported.

Absence is an explicit dependency skip, never counted as integration evidence.
A present but broken adaptation import fails normally rather than being skipped.
"""
import importlib.util
from pathlib import Path
import tempfile
import unittest

from nerve_awim.uncertainty.contracts import Claim
from nerve_awim.uncertainty.ledger import Ledger
from nerve_awim.uncertainty.policy import Policy
from nerve_awim.uncertainty.propagation import Propagator
from nerve_awim.uncertainty.output_guard import OutputGuard

_ADAPTATION_AVAILABLE = importlib.util.find_spec('nerve_awim.adaptation') is not None


@unittest.skipUnless(_ADAPTATION_AVAILABLE, 'adaptation package not yet imported into this checkout')
class CombinedUncertaintyTests(unittest.TestCase):
    def setUp(self):
        from nerve_awim.adaptation_replay import build, start
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'combined.sqlite3'
        self.now = 100.0
        self.build = build
        self.start = start
        self.c = build(self.path, now=lambda: self.now)
        start(self.c, task='combined', subject='synthetic-subject')
        self.ledger = Ledger(self.c['engine'], clock=lambda: self.now)
        self.policy = Policy(self.ledger, clock=lambda: self.now)
        self.propagator = Propagator(self.ledger)
        self.actor = self.c['actor']

    def claim(self, ident, value, *, predicate='required-source', task='combined'):
        source = self.ledger.register_source(self.actor, 'source-' + ident,
            {'value': value, 'predicate': predicate, 'synthetic': True})
        claim = Claim(ident, 'synthetic', task, 'synthetic-subject', predicate, value, **source)
        self.ledger.add_claim(self.actor, claim)
        return claim

    def execute(self, heading, *, task='combined', deps=('claim-yes',), parent=None, section='first'):
        decision = self.c['runtime'].propose(self.actor, task, 'note',
            {'heading': heading, 'facts': 'synthetic-fact', 'section': section}, [],
            'synthetic-goal', ['objective'], parent_decision_id=parent)
        assessment = self.policy.assess(self.actor, task, decision.decision_id,
            'note', list(deps), required=True)
        self.policy.bind(self.actor, decision.decision_id)
        outcome = self.c['runtime'].execute(self.actor, decision.decision_id)
        return decision, assessment, outcome

    def test_verified_local_correction_cannot_override_new_material_conflict(self):
        from nerve_awim.adaptation_replay import correction
        self.claim('claim-yes', True)
        first, _, failed = self.execute('wrong')
        self.assertNotEqual(failed.semantic_status, 'verified')
        correction_id = correction(self.c, 'combined', first.decision_id, 'verified-heading')
        context = self.c['adaptation'].read_context(self.actor, 'combined')
        self.assertEqual(context['corrections'][0]['correction_id'], correction_id)
        second, _, verified = self.execute(context['corrections'][0]['proposed_change']['value'],
            parent=first.decision_id, section='corrected')
        self.assertEqual(verified.semantic_status, 'verified')
        self.assertEqual(len(self.c['effects']), 2)

        self.claim('claim-no', False)
        conflict = self.ledger.detect(self.actor, 'combined')[0]
        third, assessment, denied = self.execute('verified-heading', section='dependent-next-step')
        self.assertEqual(assessment.status, 'verify_first')
        self.assertNotEqual(denied.semantic_status, 'verified')
        self.assertEqual(len(self.c['effects']), 2)
        state = self.c['adaptation'].inspect(self.actor, 'combined')
        self.assertIn(third.decision_id, state['action_receipts'])
        output = OutputGuard(self.ledger, self.policy).render(self.actor, 'combined',
            [{'claim_id': 'claim-yes', 'decision_id': third.decision_id}], [assessment])
        self.assertEqual(output['supported'], [])
        self.assertEqual(output['unresolved'][0]['conflict_id'], conflict.conflict_id)
        with self.c['engine']._db() as con:
            self.assertGreater(con.execute('SELECT count(*) FROM adaptation_events').fetchone()[0], 0)
            self.assertEqual(con.execute('SELECT count(*) FROM arc_decisions').fetchone()[0], 3)
            self.assertEqual(con.execute('SELECT count(*) FROM uc_conflicts').fetchone()[0], 1)

    def test_checkpoint_restart_and_reset_do_not_rewind_uncertainty(self):
        self.claim('claim-yes', True)
        self.execute('verified-heading')
        adaptation_checkpoint = self.c['adaptation'].checkpoint(self.actor, 'combined')
        self.propagator.checkpoint(self.actor, 'combined', 'uncertainty-checkpoint')
        self.claim('claim-no', False)
        conflict = self.ledger.detect(self.actor, 'combined')[0]
        newer_revision = self.ledger.revision(self.actor, 'combined')

        resumed = self.build(self.path, now=lambda: self.now)
        coordinator, actor, operator = [resumed[k] for k in ('adaptation', 'actor', 'operator')]
        with self.assertRaises(PermissionError):
            coordinator.resume(actor, 'combined', adaptation_checkpoint)
        for principal in (actor, operator):
            coordinator.grant(operator, 'combined', principal,
                subject_scope='synthetic-subject', review_reference='combined-host-reauthentication')
        coordinator.resume(actor, 'combined', adaptation_checkpoint)
        ledger = Ledger(resumed['engine'], clock=lambda: self.now)
        envelope = Propagator(ledger).resume(actor, 'combined', 'uncertainty-checkpoint')
        self.assertIn(conflict.conflict_id, envelope['open_conflict_ids'])
        self.assertTrue(envelope['refreshed'])
        self.assertEqual(envelope['ledger_revision'], newer_revision)
        before = coordinator.inspect(actor, 'combined')
        coordinator.reset(operator, 'combined', reason='combined-reset')
        after = coordinator.inspect(actor, 'combined')
        for key in ('action_receipts', 'steps', 'constraints'):
            self.assertEqual(after[key], before[key])
        self.assertEqual(ledger.revision(actor, 'combined'), newer_revision)
        self.assertEqual(ledger.open_conflicts(actor, 'combined')[0].conflict_id, conflict.conflict_id)
        with self.assertRaises(ValueError):
            coordinator.resume(actor, 'combined', adaptation_checkpoint)
        # A reopened engine cannot omit the previously enabled uncertainty gate.
        self.assertIsNone(getattr(resumed['engine'], '_uncertainty_policy', None))
        decision = resumed['runtime'].propose(actor, 'combined', 'note',
            {'heading': 'verified-heading', 'facts': 'synthetic-fact', 'section': 'after-reset'},
            [], 'synthetic-goal', ['objective'])
        outcome = resumed['runtime'].execute(actor, decision.decision_id)
        self.assertNotEqual(outcome.semantic_status, 'verified')
        self.assertEqual(resumed['effects'], [])

    def test_unaffected_adapted_task_continues_with_its_own_assessment(self):
        self.claim('claim-yes', True)
        self.claim('claim-no', False)
        self.ledger.detect(self.actor, 'combined')
        self.claim('independent', 'available', predicate='independent-input', task='independent-task')
        self.start(self.c, task='independent-task', subject='synthetic-independent')
        _, assessment, outcome = self.execute('verified-heading', task='independent-task',
            deps=('independent',), section='independent')
        self.assertEqual(assessment.status, 'proceed')
        self.assertEqual(outcome.semantic_status, 'verified')
        self.assertEqual(len(self.c['effects']), 1)
        self.assertEqual(len(self.ledger.open_conflicts(self.actor, 'combined')), 1)


if __name__ == '__main__':
    unittest.main()
