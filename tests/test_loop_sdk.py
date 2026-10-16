import json
import tempfile
import unittest
from pathlib import Path
from nerve_awim.loop import Loop, digest
from nerve_awim.loop.__main__ import demo, replay
from nerve_awim.loop.domains import DOMAINS
from nerve_awim.memory_gateway.site_router import SiteRouter

class LoopTests(unittest.TestCase):
    def test_all_domain_receipts_and_replay(self):
        for domain in DOMAINS:
            with self.subTest(domain=domain), tempfile.TemporaryDirectory() as directory:
                demo(domain,directory)
                self.assertTrue(replay(directory)['verified'])
                bundle=json.loads((Path(directory)/'bundle.json').read_text())
                self.assertTrue(bundle['evaluation']['kept'])
                self.assertGreater(bundle['evaluation']['totals']['candidate:context'],bundle['evaluation']['totals']['random'])
                self.assertFalse(bundle['status']['automatic_promotion'])
                trace=bundle['adaptation']['receipts']
                detections=[r['index'] for r in trace if r['drift']]
                self.assertEqual(len(detections),3)
                for shift,detected in zip((300,600,900),detections):
                    self.assertTrue(0 <= detected-shift <= 60)
                events=[e for r in trace for e in r['events']]
                self.assertEqual(sum(e['kind']=='rollback' for e in events),1)
                self.assertEqual(sum(e['kind']=='switch' for e in events),3)
                self.assertEqual(trace[-1]['after'],bundle['status']['incumbents'][0])

    def test_restart_identical_and_changed_stream_rejected(self):
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            interrupted=Loop('scientific',a); stream=interrupted.domain.stream()
            interrupted.adapt(stream,stop_after=611); interrupted.close()
            resumed=Loop('scientific',a); got=resumed.adapt(stream)
            clean=Loop('scientific',b); expected=clean.adapt(stream)
            self.assertEqual(got,expected)
            self.assertEqual(resumed.status()['adapt_items'],1200)
            stream[0]['abstention']=True
            with self.assertRaises(ValueError):resumed.adapt(stream)
            resumed.close();clean.close()

    def test_candidate_cannot_route_or_use_signed_gate(self):
        with self.assertRaises(ValueError):SiteRouter(['retained'],'candidate')
        with tempfile.TemporaryDirectory() as d:
            loop=Loop('scientific',d)
            with self.assertRaises(PermissionError):loop.evaluate({},[],gate='signed')
            loop.close()

    def test_rejection_memory_and_forged_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            loop=Loop('scientific',d)
            e={'id':'e','cluster':'missing-context','correct':False,'source_receipt_sha256':'a'*64}
            loop.learn([e]); c=loop.propose()
            forged=dict(c,skill='unknown')
            with self.assertRaises(ValueError):loop.evaluate(forged,loop.domain.bank(100))
            self.assertEqual(loop.evaluate(c,loop.domain.bank(1))['verdict'],'reverted')
            self.assertIsNone(loop.propose())
            with self.assertRaises(ValueError):loop.learn([dict(e,correct=True)])
            loop.close()

    def test_small_budget_revert_still_completes(self):
        with tempfile.TemporaryDirectory() as d:
            demo('scientific',d,budget=1)
            bundle=json.loads((Path(d)/'bundle.json').read_text())
            self.assertEqual(bundle['evaluation']['verdict'],'reverted')
            self.assertTrue(replay(d)['verified'])

    def test_corrupt_bundle_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            demo('scientific',d)
            path=Path(d)/'bundle.json'; b=json.loads(path.read_text());b['evaluation']['wins']+=1;path.write_text(json.dumps(b))
            with self.assertRaises(ValueError):replay(d)

if __name__=='__main__':unittest.main()
