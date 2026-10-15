import copy
import gzip
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from historical_evidence_runtime import archived_receipt
from unittest.mock import patch
from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger
from nerve_awim.memory_gateway import MemoryGateway, MemoryScope
from nerve_awim.memory_gateway import forecast_outcome_memory as module

ROOT = Path(__file__).resolve().parents[1]


@archived_receipt
class ForecastEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = gzip.decompress((ROOT/'docs/galahad/evidence/online-forecast-demo-v1.json.gz').read_bytes())
        self.summary = json.loads((ROOT/'docs/galahad/evidence/online-forecast-demo-summary.json').read_text())
        self.report = {'recommendation':'forecast_candidate_for_review','episodes':512,'holdout_consumed':True,
                       'stages':{s:{'passed':True,'sum_stratum_mae_gain':.1} for s in ('train','validation','holdout')}}
        (self.root/'report.json').write_text(json.dumps(self.report))
        (self.root/'online.json').write_bytes(self.raw)
        self.evidence = dict(directory=self.root,claims='fixture',predecessor_path='fixture',source_paths={},
                             online_artifact=self.root/'online.json',online_summary=self.root/'summary.json')
        self.save_summary()
        mock = patch.object(module.study,'validate_receipt'); self.validate = mock.start(); self.addCleanup(mock.stop)

    def save_summary(self): (self.root/'summary.json').write_text(json.dumps(self.summary))
    def fact(self): return module.verified_fact(**self.evidence)

    def test_actual_saved_online_fixture_and_narrow_positive_fact(self):
        source,content = self.fact(); fact = json.loads(content)
        self.assertLessEqual(len(content),2048)
        self.assertEqual(source,'forecast-receipt:'+fact['receipt_sha256'])
        self.assertTrue(fact['recorded_forecasts_replay_equivalent'])
        self.assertFalse(fact['comparison_states_independently_reconstructed'])
        self.assertFalse(fact['candidate_promoted'])
        self.assertFalse(fact['control_objective_improvement_established'])
        self.validate.assert_called_once_with(self.root,'fixture','fixture',{})

    def test_reformat_and_gzip_do_not_change_identity(self):
        original = self.fact()
        (self.root/'report.json').write_text(json.dumps(self.report,indent=3))
        online = json.loads(self.raw)
        altered = json.dumps(online,indent=2).encode()
        (self.root/'online.json').write_bytes(gzip.compress(altered))
        self.summary['report_sha256'] = sha256(altered).hexdigest(); self.save_summary()
        self.assertEqual(self.fact(),original)

    def test_auxiliary_state_variant_cannot_create_new_study_identity(self):
        source,content = self.fact()
        online = json.loads(self.raw)
        online['rows'][0]['online']['controller_states'][0]['gain'] = 99.
        altered = module._json(online).encode()
        (self.root/'online.json').write_bytes(altered)
        self.summary['report_sha256'] = sha256(altered).hexdigest(); self.save_summary()
        changed_source,changed_content = self.fact()
        self.assertEqual(source,changed_source)
        self.assertNotEqual(content,changed_content)
        auth = MemoryAuthority(); scope = MemoryScope('research','coordinator','forecast')
        proposer = auth.issue('research','coordinator',permissions=('read','propose'))
        admin = auth.issue('research','coordinator',permissions=('read','delete'))
        gateway = MemoryGateway(TrustedMemoryLedger(self.root/'memory.sqlite',auth))
        bridge = module.ForecastOutcomeMemory(gateway)
        with patch.object(module,'verified_fact',return_value=(source,content)):
            mid = bridge.propose(proposer,scope)
        gateway.delete(admin,mid,scope=scope)
        with self.assertRaisesRegex(ValueError,'already_consumed'):
            bridge.propose(proposer,scope,**self.evidence)

    def test_invalid_study_and_nonpositive_results_rejected(self):
        self.validate.side_effect = ValueError('bad_study')
        with self.assertRaisesRegex(ValueError,'bad_study'): self.fact()
        self.validate.side_effect = None
        self.report['stages']['holdout']['passed'] = False
        (self.root/'report.json').write_text(json.dumps(self.report))
        with self.assertRaisesRegex(ValueError,'positive_forecast'): self.fact()

    def test_source_pins_cannot_be_missing_or_changed(self):
        for pins in ({},{**self.summary['new_source_sha256'],'extra':'source'}):
            self.summary['new_source_sha256'] = pins; self.save_summary()
            with self.assertRaises(ValueError): self.fact()

    def test_artifact_changes_during_study_verification_rejected(self):
        def alter(*args):
            (self.root/'report.json').write_text(json.dumps({**self.report,'episodes':1}))
        self.validate.side_effect = alter
        with self.assertRaisesRegex(ValueError,'evidence_changed'): self.fact()

    def test_trajectory_forecasts_metrics_and_roster_are_recomputed(self):
        for field in ('trajectory','forecast','metric','roster'):
            with self.subTest(field=field):
                report = json.loads(self.raw)
                if field == 'trajectory': report['rows'][0]['online']['episode']['trace'][0]['true_velocity'] = 9.
                elif field == 'forecast': report['rows'][0]['online']['forecasts'][0]['velocity'] = 9.
                elif field == 'metric': report['rows'][0]['metrics']['legacy_mae'] = 9.
                else: report['rows'][0]['adaptive'] = 0
                altered = module._json(report).encode()
                summary = copy.deepcopy(self.summary); summary['report_sha256'] = sha256(altered).hexdigest()
                summary['cases'] = [{k:v for k,v in r.items() if k != 'online'} for r in report['rows']]
                with self.assertRaises(ValueError): module.validate_online(altered,summary)

    def test_absent_comparison_proof_not_inferred_from_driver_booleans(self):
        report = json.loads(self.raw)
        for row in report['rows']:
            row['trajectory_unchanged'] = False; row['controller_states_unchanged'] = False
        raw = module._json(report).encode()
        summary = copy.deepcopy(self.summary); summary['report_sha256'] = sha256(raw).hexdigest()
        summary['cases'] = [{k:v for k,v in r.items() if k != 'online'} for r in report['rows']]
        self.assertEqual(module.validate_online(raw,summary),report)


class ForecastMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'memory.sqlite'
        self.auth = MemoryAuthority(); self.scope = MemoryScope('research','coordinator','forecast')
        self.proposer = self.auth.issue('research','coordinator',permissions=('read','propose'))
        self.reviewer = self.auth.issue('research','coordinator',permissions=('read','approve','delete'))
        self.reader = self.auth.issue('research','coordinator',permissions=('read',))
        self.gateway = MemoryGateway(TrustedMemoryLedger(self.path,self.auth))
        self.bridge = module.ForecastOutcomeMemory(self.gateway)
        self.source = 'forecast-receipt:'+'a'*64
        self.content = module._json({'receipt_sha256':'a'*64,'candidate_promoted':False})
        mock = patch.object(module,'verified_fact',return_value=(self.source,self.content))
        self.proof = mock.start(); self.addCleanup(mock.stop)

    def test_pending_then_approved_without_reward(self):
        mid = self.bridge.propose(self.proposer,self.scope)
        self.assertIsNone(self.bridge.approved(self.reader,self.scope))
        self.bridge.review(self.reviewer,self.scope,mid)
        record = self.bridge.approved(self.reader,self.scope)
        self.assertEqual(record.memory_id,mid); self.assertIsNone(record.outcome_score)
        self.assertEqual(self.bridge.claim(self.reader,self.scope,self.source),('proposed',mid))

    def test_separate_capabilities_and_foreign_scope(self):
        mid = self.bridge.propose(self.proposer,self.scope)
        with self.assertRaises(PermissionError): self.bridge.review(self.proposer,self.scope,mid)
        combined = self.auth.issue('research','coordinator',permissions=('read','approve','propose'))
        with self.assertRaises(PermissionError): self.bridge.propose(combined,self.scope)
        with self.assertRaises(PermissionError): self.bridge.review(combined,self.scope,mid)
        foreign = self.auth.issue('other','coordinator',permissions=('read',))
        with self.assertRaises(PermissionError): self.bridge.approved(foreign,self.scope)
        with self.assertRaises(PermissionError): self.bridge.claim(foreign,self.scope,self.source)

    def test_restart_delete_tombstone(self):
        mid = self.bridge.propose(self.proposer,self.scope); self.bridge.review(self.reviewer,self.scope,mid)
        bridge = module.ForecastOutcomeMemory(MemoryGateway(TrustedMemoryLedger(self.path,self.auth)))
        self.assertEqual(bridge.approved(self.reader,self.scope).memory_id,mid)
        self.gateway.delete(self.reviewer,mid,scope=self.scope)
        self.assertIsNone(bridge.approved(self.reader,self.scope))
        with self.assertRaisesRegex(ValueError,'already_consumed'): bridge.propose(self.proposer,self.scope)

    def test_revoked_fact_not_approved(self):
        mid = self.bridge.propose(self.proposer,self.scope); self.bridge.review(self.reviewer,self.scope,mid)
        self.gateway.revoke(self.reviewer,mid,scope=self.scope,evaluator_id='host')
        self.assertIsNone(self.bridge.approved(self.reader,self.scope))
        with self.assertRaises(ValueError): self.bridge.review(self.reviewer,self.scope,mid)

    def test_changed_evidence_cannot_approve_pending(self):
        mid = self.bridge.propose(self.proposer,self.scope)
        self.proof.return_value = (self.source,self.content+' ')
        with self.assertRaises(ValueError): self.bridge.review(self.reviewer,self.scope,mid)

    def test_orphan_after_insert_is_consumed_not_reviewable(self):
        original = self.gateway.propose; inserted = []
        def fail(*args,**kwargs):
            inserted.append(original(*args,**kwargs)); raise RuntimeError('crash')
        with patch.object(self.gateway,'propose',side_effect=fail):
            with self.assertRaises(RuntimeError): self.bridge.propose(self.proposer,self.scope)
        self.assertEqual(self.bridge.claim(self.reader,self.scope,self.source),('failed_consumed',None))
        with self.assertRaisesRegex(ValueError,'not_reviewable'): self.bridge.review(self.reviewer,self.scope,inserted[0])
        with self.assertRaisesRegex(ValueError,'already_consumed'): self.bridge.propose(self.proposer,self.scope)

    def test_authority_revoked_during_verification(self):
        mid = self.bridge.propose(self.proposer,self.scope)
        def revoke(**kwargs):
            self.auth.revoke(self.reviewer); return self.source,self.content
        self.proof.side_effect = revoke
        with self.assertRaises(PermissionError): self.bridge.review(self.reviewer,self.scope,mid)
