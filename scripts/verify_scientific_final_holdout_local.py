"""Replay final calibration/holdout privately; publish aggregate-only receipt."""
from pathlib import Path
import argparse,hashlib,json,sys,tarfile
from unittest.mock import patch
BASE=Path('/Users/aliyildirim/nerve-research-runs/final-holdout-20261016')
ROOT=Path('/Users/aliyildirim/nerve-runpod-retention')
PRIOR=Path('/Users/aliyildirim/nerve-research-runs/sweden-20261016/final-extracted')
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
import run_scientific_family_b_v4_final_holdout as runner
p=argparse.ArgumentParser();p.add_argument('--archive-sha256',required=True);args=p.parse_args()
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
archive=BASE/'final-holdout-evidence.private.tar.gz';assert sha(archive)==args.archive_sha256
protocol=runner.read(runner.RESUME)
predecessor=PRIOR.parent/'resume-evidence.private.tar.gz';assert sha(predecessor)==protocol['parent_final_archive_sha256']
dest=BASE/'final-extracted';dest.mkdir(mode=0o700)
with tarfile.open(archive) as t:
 for m in t.getmembers():assert not m.issym() and not m.islnk() and not m.name.startswith('/') and '..' not in Path(m.name).parts
 t.extractall(dest)
# Reuse already completed full predecessor replay through exact file/source hashes.
for name in ('v4-dev','v4-calibration'):assert runner.verified_parent(PRIOR/name)['complete']
budget=dest/'L4-complete-budget';claims=sorted(budget.glob('call-*.json'))
assert [p.name for p in claims]==[f'call-{i:05d}.json' for i in range(len(claims))]
for name,digest in protocol['prior_claim_sha256'].items():assert sha(budget/name)==digest
assert len(claims)<=6000
reports={}
with patch.object(runner.transport,'network',side_effect=AssertionError('offline_no_network')):
 for name in ('replacement-calibration','v4-holdout'):
  if (dest/name/'aggregate.json').exists():reports[name]=runner.verify(dest/name)
  elif (dest/name).exists():raise ValueError('study_without_final_aggregate:'+name)
counts={}
for claim in claims:
 reg=runner.read(claim)['registration_sha256'];counts[reg]=counts.get(reg,0)+1
new_attempts=0
for name,report in reports.items():
 regsha=sha(dest/name/'registration.json');assert counts.get(regsha,0)==report['attempts'];new_attempts+=report['attempts']
assert len(claims)==2715+new_attempts,'unaccounted_new_claims'
metadata=dest/'bank-metadata';marker=metadata/'slice1-consumed.json'
assert sha(metadata/'manifest.json')==protocol['sealed_bank_manifest_sha256']
if 'v4-holdout' in reports:
 assert marker.exists();consumed=runner.read(marker)
 assert consumed['candidate_sha256']==protocol['candidate_sha256']
 assert consumed['dev_aggregate_sha256']==protocol['parent_aggregate_sha256']
 reg=runner.read(dest/'v4-holdout/registration.json')
 assert reg['candidate_module']==protocol['candidate_module'] and reg['task_count']==100
 assert reg['prior_aggregate_sha256']==protocol['parent_aggregate_sha256']
 assert reg['calibration_registration_sha256']==sha(dest/'replacement-calibration/registration.json')
 assert reg['sources'][protocol['candidate_module']]==protocol['candidate_sha256']
result={'verified':True,'archive_sha256':sha(archive),'predecessor_archive_sha256':sha(predecessor),'prior_claims':2715,'physical_claims':len(claims),'new_attempts':new_attempts,'claims_by_registration':counts,'reports':reports,'aggregate_sha256':{name:sha(dest/name/'aggregate.json') for name in reports},'slice1_consumption_marker_present':marker.exists(),'parent_proof_hash_verified':True,'new_model_calls_from_verification':0,'promotion_or_signing_performed':False,'private_item_contents_exported':False}
with (BASE/'final-verification.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({'verified':True,'physical_claims':len(claims),'new_attempts':new_attempts,'verdict':reports.get('v4-holdout',{}).get('verdict'),'complete':reports.get('v4-holdout',{}).get('complete')}))
