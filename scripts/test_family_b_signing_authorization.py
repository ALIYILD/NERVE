"""CPU-only authorization checks; never calls the signer main or generates a key."""
import argparse
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('signer',ROOT/'scripts/retain_scientific_family_b_v4.py')
signer=importlib.util.module_from_spec(spec);spec.loader.exec_module(signer)
class AuthorizationTests(unittest.TestCase):
 def setUp(self):
  registry=ROOT/'registry/scientific-family-b-v4-7b'
  self.record=json.loads((registry/'skill-v1.json').read_bytes())
  self.evidence=(registry/'holdout_study.json').read_bytes()
  verdict=hashlib.sha256(base64.b64decode(json.loads(self.evidence)['aggregate_bytes_base64'])).hexdigest()
  self.text=f"sign skill_id={self.record['skill_id']} version={self.record['version']} model_digest={self.record['evidence_bundle']['model_digest']} holdout_verdict_sha256={verdict}"
 def test_exact_actual_binding(self):
  self.assertEqual(signer.validate_authorization(signer.full_form(self.text),self.record,self.evidence)['instruction'],self.text)
 def test_bare_sign_refused(self):
  with self.assertRaises(argparse.ArgumentTypeError):signer.full_form('sign')
 def test_each_binding_refused(self):
  for field in ('skill_id','version','model_digest','holdout_verdict_sha256'):
   parts=self.text.split();parts=[part.split('=')[0]+'=wrong' if part.startswith(field+'=') else part for part in parts]
   with self.subTest(field=field),self.assertRaises(ValueError):signer.validate_authorization(' '.join(parts),self.record,self.evidence)
 def test_changed_evidence_refused(self):
  with self.assertRaises(ValueError):signer.validate_authorization(self.text,self.record,self.evidence+b' ')
 def test_nonpromotion_refused(self):
  study=json.loads(self.evidence);study['aggregate']['verdict']='retain_incumbent'
  study['aggregate_bytes_base64']=base64.b64encode(json.dumps(study['aggregate']).encode()).decode()
  raw=json.dumps(study).encode();record=copy.deepcopy(self.record)
  record['evidence_bundle']['holdout_study']['sha256']=hashlib.sha256(raw).hexdigest()
  with self.assertRaises(ValueError):signer.validate_authorization(self.text,record,raw)
if __name__=='__main__':unittest.main()
