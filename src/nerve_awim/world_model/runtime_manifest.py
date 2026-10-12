"""Pin the trusted interpreter/evaluator implementation, not just DSL bytes."""
from hashlib import sha256
from pathlib import Path
import sys

FILES=('contracts.py','compiler.py','generalization.py','sandbox.py','worker.py',
       'replay.py','fidelity.py','planner.py','evaluator.py','reflection.py')


def current():
    root=Path(__file__).parent
    return {'python':[sys.version_info.major,sys.version_info.minor],
            'stdlib_only':True,'files':{name:sha256((root/name).read_bytes()).hexdigest() for name in FILES}}
