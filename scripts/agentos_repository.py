"""Native Hermes paired experiments on isolated repository-derived repairs.

This trusted host never asks a model to grade itself or modifies the live repo.
Only procedural advice can be promoted; generated repairs stay in receipts.
"""
from hashlib import sha256
import json
from pathlib import Path
import random
import sqlite3
import time
import uuid

from nerve_awim.agentos_learning import atomic_json
from nerve_awim.agentos_experiments import RepositoryExperiments, SCOPE, encode
from nerve_awim import agentos_taskbench as bench

BUDGET = {'max_tokens':4096,'max_iterations':2,'timeout_seconds':90}
LIMITATION = ('Repository-derived injected faults, not resolved production tickets. '
              'Small disjoint function set; measured paired results do not prove general improvement.')


def ledger(host):
    return RepositoryExperiments(host.directory/'repository-learning.sqlite3')


def revision():
    return sha256(Path(bench.__file__).read_bytes()).hexdigest()


def predict(host, native, profile, tasks, *, model, lesson=None):
    prompt=('Repair each supplied Python function to meet its requirements. '
        'Return only a JSON object keyed by task id; each value must be '
        '{"code":"the complete replacement function source"}. '
        'Preserve the named function and signature. No tools are available. '
        'Follow the supplied patch contract. Do not include explanations.\n'+
        ('Evaluated procedural advice, subordinate to each task: '+lesson+'\n' if lesson else '')+
        'Tasks: '+json.dumps([bench.public_task(t) for t in tasks]))
    started=time.monotonic()
    answer=native(host,profile,prompt,max_tokens=BUDGET['max_tokens'])
    if answer.get('requested_model')!=model:
        raise RuntimeError('paired model changed; experiment rejected')
    if any(answer.get(k)!=v for k,v in BUDGET.items()):
        raise RuntimeError('paired execution budget mismatch')
    values=answer['value']
    ids=[bench.public_task(t)['id'] for t in tasks]
    if type(values) is not dict or set(values)!=set(ids):
        raise ValueError('repair batch output contract failed')
    checks={tid:bench.evaluate(task,values[tid]) for tid,task in zip(ids,tasks)}
    if any(c.get('category') in ('sandbox_unavailable','infrastructure_error') for c in checks.values()):
        raise RuntimeError('repair execution sandbox unavailable')
    receipt={k:v for k,v in answer.items() if k!='value'}
    receipt.update(elapsed_seconds=round(time.monotonic()-started,3),budget=dict(BUDGET),cost_usd=None)
    return values,checks,receipt


