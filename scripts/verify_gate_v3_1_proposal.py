"""Read-only proposal/full-form verification. Never signs or activates a gate."""
import sys,json,gzip,argparse
from pathlib import Path
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nerve_awim.memory_gateway.retained_promotion_gate import verify as verify_canonical
from nerve_awim.memory_gateway.scientific_promotion_gate_v3 import ANSWER
E=ROOT/'docs/galahad/evidence'
def digest(p):return sha256(p.read_bytes()).hexdigest()
def full_form(payload,path):return f"sign gate_id={payload['gate_id']} version=v3.1 payload_sha256={digest(path)} simulation_evidence_sha256={payload['simulation_evidence']['sha256']} protected_paths_sha256={payload['protected_path_manifest_update']['sha256']}"
def verify(authorization=None):
 canonical=verify_canonical();path=E/'gate-v3_1-signing-payload.json';p=json.loads(path.read_text())
 assert p['version']=='v3.1' and not p['signed'] and not p['installed']
 expected=full_form(p,path)
 assert (E/'gate-v3_1-signing-request.txt').read_text()==expected+'\n'
 if authorization is not None and authorization!=expected:raise ValueError('full_form_authorization_mismatch')
 for name in ['source','registered_design','tables','simulation_evidence','protected_path_manifest_update','replay_equivalence','reserve_admission']:
  ref=p[name];assert digest(ROOT/ref['path'])==ref['sha256'],name
 index=json.loads((ROOT/p['simulation_evidence']['path']).read_text());manifest=json.loads((ROOT/p['protected_path_manifest_update']['path']).read_text())
 for f,h in {**index['files'],**manifest['paths']}.items():assert digest(ROOT/f)==h,f
 design=json.loads((ROOT/p['registered_design']['path']).read_text());assert set(design['affected_strata'])==set(ANSWER)
 replay=json.loads((ROOT/p['replay_equivalence']['path']).read_text())
 assert replay['post_model_only'] is False and set(replay['conservative_affected_strata'])==set(ANSWER)
 for key in ['candidate_source','incumbent_source']:
  ref=p['candidate_binding'][key];assert digest(ROOT/ref['path'])==ref['sha256']==replay['sources'][ref['path']]
 for s in design['unaffected_strata']:assert replay['table'][s]['byte_identical']==replay['table'][s]['n']==100
 result=json.loads((E/'gate-v3_1-simulation/result.json').read_text())
 for batch in ['registered','fresh']:
  for tie in [64,75]:
   r=result['results'][batch][f'k6-ties{tie}'];assert r['qualifies'] and r['good085']['accept_rate']>=.8 and r['regressed']['nonpromotion_rate']>=.9 and r['H0']['accept_rate']<=.05 and r['harmful']['accepted']==0
 for f,ref in result['receipts'].items():
  path=E/'gate-v3_1-simulation'/f;raw=gzip.decompress(path.read_bytes());assert digest(path)==ref['sha256'] and sha256(raw).hexdigest()==ref['uncompressed_sha256']
  streams=json.loads(raw);assert len(streams)==10000
  batch,k,tie,scenario=f.removesuffix('.json.gz').split('-');row=result['results'][batch][k+'-'+tie][scenario]
  assert sum(s[2] for s in streams)==row['accepted'] and sum(s[0] for s in streams)==row['primary_accepts']
 bank=Path('/Users/aliyildirim/nerve-research-runs/scientific-bank-v4-20261016');admission=json.loads((ROOT/p['reserve_admission']['path']).read_text());assert digest(bank/'consumption-ledger.json')==admission['ledger_sha256']
 assert digest(bank/'manifest.json')==admission['manifest_sha256']
 return {'verified':True,'proposed_version':'v3.1','canonical_version_still':canonical['version'],'scope':'six answer strata only','original_and_fresh_targets_pass':True,'unaffected_byte_identical':300,'model_calls':0,'new_reserve_items':0,'signed':False,'installed':False,'payload_sha256':digest(E/'gate-v3_1-signing-payload.json'),'full_form':expected}
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--authorization');a=parser.parse_args();print(json.dumps(verify(a.authorization),indent=2))
