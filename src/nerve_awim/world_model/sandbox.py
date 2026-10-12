"""Separate-process declarative runner. Arbitrary code mode fails closed.

This is resource containment of a trusted interpreter, NOT an OS security
sandbox for hostile Python. Inputs cannot express files, imports, networking,
subprocesses, loops or expressions. No caller-selectable executable is accepted.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from .compiler import validate_program
from .contracts import canonical, exact, MAX_BYTES


def execute(program, initial, actions, *, wall_seconds=5, memory_mb=256):
    validate_program(program)
    if type(actions) is not list or len(actions) > 100:
        raise ValueError('bounded actions required')
    if type(wall_seconds) is not int or not 1 <= wall_seconds <= 5 or memory_mb != 256:
        raise ValueError('fixed bounded sandbox profile required')
    payload = canonical({'program':program,'initial':initial,'actions':actions}).encode()
    worker = Path(__file__).with_name('worker.py').resolve()
    with tempfile.TemporaryDirectory(prefix='nerve-wm-') as directory:
        # stdout goes to a capped file, avoiding an unbounded communicate buffer.
        with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
            process = subprocess.Popen([sys.executable,'-I',str(worker)],
                stdin=subprocess.PIPE, stdout=output, stderr=errors, cwd=directory,
                env={'PATH':os.defpath,'LANG':'C'},start_new_session=True)
            try:
                process.communicate(payload,timeout=wall_seconds)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait()
                raise TimeoutError('declarative worker wall budget exhausted')
            if process.returncode:
                raise RuntimeError('declarative worker rejected input or resource limit')
            output.seek(0)
            raw = output.read(MAX_BYTES+1)
            if len(raw) > MAX_BYTES:
                raise ValueError('worker output exceeds bound')
            result = json.loads(raw)
            if type(result) is not list or len(result) != len(actions):
                raise ValueError('worker response contract violation')
            for item in result:
                exact(item,('observation','goal','rule_id'))
            return result


def arbitrary_python(*args, **kwargs):
    raise NotImplementedError('arbitrary Python unavailable: no verified OS/container isolation backend')
