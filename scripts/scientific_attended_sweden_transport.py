"""Pinned replacement-pod transport; historical gate module stays unchanged."""
import json
import os
import platform
from pathlib import Path
import subprocess
import urllib.request
import run_scientific_runpod_gate as original

WINDOW=Path('/workspace/resume-window.json')
def pod_id():
    window=json.loads(WINDOW.read_text())
    if window.get('region')!='EU-SE-1' or window.get('hourly_usd')!=0.59:raise ValueError('registered_host_class_changed')
    pod=window['pod_id']
    if not isinstance(pod,str) or not pod.isalnum():raise ValueError('invalid_pod_id')
    provider=dict(x.split('=',1) for x in Path('/proc/1/environ').read_bytes().decode().split('\0') if '=' in x)
    if provider.get('RUNPOD_POD_ID')!=pod:raise ValueError('provider_identity_changed')
    return pod
MODEL=original.MODEL
DIGEST=original.DIGEST
ORIGIN='http://127.0.0.1:11434'
canonical=original.canonical
read=original.read
write=original.write
digest=original.digest
decode=original.decode
wilson=original.wilson

def network(path,body=None,timeout=30):
    if platform.system()!='Linux' or os.environ.get('RUNPOD_POD_ID')!=pod_id():
        raise RuntimeError('inference_requires_registered_runpod')
    req=urllib.request.Request(ORIGIN+path,data=body,headers={'Content-Type':'application/json'})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=timeout) as response:
        raw=response.read(1000001)
    if len(raw)>1000000:raise ValueError('oversize_response')
    return raw

def identity():
    m=next(m for m in json.loads(network('/api/tags'))['models'] if m['name']==MODEL)
    if m['digest']!=DIGEST:raise ValueError('model_changed')
    runtime=json.loads(network('/api/version'))
    if runtime!={'version':'0.40.5'}:raise ValueError('runtime_changed')
    gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name','--format=csv,noheader'],text=True).strip()
    if gpu not in ('NVIDIA A40','A40'):raise ValueError('gpu_changed')
    return {'pod_id':pod_id(),'gpu':gpu,'model':MODEL,'model_digest':DIGEST,'runtime':runtime}
