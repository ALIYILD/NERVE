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


def cohorts():
    from nerve_awim import agentos_taskbench_v2, agentos_taskbench_v3
    return {'v1':bench, 'v2':agentos_taskbench_v2, 'v3':agentos_taskbench_v3}


def revision(cohort='v1'):
    evaluator=Path(bench.__file__).read_bytes()
    source=Path(cohorts()[cohort].__file__).read_bytes()
    return sha256(encode({'cohort':cohort,'evaluator_sha256':sha256(evaluator).hexdigest(),
                         'cohort_sha256':sha256(source).hexdigest(),
                         'task_manifest':task_manifest(cohorts()[cohort].dataset())}).encode()).hexdigest()


def task_manifest(groups):
    return [{'id':bench.public_task(t)['id'],'phase':phase,
        'family':bench.public_task(t)['family'],'task':bench.public_task(t)}
        for phase,tasks in groups.items() for t in tasks]


def registered_tasks(cohort=None):
    available=cohorts()
    if cohort is not None and cohort not in available:
        raise ValueError('unknown repository cohort')
    return {name:{phase:[bench.public_task(t) for t in tasks]
                  for phase,tasks in module.dataset().items()}
            for name,module in available.items() if cohort is None or cohort==name}


def fresh_cohort(experiment, cohort=None):
    available=cohorts()
    if cohort is not None and cohort not in available:
        raise ValueError('unknown repository cohort')
    with sqlite3.connect(experiment.path) as db:
        rows=db.execute('SELECT hash,family FROM tasks').fetchall()
    used={row[0] for row in rows}
    families={row[1] for row in rows}
    for name,module in available.items():
        if cohort is not None and name!=cohort:
            continue
        groups=module.dataset()
        manifest=task_manifest(groups)
        if any(t['family'] in families or
               sha256(encode({k:v for k,v in t['task'].items() if k!='id'}).encode()).hexdigest() in used
               for t in manifest):
            continue
        return name,groups,manifest
    return None


REQUIRED_STUDY_SESSIONS = 8
DAILY_NATIVE_LIMIT = 20


def session_budget(host):
    # Production hosts always own the calls ledger. Lightweight test hosts may
    # omit it because their native callback performs no inference.
    if not hasattr(host,'path'):
        return DAILY_NATIVE_LIMIT
    day=time.strftime('%Y-%m-%d',time.gmtime())
    with sqlite3.connect(host.path) as db:
        used=db.execute('SELECT COUNT(*) FROM nerve_calls WHERE day=? AND provider=?',
                        (day,'hermes-free')).fetchone()[0]
    return max(0,DAILY_NATIVE_LIMIT-used)


def clear_pending(host, profile, cohort):
    path=host.directory/'pending-repository-study.json'
    if path.exists():
        pending=json.loads(path.read_text())
        if pending.get('profile')==profile and (cohort is None or pending.get('cohort') in (None,cohort)):
            path.unlink()


