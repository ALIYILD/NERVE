import importlib.util,json,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('conductor',Path(__file__).resolve().parents[1]/'scripts/overnight_conductor.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ConductorTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.state=self.root/'state';self.state.mkdir();self.now=datetime(2026,10,17,1,tzinfo=timezone.utc)
  self.write('integrity-baseline.json',{'paths':{}});self.write('pods.json',{'observed_at':self.now.isoformat(),'pods':[{'id':'p','status':'RUNNING','hourly_usd':.59}]});self.write('spend.json',{'intervals':[]});(self.state/'ledger.jsonl').write_text('');(self.state/'pod-B.lock').write_text('{}')
 def write(self,n,v):m.atomic(self.state/n,v)
 def inspect(self):
  with patch.object(Path,'home',return_value=self.root):return m.inspect(self.root,self.state,self.now)
 def test_third_failure_revokes_and_requests_stop(self):
  for _ in range(3):m.append(self.state,{'event':'end','verdict':'incomplete_infrastructure'})
  r=self.inspect();self.assertIn('infrastructure_stop',r['reasons']);self.assertEqual(r['actions'],[{'id':'p','action':'stop'}]);self.assertFalse((self.state/'pod-B.lock').exists());self.assertFalse(r['shutdown_verified'])
 def test_changed_protected_file_revokes(self):
  self.write('integrity-baseline.json',{'paths':{'missing':'a'*64}});self.assertIn('integrity',self.inspect()['reasons'])
 def test_budget_counts_open_interval_without_reset(self):
  self.write('spend.json',{'intervals':[{'start':(self.now-timedelta(hours=20)).isoformat(),'hourly_usd':.59}]});r=self.inspect();self.assertAlmostEqual(r['compute_usd'],11.8);self.assertIn('budget_stop',r['reasons']);self.assertAlmostEqual(self.inspect()['compute_usd'],11.8)
 def test_stale_exited_not_shutdown_proof(self):
  self.write('pods.json',{'observed_at':(self.now-timedelta(minutes=12)).isoformat(),'pods':[{'id':'p','status':'EXITED','hourly_usd':.59}]});r=self.inspect();self.assertFalse(r['shutdown_verified']);self.assertIn('stale_inventory',r['reasons'])
 def test_wrap_before_hard_stop_revokes(self):
  self.now=m.WRAP;self.write('pods.json',{'observed_at':self.now.isoformat(),'pods':[{'id':'p','status':'RUNNING','hourly_usd':.59}]});self.assertIn('wrap_up',self.inspect()['reasons'])
 def test_no_unregistered_verdict(self):
  with self.assertRaises(ValueError):m.append(self.state,{'verdict':'success'})
if __name__=='__main__':unittest.main()
