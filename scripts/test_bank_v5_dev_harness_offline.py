"""Mock wire responses only; isolated temporary bank, never real dev/reserve."""
import json,sys,tempfile,unittest,socket
from pathlib import Path
from unittest.mock import patch
import run_bank_v5_dev_discrimination as r
from nerve_awim.memory_gateway import scientific_task_bank_v5 as gen
class TestHarness(unittest.TestCase):
 def test_registration_refuses_unapproved_run(self):
  # Actual registration can be read; no bank item or remote operation may follow.
  with patch.object(r,'remote',side_effect=AssertionError('no transport allowed')):
   with self.assertRaises(FileNotFoundError):r.execute()
 def test_mocked_journal_and_fresh_replay(self):
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp)/'study';bank=Path(tmp)/'bank';base.mkdir();bank.mkdir();files={}
   for s in r.STRATA:
    p=bank/f'dev-{s}.json';r.write(p,[gen.item(bytes(32),'dev',s,i) for i in range(100)]);files[p.name]={'sha256':r.digest(p)};p.chmod(0)
   r.write(bank/'manifest.json',{'files':files});r.write(bank/'consumption-ledger.json',{'dev_consumed':0,'reserve_consumed':0,'allocations':[]})
   schedule=[{'stratum':s,'dev_index':i} for i in range(50) for s in r.STRATA];r.write(base/'schedule.json',schedule)
   reg=r.read(r.BASE/'registration.json');reg['bank_manifest_sha256']=r.digest(bank/'manifest.json');reg['schedule_sha256']=r.digest(base/'schedule.json');r.write(base/'registration.json',reg)
   r.write(base/'operation-authorization.json',{'authorized':True,'registration_sha256':r.digest(base/'registration.json'),'maximum_pod_seconds':1800,'exact_user_authorization':'ISOLATED MOCK TEST; no remote permission or inference'})
   r.write(base/'connection.json',{'pod_id':reg['pod_id'],'host':'127.0.0.1','port':22})
   calls=[]
   def mock_remote(connection,action,payload=None):
    if action=='identity':return {'pod_id':reg['pod_id'],'runtime':{'version':reg['runtime']},'model_digest':reg['model_digest'],'gpu':reg['gpu']}
    calls.append(payload['body']);p=json.loads(payload['body']);records=json.loads(p['messages'][1]['content'].split('Records in supplied order: ',1)[1]);eligible=p['response_format']['json_schema']['schema']['properties']['source_id']['enum'];source=sorted(eligible)[-1 if len(calls)%2 else 0];record=next(x for x in records if x['source_id']==source)
    content=json.dumps({'value':float(record['value']),'unit':record['unit'],'source_id':source});wire=json.dumps({'model':reg['model'],'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':content}}],'usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120}})
    return {'status':'ok','wire':wire,'elapsed_seconds':0.001}
   original_socket=socket.socket
   try:
    with patch.object(r,'BASE',base),patch.object(r,'BANK',bank),patch.object(r,'remote',mock_remote):
     r.execute();result=r.read(base/'result.json');self.assertEqual(result['per_stratum']['pooled']['wins'],50);self.assertEqual(result['per_stratum']['pooled']['losses'],0);self.assertEqual(len(calls),100)
     r.execute(True);self.assertTrue(r.read(base/'replay.json')['matched']);self.assertEqual(len(calls),100)
     ledger=r.read(bank/'consumption-ledger.json');self.assertEqual((ledger['dev_consumed'],ledger['reserve_consumed']),(100,0));self.assertTrue(all(p.stat().st_mode&0o777==0 for p in bank.glob('dev-*.json')))
   finally:socket.socket=original_socket
if __name__=='__main__':unittest.main()
