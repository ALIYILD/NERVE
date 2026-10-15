"""Fixed interpreter entry point; invoked with -I and without inherited secrets."""
import json
from pathlib import Path
import resource
import sys

resource.setrlimit(resource.RLIMIT_CPU, (3,3))
resource.setrlimit(resource.RLIMIT_FSIZE, (1048576,1048576))
resource.setrlimit(resource.RLIMIT_NOFILE, (32,32))
# RLIMIT_AS is not enforced reliably by macOS; advertise that limitation in doctor.
if sys.platform != 'darwin':
    resource.setrlimit(resource.RLIMIT_AS, (256*1024*1024,256*1024*1024))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from nerve_awim.world_model.compiler import Simulator
from nerve_awim.world_model.contracts import canonical, exact

request = json.loads(sys.stdin.buffer.read(1048577))
exact(request,('program','initial','actions'))
if type(request['actions']) is not list or len(request['actions']) > 100:
    raise ValueError('bounded action sequence required')
sim = Simulator(request['program'])
state = sim.initialise(request['initial'])
result = []
for action in request['actions']:
    state = sim.step(state,action)
    result.append(state)
sys.stdout.write(canonical(result))
