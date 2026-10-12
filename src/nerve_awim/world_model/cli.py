"""Local synthetic research CLI. OS user owns the DB; no remote auth implied."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
from .contracts import (Policy,canonical,exact,IntegrityError,BudgetExhausted,StaleWorker)
from .ledger import Ledger,migrate
from .coordinator import Coordinator
from .registry import Registry
from .evaluator import Evaluator
from .replay import replay
from .demo import run_demo
from ..governed_learning_v20 import LearningAuthority


def read_json(path):
    raw = Path(path).read_bytes()
    if len(raw) > 1048576:
        raise ValueError('input size limit')
    def unique(pairs):
        result = {}
        for key,value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    value = json.loads(raw,object_pairs_hook=unique)
    canonical(value)
    return value


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',default='.world-model/offline.sqlite3')
    p.add_argument('--scope',choices=['offline-demo'],default='offline-demo',
                   help='fixed local synthetic scope; cannot select another tenant')
    sub = p.add_subparsers(dest='command',required=True)
    for name in ('doctor','init','demo','study','repository-study','ingest','run','status','resume','verify','evaluate','freeze','shadow','report',
                 'authorize-canary','promote','rollback','stop'):
        s = sub.add_parser(name)
        s.add_argument('--json',action='store_true')
        s.add_argument('--dry-run',action='store_true')
        if name in ('init','run','resume'):
            s.add_argument('--config',default='configs/world_model.offline.json')
        if name == 'repository-study':
            s.add_argument('--directory',required=True)
            s.add_argument('--repository',required=True)
        if name == 'study':
            s.add_argument('--directory',required=True)
            s.add_argument('--final-per-family',type=int,default=80)
            s.add_argument('--final-seed',type=int,default=9001)
        if name == 'run':
            s.add_argument('--mode',choices=['offline'],default='offline')
        if name in ('status','resume','report','stop'):
            s.add_argument('--run-id',required=True)
        if name == 'report':
            s.add_argument('--format',choices=['json'],default='json')
        if name in ('verify','evaluate','freeze','shadow','authorize-canary','promote','rollback'):
            s.add_argument('--model-id',required=True)
        if name == 'verify':
            s.add_argument('--suite',choices=['replay'],default='replay')
        if name == 'evaluate':
            s.add_argument('--suite',choices=['selection','regression','sealed-final'],required=True)
            s.add_argument('--run-id')
        if name in ('ingest','shadow'):
            s.add_argument('--manifest',required=True)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    error_message = None
    try:
        if args.command in ('authorize-canary','promote','rollback','stop'):
            raise PermissionError('operator endpoints unavailable; CLI cannot issue deployment authority')
        if args.command == 'doctor':
            result = {'mode':'offline','enabled_by_default':False,
                      'scope':'local synthetic only','arbitrary_python':'unavailable',
                      'backend':'trusted-declarative-process-v1',
                      'languages':['declarative-exact-v1','declarative-frame-v1'],
                      'memory_limit_enforced':sys.platform != 'darwin',
                      'provider':'unavailable','deployment_authorized':False}
        elif args.dry_run:
            result = {'dry_run':True,'operation':args.command,'mutations':0}
        elif args.command == 'repository-study':
            from .repository_study import run_repository_study
            result = run_repository_study(args.repository,args.directory)
        elif args.command == 'study':
            from .study import run_study
            result = run_study(args.directory,final_per_family=args.final_per_family,final_seed=args.final_seed)
        elif args.command in ('init','demo'):
            path = Path(args.db)
            path.parent.mkdir(parents=True,exist_ok=True)
            if args.command == 'demo':
                result = run_demo(path)
            else:
                policy = Policy.load(read_json(args.config))
                migrate(path)
                result = {'initialized':True,'enabled':policy.enabled,'db':str(path)}
        else:
            if not Path(args.db).is_file():
                raise ValueError('init required before opening the research store')
            authority = LearningAuthority()
            trainer = authority.issue('offline','demo','trainer')
            evaluator = authority.issue('offline','demo','evaluator')
            ledger = Ledger(args.db,authority)
            registry = Registry(ledger)
            if args.command == 'ingest':
                manifest = read_json(args.manifest)
                exact(manifest,('schema_version','episodes'))
                if manifest['schema_version'] != 1 or type(manifest['episodes']) is not list or len(manifest['episodes']) > 100:
                    raise ValueError('bounded v1 episode manifest required')
                # Import is retrospective, never presented as foresight. Only training
                # ingestion is exposed; sealed sets belong to the trusted evaluator.
                with ledger.db():
                    for ep in manifest['episodes']:
                        exact(ep,('episode','source','family','initial','transitions'))
                        if type(ep['transitions']) is not list or len(ep['transitions']) > 100:
                            raise ValueError('bounded transitions required')
                        ledger.episode(trainer,**{k:ep[k] for k in ('episode','source','family','initial')},split='train')
                        previous = ep['initial']
                        for i,row in enumerate(ep['transitions']):
                            exact(row,('id','action','outcome','completion'))
                            ledger.reserve(trainer,transition_id=row['id'],episode=ep['episode'],sequence=i,
                                           action=row['action'],previous=previous,prediction=None)
                            ledger.complete(trainer,row['id'],outcome=row['outcome'],completion=row['completion'])
                            previous = row['outcome']
                result = {'ingested':len(manifest['episodes']),'prediction_provenance':'retrospective import; no foresight claim'}
            elif args.command in ('run','resume','status','report'):
                if args.command in ('run','resume'):
                    policy = Policy.load(read_json(args.config))
                else:
                    with ledger.db() as db:
                        row = db.execute('SELECT body FROM wm_runs WHERE scope=? AND id=?',
                                         (ledger.scope(trainer,'trainer'),args.run_id)).fetchone()
                    if row is None:
                        raise LookupError('run not found')
                    policy = Policy.load(json.loads(row['body'])['policy'])
                service = Coordinator(ledger,trainer=trainer,evaluator=evaluator,policy=policy)
                run_id = service.create() if args.command == 'run' else args.run_id
                result = service.resume(run_id) if args.command in ('run','resume') else service.status(run_id)
            elif args.command == 'verify':
                model = registry.get(evaluator,args.model_id)
                result = replay(model['program'],ledger.episodes(trainer))
                if not result['replay_pass']:
                    print(canonical(result))
                    return 4
            elif args.command == 'freeze':
                result = {'model_id':registry.freeze(evaluator,args.model_id),'deployment_authorized':False}
            elif args.command == 'evaluate':
                result = Evaluator(ledger).evaluate(evaluator,args.model_id,
                    'final' if args.suite == 'sealed-final' else args.suite,run_id=args.run_id)
                if not result['replay_pass']:
                    print(canonical(result))
                    return 4
            elif args.command == 'shadow':
                from .adapters import shadow
                exact(read_json(args.manifest),('recommended_action',))
                recommendation = read_json(args.manifest)['recommended_action']
                model = registry.get(evaluator,args.model_id)
                result = {'episodes':[shadow(model['program'],ep,recommendation) for ep in ledger.episodes(trainer)]}
        print(canonical({'operation_completed':True,'result':result}))
        return 0
    except PermissionError as error:
        code = 3
        error_message = str(error)
    except IntegrityError as error:
        code = 8
        error_message = str(error)
    except BudgetExhausted as error:
        code = 5
        error_message = str(error)
    except StaleWorker as error:
        code = 7
        error_message = str(error)
    except (FileNotFoundError,NotImplementedError,ImportError) as error:
        code = 6
        error_message = str(error)
    except (ValueError,LookupError,sqlite3.Error) as error:
        code = 2
        error_message = str(error)
    print(canonical({'operation_completed':False,'exit_code':code,'error':error_message}))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
