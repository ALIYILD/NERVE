import base64,json,sys,tempfile,unittest
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nerve_awim.memory_gateway import retained_promotion_gate as load
from sign_promotion_gate_v3 import validate_authorization
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.stage=Path(self.tmp.name)/'stage';self.stage.mkdir();self.host=Path(self.tmp.name)/'host';self.pub=Path(self.tmp.name)/'public'
  self.payload=(ROOT/'docs/galahad/evidence/gate-v3-signing-payload.json').read_bytes();p=json.loads(self.payload)
  policy=load.encoded({'active_promotion_gate':'v3','gate_v2':'retired_for_promotions'})
  message={'payload_sha256':load.PAYLOAD_SHA256,'gate_id':load.GATE_ID,'version':'v3','canonical_policy_sha256':load.digest(policy),'signed_at_utc':'test'}
  key=Ed25519PrivateKey.generate();record={'signed_message':message,'signature_base64':base64.b64encode(key.sign(load.encoded(message))).decode()}
  trust={'payload_sha256':load.PAYLOAD_SHA256,'public_key_base64':base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode(),'signed_message_sha256':load.digest(load.encoded(message)),'loader_sha256':load.digest(Path(load.__file__).read_bytes())}
  for f,b in {'payload.json':self.payload,'signed-record.json':load.encoded(record),'canonical-policy.json':policy,'protected-paths.json':(ROOT/p['protected_path_manifest_update']['path']).read_bytes(),'evidence-index.json':(ROOT/p['simulation_evidence']['path']).read_bytes()}.items():(self.stage/f).write_bytes(b)
  self.host.write_bytes(load.encoded(trust));self.pub.write_bytes(load.encoded(trust))
 def verify(self):return load.verify_bundle(ROOT,self.stage,self.host,self.pub)
 def test_valid_staged_signature(self):self.assertTrue(self.verify()['verified'])
 def test_bare_sign_refused(self):
  with self.assertRaises(ValueError):validate_authorization('sign',self.payload)
 def test_exact_authorization(self):
  text=(ROOT/'docs/galahad/evidence/gate-v3-signing-request.txt').read_text().strip();self.assertEqual(validate_authorization(text,self.payload)['version'],'v3')
  with self.assertRaises(ValueError):validate_authorization(text.replace('version=v3','version=v2'),self.payload)
 def test_payload_tamper(self):
  (self.stage/'payload.json').write_bytes(self.payload+b' ')
  with self.assertRaises(ValueError):self.verify()
 def test_policy_tamper(self):
  (self.stage/'canonical-policy.json').write_text('{}')
  with self.assertRaises(ValueError):self.verify()
 def test_record_tamper(self):
  p=self.stage/'signed-record.json';v=json.loads(p.read_text());v['signed_message']['version']='v2';p.write_bytes(load.encoded(v))
  with self.assertRaises(Exception):self.verify()
 def test_trust_mismatch(self):
  self.pub.write_text('{}')
  with self.assertRaises(ValueError):self.verify()
 def test_manifest_tamper(self):
  (self.stage/'protected-paths.json').write_text('{}')
  with self.assertRaises(ValueError):self.verify()
if __name__=='__main__':unittest.main()
