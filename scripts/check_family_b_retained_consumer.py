#!/usr/bin/env python3
"""Fresh-process, CPU-only consumer proof against actual signed artifacts.
Never signs, edits a registry, activates production, or invokes inference.
Negative cases operate on in-memory inputs or isolated registry copies.
"""
import argparse
from contextlib import ExitStack
import socket
import urllib.request
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
CASES=('actual','unsigned','tampered_config','wrong_model','wrong_manifest','tampered_registry','source_drift')

def load_adapter(path):
 spec=importlib.util.spec_from_file_location('family_b_actual_adapter',path)
 adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
 return adapter

def _check_case(adapter_path,registry,case):
 sys.path.insert(0,str(ROOT/'src'))
 from nerve_awim.retained_skill_contract import select_retained_skill
 adapter=load_adapter(adapter_path)
 if case=='tampered_registry':
  with tempfile.TemporaryDirectory(prefix='nerve-consumer-registry-') as tmp:
   copied=Path(tmp)/'registry';shutil.copytree(registry,copied)
   state=json.loads((copied/'registry.json').read_bytes());state['runtime_activation']=True
   (copied/'registry.json').write_text(json.dumps(state))
   try: inputs=adapter.load_selection_inputs(copied)
   except Exception:
    return {'case':case,'retained_skill_selected':False,'production_authorized':False,'rejected_at_loader':True}
   return {'case':case,**select_retained_skill(**inputs)}
 inputs=adapter.load_selection_inputs(registry)
 if case=='unsigned':inputs['record']=copy.deepcopy(inputs['record']);inputs['record']['signed_by']={}
 if case=='tampered_config':inputs['config_bytes']+=b'\nTAMPER'
 if case=='wrong_model':inputs['model_digest']='0'*64
 if case=='wrong_manifest':inputs['manifest_hash']='0'*64
 if case=='source_drift':
  original=Path.read_bytes;changed=[]
  def drift(path):
   raw=original(path)
   if path.suffix=='.py' and ('src' in path.parts or 'scripts' in path.parts):
    changed.append(str(path));return raw+b'\n# simulated source drift for negative consumer check\n'
   return raw
  with patch.object(Path,'read_bytes',drift):result=select_retained_skill(**inputs)
  if not changed:raise RuntimeError('source drift case did not exercise source verification')
  return {'case':case,'simulated_source_reads_changed':len(changed),**result}
 return {'case':case,**select_retained_skill(**inputs)}

def check_case(adapter_path,registry,case):
 def denied(*args,**kwargs):
  raise RuntimeError('network denied during retained consumer proof')
 with ExitStack() as stack:
  for owner,name in ((socket.socket,'connect'),(socket.socket,'connect_ex'),
                     (socket,'create_connection'),(urllib.request,'urlopen'),
                     (urllib.request.OpenerDirector,'open')):
   stack.enter_context(patch.object(owner,name,denied))
  result=_check_case(adapter_path,registry,case)
  result['network_denied']=True
  return result

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--adapter',type=Path,required=True);ap.add_argument('--registry',type=Path,required=True);ap.add_argument('--output',type=Path);ap.add_argument('--case',choices=CASES);a=ap.parse_args()
 if a.case:
  result=check_case(a.adapter.resolve(),a.registry.resolve(),a.case)
  if result['retained_skill_selected']!=(a.case=='actual') or result['production_authorized'] is not False:raise RuntimeError('consumer expectation failed')
  print(json.dumps(result,sort_keys=True));return
 if not a.output:raise SystemExit('--output required for proof suite')
 if a.output.exists():raise SystemExit('proof output already exists')
 before={str(p.relative_to(a.registry)):hashlib.sha256(p.read_bytes()).hexdigest() for p in a.registry.rglob('*') if p.is_file()}
 results=[]
 for case in CASES:
  child=subprocess.run([sys.executable,'-I',str(Path(__file__).resolve()),'--adapter',str(a.adapter.resolve()),'--registry',str(a.registry.resolve()),'--case',case],capture_output=True,text=True,timeout=180)
  if child.returncode:raise RuntimeError('consumer child failed: '+case)
  results.append(json.loads(child.stdout))
 after={str(p.relative_to(a.registry)):hashlib.sha256(p.read_bytes()).hexdigest() for p in a.registry.rglob('*') if p.is_file()}
 if before!=after:raise RuntimeError('actual registry changed during proof')
 receipt={'version':'family-b-real-retained-consumer-proof-v1','results':results,'fresh_process_per_case':True,'network_denied_in_each_child':True,'canonical_replay_network_denial':'enforced separately by trusted adapter','actual_registry_unchanged':True,'registry_file_sha256':before,'adapter_sha256':hashlib.sha256(a.adapter.read_bytes()).hexdigest(),'consumer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'model_calls':0,'production_authorized':False}
 a.output.parent.mkdir(parents=True,exist_ok=True)
 with a.output.open('x') as f:json.dump(receipt,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps({'checks':len(results),'passed':len(results),'output':str(a.output),'model_calls':0,'production_authorized':False}))
if __name__=='__main__':main()
