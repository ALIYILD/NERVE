#!/bin/bash
set -euo pipefail
umask 077
python3 - "$@" <<'PY'
import hashlib,json,os,shutil,subprocess,sys,tarfile,time
from pathlib import Path
from datetime import datetime,timezone
W=Path('/workspace/nerve-v4-resume-20261016'); S=W/'source'
provider=dict(x.split('=',1) for x in Path('/proc/1/environ').read_bytes().decode().split('\0') if '=' in x)
assert provider.get('RUNPOD_POD_ID')=='b7qj6qyx9ij6gg','wrong_provider_pod'
os.environ['RUNPOD_POD_ID']=provider['RUNPOD_POD_ID']
if provider.get('RUNPOD_API_KEY'):os.environ['RUNPOD_API_KEY']=provider['RUNPOD_API_KEY']
assert len(sys.argv)==2
stage=sys.argv[1];win=json.loads(Path('/workspace/resume-window.json').read_text())
assert win['pod_id']==provider['RUNPOD_POD_ID']
start=datetime.fromisoformat(win['provider_started_at_utc'].replace('Z','+00:00'))
assert start.tzinfo is not None,'provider_time_required'
if stage not in ('stop','backup','progress'):assert 0<=time.time()-start.timestamp()<5400,'window_expired'
W.mkdir(mode=0o700,exist_ok=True)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,obj):
 with path.open('x') as f:json.dump(obj,f,indent=2);f.flush();os.fsync(f.fileno())
def extract(path,dest,digest):
 assert sha(path)==digest,'archive_hash_changed'
 with tarfile.open(path) as t:
  for member in t.getmembers():
   assert not member.issym() and not member.islnk() and not member.name.startswith('/') and '..' not in Path(member.name).parts,'unsafe_archive'
  t.extractall(dest)
def backup():
 out=W/'resume-evidence.private.tar.gz';temp=W/'resume-evidence.private.tar.gz.tmp'
 with tarfile.open(temp,'w:gz') as t:
  for p in sorted(W.iterdir()):
   if p.name not in ('resume-evidence.private.tar.gz','resume-evidence.private.tar.gz.tmp','source','bin','nerve-attended-bank-v3','preflight-evidence.private.tar.gz'):t.add(p,arcname=p.name)
 os.replace(temp,out)
 print(json.dumps({'backup_sha256':sha(out),'bytes':out.stat().st_size,'path':str(out)}),flush=True)
if stage=='arm-watchdog':
 cli=W/'bin/runpodctl';cli.parent.mkdir(exist_ok=True)
 src=Path('/workspace/runpodctl-linux-amd64')
 assert sha(src)=='b66d11eca8cacbf18a2de6943c6e18a79ffbdc8a3c30aa13a49dc6cfc15d4239'
 shutil.copyfile(src,cli);cli.chmod(0o700)
 os.environ['PATH']=str(cli.parent)+':'+os.environ['PATH']
 watcher=Path('/workspace/runpod-self-stop-v1.py')
 assert sha(watcher)=='0023da670d7a38fc58b7eb119d7bb8bffda6d66cc5d8a240574b9a48d3a205b7'
 with (W/'watchdog.log').open('xb') as log:
  p=subprocess.Popen(['python3',str(watcher),'--restart-epoch',str(start.timestamp()),'--receipt-dir',str(W)],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env=os.environ)
 for _ in range(45):
  if (W/'watchdog-ready.json').exists():print((W/'watchdog-ready.json').read_text(),flush=True);break
  assert p.poll() is None,'watchdog_failed'
  time.sleep(1)
 else:raise RuntimeError('watchdog_not_ready')
 raise SystemExit
if stage=='stop':
 (W/'STOP_NOW').touch();print('Stop requested through armed watchdog',flush=True);raise SystemExit
if stage=='restore':
 assert not S.exists() and not (W/'L4-complete-budget').exists(),'restore_once_only'
 S.mkdir(mode=0o700)
 extract(Path('/workspace/nerve-resume-source.tar.gz'),S,win['source_archive_sha256'])
 extract(Path('/workspace/nerve-attended-bank-v3.private.tar.gz'),W,'6b61fdc3cd68ca4d9ed45fb937b46765936e9e049827ce3133b4278ad8f921dc')
 extract(Path('/workspace/nerve-canada-final.private.tar.gz'),W,'c387c9d9bb04bd536d521f7e4636cd249d141756cdc0f65604b55b8c4e39a8f6')
