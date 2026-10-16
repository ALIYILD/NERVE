#!/bin/bash
set -euo pipefail
umask 077
python3 - "$@" <<'PY'
import hashlib,json,os,shutil,subprocess,sys,tarfile,time
from pathlib import Path
from datetime import datetime,timezone
W=Path('/workspace/nerve-v4-holdout-replacement-20261016');OLD=W;S=W/'source'
provider=dict(x.split('=',1) for x in Path('/proc/1/environ').read_bytes().decode().split('\0') if '=' in x)
assert provider.get('RUNPOD_POD_ID'),'missing_provider_identity'
os.environ['RUNPOD_POD_ID']=provider['RUNPOD_POD_ID']
if provider.get('RUNPOD_API_KEY'):os.environ['RUNPOD_API_KEY']=provider['RUNPOD_API_KEY']
assert len(sys.argv)==2;stage=sys.argv[1]
win=json.loads(Path('/workspace/holdout-replacement-window.json').read_text())
assert win['pod_id']==provider['RUNPOD_POD_ID'] and win['region']=='CA-MTL-1' and win['hourly_usd']==0.59
assert win['prior_gpu_seconds']==19467.934 and win['gpu_budget_seconds']==21600
start=datetime.fromisoformat(win['provider_started_at_utc'].replace('Z','+00:00'));assert start.tzinfo
if stage not in ('stop','backup','progress'):assert 0<=time.time()-start.timestamp()<1800
W.mkdir(mode=0o700,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,obj):
 with p.open('x') as f:json.dump(obj,f,indent=2);f.flush();os.fsync(f.fileno())
def backup():
 out=W/'holdout-replacement-evidence.private.tar.gz';temp=W/'holdout-replacement-evidence.private.tar.gz.tmp'
 with tarfile.open(temp,'w:gz') as t:
  for p in sorted(W.iterdir()):
   if p.name not in ('source','bin','holdout-replacement-evidence.private.tar.gz','holdout-replacement-evidence.private.tar.gz.tmp','preflight-evidence.private.tar.gz','L4-complete-budget','nerve-attended-bank-v3','bank-metadata'):t.add(p,arcname=p.name)
  t.add(OLD/'L4-complete-budget',arcname='L4-complete-budget')
  for name in ('manifest.json','sealing-receipt.json','slice1-consumed.json'):
   p=OLD/'nerve-attended-bank-v3'/name
   if p.exists():t.add(p,arcname='bank-metadata/'+name)
 os.replace(temp,out);print(json.dumps({'backup_sha256':sha(out),'bytes':out.stat().st_size,'path':str(out)}),flush=True)
if stage=='arm-watchdog':
 cli=W/'bin/runpodctl';cli.parent.mkdir(exist_ok=True)
 src=Path('/workspace/runpodctl-linux-amd64');assert sha(src)=='b66d11eca8cacbf18a2de6943c6e18a79ffbdc8a3c30aa13a49dc6cfc15d4239';shutil.copyfile(src,cli);cli.chmod(0o700)
 os.environ['PATH']=str(cli.parent)+':'+os.environ['PATH']
 watcher=Path('/workspace/runpod-self-stop-holdout-replacement-v1.py');assert sha(watcher)=='68906d7efd8beadd68d7749b866309f0b96bd131d52daf75feade09ae4ffc1d0'
 with (W/'watchdog.log').open('xb') as log:p=subprocess.Popen(['python3',str(watcher),'--restart-epoch',str(start.timestamp()),'--receipt-dir',str(W)],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env=os.environ)
 for _ in range(45):
  if (W/'watchdog-ready.json').exists():print((W/'watchdog-ready.json').read_text());break
  assert p.poll() is None,'watchdog_failed';time.sleep(1)
 else:raise RuntimeError('watchdog_not_ready')
 raise SystemExit
if stage=='stop':(W/'STOP_NOW').touch();print('Stop requested through watchdog');raise SystemExit
if stage=='restore':
 assert not S.exists(),'source_restore_once';S.mkdir(mode=0o700)
 archive=Path('/workspace/nerve-holdout-replacement-source.tar.gz');assert sha(archive)==win['source_archive_sha256']
 with tarfile.open(archive) as t:
  for m in t.getmembers():assert not m.issym() and not m.islnk() and not m.name.startswith('/') and '..' not in Path(m.name).parts
  t.extractall(S)
 for archive_name,digest in (('nerve-sweden-final.private.tar.gz','d82ff7929f9e174a28d4d2fe93fae8d30e9258a073c9fcd9bd405521883903ff'),('nerve-attended-bank-v3.private.tar.gz','6b61fdc3cd68ca4d9ed45fb937b46765936e9e049827ce3133b4278ad8f921dc')):
  archive=Path('/workspace')/archive_name;assert sha(archive)==digest
  with tarfile.open(archive) as t:
   for m in t.getmembers():
    assert not m.issym() and not m.islnk() and not m.name.startswith('/') and '..' not in Path(m.name).parts
   # Historical watchdog/receipt names must not overwrite the new guard.
   allowed=('L4-complete-budget','v4-dev','v4-calibration','canada-v4-L5-registration','nerve-attended-bank-v3')
   members=[m for m in t.getmembers() if Path(m.name).parts[0] in allowed]
   for name in {Path(m.name).parts[0] for m in members}:assert not (W/name).exists(),'restore_no_overwrite'
   t.extractall(W,members=members)
