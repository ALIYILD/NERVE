"""CPU-only statistical and persistence contracts for the unsigned gate."""
from copy import deepcopy
import math
from pathlib import Path
import sqlite3
import tempfile
import unittest

from nerve_awim.sequential_gate_contract import plateau_minimum, register, canonical
from nerve_awim.sequential_gate_simulation import registration, slice_accept, KEY
from nerve_awim.sequential_gate_v1 import Gate, IntegrityError


class SequentialGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'private'
        self.gate = Gate(self.path, key=KEY)
        self.reg = registration(0)
        self.gate.start(self.reg)

    def tearDown(self):
        self.gate.close(); self.temp.cleanup()

    def row(self, index, candidate=True, incumbent=False, abstain=False, random=False):
        item = self.reg['schedule'][index]
        self.gate.claim(self.reg['study_id'], **item)
        self.gate.record(self.reg['study_id'], item['item_id'], candidate=candidate,
                         incumbent=incumbent, controls={'always_abstain':abstain, 'random':random}, violations=[])

    def report(self):
        return self.gate.report(self.reg['study_id'])

    def test_ties_no_evidence_and_win_loss_product(self):
        self.row(0, True, True, True, True)
        self.assertEqual(self.report()['log_e']['incumbent'], 0)
        self.row(1); self.row(2, False, True)
        self.assertAlmostEqual(math.exp(self.report()['log_e']['incumbent']), .75)

    def test_null_one_step_supermartingale(self):
        for p in (0, .25, .5):
            self.assertLessEqual(p*1.5+(1-p)*.5, 1)

    def test_controls_must_be_beaten(self):
        for i in range(100): self.row(i, True, False, False, True)
        self.assertEqual(self.report()['verdict'], 'insufficient_power')

    def test_futility_and_promotion_are_terminal(self):
        for i in range(5): self.row(i, False, True)
        self.assertEqual(self.report()['verdict'], 'reject_futility')
        with self.assertRaises(PermissionError): self.row(5)

    def test_promotion_only_review_never_authorization(self):
        for i in range(21): self.row(i)
        self.assertEqual(self.report()['verdict'], 'exploratory_only')
        self.assertFalse(self.report()['promotion_authorized'])

    def test_plateau_uses_seed_variance(self):
        reg = registration(1); reg['dev_seed_deltas'] = [-1, 0, 1]
        reg['gate']['minimum_net_wins'] = plateau_minimum(reg['dev_seed_deltas'], 100)
        self.gate.start(reg); self.reg = reg
        for i in range(21): self.row(i)
        self.assertEqual(self.report()['verdict'], 'plateau')
        reg['gate']['minimum_net_wins'] = 1
        with self.assertRaises(ValueError): register(reg)

    def test_wrong_direction_stratum_veto_latched(self):
        reg = registration(1); reg['gate']['alpha'] = .01
        self.gate.start(reg); self.reg = reg
        # Keep primary tied so it cannot stop for futility; one stratum loses to abstain.
        for i, item in enumerate(self.reg['schedule']):
            if self.report()['verdict'] != 'running': break
            self.row(i, False, False, item['stratum']=='s0', False)
        self.assertEqual(self.report()['verdict'], 'verifier_veto')
        self.assertTrue(self.report()['stratum_veto'])

    def test_restart_same_evalue_no_repeat_dispatch(self):
        self.row(0); expected = canonical(self.report())
        self.gate.close(); self.gate = Gate(self.path, key=KEY)
        self.assertEqual(canonical(self.report()), expected)
        self.assertEqual(self.gate.claim(self.reg['study_id'], **self.reg['schedule'][0]), 'cached')
        pending = self.reg['schedule'][1]
        self.gate.claim(self.reg['study_id'], **pending)
        self.gate.close(); self.gate = Gate(self.path, key=KEY)
        self.assertEqual(self.gate.claim(self.reg['study_id'], **pending), 'incomplete_infrastructure')
        self.assertEqual(self.report()['items'], 1)
        # Trusted durable response recovery records the original pending result, never re-dispatches.
        self.gate.record(self.reg['study_id'], pending['item_id'], candidate=True, incumbent=False,
                         controls={'always_abstain':False, 'random':False}, violations=[])
        self.assertEqual(self.report()['items'], 2)

    def test_wallet_exhaustion_before_claim_and_restart_idempotency(self):
        reg = registration(1); reg['gate']['alpha'] = .04975
        self.gate.start(reg); self.gate.start(reg)
        with self.assertRaisesRegex(PermissionError, 'wallet_exhausted'):
            self.gate.start(registration(2))
        with self.assertRaises(ValueError):
            self.gate.claim('synthetic-2', 'never-opened', 's0')

    def test_tamper_history_detected_before_new_study(self):
        self.row(0)
        db = sqlite3.connect(self.path/'gate.sqlite')
        db.execute("UPDATE events SET body=replace(body, 'true', 'false') WHERE body LIKE '%outcome%'")
        db.commit(); db.close()
        with self.assertRaisesRegex(IntegrityError, 'integrity'): self.gate.start(registration(1))

    def test_trusted_head_detects_whole_database_rollback(self):
        head = self.gate.ledger_head()
        self.gate.close()
        db = sqlite3.connect(self.path/'gate.sqlite')
        db.execute('DELETE FROM events'); db.execute('DELETE FROM checkpoint')
        db.commit(); db.close()
        with self.assertRaisesRegex(IntegrityError, 'trusted ledger head'):
            Gate(self.path, key=KEY, expected_ledger_head=head)
        self.gate = Gate(self.path, key=KEY)

    def test_changed_registration_order_and_old_incumbent_refused(self):
        with self.assertRaisesRegex(ValueError, 'item_order'): self.row(1)
        reg = deepcopy(self.reg); reg['incumbent'] = 'stale-v1'
        with self.assertRaisesRegex(ValueError, 'marginal'): register(reg)
        reg = deepcopy(self.reg); reg['bank']['split'] = 'holdout'
        with self.assertRaises(PermissionError): register(reg)
        reg = deepcopy(self.reg); reg['gate']['bet'] = .4
        with self.assertRaises(IntegrityError): self.gate.start(reg)

    def test_slice_predicate_full_controls_and_stratum_guard(self):
        rows = [dict(stratum=f's{i%5}', candidate=True, incumbent=False, always_abstain=False, random=False) for i in range(100)]
        self.assertTrue(slice_accept(rows)); self.assertFalse(slice_accept(rows[:-1]))
        for row in rows: row['random'] = True
        self.assertFalse(slice_accept(rows))
        for row in rows:
            row['random'] = False
            if row['stratum']=='s0': row.update(candidate=False, always_abstain=True)
        self.assertFalse(slice_accept(rows))
