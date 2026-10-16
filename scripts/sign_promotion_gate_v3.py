#!/usr/bin/env python3
"""One-shot full-form operator-authorized canonical gate signature; zero inference."""
import argparse,base64,json,os,socket,sys,tempfile
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nerve_awim.memory_gateway import retained_promotion_gate as loader
E=ROOT/'docs/galahad/evidence';KEYDIR=Path('/Users/aliyildirim/.local/share/nerve/signing/scientific-promotion-gate-v3')
def put(path,data,mode=0o600):
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,mode)
 with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
def validate_authorization(text,payload_raw):
 p=json.loads(payload_raw)
 expected=f"sign gate_id={loader.GATE_ID} version=v3 payload_sha256={loader.digest(payload_raw)} simulation_evidence_sha256={p['simulation_evidence']['sha256']} protected_paths_sha256={p['protected_path_manifest_update']['sha256']}"
 loader.require(text==expected and loader.digest(payload_raw)==loader.PAYLOAD_SHA256,'full_form_authorization_mismatch')
 return p

def sign(authorization):
 payload_raw=(E/'gate-v3-signing-payload.json').read_bytes();p=validate_authorization(authorization,payload_raw)
 loader.require(not any(x.exists() for x in (loader.REGISTRY,loader.TRUST,loader.PUBLIC,KEYDIR)),'already_signed_or_partial_state')
 checked={}
 for key in ('source','simulation_evidence','registered_design','tables','protected_path_manifest_update'):
  ref=p[key];data=(ROOT/ref['path']).read_bytes();loader.require(loader.digest(data)==ref['sha256'],'binding:'+key);checked[ref['path']]=data
 index=json.loads(checked[p['simulation_evidence']['path']]);protected=json.loads(checked[p['protected_path_manifest_update']['path']])
 for path,h in {**index['files'],**protected['paths']}.items():
  data=(ROOT/path).read_bytes();loader.require(loader.digest(data)==h,'source_or_evidence_drift:'+path);checked[path]=data
 result=json.loads((E/'gate-v3-confirmation-v1-result.json').read_text());loader.require(result['chosen_m']==10,'selection_mismatch')
 for condition in [result['results']['good_085']['10']['accept_rate']>=.8,result['results']['regression_requested']['10']['nonpromotion_rate']>=.9,result['results']['H0']['10']['accept_rate']<=.05,result['results']['harmful']['10']['accepted']==0]:loader.require(condition,'confirmation_target_failed')
 bank=Path(p['bank_v4']['gate_private_directory']);loader.require(loader.digest((bank/'manifest.json').read_bytes())==p['bank_v4']['manifest_sha256'],'bank_manifest_changed')
 ledger=json.loads((bank/'consumption-ledger.json').read_text());loader.require(ledger['consumed_items']==0 and ledger['allocations']==[],'reserve_already_allocated')
 seal=json.loads((bank/'sealing-receipt.json').read_text());loader.require(seal['sealed'] and all((bank/name).stat().st_mode & 0o777==0 for name in seal['private_modes']),'bank_not_sealed')
 policy={'gate_id':loader.GATE_ID,'active_promotion_gate':'v3','selected_m':10,'t':0,'total_cap':500,'risk_stratum':'dissenter','risk_followup_N':40,'gate_v2':'retired_for_promotions','gate_v2_historical_replay_allowed':True,'basis':p['canonical_policy_on_valid_signing_and_activation'],'candidate_signing_automatic':False,'inference_or_study_authorized':False,'protected_manifest_sha256':p['protected_path_manifest_update']['sha256']}
 policy_raw=loader.encoded(policy);now=datetime.now(timezone.utc).isoformat()
 message={'gate_id':loader.GATE_ID,'version':'v3','payload_sha256':loader.PAYLOAD_SHA256,'simulation_evidence_sha256':p['simulation_evidence']['sha256'],'protected_paths_sha256':p['protected_path_manifest_update']['sha256'],'canonical_policy_sha256':loader.digest(policy_raw),'signed_at_utc':now,'authorization':authorization,'authorized_by':'user','executed_by':'Codex','signature_type':'delegated_local_ed25519','user_personal_key':False}
 key=Ed25519PrivateKey.generate();pub=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
 record={'signed_message':message,'signature_base64':base64.b64encode(key.sign(loader.encoded(message))).decode()}
 trust={'gate_id':loader.GATE_ID,'version':'v3','payload_sha256':loader.PAYLOAD_SHA256,'public_key_base64':base64.b64encode(pub).decode(),'signed_message_sha256':loader.digest(loader.encoded(message)),'loader_sha256':loader.digest(Path(loader.__file__).read_bytes()),'signer_sha256':loader.digest(Path(__file__).read_bytes()),'signed_at_utc':now,'authority':'Exact full-form user instruction; locally delegated key, not user personal key.'}
 loader.require(all((ROOT/path).read_bytes()==data for path,data in checked.items()),'prepublication_drift')
 loader.REGISTRY.parent.mkdir(exist_ok=True);stage=Path(tempfile.mkdtemp(prefix='.gate-v3-',dir=loader.REGISTRY.parent))
 for name,data in {'payload.json':payload_raw,'signed-record.json':loader.encoded(record),'canonical-policy.json':policy_raw,'evidence-index.json':checked[p['simulation_evidence']['path']],'protected-paths.json':checked[p['protected_path_manifest_update']['path']]}.items():put(stage/name,data)
 # Validate staged signature and all bindings before publishing any canonical state.
 with tempfile.TemporaryDirectory(prefix='gate-v3-trust-check-') as tmp:
  a=Path(tmp)/'host.json';b=Path(tmp)/'public.json';a.write_bytes(loader.encoded(trust));b.write_bytes(loader.encoded(trust));loader.verify_bundle(ROOT,stage,a,b)
 KEYDIR.mkdir(mode=0o700,parents=True);os.chmod(KEYDIR,0o700)
 put(KEYDIR/'delegated-key.pem',key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
 loader.TRUST.parent.mkdir(parents=True,exist_ok=True);loader.PUBLIC.parent.mkdir(parents=True,exist_ok=True)
 put(loader.TRUST,loader.encoded(trust));put(loader.PUBLIC,loader.encoded(trust),0o644)
 os.rename(stage,loader.REGISTRY)
 proof=loader.verify();print(json.dumps({'signed':True,'canonical_gate':'v3','gate_v2':'retired_for_promotions','payload_sha256':loader.PAYLOAD_SHA256,'trust_sha256':loader.digest(loader.encoded(trust)),'record_sha256':loader.digest(loader.encoded(record)),'signed_at_utc':now,'verified':proof['verified'],'model_calls':0,'reserve_consumed':0}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--authorization',required=True);a=p.parse_args()
 def deny(*a,**kw):raise RuntimeError('network forbidden')
 with patch.object(socket.socket,'connect',deny),patch.object(socket.socket,'connect_ex',deny),patch.object(socket,'create_connection',deny):sign(a.authorization)