os.chdir(S);sys.path[:0]=[str(S/'scripts'),str(S/'src')];os.environ['PYTHONPATH']=str(S/'src')+':'+str(S/'scripts')
import run_scientific_family_b_v4_holdout_replacement as runner
if stage not in ('backup','progress'):runner.check_watchdog(start)
if stage=='restore':
 protocol=runner.read(runner.RESUME);budget=OLD/'L4-complete-budget'
 assert len(list(budget.glob('call-*.json')))==2715
 for name,digest in protocol['prior_claim_sha256'].items():assert sha(budget/name)==digest
 for name in ('v4-dev','v4-calibration'):assert runner.verified_parent(OLD/name)['complete']
 bank=OLD/'nerve-attended-bank-v3';assert sha(bank/'manifest.json')==protocol['sealed_bank_manifest_sha256']
 for name in ('private-seed.json','holdout.json','slice1.json','slice2.json','slice3.json'):assert (bank/name).stat().st_mode&0o777==0
 assert not (bank/'slice1-consumed.json').exists(),'slice_already_consumed'
 write(W/'restore-receipt.json',{'restored_sources':True,'canonical_bank_preserved':True,'parent_hashes_match_offline_verified_journals':True,'physical_claims':2715,'slice1_consumed':False,'holdout_private_modes':0,'new_model_calls':0})
 backup();shutil.copyfile(W/'holdout-replacement-evidence.private.tar.gz',W/'preflight-evidence.private.tar.gz');raise SystemExit
if stage=='bootstrap':
 deadline=time.monotonic()+240
 def left():
  remaining=deadline-time.monotonic()
  if remaining<=0:raise TimeoutError('cached_bootstrap_budget')
  return remaining
 runtime=Path('/workspace/nerve-attended-runtime/ollama-0.40.5.tar.zst');runtime.parent.mkdir(exist_ok=True)
 Path('/workspace/nerve-attended-models').mkdir(exist_ok=True)
 if not runtime.exists():subprocess.run(['curl','--fail','--location','--retry','1','--max-time','180','--output',str(runtime),'https://github.com/ollama/ollama/releases/download/v0.40.5/ollama-linux-amd64.tar.zst'],check=True,timeout=left())
 if not shutil.which('zstd'):
  subprocess.run(['apt-get','update','-qq'],check=True,timeout=left());subprocess.run(['apt-get','install','-y','-qq','zstd'],check=True,timeout=left())
 subprocess.run(['tar','--zstd','-xf',str(runtime),'-C','/usr'],check=True,timeout=left())
 env=dict(os.environ,OLLAMA_HOST='127.0.0.1',OLLAMA_MODELS='/workspace/nerve-attended-models')
 if subprocess.run(['pgrep','-x','ollama'],stdout=subprocess.DEVNULL).returncode:
  with (W/'ollama.log').open('xb') as log:subprocess.Popen(['/usr/bin/ollama','serve'],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env=env)
 for _ in range(30):
  left()
  try:
   assert json.loads(runner.transport.network('/api/version'))=={'version':'0.40.5'};break
  except Exception:time.sleep(1)
 else:raise RuntimeError('runtime_unavailable')
 subprocess.run(['/usr/bin/ollama','pull','qwen2.5-coder:7b'],env=env,stdout=subprocess.DEVNULL,check=True,timeout=left())
 for _ in range(30):
  left()
  try:identity=runner.transport.identity();break
  except Exception:time.sleep(1)
 else:raise RuntimeError('exact_cached_runtime_unavailable')
 write(W/'runtime-identity.json',identity);print(json.dumps(identity));raise SystemExit
if stage=='backup':backup();raise SystemExit
if stage=='progress':
 print(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),'physical_claims':len(list((OLD/'L4-complete-budget').glob('call-*.json'))),'holdout_rows':len(list((W/'v4-holdout').glob('row-*.json'))),'holdout_report':(W/'v4-holdout/aggregate.json').exists(),'slice1_consumed':(OLD/'nerve-attended-bank-v3/slice1-consumed.json').exists()}));raise SystemExit
assert (W/'restore-receipt.json').exists() and win.get('backup_preflight_sha256')==sha(W/'preflight-evidence.private.tar.gz'),'backup_admission_required'
assert runner.transport.identity()==runner.read(W/'runtime-identity.json')
if stage=='register-calibration':result=runner.register(W/'replacement-calibration','calibration',OLD/'nerve-attended-bank-v3',S/'docs/galahad/evidence/family-b-attended-protocol-v3.json',W/'replacement-calibration',OLD/'L4-complete-budget',None,None,win['provider_started_at_utc'],19467.934)
elif stage=='run-calibration':result=runner.run(W/'replacement-calibration')
elif stage=='verify-calibration':result=runner.verify(W/'replacement-calibration')
elif stage=='register-holdout':result=runner.register(W/'v4-holdout','holdout',OLD/'nerve-attended-bank-v3',S/'docs/galahad/evidence/family-b-attended-protocol-v3.json',W/'replacement-calibration',OLD/'L4-complete-budget','src/nerve_awim/memory_gateway/scientific_family_b_v4.py',OLD/'v4-dev',win['provider_started_at_utc'],19467.934)
elif stage=='run-holdout':result=runner.run(W/'v4-holdout')
elif stage=='verify-holdout':result=runner.verify(W/'v4-holdout')
else:raise ValueError('unsupported_stage')
print(json.dumps(result,sort_keys=True,indent=2))
PY
