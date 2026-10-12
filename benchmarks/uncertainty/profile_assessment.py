"""Development-only assessment latency diagnostic; never a release gate."""
import argparse
import json
from pathlib import Path
import statistics
import tempfile
import time

from nerve_awim.arc_workflows import build_workflow_engine
from nerve_awim.uncertainty.contracts import Claim
from nerve_awim.uncertainty.ledger import Ledger
from nerve_awim.uncertainty.policy import Policy


def measure(repeats=7, decisions=30):
    if type(repeats) is not int or not 3 <= repeats <= 50:
        raise ValueError('3 to 50 repetitions required')
    if type(decisions) is not int or not 1 <= decisions <= 1000:
        raise ValueError('1 to 1000 decisions required')
    durations=[]
    for _ in range(repeats):
        with tempfile.TemporaryDirectory() as temporary:
            host=build_workflow_engine(Path(temporary)/'state.sqlite3')
            actor=host['actor']; ledger=Ledger(host['engine']); policy=Policy(ledger)
            source=ledger.register_source(actor,'source',{'value':True})
            ledger.add_claim(actor,Claim('claim',actor.tenant,'task','subject','ready',True,**source))
            start=time.perf_counter()
            for index in range(decisions):
                result=policy.assess(actor,'task',f'decision-{index}','inventory',['claim'],required=True)
                if result.status!='proceed': raise RuntimeError('diagnostic prerequisite unexpectedly denied')
            durations.append(time.perf_counter()-start)
    return {'evidence_type':'local sequential development microbenchmark; no promotion evidence',
            'decisions_per_repetition':decisions,'repetitions':repeats,
            'elapsed_seconds':durations,'median_seconds':statistics.median(durations),
            'median_ms_per_assessment':1000*statistics.median(durations)/decisions,
            'setup_included':False,'database_per_repetition':'fresh disposable SQLite',
            'provider_requests':0,'paid_cost_usd':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats',type=int,default=7)
    parser.add_argument('--decisions',type=int,default=30)
    args=parser.parse_args()
    print(json.dumps(measure(args.repeats,args.decisions),indent=2))