os.chdir(S);sys.path[:0]=[str(S/'scripts'),str(S/'src')];os.environ['PYTHONPATH']=str(S/'src')+':'+str(S/'scripts')
import run_scientific_family_b_v4_resume as runner
if stage not in ('backup','progress'):runner.check_watchdog(start)
if stage=='restore':
 from unittest.mock import patch
 with patch.object(runner.transport,'network',side_effect=AssertionError('restore_no_model_calls')):
  assert runner.historical.verify(W/'L4-essential-backup')['complete']
  assert runner.historical.verify(W/'nerve-canada-calibration')['complete']
 protocol=runner.read(runner.RESUME);budget=W/'L4-complete-budget'
 assert len(list(budget.glob('call-*.json')))==1510
 for name,digest in protocol['prior_claim_sha256'].items():assert sha(budget/name)==digest
 bank=W/'nerve-attended-bank-v3'
 assert sha(bank/'manifest.json')==protocol['sealed_bank_manifest_sha256']
 for name in ('private-seed.json','holdout.json','slice1.json','slice2.json','slice3.json'):assert (bank/name).stat().st_mode&0o777==0
 assert not (bank/'slice1-consumed.json').exists()
 write(W/'restore-receipt.json',{'restored':True,'physical_attempts':1510,'historical_replay':True,'source_archive_sha256':win['source_archive_sha256'],'new_model_calls':0})
 backup()
 shutil.copyfile(W/'resume-evidence.private.tar.gz',W/'preflight-evidence.private.tar.gz')
 raise SystemExit
if stage=='bootstrap':
 runtime=Path('/workspace/nerve-attended-runtime/ollama-0.40.5.tar.zst');assert runtime.exists(),'cached_runtime_required'
 if not shutil.which('zstd'):
  subprocess.run(['apt-get','update','-qq'],check=True,timeout=120)
  subprocess.run(['apt-get','install','-y','-qq','zstd'],check=True,timeout=120)
 subprocess.run(['tar','--zstd','-xf',str(runtime),'-C','/usr'],check=True)
 env=dict(os.environ,OLLAMA_HOST='127.0.0.1',OLLAMA_MODELS='/workspace/nerve-attended-models')
 if subprocess.run(['pgrep','-x','ollama'],stdout=subprocess.DEVNULL).returncode:
  with (W/'ollama.log').open('xb') as log:subprocess.Popen(['/usr/bin/ollama','serve'],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env=env)
 for _ in range(30):
  try:identity=runner.transport.identity();break
  except Exception:time.sleep(1)
 else:raise RuntimeError('exact_cached_runtime_unavailable')
 write(W/'runtime-identity.json',identity);print(json.dumps(identity),flush=True);raise SystemExit
if stage=='backup':backup();raise SystemExit
if stage=='progress':
 print(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),'physical_claims':len(list((W/'L4-complete-budget').glob('call-*.json'))),'dev_rows':len(list((W/'v4-dev').glob('row-*.json'))),'holdout_rows':len(list((W/'v4-holdout').glob('row-*.json'))),'dev_report':(W/'v4-dev/aggregate.json').exists(),'holdout_report':(W/'v4-holdout/aggregate.json').exists()}));raise SystemExit
assert (W/'runtime-identity.json').exists() and (W/'restore-receipt.json').exists() and win.get('backup_preflight_sha256')==sha(W/'preflight-evidence.private.tar.gz'),'admission_preflight_required'
assert runner.transport.identity()==runner.read(W/'runtime-identity.json'),'runtime_changed'
kind='holdout' if stage.endswith('holdout') else 'dev';directory=W/('v4-'+kind)
if stage in ('register-dev','register-holdout'):
 result=runner.register(directory,kind,W/'nerve-attended-bank-v3',S/'docs/galahad/evidence/family-b-attended-protocol-v3.json',W/'nerve-canada-calibration',W/'L4-complete-budget','src/nerve_awim/memory_gateway/scientific_family_b_v4.py',W/('v4-dev' if kind=='holdout' else 'L4-essential-backup'),win['provider_started_at_utc'],15597.911)
elif stage in ('run-dev','run-holdout'):result=runner.run(directory)
elif stage in ('verify-dev','verify-holdout'):result=runner.verify(directory)
else:raise ValueError('unsupported_fixed_stage')
print(json.dumps(result,sort_keys=True,indent=2),flush=True)
PY
