import cProfile
import io
import json
from pathlib import Path
import pstats
import sys
import time

root = Path(sys.argv[1])
sys.path[:0] = [str(root / 'src'), str(root)]
from nerve_awim.arc_evaluation import load_dataset, _run
case = next(c for c in load_dataset()['cases'] if c['split'] == 'development')
profiler = cProfile.Profile()
start = time.perf_counter()
profiler.enable()
rows = [_run(case, 'full') for _ in range(5)]
profiler.disable()
elapsed = time.perf_counter() - start
buffer = io.StringIO()
pstats.Stats(profiler, stream=buffer).sort_stats('cumulative').print_stats(20)
print(json.dumps({'root':str(root),'case_id':case['id'],'iterations':5,'elapsed_seconds':elapsed,
 'matched':[r['matched'] for r in rows],'model_calls':0,'profile':buffer.getvalue()},indent=2))
