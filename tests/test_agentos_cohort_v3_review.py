"""Independent manual gold for public v3 compositions; no inference/admission."""
import json
from hashlib import sha256
from pathlib import Path
import unittest
from nerve_awim import agentos_audit_cohort as legacy
from nerve_awim import agentos_audit_evidence as oracle
from nerve_awim.agentos_audit_fixtures import development_cases

ROOT=Path(__file__).resolve().parents[1]
# Derived from inspected bundles before invoking the oracle. Every ID here is
# an applicable independent observation, not a derived assertion or majority.
GOLD={
 'expired-root-diamond-refresh':('unknown',[]),
 'independent-root-survives-derived-diamond':('supported',['free']),
 'credential-majority-not-resolution':('unknown',['no','yes-a','yes-b']),
 'fresh-root-stale-derived-wrapper':('supported',['fresh']),
 'request-join-time-laundering':('contradicted',['observed']),
 'pricing-component-splice':('contradicted',['input-free','output-free']),
 'old-parent-does-not-disqualify-new-independent-root':('supported',['current']),
 'catalog-provider-model-composite-key':('contradicted',['negative']),
 'execution-complete-conflict-citations':('unknown',['no','yes-a','yes-b']),
 'pricing-future-root-with-past-descendants':('unknown',[]),
 'credential-disjoint-branches-cross-identity-conflict':('unknown',['no','yes']),
 'catalog-consensus-identity-bridge-future-dissent':('supported',['yes-a','yes-b']),
 'execution-identity-cartesian-join-plus-root-conflict':('unknown',['no','yes']),
 'price-unanimous-paid-opposite-component-echoes':('contradicted',['paid-a','paid-b','paid-c']),
 'catalog-stale-and-foreign-parent-laundering':('unknown',[]),
 'pricing-conflict-with-stale-future-tiebreakers':('unknown',['free','paid']),
}
FIELDS={
 'credential_present':['fields.present','model','observed_at','provider'],
 'catalog_listed':['fields.listed','model','observed_at','provider'],
 'execution_success':['fields.request_id','fields.success','model','observed_at','provider'],
 'zero_price':['fields.input_usd','fields.output_usd','model','observed_at','provider'],
}

def fixture():
 return json.loads((ROOT/'docs/evidence/agentos-audit-composition-v3.json').read_text())

class V3IndependentReviewTests(unittest.TestCase):
 def test_manual_decisions_and_exact_citation_fields(self):
  data=fixture()
  rows=[r for group in data['splits'].values() for r in group]
  self.assertEqual({r['id'].removeprefix('audit-v3-') for r in rows},set(GOLD))
  for row in rows:
   decision,ids=GOLD[row['id'].removeprefix('audit-v3-')]
   gold={'decision':decision,'citations':[{'source_id':i,'fields':FIELDS[row['bundle']['claim']['kind']]} for i in ids]}
   with self.subTest(case=row['id']):
    self.assertEqual(row['expected'],gold)
    self.assertEqual(oracle.expected_decision(row['bundle']),gold)
 def test_separated_compositions_against_development_v1_v2(self):
  data=fixture(); rows=[r for group in data['splits'].values() for r in group]
  v2=json.loads((ROOT/'docs/evidence/agentos-audit-composition-v2.json').read_text())
  prior=development_cases()+[r for group in legacy.cohort()['splits'].values() for r in group]+[r for group in v2['splits'].values() for r in group]
  self.assertEqual({k:len(v) for k,v in data['splits'].items()},{'train':2,'selection':4,'retention':4,'final':6})
  for key in ('id','family'):
   self.assertEqual(len({r[key] for r in rows}),16)
   self.assertFalse({r[key] for r in rows}&{r[key] for r in prior})
  identities={legacy.canonical_identity(r) for r in rows}
  self.assertEqual(len(identities),16)
  self.assertFalse(identities&{legacy.canonical_identity(r) for r in prior})
 def test_review_pins_manifest_and_documents_nonchronological_scope(self):
  data=fixture()
  digest=sha256(json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
  review=json.loads((ROOT/'docs/evidence/agentos-audit-composition-v3-independent-review.json').read_text())
  self.assertEqual(digest,'ef671cbfdda13620f3ea31de9165224e0c28f39e13fa6a018be7243e264cea37')
  self.assertEqual(review['manifest_sha256'],digest)
  self.assertEqual(review['checks'],{'gold':True,'novelty':True,'split_separation':True})
  self.assertIn('nonchronological',review['method'])

if __name__=='__main__': unittest.main()
