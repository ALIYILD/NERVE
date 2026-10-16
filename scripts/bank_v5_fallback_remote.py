"""One remote-only Ollama request, or identity/bootstrap. No study data selection."""
import json, os, platform, subprocess, sys, time, urllib.request
from pathlib import Path
POD='lvojhtouu5gede'
DIGEST='dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364'
provider=dict(x.split('=',1) for x in Path('/proc/1/environ').read_text().split('\0') if '=' in x)
assert platform.system()=='Linux' and provider.get('RUNPOD_POD_ID')==POD
def network(path,body=None,timeout=30):
    request=urllib.request.Request('http://127.0.0.1:11434'+path,data=body,headers={'Content-Type':'application/json'})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request,timeout=timeout) as r:
        data=r.read(1000001)
    assert len(data)<=1000000
    return data.decode()
if sys.argv[1]=='bootstrap':
    subprocess.run(['tar','--zstd','-xf','/workspace/nerve-attended-runtime/ollama-0.40.5.tar.zst','-C','/usr'],check=True,timeout=120)
    env=dict(os.environ,OLLAMA_HOST='127.0.0.1',OLLAMA_MODELS='/workspace/nerve-attended-models')
    with open('/workspace/v5-ollama.log','xb') as log:
        subprocess.Popen(['/usr/bin/ollama','serve'],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
    for _ in range(30):
        try: network('/api/version');break
        except Exception:time.sleep(1)
    else:raise RuntimeError('runtime_not_ready')
if sys.argv[1] in ('identity','bootstrap'):
    runtime=json.loads(network('/api/version'))
    model=next(x for x in json.loads(network('/api/tags'))['models'] if x['name']=='qwen2.5-coder:7b')
    gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name','--format=csv,noheader'],text=True).strip()
    assert runtime=={'version':'0.40.5'} and model['digest']==DIGEST and gpu in ('A40','NVIDIA A40')
    print(json.dumps(dict(pod_id=POD,gpu=gpu,runtime=runtime,model=model['name'],model_digest=model['digest'])))
elif sys.argv[1]=='call':
    data=json.load(sys.stdin); start=time.monotonic()
    try:
        wire=network('/v1/chat/completions',data['body'].encode(),data['timeout'])
        print(json.dumps(dict(status='ok',wire=wire,elapsed_seconds=time.monotonic()-start)))
    except TimeoutError:
        print(json.dumps(dict(status='timeout',elapsed_seconds=time.monotonic()-start)))
else:raise ValueError('action')
