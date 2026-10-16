#!/usr/bin/env python3
"""One-shot, explicitly delegated family-B retention; never activates production.
Run only after review of the exact preparation SHA supplied on the command line.
"""
import argparse,base64,hashlib,json,os,shutil,subprocess,sys,tempfile
from pathlib import Path
from datetime import datetime,timezone
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from nerve_awim.retained_skill_contract import signing_payload
BASE=Path('/Users/aliyildirim/nerve-research-runs/family-b-retention-20261016')
REGISTRY=ROOT/'registry/scientific-family-b-v4-7b'
TRUST=Path('/Users/aliyildirim/.local/share/nerve/trust/scientific-family-b-v4-7b-operator.json')
PUBLIC=ROOT/'trust/scientific-family-b-v4-7b-operator.json'
KEYDIR=Path('/Users/aliyildirim/.local/share/nerve/signing/scientific-family-b-v4-7b-20261016')
HELPER=ROOT/'scripts/scientific_family_b_retention_evidence.py'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def raw(value):return (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
def require(value):
 if not value:raise ValueError('family_b_signing_admission_failed')
def exclusive(path,value,mode=0o600):
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,mode)
 with os.fdopen(fd,'wb') as f:f.write(value);f.flush();os.fsync(f.fileno())
def main():
 p=argparse.ArgumentParser();p.add_argument('--prepared-sha256',required=True);a=p.parse_args()
 metadata_raw=(BASE/'preparation.json').read_bytes();require(sha(metadata_raw)==a.prepared_sha256);metadata=json.loads(metadata_raw)
 require(not any(p.exists() for p in (REGISTRY,TRUST,PUBLIC,KEYDIR)))
 require(sha(HELPER.read_bytes())==metadata['helper_sha256'])
 prepared=BASE/'prepared';prepared_bytes={p.name:p.read_bytes() for p in prepared.iterdir() if p.is_file()}
 require({name:sha(data) for name,data in prepared_bytes.items()}==metadata['prepared_files'])
 result=subprocess.run([sys.executable,'-I',str(HELPER),'verify','--metadata',str(BASE/'preparation.json')],check=True,capture_output=True,text=True,timeout=180)
 proof=json.loads(result.stdout);require(proof['verified'] and proof['holdout_verdict']=='promote_proposal' and proof['model_calls']==0)
 require((BASE/'preparation.json').read_bytes()==metadata_raw and sha(HELPER.read_bytes())==metadata['helper_sha256'])
 require({p.name:sha(p.read_bytes()) for p in prepared.iterdir() if p.is_file()}==metadata['prepared_files'])
 record=json.loads(prepared_bytes['unsigned-record.json']);payload=signing_payload(record)
 require(record['skill_id']=='scientific-family-b-measurement-qwen2.5-coder-7b' and record['version']=='v1' and record['supersedes']['version']=='adapted-v1@7B-bootstrap')
 # All evidence and unsigned bytes were checked before any registry/key mutation.
 REGISTRY.parent.mkdir(parents=True,exist_ok=True);staging=Path(tempfile.mkdtemp(prefix='.family-b-retention-',dir=REGISTRY.parent))
 for name in ('candidate-config.json','baseline-config.json','dev_study.json','holdout_study.json','task-bank-manifest.json'):
  exclusive(staging/name,prepared_bytes[name])
 KEYDIR.mkdir(parents=True,mode=0o700);os.chmod(KEYDIR,0o700)
 key=Ed25519PrivateKey.generate();public=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
 exclusive(KEYDIR/'delegated-key.pem',key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
 keyid='delegated-local-ed25519:'+sha(public)
 record['signed_by']={'key_id':keyid,'signature':base64.b64encode(key.sign(payload)).decode()}
 exclusive(staging/'skill-v1.json',raw(record));exclusive(staging/'registry.json',prepared_bytes['registry-transition.json'])
 trust={k:record[k] for k in ('skill_id','version','config_hash','evidence_bundle')}
 trust.update({'key_id':keyid,'public_key_base64':base64.b64encode(public).decode(),'authorized_payload_sha256':sha(payload),'incumbent':record['supersedes'],'model_digest':record['evidence_bundle']['model_digest'],'manifest_hash':metadata['manifest_hash'],'metadata_path':str(BASE/'preparation.json'),'metadata_sha256':sha(metadata_raw),'helper_path':str(HELPER),'helper_sha256':metadata['helper_sha256'],'prepared_files':metadata['prepared_files'],'registry_state_sha256':sha(prepared_bytes['registry-transition.json']),'authorization':metadata['authorization'],'signed_at_utc':datetime.now(timezone.utc).isoformat(),'registry_only':True,'production_authorized':False,'signature_is_user_personal_key':False,'verification':proof})
 TRUST.parent.mkdir(parents=True,exist_ok=True);PUBLIC.parent.mkdir(parents=True,exist_ok=True)
 exclusive(TRUST,raw(trust));exclusive(PUBLIC,raw(trust),0o644)
 os.rename(staging,REGISTRY)
 print(json.dumps({'retained':True,'registry':str(REGISTRY),'trust_sha256':sha(raw(trust)),'record_sha256':sha(raw(record)),'production_authorized':False,'model_calls':0}))
if __name__=='__main__':main()