def predict(host, native, profile, tasks, *, model, lesson=None):
    prompt=('Repair each supplied Python function to meet its requirements. '
        'Return only a JSON object keyed by task id; each value must be '
        '{"code":"the complete replacement function source"}. '
        'The exact outer shape is {"<task id>":{"code":"def <function>(...):\\n    ..."}} '
        'with one entry for every supplied task id. '
        'Each task source includes the function to repair and may include dependency '
        'definitions above it. Those dependencies are IMMUTABLE CONTEXT supplied by '
        'the host, not part of your replacement. Reference their existing names inside '
        'the function; never copy or redefine them in the output. '
        'Each code string must contain exactly one def statement with its body. '
        'No top-level assignments, constants, helper functions, imports, or test calls. '
        'Preserve the named function and signature. No tools are available. '
        'Follow the supplied patch contract. Return raw JSON without Markdown fences '
        'or explanations. Invalid patches are rejected as submitted; no repair retry '
        'or automatic extraction is performed.\n'+
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


def study(host, native, profile, vault, *, progress=lambda:None, cohort=None):
    experiment=ledger(host)
    selected=fresh_cohort(experiment,cohort)
    if selected is None:
        clear_pending(host,profile,cohort)
        return {'result':{'status':'no_fresh_tasks'},'limitation':
                'All requested cohorts contain reserved function families. Add independent function families before another study.'}
    cohort,groups,manifest=selected
    remaining=session_budget(host)
    if remaining<REQUIRED_STUDY_SESSIONS:
        atomic_json(host.directory/'pending-repository-study.json',
                    {'profile':profile,'cohort':cohort,
                     'requested_day':time.strftime('%Y-%m-%d',time.gmtime()),
                     'status':'deferred_daily_budget','required_sessions':REQUIRED_STUDY_SESSIONS,
                     'remaining_sessions':remaining})
        return {'cohort':cohort,'result':{'status':'deferred_daily_budget',
                'required_sessions':REQUIRED_STUDY_SESSIONS,'remaining_sessions':remaining},
                'limitation':'Fresh evidence remains unreserved; the scheduled cycle retries after the UTC daily budget resets.'}
    judge_revision=revision(cohort)
    # Independent evaluator self-check before reserving the holdout or spending.
    for tasks in groups.values():
        for task in tasks:
            if not bench.evaluate(task,bench.reference_solution(task))['passed']:
                raise RuntimeError('reference repair failed evaluator preflight')
    model=native(host,profile,'',inspect=True)['requested_model']
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
        if cohort!='v1':
            (snapshot/'cohort.py').write_bytes(Path(cohorts()[cohort].__file__).read_bytes())
        atomic_json(snapshot/'manifest.json',{'study_id':sid,'judge_revision':judge_revision,
            'scope':SCOPE,'cohort':cohort,'tasks':manifest})
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
        receipt=dict(id=sid,profile=profile,scope=SCOPE,cohort=cohort,model=model,judge_revision=judge_revision,
                     result=result,native_sessions=sessions,artifacts=artifacts,limitation=LIMITATION)
    except Exception as error:
        # Native wrapper errors are categorical. Avoid raw provider or code text.
        reason=type(error).__name__+': repository experiment did not complete'
        experiment.fail(sid,reason,results=evidence)
        receipt=dict(id=sid,profile=profile,scope=SCOPE,cohort=cohort,model=model,judge_revision=judge_revision,
                     result={'status':'failed','reason':reason},native_sessions=sessions,
                     artifacts=artifacts,limitation=LIMITATION)
        atomic_json(host.directory/'latest-repository-study.json',receipt)
        atomic_json(vault/'Journal/nerve'/f'{sid}.json',receipt)
        clear_pending(host,profile,cohort)
        progress()
        raise
    atomic_json(host.directory/'latest-repository-study.json',receipt)
    atomic_json(vault/'Journal/nerve'/f'{sid}.json',receipt)
    clear_pending(host,profile,cohort)
    progress()
    return receipt


def run(host,native,profile,task_id, *, cohort=None):
    """Monitored reuse on a registered repair; this is replay, not fresh evidence."""
    available=cohorts()
    if cohort is not None and cohort not in available:
        raise ValueError('unknown repository cohort')
    matches=[(name,t) for name,module in available.items() if cohort is None or name==cohort
             for group in module.dataset().values() for t in group
             if bench.public_task(t)['id']==task_id]
    if len(matches)!=1:
        raise ValueError('one unambiguous registered repair task required')
    cohort,task=matches[0]
    model=native(host,profile,'',inspect=True)['requested_model']
    judge_revision=revision(cohort)
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
    result=dict(task_id=task_id,scope=SCOPE,cohort=cohort,judge_revision=judge_revision,output=outputs[task_id],check=checks[task_id],
                lesson_id=advice['id'] if advice else None,monitor=outcome,native=receipt,
                limitation='Registered task replay; not a fresh held-out improvement measurement.')
    atomic_json(host.directory/'latest-repository-run.json',result)
    return result
