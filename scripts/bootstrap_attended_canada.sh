#!/bin/bash
set -euo pipefail
umask 077
mkdir -p /workspace/nerve-attended-runtime /workspace/nerve-attended-models
apt-get update -qq
apt-get install -y -qq zstd
if [ ! -f /workspace/nerve-attended-runtime/ollama-0.40.5.tar.zst ]; then
  curl --fail --location --retry 2 --max-time 1200 --output /workspace/nerve-attended-runtime/ollama-0.40.5.tar.zst https://github.com/ollama/ollama/releases/download/v0.40.5/ollama-linux-amd64.tar.zst
fi
tar --zstd -xf /workspace/nerve-attended-runtime/ollama-0.40.5.tar.zst -C /usr
if ! pgrep -x ollama >/dev/null; then
nohup env OLLAMA_HOST=127.0.0.1 OLLAMA_MODELS=/workspace/nerve-attended-models /usr/bin/ollama serve > /workspace/nerve-attended-runtime/server.log 2>&1 < /dev/null &
echo $! > /workspace/nerve-attended-runtime/server.pid
fi
python3 - <<'PY'
import time,urllib.request,json
for i in range(30):
 try:
  v=json.load(urllib.request.urlopen('http://127.0.0.1:11434/api/version',timeout=10))
  assert v=={'version':'0.40.5'},v
  print(v,flush=True);break
 except (ConnectionError,TimeoutError):time.sleep(1)
 except urllib.error.URLError:time.sleep(1)
else:raise SystemExit('runtime_not_ready')
PY
OLLAMA_HOST=127.0.0.1 /usr/bin/ollama pull qwen2.5-coder:7b > /workspace/nerve-attended-runtime/model-pull.log 2>&1
python3 - <<'PY'
import json,urllib.request,os,subprocess
m=next(m for m in json.load(urllib.request.urlopen('http://127.0.0.1:11434/api/tags'))['models'] if m['name']=='qwen2.5-coder:7b')
assert m['digest']=='dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364',m['digest']
from pathlib import Path
provider=dict(x.split('=',1) for x in Path('/proc/1/environ').read_bytes().decode().split('\0') if '=' in x)
os.environ['RUNPOD_POD_ID']=provider['RUNPOD_POD_ID']
assert os.environ['RUNPOD_POD_ID']=='b7qj6qyx9ij6gg'
gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name','--format=csv,noheader'],text=True).strip();assert gpu in ('A40','NVIDIA A40')
r={'pod_id':os.environ['RUNPOD_POD_ID'],'gpu':gpu,'model':m['name'],'digest':m['digest'],'runtime':'0.40.5','model_calls':0}
with open('/workspace/nerve-attended-runtime/identity.json','x') as f:json.dump(r,f,indent=2)
print(json.dumps(r),flush=True)
PY
