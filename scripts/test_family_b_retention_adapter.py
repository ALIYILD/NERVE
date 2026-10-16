"""CPU-only isolated trust tests; no real keys, registry, or private evidence altered."""
import base64,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
sys.path[:0]=[str(Path(__file__).resolve().parent),str(Path(__file__).resolve().parents[1]/'src')]
import retained_scientific_family_b_skill as adapter
from nerve_awim.retained_skill_contract import select_retained_skill,signing_payload
class TrustTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.reg=self.root/'registry';self.reg.mkdir()
  def save(path,value):
   data=json.dumps(value,sort_keys=True).encode();path.write_bytes(data);return data
  self.save=save;sha=adapter._sha;config=b'candidate';baseline=b'baseline';model='a'*64
  (self.reg/'candidate-config.json').write_bytes(config);(self.reg/'baseline-config.json').write_bytes(baseline)
  incumbent={'skill_id':'family-b-fixture','version':'bootstrap','config_hash':sha(baseline)};evidence={}
  dirs={}
  for name in ('dev_study','holdout_study'):
   private=self.root/name;private.mkdir();dirs[name]=str(private)
   reg={'identity':{'model_digest':model}};agg={'complete':True}
   rr=save(private/'registration.json',reg);ar=save(private/'aggregate.json',agg)
   data=save(self.reg/(name+'.json'),{'registration':reg,'aggregate':agg,'registration_bytes_base64':base64.b64encode(rr).decode(),'aggregate_bytes_base64':base64.b64encode(ar).decode(),'candidate_config_sha256':sha(config),'incumbent_config_sha256':sha(baseline)})
   evidence[name]={'uri':name+'.json','sha256':sha(data)}
  manifest=save(self.reg/'manifest.json',{});evidence['task_bank_manifest']={'uri':'manifest.json','sha256':sha(manifest)};evidence['model_digest']=model
  record={'skill_id':incumbent['skill_id'],'version':'v1','config_hash':sha(config),'evidence_bundle':evidence,'supersedes':incumbent}
  key=Ed25519PrivateKey.generate();payload=signing_payload(record);record['signed_by']={'key_id':'fixture','signature':base64.b64encode(key.sign(payload)).decode()};save(self.reg/'skill-v1.json',record)
  state=save(self.reg/'registry.json',{'runtime_activation':False,'production_authorized':False})
  helper=self.root/'helper.py';helper.write_text('# fixture only');frozen=self.root/'frozen';(frozen/'src').mkdir(parents=True);self.source=frozen/'src/example.py';self.source.write_text('# source')
  metadata={'helper_sha256':sha(helper.read_bytes()),'frozen_checkout':str(frozen),'sources':{'src/example.py':sha(self.source.read_bytes())},'dev_directory':dirs['dev_study'],'holdout_directory':dirs['holdout_study']};meta=self.root/'metadata.json';mr=save(meta,metadata)
  trust={k:record[k] for k in ('skill_id','version','config_hash','evidence_bundle')};trust.update({'registry_only':True,'production_authorized':False,'incumbent':incumbent,'registry_state_sha256':sha(state),'key_id':'fixture','authorized_payload_sha256':sha(payload),'public_key_base64':base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode(),'metadata_path':str(meta),'metadata_sha256':sha(mr),'helper_path':str(helper),'helper_sha256':sha(helper.read_bytes()),'manifest_hash':sha(manifest),'model_digest':model})
  self.trust=self.root/'trust.json';tr=save(self.trust,trust)
  self.patches=[patch.object(adapter,'TRUST_PATH',self.trust),patch.object(adapter,'TRUST_SHA256',sha(tr)),patch.object(adapter.subprocess,'run',return_value=SimpleNamespace(stdout=json.dumps({'verified':True,'holdout_verdict':'promote_proposal','model_calls':0})))]
  for p in self.patches:p.start()
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  self.tmp.cleanup()
 def select(self):return select_retained_skill(**adapter.load_selection_inputs(self.reg))
 def test_valid_signature_selects_without_production(self):
  result=self.select();self.assertTrue(result['retained_skill_selected']);self.assertFalse(result['production_authorized'])
 def test_source_changed_after_loader_rejected(self):
  inputs=adapter.load_selection_inputs(self.reg);self.source.write_text('# drift');self.assertFalse(select_retained_skill(**inputs)['retained_skill_selected'])
 def test_external_trust_tamper_rejected(self):
  self.trust.write_text('{}')
  with self.assertRaises(ValueError):adapter.load_selection_inputs(self.reg)
 def test_registry_activation_rejected(self):
  self.save(self.reg/'registry.json',{'runtime_activation':True,'production_authorized':False})
  with self.assertRaises(ValueError):adapter.load_selection_inputs(self.reg)
 def test_forged_signature_rejected(self):
  inputs=adapter.load_selection_inputs(self.reg);inputs['record']['signed_by']['signature']=base64.b64encode(b'x'*64).decode();self.assertFalse(select_retained_skill(**inputs)['retained_skill_selected'])
 def test_missing_private_evidence_rejected(self):
  (self.root/'holdout_study/registration.json').unlink();self.assertFalse(self.select()['retained_skill_selected'])
if __name__=='__main__':unittest.main()
