#!/usr/bin/env python3
"""Prepare immutable family-B retention inputs and verify private evidence offline.
No key creation, signing, registry activation, inference, or network access.
"""
import argparse, ast, base64, hashlib, json, socket, sys, tarfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
BASE=Path('/Users/aliyildirim/nerve-research-runs/family-b-retention-20261016')
FINAL=Path('/Users/aliyildirim/nerve-research-runs/final-holdout-20261016')
PRIOR=Path('/Users/aliyildirim/nerve-research-runs/sweden-20261016')
SKILL='scientific-family-b-measurement-qwen2.5-coder-7b'
MODEL='dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364'
CANDIDATE='src/nerve_awim/memory_gateway/scientific_family_b_v4.py'
CANDIDATE_SHA='764961cf67b04bbdc4ebd1d8dabb7af2380c7de2a42ca064ce5f0799dd323ee9'
ARCHIVES={str(FINAL/'nerve-final-holdout-source.tar.gz'):'bea67b12ecd5b05fe98a5d4b5ee4a84b14f8e0536b1034b27f3e665657ab64b4',str(FINAL/'final-holdout-evidence.private.tar.gz'):'5216c3fe3532e9bbc5f9d79bdae8c0ed234ee448747339c5df63240df0e97d1e',str(PRIOR/'resume-evidence.private.tar.gz'):'d82ff7929f9e174a28d4d2fe93fae8d30e9258a073c9fcd9bd405521883903ff'}
def raw(value):return (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
def sha(value):return hashlib.sha256(value).hexdigest()
def read(path):return json.loads(Path(path).read_bytes())
def require(value):
 if not value:raise ValueError('family_b_evidence_verification_failed')
def write(path,value):
 with path.open('xb') as f:f.write(raw(value))
def source_hashes(frozen,expected):
 require(all(sha((frozen/name).read_bytes())==digest for name,digest in expected.items()))
def prepare():
 for name,digest in ARCHIVES.items():require(sha(Path(name).read_bytes())==digest)
 BASE.mkdir(mode=0o700,exist_ok=True);frozen=BASE/'frozen-source';frozen.mkdir(mode=0o700)
 with tarfile.open(FINAL/'nerve-final-holdout-source.tar.gz') as t:
  for member in t.getmembers():require(not member.issym() and not member.islnk() and not member.name.startswith('/') and '..' not in Path(member.name).parts)
  t.extractall(frozen)
 dest=BASE/'prepared';dest.mkdir(mode=0o700)
 paths={'dev_study':PRIOR/'final-extracted/v4-dev','holdout_study':FINAL/'final-extracted/v4-holdout'}
 regs={k:read(v/'registration.json') for k,v in paths.items()};dr,hr=regs.values()
 require(dr['candidate_module']==hr['candidate_module']==CANDIDATE)
 require(dr['sources'][CANDIDATE]==hr['sources'][CANDIDATE]==CANDIDATE_SHA)
 keys=('seed','max_output_tokens','prompt_token_cap','protocol_sha256','acceptance','arms','bank_manifest_sha256')
 require(all(dr[k]==hr[k] for k in keys))
 require(all(r['identity']['model_digest']==MODEL for r in regs.values()))
 common={k:v for k,v in dr['sources'].items() if k.startswith('src/')}
 require(all(hr['sources'].get(k)==v for k,v in common.items()))
 science={}
 runners=('scripts/run_scientific_family_b_v4_sweden.py','scripts/run_scientific_family_b_v4_final_holdout.py')
 for name in ('prepare','schedule','score','control_raw','control_prepared','aggregate'):
  codes=[]
  for path in runners:
   tree=ast.parse((frozen/path).read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
   codes.append(ast.dump(node,include_attributes=False))
  require(codes[0]==codes[1]);science[name]=sha(codes[0].encode())
 config={k:dr[k] for k in keys};config.update({'skill_id':SKILL,'input_domain':'family-B adapted preparation; raw entities, source IDs, ordering, stale records and qualified measurements preserved','model_digest':MODEL,'model':dr['identity']['model'],'runtime':dr['identity']['runtime'],'common_scientific_sources':common,'scientific_function_ast_sha256':science,'operational_runner_sha256':{p:sha((frozen/p).read_bytes()) for p in runners},'candidate_module':CANDIDATE,'candidate_version':'v4@7B','arm':'candidate','production_authorized':False})
 baseline=dict(config,arm='adapted_v1',candidate_module=None,candidate_version='adapted-v1@7B-bootstrap')
 write(dest/'candidate-config.json',config);write(dest/'baseline-config.json',baseline)
 incumbent={'skill_id':SKILL,'version':'adapted-v1@7B-bootstrap','config_hash':sha(raw(baseline))}
 evidence={}
 for name,path in paths.items():
  regraw=(path/'registration.json').read_bytes();aggraw=(path/'aggregate.json').read_bytes()
  value={'registration':json.loads(regraw),'aggregate':json.loads(aggraw),'registration_bytes_base64':base64.b64encode(regraw).decode(),'aggregate_bytes_base64':base64.b64encode(aggraw).decode(),'candidate_config_sha256':sha(raw(config)),'incumbent_config_sha256':incumbent['config_hash']}
  write(dest/(name+'.json'),value);evidence[name]={'uri':name+'.json','sha256':sha(raw(value))}
 manifest=(FINAL/'final-extracted/bank-metadata/manifest.json').read_bytes();require(sha(manifest)==dr['bank_manifest_sha256'])
 (dest/'task-bank-manifest.json').write_bytes(manifest);evidence['task_bank_manifest']={'uri':'task-bank-manifest.json','sha256':sha(manifest)};evidence['model_digest']=MODEL
 payload={'skill_id':SKILL,'version':'v1','config_hash':sha(raw(config)),'evidence_bundle':evidence,'supersedes':incumbent}
 write(dest/'unsigned-record.json',payload)
 state={'current':{k:payload[k] for k in ('skill_id','version','config_hash')},'records':{'v1':{'status':'retained','record':'skill-v1.json'},incumbent['version']:{'status':'superseded','descriptor':incumbent,'superseded_by':'v1','bootstrap':True}},'runtime_activation':False,'production_authorized':False}
 write(dest/'registry-transition.json',state)
 sources=dict(dr['sources']);sources.update(hr['sources']);source_hashes(frozen,sources)
 metadata={'version':'family-b-retention-preparation-v1','frozen_checkout':str(frozen),'sources':sources,'archives':ARCHIVES,'dev_directory':str(paths['dev_study']),'holdout_directory':str(paths['holdout_study']),'calibration_directory':str(FINAL/'final-extracted/replacement-calibration'),'prior_directory':str(PRIOR/'final-extracted'),'final_directory':str(FINAL/'final-extracted'),'manifest_hash':sha(manifest),'helper_sha256':sha(Path(__file__).read_bytes()),'prepared_files':{p.name:sha(p.read_bytes()) for p in dest.iterdir() if p.is_file()},'authorization':{'authorized_by':'user','instruction':'sign','executed_by':'Codex','signature_type':'delegated-local-ed25519','scope':'family-B skill v1 retaining evaluated v4; original family-A skill unchanged'},'production_authorized':False}
 write(BASE/'preparation.json',metadata)
 print(json.dumps({'prepared':True,'preparation_sha256':sha((BASE/'preparation.json').read_bytes()),'signing_performed':False}))
def verify(metadata):
 for name,digest in metadata['archives'].items():require(sha(Path(name).read_bytes())==digest)
 frozen=Path(metadata['frozen_checkout']);source_hashes(frozen,metadata['sources'])
 sys.path[:0]=[str(frozen/'scripts'),str(frozen/'src')]
 import run_scientific_family_b_v4_final_holdout as runner
 protocol=runner.read(runner.RESUME);prior=Path(metadata['prior_directory']);final=Path(metadata['final_directory'])
 def denied(*args,**kwargs):raise RuntimeError('offline_network_forbidden')
 with patch.object(socket.socket,'connect',denied),patch.object(socket,'create_connection',denied),patch.object(runner.transport,'network',denied):
  dev=runner.verified_parent(prior/'v4-dev');require(dev['complete'] and dev['verdict']=='holdout_eligible')
  require(runner.verified_parent(prior/'v4-calibration')['complete'])
  cal=runner.verify(final/'replacement-calibration');hold=runner.verify(final/'v4-holdout')
 require(cal['complete'] and hold['complete'] and hold['verdict']=='promote_proposal')
 dr=read(prior/'v4-dev/registration.json');hr=read(final/'v4-holdout/registration.json')
 require(hr['prior_aggregate_sha256']==sha((prior/'v4-dev/aggregate.json').read_bytes()))
 require(hr['candidate_module']==dr['candidate_module']==CANDIDATE and hr['sources'][CANDIDATE]==CANDIDATE_SHA)
 require(hr['calibration_registration_sha256']==sha((final/'replacement-calibration/registration.json').read_bytes()))
 budget=final/'L4-complete-budget';claims=sorted(budget.glob('call-*.json'));require([p.name for p in claims]==[f'call-{i:05d}.json' for i in range(2854)])
 for name,digest in protocol['prior_claim_sha256'].items():require(sha((budget/name).read_bytes())==digest)
 counts={}
 for p in claims:
  key=read(p)['registration_sha256'];counts[key]=counts.get(key,0)+1
 require(counts[hold['registration_sha256']]==hold['attempts']==134 and counts[cal['registration_sha256']]==cal['attempts']==5)
 require(sha((final/'bank-metadata/manifest.json').read_bytes())==metadata['manifest_hash'])
 marker=read(final/'bank-metadata/slice1-consumed.json');require(marker['candidate_sha256']==CANDIDATE_SHA and marker['dev_aggregate_sha256']==hr['prior_aggregate_sha256'])
 return {'verified':True,'dev_verdict':dev['verdict'],'holdout_verdict':hold['verdict'],'physical_claims':2854,'model_calls':0}
def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=('prepare','verify'));p.add_argument('--metadata',type=Path,default=BASE/'preparation.json');a=p.parse_args()
 if a.action=='prepare':prepare()
 else:print(json.dumps(verify(read(a.metadata)),sort_keys=True))
if __name__=='__main__':main()
