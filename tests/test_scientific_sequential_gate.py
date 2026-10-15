"""CPU-only simulation contract tests; no network or model runtime."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import random
import sqlite3
import tempfile
import unittest
from nerve_awim.memory_gateway.scientific_alpha_wallet import AlphaWallet
from nerve_awim.memory_gateway.scientific_sequential_gate import Gate, Process
from nerve_awim.memory_gateway.scientific_sequential_journal import IntegrityError
from nerve_awim.memory_gateway.scientific_sequential_contract import register

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('sim',ROOT/'scripts/simulate_sequential_gate.py')
sim=importlib.util.module_from_spec(spec);spec.loader.exec_module(sim)


class SequentialGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.reg=sim.registration(0); self.path=self.root/'wallet.json'
        self.digest=AlphaWallet.create(self.path,[self.reg])
        self.wallet=AlphaWallet(self.path,expected_sha256=self.digest)
        self.gate=Gate(self.root/'journals'/'sim-0',wallet=self.wallet,key=sim.KEY)
        self.gate.start(self.reg)

    def tearDown(self):
        self.gate.close(); self.tmp.cleanup()

    def add(self, index, candidate=True, incumbent=False, abstain=False):
        item=self.reg['schedule'][index]
        self.gate.claim('sim-0',**item)
        self.gate.record('sim-0',item['item_id'],candidate=candidate,incumbent=incumbent,
                         controls=dict(always_abstain=abstain,random=False),violations=[])

    def test_type_i_10000_null_streams(self):
        rng=random.Random(2026101601); crossings=0
        g=dict(self.reg['gate'],alpha=.05,item_budget=200,strata=['s'],futility_e=0)
        for _ in range(10000):
            p=Process(g)
            for _ in range(200):
                win=rng.random()<.5
                p.update(candidate=win,incumbent=not win,abstain=False,stratum='s')
                if p.verdict!='running': break
            crossings+=p.verdict=='promote_proposal'
        self.assertLessEqual(crossings/10000,.05)
        print(f'NULL_STREAM_RECEIPT streams=10000 horizon=200 alpha=.05 crossings={crossings} rate={crossings/10000}')

    def test_h1_early_stop(self):
        for i in range(100):
            self.add(i)
            if self.gate.report('sim-0')['verdict']!='running':break
        report=self.gate.report('sim-0')
        self.assertEqual(report['verdict'],'promote_proposal')
        self.assertLess(report['items'],100)
        self.assertFalse(report['promotion_authorized'])

    def test_ties_and_marginal_delta(self):
        self.add(0,True,True);self.add(1)
        r=self.gate.report('sim-0')
        self.assertAlmostEqual(r['e_value'],1.3)
        self.assertEqual(r['marginal_delta'],.5)

    def test_plateau_floor(self):
        g=dict(self.reg['gate'],alpha=.05,bet=.9,minimum_net_wins=10,strata=['s'])
        p=Process(g)
        for _ in range(5):p.update(candidate=True,incumbent=False,abstain=False,stratum='s')
        self.assertGreater(p.report()['e_value'],20)
        self.assertEqual(p.verdict,'running')

    def test_reverse_stratum_veto(self):
        g=dict(self.reg['gate'],alpha=.05,strata=['s'],futility_e=0)
        p=Process(g)
        for _ in range(100):
            p.update(candidate=False,incumbent=False,abstain=True,stratum='s')
            if p.verdict!='running':break
        self.assertEqual(p.verdict,'retain_incumbent');self.assertTrue(p.veto)

    def test_no_crossing_not_noninferiority(self):
        self.add(0,False,False,True)
        r=self.gate.report('sim-0')
        self.assertFalse(r['stratum_veto']);self.assertEqual(r['verdict'],'running')

    def test_futility_and_budget(self):
        p=Process(dict(self.reg['gate'],strata=['s']))
        for _ in range(100):
            p.update(candidate=False,incumbent=True,abstain=False,stratum='s')
            if p.verdict!='running':break
        self.assertEqual(p.reason,'registered_futility_bound')
        p=Process(dict(self.reg['gate'],strata=['s'],item_budget=2))
        for _ in range(2):p.update(candidate=True,incumbent=True,abstain=False,stratum='s')
        self.assertEqual(p.verdict,'insufficient_power')

    def test_wallet_exhaustion_immutable(self):
        regs=[sim.registration(i) for i in range(201)]
        with self.assertRaises(PermissionError):AlphaWallet.create(self.root/'over.json',regs)
        with self.assertRaises(PermissionError):self.gate.start(sim.registration(1))
        with self.assertRaises(FileExistsError):AlphaWallet.create(self.path,[self.reg])
        self.wallet.verify()

    def test_wallet_no_refunds_or_reuse(self):
        r=sim.registration(1);r['schedule']=copy.deepcopy(self.reg['schedule'])
        with self.assertRaises(ValueError):AlphaWallet.create(self.root/'reuse.json',[self.reg,r])
        self.add(0)
        self.wallet.verify();self.assertEqual(self.wallet.expected_sha256,self.digest)

    def test_resume_and_cached_claim_no_repeated_dispatch(self):
        self.add(0); report=self.gate.report('sim-0');head=self.gate.ledger_head()
        self.gate.close()
        self.gate=Gate(self.root/'journals'/'sim-0',wallet=self.wallet,key=sim.KEY,expected_ledger_head=head)
        self.assertEqual(self.gate.report('sim-0'),report)
        self.assertEqual(self.gate.claim('sim-0',**self.reg['schedule'][0]),'cached')
        self.add(1);self.assertEqual(self.gate.report('sim-0')['items'],2)

    def test_pending_claim_fail_closed(self):
        item=self.reg['schedule'][0]
        self.assertEqual(self.gate.claim('sim-0',**item),'dispatch_once')
        self.assertEqual(self.gate.claim('sim-0',**item),'incomplete_infrastructure')
        self.assertEqual(self.gate.report('sim-0')['verdict'],'incomplete_infrastructure')
        with self.assertRaises(PermissionError):self.gate.claim('sim-0',**self.reg['schedule'][1])

    def test_tamper_history_detected(self):
        self.add(0)
        self.gate.db.execute("UPDATE events SET body='{}' WHERE seq=3")
        with self.assertRaises(IntegrityError):self.gate.report('sim-0')

    def test_trusted_checkpoint_detects_rollback(self):
        database=self.root/'journals'/'sim-0'/'gate.sqlite'
        snapshot=database.read_bytes()
        self.add(0);newhead=self.gate.ledger_head()
        self.gate.close()
        database.write_bytes(snapshot)
        with self.assertRaises(IntegrityError):
            Gate(self.root/'journals'/'sim-0',wallet=self.wallet,key=sim.KEY,expected_ledger_head=newhead)
        # A deliberately unanchored simulation reopen illustrates the documented limitation.
        self.gate=Gate(self.root/'journals'/'sim-0',wallet=self.wallet,key=sim.KEY)
        self.assertEqual(self.gate.report('sim-0')['items'],0)

    def test_alternate_journal_path_rejected(self):
        other=Gate(self.root/'elsewhere',wallet=self.wallet,key=sim.KEY)
        try:
            with self.assertRaises(ValueError):other.start(self.reg)
        finally:other.close()

    def test_wallet_tamper_detected(self):
        self.path.chmod(0o600);self.path.write_text('{}')
        with self.assertRaises(ValueError):self.gate.report('sim-0')

    def test_registration_identity_and_order(self):
        r=copy.deepcopy(self.reg);r['incumbent']='different'
        with self.assertRaises(ValueError):register(r)
        with self.assertRaises(ValueError):self.gate.claim('sim-0',**self.reg['schedule'][1])
        r=copy.deepcopy(self.reg);r['gate']['bet']=.4
        with self.assertRaises(ValueError):self.gate.start(r)

    def test_exact_current_slice_comparator(self):
        rows=[dict(stratum=s,candidate=True,incumbent=False,always_abstain=False,random=False)
              for _ in range(20) for s in sim.DESIGN['strata']]
        self.assertTrue(sim.slice_accept(rows))
        for row in rows:row['incumbent']=True
        self.assertFalse(sim.slice_accept(rows))
        rows.pop();self.assertFalse(sim.slice_accept(rows))

    def test_null_conditional_expectation(self):
        for b in (.1,.3,.9):
            for p in (0,.35,.5): self.assertLessEqual(p*(1+b)+(1-p)*(1-b),1+1e-15)

if __name__=='__main__': unittest.main()
