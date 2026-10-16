"""Verified canonical gate loader. Never evaluates models or opens reserve items."""
import base64,hashlib,importlib.util,json
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
ROOT=Path(__file__).resolve().parents[3]
GATE_ID='scientific-paired-sequential-promotion'
PAYLOAD_SHA256='c1dab32c453609ce2cae72a7c3b660874f243b1f2e67bebde8c9463d44de22d8'
REGISTRY=ROOT/'registry/scientific-promotion-gate-v3'
TRUST=Path('/Users/aliyildirim/.local/share/nerve/trust/scientific-promotion-gate-v3-operator.json')
PUBLIC=ROOT/'trust/scientific-promotion-gate-v3-operator.json'
def digest(data):return hashlib.sha256(data).hexdigest()
def encoded(value):return (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
def require(ok,why):
 if not ok:raise ValueError(why)
def verify_bundle(root,registry,trust_path,public_path,*,check_loader=True):
 trust_raw=trust_path.read_bytes();trust=json.loads(trust_raw)
 require(public_path.read_bytes()==trust_raw,'host_public_trust_mismatch')
 if check_loader:require(digest(Path(__file__).read_bytes())==trust['loader_sha256'],'loader_source_drift')
 payload_raw=(registry/'payload.json').read_bytes();require(digest(payload_raw)==PAYLOAD_SHA256==trust['payload_sha256'],'payload_mismatch')
 record=json.loads((registry/'signed-record.json').read_text());message=record['signed_message']
 Ed25519PublicKey.from_public_bytes(base64.b64decode(trust['public_key_base64'],validate=True)).verify(base64.b64decode(record['signature_base64'],validate=True),encoded(message))
 require(digest(encoded(message))==trust['signed_message_sha256'],'signed_message_mismatch')
 require(message['payload_sha256']==PAYLOAD_SHA256 and message['gate_id']==GATE_ID and message['version']=='v3','signed_identity_mismatch')
 policy_raw=(registry/'canonical-policy.json').read_bytes();require(digest(policy_raw)==message['canonical_policy_sha256'],'policy_mismatch')
 policy=json.loads(policy_raw);require(policy['active_promotion_gate']=='v3' and policy['gate_v2']=='retired_for_promotions','inactive_or_wrong_policy')
 payload=json.loads(payload_raw)
 for key in ('source','simulation_evidence','registered_design','tables','protected_path_manifest_update'):
  ref=payload[key];require(digest((root/ref['path']).read_bytes())==ref['sha256'],'binding_mismatch:'+key)
 index=json.loads((root/payload['simulation_evidence']['path']).read_text())
 protected=json.loads((root/payload['protected_path_manifest_update']['path']).read_text())
 for path,h in {**index['files'],**protected['paths']}.items():require(digest((root/path).read_bytes())==h,'protected_or_evidence_drift:'+path)
 require((registry/'protected-paths.json').read_bytes()==(root/payload['protected_path_manifest_update']['path']).read_bytes(),'active_manifest_mismatch')
 require((registry/'evidence-index.json').read_bytes()==(root/payload['simulation_evidence']['path']).read_bytes(),'active_evidence_mismatch')
 return {'verified':True,'gate_id':GATE_ID,'version':'v3','policy':policy,'payload_sha256':PAYLOAD_SHA256,'payload':payload,'signed_at_utc':message['signed_at_utc'],'model_calls':0}
def verify():return verify_bundle(ROOT,REGISTRY,TRUST,PUBLIC)
def require_promotion_gate(version):
 result=verify();require(version=='v3','gate_v2_retired_for_promotions');return result
class CanonicalProcess:
 def __init__(self,*,planned_discordant_p,order_offset=0,fresh_items=True):
  self.proof=require_promotion_gate('v3');p=self.proof['payload'];design=json.loads((ROOT/p['registered_design']['path']).read_text())
  path=ROOT/p['source']['path'];source=path.read_bytes();require(digest(source)==p['source']['sha256'],'gate_source_drift')
  # Execute exactly the verified bytes; no import-time pycache or unverified reload.
  namespace={'__name__':'verified_scientific_promotion_gate_v3','__file__':str(path)};exec(compile(source,str(path),'exec'),namespace)
  self.process=namespace['Process'](m=design['selected_m'],risk_stratum=design['risk_followup']['stratum'],planned_discordant_p=planned_discordant_p,order_offset=order_offset,fresh_items=fresh_items)
 def next_stratum(self):return self.process.next_stratum()
 def update(self,**kwargs):return self.process.update(**kwargs)
 def report(self):
  r=self.process.report();r.update(installed=True,signature_verified=True,canonical_gate=True,payload_sha256=PAYLOAD_SHA256)
  # A gate proposal still never signs/retains a candidate automatically.
  return r
