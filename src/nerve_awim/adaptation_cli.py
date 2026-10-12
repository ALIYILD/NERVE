"""Local synthetic adaptation commands in the existing Agent OS bridge."""
from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile
from .adaptation import AdaptationConfig
from .adaptation_replay import build, start, step, episode, benchmark, load_suite
from .arc_cli import read_task

ROOT=Path(__file__).resolve().parents[2]


def dispatch(args):
    command=args.command
    if command=='adaptation-validate-config':
        if args.config is None: raise ValueError('--config required')
        return {'valid':True,'configuration':asdict(AdaptationConfig(**read_task(args.config)))}
    if command=='adaptation-inspect':
        result={'schema':'adaptation-v1','production_default':'off','entrypoint':'scripts/agentos_bridge.py','runtime':'nerve_awim.arc_execution.ArcRuntime','store':'GovernedLearning SQLite','research_optional':True,'provider_spend_usd':0,'scope':'host-issued task capability','documentation':'docs/adaptation/runbook.md'}
        if args.output:
            args.output.mkdir(parents=True,exist_ok=True)
            (args.output/'inspection.json').write_text(json.dumps(result,indent=2)+'\n')
        return result
    if command in ('adaptation-replay','adaptation-evaluate'):
        if args.suite is None: raise ValueError('--suite required')
        if command=='adaptation-evaluate':
            from .adaptation_evaluation import evaluate_candidate
            if not args.candidate: raise ValueError('--candidate required')
            result=evaluate_candidate(args.state/'adaptation-evaluation.sqlite3',candidate=args.candidate,suite=args.suite,split=args.split)
        else:
            if args.split!='development': raise PermissionError('heldout requires frozen candidate evaluation')
            result=benchmark(args.suite,mode=args.adaptation_mode,split=args.split)
    elif command=='adaptation-run':
        from .adaptation_repository import run_repository
        root=ROOT if args.repository is None else args.repository
        database=args.state/'repository-adaptation.sqlite3'
        database.parent.mkdir(parents=True,exist_ok=True)
        paths=[str(args.source)] if args.source else None
        if args.scenario not in (None,'recover-regex'): raise ValueError('repository scenario must be recover-regex or omitted')
        result=run_repository(str(database),root,paths=paths,mode=args.adaptation_mode,restart=args.restart,task_id=args.task_id,initial_tool='regex-inventory' if args.scenario=='recover-regex' else 'ast-inventory')
    elif command=='adaptation-demo':
        if not args.synthetic: raise PermissionError('explicit --synthetic required')
        scenario=args.scenario or 'resume'
        database=args.state/'adaptation.sqlite3'; database.parent.mkdir(parents=True,exist_ok=True)
        if scenario in ('heading','tool-outage','contradiction','resume','injection','isolation'):
            result=episode(str(database),{'id':args.task_id or 'demo-'+scenario,'family':scenario,'heading':'verified-demo','template':'synthetic-section'},mode=args.adaptation_mode)
        elif scenario in ('budget','kill-switch'):
            c=build(str(database)); task=start(c,args.task_id or 'demo-'+scenario); parent=None
            if scenario=='kill-switch':
                step(c,task,'verified-demo'); c['adaptation'].kill_switch(c['operator'],reason='synthetic-kill-demonstration')
            else:
                for n in range(4): parent=step(c,task,'wrong',section=str(n),parent=parent)[0].decision_id
            try: step(c,task,'verified-demo',section='final',parent=parent)
            except RuntimeError:
                result={'scenario':scenario,'stopped':True,'state':c['adaptation'].inspect(c['actor'],task)}
            else: raise AssertionError('expected bounded termination')
        else: raise ValueError('unknown demo scenario')
    elif command in ('adaptation-status','adaptation-reset','adaptation-kill'):
        if not args.synthetic: raise PermissionError('CLI can reauthenticate only explicitly synthetic scope')
        c=build(str(args.state/'adaptation.sqlite3')); a=c['adaptation']; operator=c['operator']
        if command=='adaptation-kill':
            if not args.reason: raise ValueError('--reason required')
            a.kill_switch(operator,reason=args.reason); return {'killed':True,'production_activation':False}
        if not args.task_id: raise ValueError('--task-id required')
        a.grant(operator,args.task_id,operator,subject_scope='subject-a',review_reference='local-synthetic-cli')
        if command=='adaptation-reset':
            if not args.reason: raise ValueError('--reason required')
            a.reset(operator,args.task_id,reason=args.reason)
        result=a.inspect(operator,args.task_id)
    elif command in ('research-fast-memory-train','research-fast-memory-evaluate'):
        if not args.synthetic or not args.budget: raise PermissionError('research requires --synthetic and --budget')
        # Import optional numerical dependencies only after explicit opt-in.
        sys.path.insert(0,str(ROOT))
        from research.fast_weight_memory.experiment import train,evaluate
        budget=read_task(args.budget)
        if command.endswith('-train'):
            if not args.config: raise ValueError('--config required')
            result=train(read_task(args.config),budget)
        else:
            if not args.checkpoint or not args.suite: raise ValueError('--checkpoint and --suite required')
            result=evaluate(read_task(args.checkpoint),read_task(args.suite),budget)
    else: raise ValueError('unknown adaptation command')
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return result
