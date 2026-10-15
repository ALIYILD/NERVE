"""Mock transport/metadata, real claims and authority; no real model calls."""
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from nerve_awim.memory_gateway import scientific_candidate_transport_smoke as smoke

DIGEST='d'*64


class CandidateTransportSmokeTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)/'smoke';self.journal=Path(temporary.name)/'external.sqlite'
        for name,value in [('metadata',{'model':smoke.pilot.MODEL,'digest':DIGEST}),('preload',{'ready':True}),('runtime_version','fixture-runtime')]:
            mocked=patch.object(smoke,name,return_value=value);setattr(self,name,mocked.start());self.addCleanup(mocked.stop)
        mocked=patch.object(smoke.transport,'run',side_effect=self.respond)
        self.model=mocked.start();self.addCleanup(mocked.stop)

    def respond(self,config,query,evidence,*,authorize,constrained):
        with sqlite3.connect(self.root/'claim.sqlite') as db:
            report=json.loads(db.execute('SELECT report FROM attempt').fetchone()[0])
        self.assertEqual(report['model_attempts'],1);self.assertEqual(report['status'],'running')
        authorize()
        result=smoke.execution.execute(config,query,evidence,lambda payload:smoke.canonical(smoke.EXPECTED),authorize=authorize)
        return dict(result,usage={'prompt_tokens':90,'completion_tokens':25,'total_tokens':115},model=smoke.pilot.MODEL,origin=smoke.pilot.ORIGIN,constrained=constrained)

    def run_smoke(self):return smoke.run(self.root,DIGEST,self.journal)

    def test_one_call_claimed_before_dispatch_and_network_free_resume(self):
        report=self.run_smoke();self.assertEqual(report['status'],'complete',report)
        self.assertEqual(report['model_attempts'],1);self.assertTrue(report['score']['strict_correct'])
        self.assertFalse(report['efficacy_established']);self.assertEqual(report['rejection_receipts_created'],0)
        self.assertEqual(self.metadata.call_count,2);self.preload.assert_called_once();self.assertEqual(self.runtime_version.call_count,2)
        before={p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in (self.root/'claim.sqlite',self.root/'report.json')}
        self.assertEqual(self.run_smoke(),report)
        self.assertEqual({p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in (self.root/'claim.sqlite',self.root/'report.json')},before)
        self.assertEqual(self.model.call_count,1);self.assertEqual(self.metadata.call_count,2)

    def test_exception_is_consumed_and_never_retried(self):
        self.model.side_effect=TimeoutError('fixture')
        report=self.run_smoke();self.assertEqual(report['status'],'failed_consumed')
        self.assertEqual(self.run_smoke(),report);self.assertEqual(self.model.call_count,1)
        self.assertEqual(report['rejection_receipts_created'],0)

    def test_partial_usage_fails_and_keeps_raw_output(self):
        original=self.respond
        def partial(*args,**kwargs):
            value=original(*args,**kwargs);value['usage']={'prompt_tokens':90};return value
        self.model.side_effect=partial
        report=self.run_smoke();self.assertEqual(report['status'],'failed_consumed')
        self.assertEqual(report['response']['raw_output'],smoke.canonical(smoke.EXPECTED))
        self.run_smoke();self.assertEqual(self.model.call_count,1)

    def test_keyboard_interrupt_preserved_then_network_free_resume(self):
        self.model.side_effect=KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.run_smoke()
        report=self.run_smoke();self.assertEqual(report['status'],'failed_consumed')
        self.assertEqual(self.model.call_count,1)

    def test_missing_claim_cannot_reset(self):
        self.run_smoke();(self.root/'claim.sqlite').unlink()
        with self.assertRaisesRegex(ValueError,'missing_claim'):self.run_smoke()
        self.assertFalse((self.root/'claim.sqlite').exists());self.assertEqual(self.model.call_count,1)

    def test_corrupt_claim_not_overwritten(self):
        self.run_smoke();path=self.root/'claim.sqlite';path.write_bytes(b'corrupt')
        with self.assertRaises(Exception):self.run_smoke()
        self.assertEqual(path.read_bytes(),b'corrupt');self.assertEqual(self.model.call_count,1)

    def test_changed_source_or_digest_rejects_without_network(self):
        self.run_smoke()
        with self.assertRaises(ValueError):smoke.run(self.root,'e'*64,self.journal)
        with patch.object(smoke,'sources',return_value={'changed':'a'*64}):
            with self.assertRaises(ValueError):self.run_smoke()
        self.assertEqual(self.model.call_count,1)

    def test_claim_before_first_checkpoint_is_consumed(self):
        original=smoke._save
        with patch.object(smoke,'_save',side_effect=RuntimeError('injected first checkpoint')):
            with self.assertRaises(RuntimeError):self.run_smoke()
        report=self.run_smoke();self.assertEqual(report['status'],'failed_consumed')
        self.metadata.assert_not_called();self.model.assert_not_called()

    def test_model_identity_mismatch_prevents_dispatch(self):
        self.metadata.return_value={'model':smoke.pilot.MODEL,'digest':'e'*64}
        report=self.run_smoke();self.assertEqual(report['status'],'failed_consumed')
        self.model.assert_not_called();self.preload.assert_not_called()

    def test_shared_claim_refuses_new_output_directory(self):
        self.run_smoke()
        with self.assertRaisesRegex(ValueError,'already_consumed'):
            smoke.run(self.root.parent/'other',DIGEST,self.journal)
        self.assertEqual(self.model.call_count,1)

    def test_missing_external_claim_never_reset(self):
        self.run_smoke();self.journal.unlink()
        with self.assertRaisesRegex(ValueError,'external_claim_missing'):self.run_smoke()
        self.assertFalse(self.journal.exists());self.assertEqual(self.model.call_count,1)

    def test_claim_only_crash_cannot_dispatch(self):
        with patch.object(smoke,'_save_exact',side_effect=RuntimeError('before local marker')):
            with self.assertRaises(RuntimeError):self.run_smoke()
        with self.assertRaisesRegex(ValueError,'missing_claim'):self.run_smoke()
        self.metadata.assert_not_called();self.model.assert_not_called()

    def test_complete_rehashed_metric_and_usage_tampering_rejected(self):
        from hashlib import sha256
        original=self.run_smoke()
        from copy import deepcopy
        mutations=[lambda r:r['response'].update(usage=None),
                   lambda r:r.update(model_attempts=True),
                   lambda r:r['metadata_after'].update(digest='f'*64),
                   lambda r:r['score'].update(strict_correct=1),
                   lambda r:r['response'].update(config_sha256='0'*64)]
        for mutate in mutations:
            report=deepcopy(original);mutate(report);encoded=smoke.canonical(report)
            with sqlite3.connect(self.root/'claim.sqlite') as db:
                db.execute('UPDATE attempt SET report=?,digest=?',(encoded,sha256(encoded.encode()).hexdigest()))
            with self.assertRaises(ValueError):self.run_smoke()
        self.assertEqual(self.model.call_count,1);self.assertEqual(self.metadata.call_count,2)

    def test_sanitized_transport_reason_preserved(self):
        self.model.side_effect=smoke.previous.InferenceUnavailable('timeout')
        report=self.run_smoke()
        self.assertEqual(report['status'],'failed_consumed');self.assertEqual(report['failure_reason'],'timeout')
        self.assertEqual(self.run_smoke(),report);self.assertEqual(self.model.call_count,1)

    def test_mid_call_external_claim_tamper_blocks_publication(self):
        original=self.respond
        def mutate(*args,**kwargs):
            response=original(*args,**kwargs)
            with sqlite3.connect(self.journal) as db:db.execute("UPDATE smoke_claims SET status='changed'")
            return response
        self.model.side_effect=mutate
        with self.assertRaisesRegex(ValueError,'external_claim_changed'):self.run_smoke()
        self.assertFalse((self.root/'report.json').exists())
        with self.assertRaises(ValueError):self.run_smoke()
        self.assertEqual(self.model.call_count,1)

    def test_mid_call_deleted_external_claim_not_recreated(self):
        original=self.respond
        def mutate(*args,**kwargs):
            response=original(*args,**kwargs);self.journal.unlink();return response
        self.model.side_effect=mutate
        with self.assertRaises(OSError):self.run_smoke()
        self.assertFalse(self.journal.exists());self.assertFalse((self.root/'report.json').exists())
        with self.assertRaises(ValueError):self.run_smoke()
        self.assertFalse(self.journal.exists());self.assertEqual(self.model.call_count,1)

    def test_rehashed_failed_counter_and_safety_tamper_rejected(self):
        from hashlib import sha256
        from copy import deepcopy
        self.model.side_effect=TimeoutError('fixture')
        original=self.run_smoke()
        for key,value in [('model_attempts',999),('metadata_attempts',True),('promotion_authorized',True),('model_weights_trained',True),('rejection_receipts_created',1)]:
            report=deepcopy(original);report[key]=value;encoded=smoke.canonical(report)
            with sqlite3.connect(self.root/'claim.sqlite') as db:
                db.execute('UPDATE attempt SET report=?,digest=?',(encoded,sha256(encoded.encode()).hexdigest()))
            with self.assertRaisesRegex(ValueError,'invalid_terminal'):self.run_smoke()
        self.assertEqual(self.model.call_count,1)

    def test_private_directory_and_claim(self):
        self.root.mkdir(mode=0o755)
        with self.assertRaisesRegex(ValueError,'private_smoke'):self.run_smoke()
        self.root.chmod(0o700);self.run_smoke()
        self.assertEqual((self.root/'claim.sqlite').stat().st_mode & 0o777,0o600)
        self.assertEqual((self.root/'report.json').stat().st_mode & 0o777,0o600)


if __name__=='__main__':unittest.main()
