#!/usr/bin/env python3
"""Kill a CPU worker after a durable checkpoint; compare resumed and clean receipts."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from nerve_awim.loop import Loop, canonical, digest


def main():
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--worker',action='store_true');a=p.parse_args()
    root=Path(a.directory);root.mkdir(parents=True,exist_ok=True)
    if a.worker:
        loop=Loop('scientific',root/'interrupted')
        loop.adapt(loop.domain.stream(),stop_after=611)
        (root/'checkpoint-ready').write_text('611\n')
        while True:time.sleep(1)
    worker=subprocess.Popen([sys.executable,__file__,str(root),'--worker'])
    try:
        deadline=time.monotonic()+120
        while not (root/'checkpoint-ready').exists():
            if worker.poll() is not None:raise RuntimeError('worker failed before checkpoint')
            if time.monotonic()>deadline:raise TimeoutError('checkpoint deadline')
            time.sleep(.05)
        os.kill(worker.pid,signal.SIGKILL);code=worker.wait(timeout=10)
        resumed=Loop('scientific',root/'interrupted');got=resumed.adapt(resumed.domain.stream());resumed.close()
        clean=Loop('scientific',root/'clean');expected=clean.adapt(clean.domain.stream());clean.close()
        if got!=expected:raise ValueError('restart receipts diverged')
        proof={'worker_returncode':code,'signal':'SIGKILL','checkpoint_items':611,'total_items':1200,
               'unique_items':len({r['index'] for r in got['receipts']}),'resumed_sha256':digest(got),
               'clean_sha256':digest(expected),'equal':True,'model_calls':0,
               'boundary':'CPU recorded outcomes only; not exactly-once remote inference'}
        (root/'restart-proof.json').write_text(canonical(proof)+'\n');print(canonical(proof))
    finally:
        if worker.poll() is None:worker.kill();worker.wait()

if __name__=='__main__':main()
