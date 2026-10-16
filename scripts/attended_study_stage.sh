#!/bin/bash
set -euo pipefail
umask 077
cd /root/nerve-attended-source
python3 - "$@" <<'PY'
import os,subprocess,sys
from pathlib import Path
provider=dict(x.split('=',1) for x in Path('/proc/1/environ').read_bytes().decode().split('\0') if '=' in x)
assert provider.get('RUNPOD_POD_ID')=='97vr620wnmtuga','provider_pod_identity_changed'
os.environ['RUNPOD_POD_ID']=provider['RUNPOD_POD_ID'];os.environ['PYTHONPATH']='src'
assert len(sys.argv)==2,'one_fixed_stage_required'
stage=sys.argv[1];cli=['python3','scripts/run_scientific_family_b_study.py'];base=['--protocol','docs/galahad/evidence/family-b-attended-protocol-v3.json','--budget','/root/nerve-attended-budget','--running-start-utc','2026-10-16T06:27:28.749Z','--prior-running-seconds','1160.783']
cal='/root/nerve-attended-calibration';dev='/root/nerve-attended-l4';bank='/root/nerve-attended-bank-v3'
stages={
 'register-calibration':['register','--kind','calibration','--directory',cal]+base,
 'run-calibration':['run','--directory',cal],
 'verify-calibration':['verify','--directory',cal],
 'register-dev':['register','--kind','dev','--directory',dev,'--bank',bank,'--calibration',cal]+base,
 'run-dev':['run','--directory',dev],
 'verify-dev':['verify','--directory',dev],
}
assert stage in stages,'unregistered_stage'
subprocess.run(cli+stages[stage],check=True,env=os.environ)
PY
