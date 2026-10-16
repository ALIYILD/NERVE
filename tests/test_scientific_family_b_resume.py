"""Resume admission/window guards; no model calls or bank item access."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
import run_scientific_family_b_v4_resume as r
class ResumeTests(unittest.TestCase):
 def setUp(self):
  self.start=datetime.now(timezone.utc)-timedelta(seconds=5)
  self.ready={'pod_id':'b7qj6qyx9ij6gg','armed':True,'read_only_auth_probe_ok':True,'provider_started_at_utc':self.start.isoformat(),'stop_deadline_utc':(self.start+timedelta(seconds=5400)).isoformat(),'inference_deadline_utc':(self.start+timedelta(seconds=4800)).isoformat(),'heartbeat_epoch':time.time(),'pid':123,'script_sha256':r.read(r.RESUME)['watchdog_sha256']}
 def check(self,change=None):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);data=dict(self.ready);data.update(change or {});(p/'watchdog-ready.json').write_text(json.dumps(data))
   with patch.object(r,'WORKSPACE',p),patch.object(r.os,'kill'):
    return r.check_watchdog(self.start)
 def test_window(self):
  self.assertEqual(r.resume_deadline(self.start,15597.911),self.start+timedelta(seconds=4800))
  with self.assertRaises(ValueError):r.resume_deadline(self.start,0)
 def test_ready(self):self.assertTrue(self.check()['armed'])
 def test_fail_closed(self):
  for change in ({'armed':False},{'heartbeat_epoch':time.time()-121},{'script_sha256':'changed'},{'pod_id':'other'},{'stop_deadline_utc':(self.start+timedelta(seconds=6000)).isoformat()}):
   with self.subTest(change=change),self.assertRaises(ValueError):self.check(change)
 def test_migration(self):
  protocol=r.read(r.RESUME)
  self.assertEqual(len(protocol['prior_claim_sha256']),1510)
  self.assertEqual(protocol['prior_running_seconds'],15597.911)
  self.assertEqual(r.hashbytes((ROOT/protocol['candidate_module']).read_bytes()),protocol['candidate_sha256'])
 def test_residual(self):
  self.assertEqual(r.study_wall_budget('holdout','candidate',{'wall_seconds':2100}),1500)
  with self.assertRaises(ValueError):r.study_wall_budget('holdout','candidate',{'wall_seconds':3600})
if __name__=='__main__':unittest.main()
