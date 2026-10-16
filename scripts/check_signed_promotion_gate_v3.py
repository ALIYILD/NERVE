#!/usr/bin/env python3
"""Fresh-process signature and canonical-consumer check; synthetic scores only."""
import json,socket,sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nerve_awim.memory_gateway import retained_promotion_gate as gate

def run():
 proof=gate.verify();refused=False
 try:gate.require_promotion_gate('v2')
 except ValueError as e:refused=str(e)=='gate_v2_retired_for_promotions'
 assert refused
 p=gate.CanonicalProcess(planned_discordant_p=.85)
 while p.report()['phase']!='done':
  s=p.next_stratum();safe=s in ('conflict','unit-mismatch','dissenter')
  p.update(item_id='consumer-fixture-'+str(p.report()['items']),stratum=s,candidate=True,incumbent=safe,abstain=safe)
 r=p.report();assert r['verdict']=='promote_proposal' and r['m']==10 and r['risk_items']==40 and r['items']<=500 and r['signature_verified'] and r['installed']
 try:gate.CanonicalProcess(planned_discordant_p=.85,fresh_items=False)
 except ValueError:reuse_refused=True
 else:reuse_refused=False
 assert reuse_refused
 bank=Path(proof['payload']['bank_v4']['gate_private_directory']);ledger=json.loads((bank/'consumption-ledger.json').read_text());assert ledger['consumed_items']==0 and ledger['allocations']==[]
 return {'verified':True,'canonical_gate':'v3','v2_promotion_refused':refused,'reuse_refused':reuse_refused,'consumer_report':r,'signed_at_utc':proof['signed_at_utc'],'signed_payload_sha256':proof['payload_sha256'],'signature_type':'delegated_local_ed25519','user_personal_key':False,'new_model_calls':0,'reserve_consumed':0,'synthetic_consumer_fixture_only':True}
if __name__=='__main__':
 def deny(*a,**kw):raise RuntimeError('network forbidden')
 with patch.object(socket.socket,'connect',deny),patch.object(socket.socket,'connect_ex',deny),patch.object(socket,'create_connection',deny):print(json.dumps(run(),indent=2))
