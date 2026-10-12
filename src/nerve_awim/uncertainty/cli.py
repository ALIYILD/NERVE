"""Scoped local operator commands; no flag grants tenant or reviewer authority."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
import uuid

from . import evaluation


def _default_state():
    return os.environ.get('NERVE_UNCERTAINTY_STATE', str(Path.home()/'.agentic-os/nerve/uncertainty.sqlite3'))


def parser():
    root=argparse.ArgumentParser(description='NERVE persistent uncertainty: local offline operator interface')
    commands=root.add_subparsers(dest='command',required=True)
    for name,description in (
        ('doctor','Inspect offline dependencies and host scope'),('demo','Run a synthetic conflict through the actual local path'),
        ('inspect','Inspect scoped task references and open conflicts'),('verify','Perform a bounded registered offline check'),
        ('resume','Resume a persisted checkpoint without repeating completed checks'),('evaluate','Run paired scripted-provider ablations'),
        ('freeze','Freeze selection code, policy and dataset before sealed evaluation'),('report','Read an existing evaluation receipt')):
        sub=commands.add_parser(name,help=description)
        sub.add_argument('--state',default=_default_state(),help='Local SQLite path; does not change host identity')
        sub.add_argument('--json',action='store_true',help='Emit structured JSON (default)')
        if name=='demo':
            sub.add_argument('--offline',action='store_true',required=True)
            sub.add_argument('--output',default='artifacts/uncertainty-demo')
        elif name=='inspect':sub.add_argument('--task-id',required=True)
        elif name=='verify':
            sub.add_argument('--conflict-id',required=True)
            sub.add_argument('--config',default='configs/uncertainty.offline.json')
        elif name in ('resume','freeze','report'):
            sub.add_argument('--run-id',required=True)
            if name=='report':sub.add_argument('--format',choices=('json',),default='json')
        elif name=='evaluate':
            sub.add_argument('--suite',choices=('paired-conflicts',),default='paired-conflicts')
            sub.add_argument('--split',choices=('selection','sealed-final'),default='selection')
            sub.add_argument('--run-id')
    return root


def _demo_table(engine):
    with engine._db() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS ue_demo_runs(id TEXT PRIMARY KEY,
            tenant TEXT,agent TEXT,task TEXT,receipt TEXT)''')


def _demo_record(engine, actor, run_id):
    _demo_table(engine)
    with engine._db() as con:
        row=con.execute('SELECT * FROM ue_demo_runs WHERE id=? AND tenant=? AND agent=?',
                        (run_id,actor.tenant,actor.agent)).fetchone()
    return dict(row) if row else None


def execute(args):
    command=args.command
    if command=='doctor':
        cases,manifest=evaluation.load_suite()
        return {'status':'offline_ready','tenant_scope':evaluation._tenant(),
            'provider':'scripted-fixture','live_provider_verified':False,'paid_budget_usd':0,
            'cases':len(cases),'default_mode':'shadow','policy':manifest['policy']['version'],
            'source_revision':evaluation.code_revision(),'state':str(Path(args.state).expanduser()),
            'memento_integration':('local world_model adapter available; provider verification not claimed' if (Path(__file__).parent.parent/'world_model').is_dir() and (Path(__file__).parent/'world_model_adapter.py').exists() else 'package or adapter unavailable')},0
    if command=='evaluate':
        return evaluation.evaluate(args.state,split=args.split,run_id=args.run_id),0
    if command=='freeze':return evaluation.freeze(args.state,args.run_id),0
    if command=='report':return evaluation.report(args.state,args.run_id),0
    engine,ledger,actor,operator=evaluation.host(args.state)
    if command=='demo':
        case=next(c for c in evaluation.load_suite('train')[0] if c['labels']['material'] and not c['resolvable'])
        # Unique task identities permit multiple independent demos in one scoped store.
        case=json.loads(json.dumps(case));case['id']='demo-'+uuid.uuid4().hex
        row=evaluation.run_case(case,'D',db_path=args.state)
        run_id='demo-run-'+uuid.uuid4().hex
        receipt={'run_id':run_id,'task_id':case['id'],'conflict_ids':row['conflict_ids'],
            'provider':'scripted-fixture','provider_verified':False,'paid_cost_usd':0,'result':row['result'],
            'verification_calls':row['calls']['verification'],'state':str(args.state),'required':case['required']}
        _demo_table(engine)
        with engine._db() as con:
            con.execute('INSERT INTO ue_demo_runs VALUES(?,?,?,?,?)',(run_id,actor.tenant,actor.agent,case['id'],evaluation.canonical(receipt)))
        output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
        (output/'demo.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
        (output/'conflict-events.json').write_text(json.dumps(ledger.events(actor,case['id']),indent=2,sort_keys=True)+'\n')
        return receipt,0
    if command=='inspect':
        claims=ledger.claims(actor,args.task_id)
        if not claims:raise LookupError('task unavailable in host scope')
        return {'task_id':args.task_id,'tenant_scope':actor.tenant,'revision':ledger.revision(actor,args.task_id),
            'claims':[{'claim_id':c.claim_id,'source_ref':c.source_ref,'source_revision':c.source_revision} for c in claims],
            'conflicts':[c.to_dict() for c in ledger.conflicts(actor,args.task_id)],
            'events':ledger.events(actor,args.task_id)},0
    if command=='resume':
        demo=_demo_record(engine,actor,args.run_id)
        if demo:
            from .propagation import Propagator
            propagator=Propagator(ledger)
            propagator.resume(actor,demo['task'],'checkpoint-D')
            from .policy import Policy
            from .output_guard import OutputGuard
            saved=json.loads(demo['receipt'])
            conclusions=[{key:item[key] for key in ('claim_id','text','dependency_claim_ids')}
                for item in saved['result'].get('supported',[])+saved['result'].get('qualified',[])]
            dependencies=sorted({cid for item in conclusions for cid in item['dependency_claim_ids']})
            policy=Policy(ledger)
            assessment=policy.assess(actor,demo['task'],demo['task']+'-decision','answer',dependencies,
                required=saved.get('required',True))
            result=OutputGuard(ledger,policy).render(actor,demo['task'],conclusions,[assessment])
            return {'run_id':args.run_id,'task_id':demo['task'],'envelope':propagator.envelope(actor,demo['task']),
                    'repeated_calls':0,'result':result},0
        return evaluation.resume(args.state,args.run_id),0
    if command=='verify':
        from .verification import Verifier,ToolSpec
        config=json.loads(Path(args.config).read_text())
        expected={'mode','paid_budget_usd','checks_per_conflict','checks_per_task','call_timeout_seconds','task_timeout_seconds','provider','policy'}
        if type(config) is not dict or set(config)!=expected or config['mode']!='offline' or config['paid_budget_usd']!=0 or config['provider']!='scripted-fixture' or config['policy']!='uncertainty-pilot-v1':
            raise PermissionError('only the reviewed zero-cost offline configuration is supported')
        conflict=ledger.get_conflict(actor,args.conflict_id)
        # The CLI has no authenticated external source. An attempted check cannot
        # fabricate a primary record or count as factual resolution.
        tool=ToolSpec(lambda request:{'evidence_refs':[],'outcome':'inconclusive'},
            lambda request:request=={'conflict_id':args.conflict_id},(conflict.kind,))
        verifier=Verifier(ledger,tools={'offline-primary-read':tool},max_conflict=config['checks_per_conflict'],
            max_task=config['checks_per_task'],call_seconds=config['call_timeout_seconds'],task_seconds=config['task_timeout_seconds'])
        result=verifier.check(actor,args.conflict_id,'offline-primary-read',{'conflict_id':args.conflict_id})
        code={'resolved':0,'unresolved_budget':5,'verifier_unavailable':6}.get(result['boundary'],4)
        return result,code
    raise ValueError('unknown command')


def main(argv=None):
    args=parser().parse_args(argv)
    try:
        result,code=execute(args)
    except PermissionError as exc:result,code={'error':str(exc)},3
    except LookupError as exc:result,code={'error':str(exc)},6
    except (ImportError,ModuleNotFoundError,FileNotFoundError) as exc:result,code={'error':type(exc).__name__,'detail':'required local dependency or file unavailable'},6
    except (ValueError,TypeError) as exc:
        message=str(exc)
        code=8 if any(s in message for s in ('integrity','hash mismatch')) else 7 if any(s in message for s in ('changed','revision','consumed','concurrency')) else 2
        result={'error':message}
    except (sqlite3.OperationalError,RuntimeError) as exc:
        message=str(exc)
        result,code={'error':message},7 if any(s in message for s in ('locked','revision','changed')) else 6
    print(json.dumps(result,sort_keys=True,allow_nan=False))
    return code


if __name__=='__main__':
    sys.exit(main())
