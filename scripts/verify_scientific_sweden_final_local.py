"""Verify actual final private archive locally without any model/network call."""
from pathlib import Path
import argparse,hashlib,json,sys,tarfile
from unittest.mock import patch
BASE=Path('/Users/aliyildirim/nerve-research-runs/sweden-20261016')
ROOT=Path('/Users/aliyildirim/nerve-runpod-retention')
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
import run_scientific_family_b_v4_sweden as runner
p=argparse.ArgumentParser();p.add_argument('--archive-sha256',required=True);args=p.parse_args()
archive=BASE/'resume-evidence.private.tar.gz'
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
assert sha(archive)==args.archive_sha256,'final_archive_hash_mismatch'
dest=BASE/'final-extracted';dest.mkdir(mode=0o700)
with tarfile.open(archive) as t:
 for m in t.getmembers():
  assert not m.issym() and not m.islnk() and not m.name.startswith('/') and '..' not in Path(m.name).parts,'unsafe_archive'
 t.extractall(dest)
protocol=runner.read(runner.RESUME)
budget=dest/'L4-complete-budget';claims=sorted(budget.glob('call-*.json'))
assert [x.name for x in claims]==[f'call-{i:05d}.json' for i in range(len(claims))]
for name,digest in protocol['prior_claim_sha256'].items():assert sha(budget/name)==digest
assert len(claims)<=6000
reports={}
with patch.object(runner.transport,'network',side_effect=AssertionError('offline_verification_no_network')),patch.object(runner.historical.transport,'network',side_effect=AssertionError('offline_historical_no_network')):
 for name in ('v4-calibration','v4-dev','v4-holdout'):
  if (dest/name/'aggregate.json').exists():reports[name]=runner.verify(dest/name)
  elif (dest/name).exists():raise ValueError('study_without_final_report:'+name)
 assert runner.historical.verify(dest/'L4-essential-backup')['complete']
 assert runner.historical.verify(dest/'nerve-canada-calibration')['complete']
registration_counts={}
for claim in claims:
 reg=runner.read(claim)['registration_sha256'];registration_counts[reg]=registration_counts.get(reg,0)+1
for name,report in reports.items():
 regsha=sha(dest/name/'registration.json')
 assert registration_counts.get(regsha,0)==report['attempts'],'attempt_count_mismatch'
result={'verified':True,'archive_sha256':sha(archive),'physical_claims':len(claims),'prior_physical_claims':1510,'new_physical_claims':len(claims)-1510,'claims_by_registration':registration_counts,'aggregate_sha256':{name:sha(dest/name/'aggregate.json') for name in reports},'reports':reports,'holdout_study_directory_present':(dest/'v4-holdout').exists(),'holdout_bank_marker_in_backup':False,'holdout_marker_verification_limitation':'Bank was separately preserved and excluded from final archive; rely on pre-study restore receipt and root stage history. No final bank marker or permissions readback was performed.','new_model_calls_from_verification':0}
with (BASE/'final-verification.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps(result,sort_keys=True,indent=2))
