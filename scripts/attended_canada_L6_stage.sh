#!/bin/bash
set -euo pipefail
umask 077
cd /root/nerve-attended-source
python3 - "$@" <<'PY'
import hashlib,json,os,subprocess,sys
from pathlib import Path
provider=dict(x.split('=',1) for x in Path('/proc/1/environ').read_bytes().decode().split('\0') if '=' in x)
assert provider.get('RUNPOD_POD_ID')=='b7qj6qyx9ij6gg','provider_pod_identity_changed'
os.environ['RUNPOD_POD_ID']=provider['RUNPOD_POD_ID'];os.environ['PYTHONPATH']='src'
assert len(sys.argv)==2,'one_fixed_stage_required'
a=json.loads(Path('/root/nerve-canada-v4-authorization.json').read_text())
assert a['approved_for_research'] is True and a['signing_authorized'] is False,'research_only_required'
assert a['L4_registration_sha256']=='1c0b7ff95de25979fbef6e42fdac521d33ed6cda55240f200a5f8c3c495ee07e','L4_binding_changed'
report=Path('/root/nerve-canada-v4-registration.json')
assert hashlib.sha256(report.read_bytes()).hexdigest()==a['candidate_registration_sha256'],'candidate_registration_changed'
r=json.loads(report.read_text());selected=[p for p in r['proposals'] if p['selected']]
assert r['registration_sha256']==a['L4_registration_sha256'],'L5_L4_registration_changed'
assert hashlib.sha256(Path('/root/nerve-canada-l4/registration.json').read_bytes()).hexdigest()==a['L4_registration_sha256'],'actual_L4_registration_changed'
assert len(selected)==1 and r['new_model_calls']==0 and r['holdout_accessed'] is False,'registered_single_candidate_required'
candidate='src/nerve_awim/memory_gateway/scientific_family_b_v4.py'
assert selected[0]['module']==candidate,'fixed_candidate_path_required'
assert selected[0]['hypothesis_sha256']==a['hypothesis_sha256'],'hypothesis_changed'
assert hashlib.sha256(Path(candidate).read_bytes()).hexdigest()==selected[0]['static']['source_sha256']==a['candidate_sha256'],'candidate_changed'
assert hashlib.sha256(Path('scripts/register_scientific_family_b_candidate.py').read_bytes()).hexdigest()==r['wrapper_sha256'],'L5_wrapper_changed'
assert hashlib.sha256(Path('scripts/attended_canada_L6_stage.sh').read_bytes()).hexdigest()==a['stage_sha256'],'stage_changed'
assert hashlib.sha256(Path('/root/nerve-canada-l4/aggregate.json').read_bytes()).hexdigest()==r['aggregate_sha256'],'L4_aggregate_changed'
cli=['python3','scripts/run_scientific_family_b_canada.py']
base=['--protocol','docs/galahad/evidence/family-b-attended-protocol-v3.json','--budget','/root/nerve-attended-budget','--running-start-utc','2026-10-16T08:33:31.123Z','--prior-running-seconds','3937.034']
common=['--bank','/root/nerve-attended-bank-v3','--calibration','/root/nerve-canada-calibration','--candidate-module',candidate]+base
dev='/root/nerve-canada-v4-dev';holdout='/root/nerve-canada-v4-holdout'
stages={
 'register-dev':['register','--kind','dev','--directory',dev,'--prior','/root/nerve-canada-l4']+common,
 'run-dev':['run','--directory',dev],
 'verify-dev':['verify','--directory',dev],
 'register-holdout':['register','--kind','holdout','--directory',holdout,'--prior',dev]+common,
 'run-holdout':['run','--directory',holdout],
 'verify-holdout':['verify','--directory',holdout],
}
assert sys.argv[1] in stages,'unregistered_stage'
subprocess.run(cli+stages[sys.argv[1]],check=True,env=os.environ)
PY
