"""Operational continuation checks only; no holdout item access or inference."""
from pathlib import Path
import json,sys,tempfile,time,unittest
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
import run_scientific_family_b_v4_holdout_replacement as r
class HoldoutReplacementTests(unittest.TestCase):
 def test_window_and_budget(self):
  started=datetime.now(timezone.utc)
  self.assertEqual(r.resume_deadline(started,19467.934),started+timedelta(seconds=1500))
  self.assertEqual(r.study_wall_budget('holdout','candidate',{'wall_seconds':3021.795081410557}),1200)
  with self.assertRaises(ValueError):r.study_wall_budget('dev','candidate')
  with self.assertRaises(ValueError):r.resume_deadline(started,15597.911)
 def test_fixed_science_and_claims(self):
  p=r.read(r.RESUME)
  self.assertEqual(len(p['prior_claim_sha256']),2715)
  self.assertEqual(r.hashbytes((ROOT/p['candidate_module']).read_bytes()),p['candidate_sha256'])
  self.assertIn('fresh_calibration_max_seconds',p['minimum_preconsumption_formula'])
  self.assertEqual(p['allowed_regions'],['CA-MTL-1','EU-SE-1'])
 def test_allowed_region_binding(self):
  with tempfile.TemporaryDirectory() as d:
   window=Path(d)/'window.json'
   with patch.object(r.transport,'WINDOW',window),patch.object(Path,'read_bytes',return_value=b'RUNPOD_POD_ID=testpod\0'):
    for region in ('CA-MTL-1','EU-SE-1'):
     window.write_text(json.dumps({'pod_id':'testpod','region':region,'hourly_usd':0.59}))
     self.assertEqual(r.transport.pod_id(),'testpod')
    window.write_text(json.dumps({'pod_id':'testpod','region':'OTHER','hourly_usd':0.59}))
    with self.assertRaises(ValueError):r.transport.pod_id()
 def test_public_calibration(self):
  tasks=[r.bank.item(bytes(32),'dev','multi-source-agreement',1000+i) for i in range(5)]
  rows=r.schedule(tasks,['adapted_v1'],kind='calibration')
  self.assertEqual(len(rows),5)
  self.assertTrue(all(row['payload'] is not None for row in rows))
  self.assertEqual(r.study_wall_budget('calibration',None),600)
 def test_watchdog(self):
  started=datetime.now(timezone.utc)
  ready={'pod_id':'lvojhtouu5gede','armed':True,'read_only_auth_probe_ok':True,'script_sha256':r.read(r.RESUME)['watchdog_sha256'],'provider_started_at_utc':started.isoformat(),'stop_deadline_utc':(started+timedelta(seconds=1800)).isoformat(),'inference_deadline_utc':(started+timedelta(seconds=1500)).isoformat(),'heartbeat_epoch':time.time(),'pid':123}
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   with patch.object(r,'WORKSPACE',p),patch.object(r.os,'kill'),patch.object(r.transport,'pod_id',return_value='lvojhtouu5gede'):
    (p/'watchdog-ready.json').write_text(json.dumps(ready));self.assertTrue(r.check_watchdog(started)['armed'])
    ready['stop_deadline_utc']=(started+timedelta(seconds=5400)).isoformat();(p/'watchdog-ready.json').write_text(json.dumps(ready))
    with self.assertRaises(ValueError):r.check_watchdog(started)
 def test_parent_mutation_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'v4-dev';p.mkdir();(p/'aggregate.json').write_text('{}')
   with patch.object(r,'read',return_value={'parent_evidence_sha256':{'v4-dev':{'aggregate.json':'bad'}}}):
    with self.assertRaisesRegex(ValueError,'offline_verified_parent_changed'):r.verified_parent(p)
 def test_registration_dev_rejected_before_items(self):
  with self.assertRaisesRegex(ValueError,'fixed_v4_holdout_only'):
   r.register(Path('/unused'),'dev',None,None,None,None,None,None,None,None)
if __name__=='__main__':unittest.main()
