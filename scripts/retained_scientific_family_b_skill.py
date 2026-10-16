#!/usr/bin/env python3
"""Opt-in family-B retained consumer. Independent host trust; CPU evidence only."""
import base64,hashlib,json,subprocess,sys
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
TRUST_SHA256='f592a0aca09e0d32fb4ede63a607012d7866a486aa6eef5103ac2025e54d8a50'
TRUST_PATH=Path('/Users/aliyildirim/.local/share/nerve/trust/scientific-family-b-v4-7b-operator.json')
def _sha(raw):return hashlib.sha256(raw).hexdigest()
def _require(value):
 if not value:raise ValueError('family_b_retention_trust_failed')
def _trust():
 raw=TRUST_PATH.read_bytes();_require(_sha(raw)==TRUST_SHA256);value=json.loads(raw)
 _require(value['registry_only'] is True and value['production_authorized'] is False)
 return value

def load_selection_inputs(registry_directory):
 trust=_trust();root=Path(registry_directory)
 record=json.loads((root/'skill-v1.json').read_bytes());config=(root/'candidate-config.json').read_bytes()
 _require(_sha((root/'baseline-config.json').read_bytes())==trust['incumbent']['config_hash'])
 state=(root/'registry.json').read_bytes();_require(_sha(state)==trust['registry_state_sha256'])
 value=json.loads(state);_require(value['runtime_activation'] is False and value['production_authorized'] is False)
 artifacts={ref['uri']:(root/ref['uri']).read_bytes() for name,ref in trust['evidence_bundle'].items() if name!='model_digest'}
 def verify_signature(key_id,payload,signature):
  try:
   _require(_trust()==trust and key_id==trust['key_id'] and _sha(payload)==trust['authorized_payload_sha256'])
   Ed25519PublicKey.from_public_bytes(base64.b64decode(trust['public_key_base64'],validate=True)).verify(base64.b64decode(signature,validate=True),payload)
   return True
  except Exception:return False
 def verify_gate(item,verified_artifacts):
  try:
   _require(_trust()==trust and _sha(config)==trust['config_hash'])
   _require(all(item[k]==trust[k] for k in ('skill_id','version','config_hash','evidence_bundle')) and item['supersedes']==trust['incumbent'])
   metadata_raw=Path(trust['metadata_path']).read_bytes();_require(_sha(metadata_raw)==trust['metadata_sha256']);metadata=json.loads(metadata_raw)
   helper=Path(trust['helper_path']);_require(_sha(helper.read_bytes())==trust['helper_sha256']==metadata['helper_sha256'])
   frozen=Path(metadata['frozen_checkout'])
   for name,digest in metadata['sources'].items():_require(_sha((frozen/name).read_bytes())==digest)
   for name in ('dev_study','holdout_study','task_bank_manifest'):
    _require(_sha(verified_artifacts[name])==trust['evidence_bundle'][name]['sha256'])
   for name,directory in (('dev_study',metadata['dev_directory']),('holdout_study',metadata['holdout_directory'])):
    study=json.loads(verified_artifacts[name]);private=Path(directory)
    _require(study['candidate_config_sha256']==trust['config_hash'] and study['incumbent_config_sha256']==trust['incumbent']['config_hash'])
    for key in ('registration','aggregate'):
     exact=base64.b64decode(study[key+'_bytes_base64'],validate=True)
     _require(exact==(private/(key+'.json')).read_bytes() and json.loads(exact)==study[key])
    _require(study['registration']['identity']['model_digest']==trust['model_digest'])
   result=subprocess.run([sys.executable,'-I',str(helper),'verify','--metadata',trust['metadata_path']],check=True,capture_output=True,text=True,timeout=180)
   proof=json.loads(result.stdout);_require(proof['verified'] is True and proof['holdout_verdict']=='promote_proposal' and proof['model_calls']==0)
   return True
  except Exception:return False
 return {'record':record,'incumbent':trust['incumbent'],'config_bytes':config,'artifact_bytes':artifacts,'manifest_hash':trust['manifest_hash'],'model_digest':trust['model_digest'],'verify_gate':verify_gate,'verify_signature':verify_signature}
