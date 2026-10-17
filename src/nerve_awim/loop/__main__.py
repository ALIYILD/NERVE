"""CPU-only demos and independent fresh-process replay."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import tempfile
from . import Loop, canonical, digest
from ..goal_orchestrator import GoalOrchestrator


def demo(domain, directory, budget=100):
    if type(budget) is not int or not 1 <= budget <= 10000:
        raise ValueError('demo budget must be 1..10000 synthetic dev items')
    directory=Path(directory); directory.mkdir(parents=True,exist_ok=True)
    loop=Loop(domain,directory)
    bank=loop.domain.bank(budget)
    protocol={'schema':'loop-demo-protocol-v2','domain':domain,'domain_version':loop.domain.version,
              'budget':budget,'bank_hash':digest(bank),'source_sha256':source_hashes(),
              'keep_rule':{'net_wins':6,'max_losses':1,'safety_errors':0,'beat_controls':True},
              'model_calls':0,'adaptation':'legacy synthetic paired reward fixture; not canonical D5'}
    protocol_path=directory/'protocol.json'
    if protocol_path.exists() and json.loads(protocol_path.read_text())!=protocol:
        raise ValueError('registered demo protocol changed')
    protocol_path.write_text(canonical(protocol)+'\n')  # Before any prediction.
    baseline=[{'item':r,'prediction':loop.domain.predict(loop.domain.skills[0],loop.domain.public_input(r))} for r in bank]
    baseline_hash=digest(baseline)
    episodes=[{'id':r['item']['id'],'cluster':r['item']['cluster'],
               'correct':loop.domain.correct(r['prediction'],r['item']),
               'source_receipt_sha256':baseline_hash,'source_ordinal':i} for i,r in enumerate(baseline)]
    def evaluate_task(ctx):
        receipt=loop.evaluate(ctx['propose'],bank)
        return {'receipt_hash':digest(receipt),'items':len(receipt['rows']),
                'study':receipt['study'],'verdict':receipt['verdict']}
    handlers={
        'learn':lambda _:loop.learn(episodes),
        'propose':lambda _:loop.propose(),
        'evaluate':evaluate_task,
        'adapt':lambda _: {'receipt_hash':digest(loop.adapt(loop.domain.stream())), 'items':1200,'model_calls':0},
    }
    validators={
        'learn':lambda r:r['learned']==len(episodes) and r['model_calls']==0,
        'propose':lambda r:r is not None and r['domain']==domain,
        'evaluate':lambda r:r['items']==budget and r['verdict'] in ('kept','reverted') and loop.db.execute('SELECT 1 FROM receipts WHERE id=?',(r['study'],)).fetchone() is not None,
        'adapt':lambda r:r['items']==1200 and r['model_calls']==0,
    }
    orchestrator=GoalOrchestrator(directory/'goal',handlers=handlers,validators=validators)
    if not orchestrator.path.exists():
        orchestrator.create(goal_id='loop-demo-'+domain,target='auditable synthetic development cycle',tasks=[
            {'id':'learn','handler':'learn'},
            {'id':'propose','handler':'propose','depends_on':['learn']},
            {'id':'evaluate','handler':'evaluate','depends_on':['propose']},
            {'id':'adapt','handler':'adapt','depends_on':['evaluate']},
        ])
    for _ in range(10):
        state=orchestrator.tick()
        if state['status']!='active':break
    if state['status']!='complete':
        raise RuntimeError('orchestration did not succeed: '+state['status'])
    candidate=next(t['receipt'] for t in state['tasks'] if t['id']=='propose')
    evaluation=loop.evaluate(candidate,bank)
    adaptation=loop.adapt(loop.domain.stream())
    bundle={'schema':'loop-demo-v2','protocol':protocol,'protocol_sha256':digest(protocol),'domain':domain,'budget':budget,'baseline':baseline,
            'episodes':episodes,'candidate':candidate,'evaluation':evaluation,'adaptation':adaptation,
            'status':loop.status(),'orchestrator_status':state['status'],
            'learning':next(t['receipt'] for t in state['tasks'] if t['id']=='learn'),
            'experience_head':loop.memory.store.query(loop.memory.actor)['head']}
    loop.close()
    (directory/'bundle.json').write_text(canonical(bundle)+'\n')
    manifest={'bundle_sha256':digest(bundle),'model_calls':0,'synthetic':True,
              'source_sha256':source_hashes()}
    (directory/'manifest.json').write_text(canonical(manifest)+'\n')
    return manifest


def source_hashes():
    source_root=Path(__file__).resolve().parents[1]
    sources=['loop/__init__.py','loop/__main__.py','loop/domains.py','loop/experience.py',
             'memory_gateway/drift_monitor.py','memory_gateway/site_router.py',
             'memory_gateway/experience_study_store_v2.py','goal_orchestrator.py']
    return {p:sha256((source_root/p).read_bytes()).hexdigest() for p in sources}


def replay(directory):
    directory=Path(directory)
    bundle=json.loads((directory/'bundle.json').read_text()); manifest=json.loads((directory/'manifest.json').read_text())
    if digest(bundle)!=manifest['bundle_sha256']:
        raise ValueError('bundle hash mismatch')
    if bundle.get('schema')!='loop-demo-v2':
        raise ValueError('legacy fixture: replay using its original pinned source checkout')
    if manifest.get('source_sha256')!=source_hashes():
        raise ValueError('source hash mismatch; use pinned source checkout')
    protocol=json.loads((directory/'protocol.json').read_text())
    if protocol!=bundle['protocol'] or digest(protocol)!=bundle['protocol_sha256']:
        raise ValueError('registered protocol mismatch')
    with tempfile.TemporaryDirectory() as temporary:
        result=demo(bundle['domain'],temporary,bundle['budget'])
        if result!=manifest:
            raise ValueError('fresh replay mismatch')
    return {'verified':True,'model_calls':0,'bundle_sha256':manifest['bundle_sha256']}


def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='command',required=True)
    d=sub.add_parser('demo'); d.add_argument('--domain',required=True); d.add_argument('--budget',type=int,default=100); d.add_argument('--output')
    r=sub.add_parser('replay'); r.add_argument('directory')
    a=p.parse_args()
    if a.command=='replay':result=replay(a.directory)
    else:
        output=a.output or 'receipts/loop-demo-'+a.domain+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        result=demo(a.domain,output,a.budget); result['directory']=output
    print(canonical(result))

if __name__=='__main__':main()