def study(host, native, profile, vault, *, progress=lambda:None):
    groups=bench.dataset()
    experiment=ledger(host)
    model=native(host,profile,'',inspect=True)['requested_model']
    judge_revision=revision()
    manifest=[{'id':bench.public_task(t)['id'],'phase':phase,
        'family':bench.public_task(t)['family'],'task':bench.public_task(t)}
        for phase,tasks in groups.items() for t in tasks]
    with sqlite3.connect(experiment.path) as db:
        used={row[0] for row in db.execute('SELECT hash FROM tasks')}
    if any(sha256(encode({k:v for k,v in t['task'].items() if k!='id'}).encode()).hexdigest() in used
           for t in manifest):
        return {'result':{'status':'no_fresh_tasks'},'limitation':
                'This fixture contains previously reserved evidence. Add independent function families before another study.'}
    # Independent evaluator self-check before reserving the holdout or spending.
    for tasks in groups.values():
        for task in tasks:
            if not bench.evaluate(task,bench.reference_solution(task))['passed']:
                raise RuntimeError('reference repair failed evaluator preflight')
    sid='repair-'+uuid.uuid4().hex
    experiment.start(sid,profile=profile,model=model,judge_revision=judge_revision,
                     tasks=manifest,budget=BUDGET)
    evidence=[]
    sessions=[]
    artifacts=[]
    def execute(phase,arm,advice=None):
        tasks=groups[phase]
        outputs,checks,receipt=predict(host,native,profile,tasks,model=model,lesson=advice)
        sessions.append(dict(phase=phase,arm=arm,**receipt))
        for t in tasks:
            tid=bench.public_task(t)['id']
            evidence.append(dict(task_id=tid,arm=arm,passed=checks[tid]['passed'],
                                 model=model,budget=dict(BUDGET)))
            artifacts.append(dict(task_id=tid,phase=phase,arm=arm,output=outputs[tid],check=checks[tid]))
        return outputs,checks
    result=None
    try:
        snapshot=host.directory/'study-inputs'/sid
        snapshot.mkdir(parents=True,exist_ok=False)
        (snapshot/'judge.py').write_bytes(Path(bench.__file__).read_bytes())
        atomic_json(snapshot/'manifest.json',{'study_id':sid,'judge_revision':judge_revision,
            'scope':SCOPE,'tasks':manifest})
        progress()
        outputs,checks=execute('train','baseline')
        prompt=('Extract one concise reusable Python repair lesson from only these training attempts. '
            'Return JSON {"lesson":"..."}, at most 3000 characters. Describe methods that may '
            'transfer across functions; do not claim approval or invent hidden tests.\n'+
            json.dumps([{'task':bench.public_task(t),'attempt':outputs[bench.public_task(t)['id']],
                         'observed_test_result':checks[bench.public_task(t)['id']]}
                        for t in groups['train']]))
        proposed=native(host,'nina-memory-librarian',prompt,max_tokens=BUDGET['max_tokens'])
        lesson=proposed['value'].get('lesson') if type(proposed['value']) is dict else None
        if type(lesson) is not str or not 1<=len(lesson)<=3000:
            raise ValueError('bounded repair lesson required')
        sessions.append(dict(phase='proposal',**{k:v for k,v in proposed.items() if k!='value'}))
        experiment.freeze(sid,lesson)
        for phase in ('selection','retention','final'):
            arms=['baseline','lesson']
            random.SystemRandom().shuffle(arms)
            for arm in arms:
                execute(phase,arm,lesson if arm=='lesson' else None)
            ids={bench.public_task(t)['id'] for t in groups[phase]}
            pairs={tid:{e['arm']:e['passed'] for e in evidence if e['task_id']==tid} for tid in ids}
            wins=sum(p['lesson'] and not p['baseline'] for p in pairs.values())
            losses=sum(p['baseline'] and not p['lesson'] for p in pairs.values())
            if (phase=='selection' and (wins==0 or losses)) or (phase=='retention' and losses):
                result=experiment.finish_no_gain(sid,results=evidence)
                break
        if result is None:
            result=experiment.complete(sid,results=evidence)
        receipt=dict(id=sid,profile=profile,scope=SCOPE,model=model,judge_revision=judge_revision,
                     result=result,native_sessions=sessions,artifacts=artifacts,limitation=LIMITATION)
    except Exception as error:
        # Native wrapper errors are categorical. Avoid raw provider or code text.
        reason=type(error).__name__+': repository experiment did not complete'
        experiment.fail(sid,reason,results=evidence)
        receipt=dict(id=sid,profile=profile,scope=SCOPE,model=model,judge_revision=judge_revision,
                     result={'status':'failed','reason':reason},native_sessions=sessions,
                     artifacts=artifacts,limitation=LIMITATION)
        atomic_json(host.directory/'latest-repository-study.json',receipt)
        atomic_json(vault/'Journal/nerve'/f'{sid}.json',receipt)
        progress()
        raise
    atomic_json(host.directory/'latest-repository-study.json',receipt)
    atomic_json(vault/'Journal/nerve'/f'{sid}.json',receipt)
    progress()
    return receipt


def run(host,native,profile,task_id):
    """Monitored reuse on a registered repair; this is replay, not fresh evidence."""
    tasks=[t for group in bench.dataset().values() for t in group]
    task=next((t for t in tasks if bench.public_task(t)['id']==task_id),None)
    if task is None:
        raise ValueError('registered repair task required')
    model=native(host,profile,'',inspect=True)['requested_model']
    judge_revision=revision()
    experiment=ledger(host)
    advice=experiment.recall(profile,model,judge_revision)
    outputs,checks,receipt=predict(host,native,profile,[task],model=model,
                                   lesson=advice['content'] if advice else None)
    outcome=None
    if advice:
        _,base,_=predict(host,native,profile,[task],model=model)
        # One monitoring receipt per factual task/lesson. Replaying doesn't add credit.
        episode=sha256(json.dumps([bench.public_task(task),advice['id']],sort_keys=True).encode()).hexdigest()
        outcome=experiment.observe(episode,profile=profile,model=model,judge_revision=judge_revision,
            lesson_id=advice['id'],passed=checks[task_id]['passed'],baseline_passed=base[task_id]['passed'])
    result=dict(task_id=task_id,scope=SCOPE,output=outputs[task_id],check=checks[task_id],
                lesson_id=advice['id'] if advice else None,monitor=outcome,native=receipt,
                limitation='Registered task replay; not a fresh held-out improvement measurement.')
    atomic_json(host.directory/'latest-repository-run.json',result)
    return result
