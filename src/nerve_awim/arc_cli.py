"""ARC subcommands for the existing Agent OS bridge; local synthetic scope only."""
import json
from pathlib import Path
from .arc_contracts import SCHEMA
from .arc_operations import ArcOperations
from .arc_workflows import build_workflow_engine, run_workflow
from .skill_model import _object, _nonfinite


def read_task(path):
    data=Path(path).read_bytes()
    if len(data)>65536: raise ValueError('task exceeds 64KiB limit')
    value=json.loads(data,object_pairs_hook=_object,parse_constant=_nonfinite)
    if type(value) is not dict: raise ValueError('task must be a JSON object')
    return value


def dispatch(args):
    database=args.state/'learning.sqlite3'
    if args.command=='arc-evaluate':
        from .arc_evaluation import run_benchmark
        return run_benchmark(database,report_path=args.report)
    if args.command=='arc-improve':
        from .arc_evaluation import run_candidates
        return run_candidates(database,max_candidates=args.candidate_budget)
    if args.command=='arc-candidate-status':
        from .arc_evaluation import evaluation_status
        return evaluation_status(database)
    if args.command=='arc-run':
        if args.task is not None:
            scenario=read_task(args.task)
        elif args.source is not None:
            source=args.source.read_bytes()
            if len(source)>12000: raise ValueError('source exceeds local inventory input limit')
            scenario={'workflow':'inventory','source':source.decode(),'task_id':args.task_id or 'local-inventory'}
        else:
            raise ValueError('arc-run requires --task or --source')
        if scenario.get('tenant','synthetic')!='synthetic':
            raise PermissionError('CLI only issues the local synthetic tenant capability')
        if args.task_id: scenario['task_id']=args.task_id
        if args.restart: scenario['restart']=True
        return run_workflow(database,scenario,mode='full')
    components=build_workflow_engine(database,tenant='synthetic',mode='full')
    runtime,engine,operator=(components[k] for k in ('runtime','engine','operator'))
    # Administrative inspection/staging never opts a previously unused context in.
    # arc-run is the explicit opt-in to the bounded local synthetic workflow.
    runtime.mode='off'
    operations=ArcOperations(runtime)
    if args.command=='arc-inspect':
        return {'episodes':operations.inspect(operator,task_id=args.task_id,decision_id=args.decision_id),
                'metrics':operations.metrics(operator)}
    if args.command=='arc-replay':
        if not args.decision_id: raise ValueError('arc-replay requires --decision-id')
        return operations.replay(operator,args.decision_id)
    if args.command=='arc-reconcile':
        if not args.decision_id or not args.review_ref or not args.observed_status:
            raise ValueError('reconcile requires --decision-id, --observed-status and --review-ref')
        return {'status':runtime.reconcile(operator,args.decision_id,
                observed_status=args.observed_status,review_ref=args.review_ref)}
    if args.command=='arc-release-status':
        return operations.status(operator)
    if args.command=='arc-stage':
        proposer=engine.authority.issue('synthetic','arc-workflow','evaluator')
        ident=operations.stage(proposer,context=args.context,mode=args.arc_mode,canary_limit=args.canary_limit,
            versions={'schema':SCHEMA,'prompt':'arc-v1','model':'deterministic-v1',
                      'policy':engine.contract,'strategy':'registered-workflows-v1'})
        return {'manifest_id':ident,'status':'staged','production_activation':False}
    if args.command in ('arc-promote','arc-rollback'):
        if not args.manifest_id or not args.review_ref:
            raise ValueError('manifest ID and explicit review reference required')
        ident=args.manifest_id
        if ident=='latest':
            wanted='staged' if args.command=='arc-promote' else 'active'
            choices=[r['id'] for r in operations.status(operator)['manifests'] if r['status']==wanted]
            if not choices: raise ValueError('no matching manifest')
            ident=choices[-1]
        method=operations.promote if args.command=='arc-promote' else operations.rollback
        return method(operator,ident,review=args.review_ref)
    raise ValueError('unknown ARC command')
