"""Fixed cross-process persistence experiment; synthetic tools, never promotion."""
from dataclasses import replace
from hashlib import sha256
import json
import multiprocessing
from pathlib import Path
import sqlite3
import time

from ..agent_bridge_v13 import DemoAgentBridge
from ..memory_v18 import MemoryAuthority, TrustedMemoryLedger
from . import online_adaptation_study as study
from .automation import AutomaticLearningRun
from .contracts import MemoryScope
from .gateway import MemoryGateway
from .learning import VerifiedOutcomeLearning
from .research_campaign import _ownership, _export

SEED = 21001
MAX_CALLS = 80


def manifest():
    sources = study.protocol_manifest()['source_sha256']
    root = Path(__file__).parent
    sources = {**sources, **{name: sha256((root/name).read_bytes()).hexdigest() for name in
              ('restart_learning_study.py', 'research_campaign.py', '../../../scripts/verify_restart_learning.py')}}
    return {'version': 'restart-learning-v1', 'seed': SEED, 'scenarios': list(study.SCENARIOS),
            'arms': list(study.ARMS), 'episodes': 32, 'chunks': [8, 8, 8, 8],
            'max_child_calls': MAX_CALLS, 'pipeline_episodes': 1024,
            'child_timeout_seconds': 60, 'source_sha256': sources,
            'public_synthetic_nonsealed': True, 'promotion_authorized': False}


def _hashes(protocol):
    root = Path(__file__).parent
    return {name: sha256((root/name).read_bytes()).hexdigest() for name in protocol['source_sha256']}


def _chunk(directory, scenario, arm, start, count):
    if scenario not in study.SCENARIOS or arm not in study.ARMS or (start, count) not in ((0,32),(0,8),(8,8),(16,8),(24,8)):
        raise ValueError('unregistered chunk')
    root = Path(directory)
    root.mkdir(exist_ok=True)
    memory = root/'memory.sqlite'
    authority = MemoryAuthority()
    host = authority.issue('synthetic', 'agent', permissions=('read', 'propose', 'approve'))
    reader = authority.issue('synthetic', 'agent', permissions=('read',))
    scope = MemoryScope('synthetic', 'agent', 'restart-study')
    if start == 0 and memory.exists():
        raise ValueError('initial chunk already consumed')
    if start and not memory.exists():
        raise ValueError('persistent state missing')
    gateway = MemoryGateway(TrustedMemoryLedger(memory, authority))
    if start == 0:
        for strategy, stable in (('lower-only','fixture-z-lower'), ('trim-lower','fixture-a-trim')):
            mid = gateway.propose(host, scope=scope, source_id='host-fixture', content=json.dumps({
                'schema':'nerve-demo-strategy-v1', 'task':'email-normalization',
                'extract':'json-field', 'normalise':strategy}))
            with sqlite3.connect(memory) as db:
                db.execute('UPDATE trusted_memory_v18 SET memory_id=?,created_at=1 WHERE memory_id=?', (stable,mid))
            gateway.decide(host, stable, scope=scope, approve=True, evaluator_id='host-review')
    # Never regenerate or reapprove records at a later chunk. Exact fixture integrity is mandatory.
    with sqlite3.connect(memory) as db:
        records = db.execute('SELECT memory_id,status,content,source_sha256 FROM trusted_memory_v18 ORDER BY memory_id').fetchall()
    if len(records) != 2 or {row[0] for row in records} != {'fixture-z-lower','fixture-a-trim'}:
        raise ValueError('source fixture changed')
    for mid, status, content, digest in records:
        expected = json.dumps({'schema':'nerve-demo-strategy-v1', 'task':'email-normalization',
            'extract':'json-field','normalise':'lower-only' if mid=='fixture-z-lower' else 'trim-lower'})
        if status != 'approved' or content != expected or sha256(content.encode()).hexdigest() != digest:
            raise ValueError('source revoked or corrupt')
    cases = study._cases(SEED, scenario)
    answers = {study._digest(task): json.loads(task['document'])['email'].strip().lower()
               if trim else json.loads(task['document'])['email'].lower() for task,trim in cases}
    def judge(record, task, output):
        return output == answers[study._digest(task)]
    learning = VerifiedOutcomeLearning(gateway, host, scope, judge, 'restart-learning-v1',
                window=3, discount_half_life=1 if arm=='candidate' else None)
    session = replace(learning.session(reader), can_propose=False)
    bridge = DemoAgentBridge(root/'agent.sqlite', memory_session=session, require_verified_memory=True)
    fixed = {'fixed_lower':'lower-only','fixed_trim':'trim-lower'}.get(arm)
    runner = AutomaticLearningRun(learning, reader, root/'agent.sqlite', 'restart-study', max_episodes=32,max_failures=32)
    if runner.status()['consumed'] != (0 if fixed else start):
        raise ValueError('persistent budget mismatch')
    before = study._snapshot(memory)['count']
    if before != (0 if fixed else start):
        raise ValueError('persistent utility mismatch')
    outcomes, strategies = [], []
    for index in range(start,start+count):
        task = cases[index][0]
        if fixed:
            result = bridge.execute_plan(task_id=f'case-{index}', email_document=task['document'],
                                        extract_strategy='json-field', normalise_strategy=fixed)
            success, strategy = judge(None, task, result['result']), fixed
        else:
            result = runner.execute(f'case-{index}', task)
            if result['status'] != 'judged':
                raise ValueError('episode not independently judged')
            success, strategy = result['success'], result['strategies']['normalise']
        outcomes.append(success)
        strategies.append(strategy)
    return {'scenario': scenario,'arm':arm,'start':start,'count':count,
            'outcomes':outcomes,'strategies':strategies,'hits':sum(outcomes),
            'feedback_before':before,'feedback_after':study._snapshot(memory)['count'],
            'consumed':runner.status()['consumed'],
            'payload_sha256':[study._digest(task) for task,_ in cases[start:start+count]]}


def _child(connection, args):
    try:
        connection.send(('ok',_chunk(*args)))
    except BaseException:
        connection.send(('error',None))
    finally:
        connection.close()


def _execute(directory, scenario, arm, start, count):
    context = multiprocessing.get_context('spawn')
    reader, writer = context.Pipe(duplex=False)
    process = context.Process(target=_child,args=(writer,(directory,scenario,arm,start,count)))
    try:
        process.start()
        writer.close()
        if not reader.poll(60):
            raise TimeoutError('child_timeout')
        status,row = reader.recv()
        if status != 'ok':
            raise RuntimeError('child_failed')
        return row
    finally:
        if process.pid is not None:
            if process.is_alive(): process.terminate()
            process.join(1)
            if process.is_alive():
                process.kill()
                process.join(1)
        reader.close()
        writer.close()


def _validate(row, scenario, arm, start, count):
    if type(row) is not dict or any(row.get(key)!=value for key,value in
       (('scenario',scenario),('arm',arm),('start',start),('count',count))):
        raise ValueError('chunk identity mismatch')
    outcomes = row.get('outcomes')
    strategies = row.get('strategies')
    if type(outcomes) is not list or len(outcomes)!=count or any(type(v) is not bool for v in outcomes):
        raise ValueError('invalid outcomes')
    if type(strategies) is not list or len(strategies)!=count or any(s not in ('lower-only','trim-lower') for s in strategies):
        raise ValueError('invalid strategies')
    fixed = arm.startswith('fixed_')
    for key,value in (('hits',sum(outcomes)),('feedback_before',0 if fixed else start),
                      ('feedback_after',0 if fixed else start+count),('consumed',0 if fixed else start+count)):
        if type(row.get(key)) is not int or row[key]!=value:
            raise ValueError('evidence budget mismatch')
    if row.get('payload_sha256') != [study._digest(t) for t,_ in study._cases(SEED,scenario)[start:start+count]]:
        raise ValueError('unmatched fixtures')
    # Independently recompute success from the fixed known registered transformations.
    for (_,trim), strategy, success in zip(study._cases(SEED,scenario)[start:start+count],strategies,outcomes):
        if success != (trim == (strategy=='trim-lower')):
            raise ValueError('unsupported outcome score')
        if fixed and strategy != {'fixed_lower':'lower-only','fixed_trim':'trim-lower'}[arm]:
            raise ValueError('fixed control changed')
    return row


def run_study(directory):
    return _run(directory,_execute)


def _run(directory, executor):
    root = Path(directory).resolve()
    root.mkdir(parents=True,exist_ok=True)
    protocol = manifest()
    report = {'protocol':protocol,'status':'running','calls':[], 'claimed_pipeline_episodes':0,
              'completed_pipeline_episodes':0,'model_weights_trained':False,'deployed':False,
              'promotion_authorized':False,'scope':'Synthetic persistent strategy preferences across real process boundaries.'}
    with _ownership(root/'study.sqlite'):
        if any(entry.name != 'study.sqlite.lock' or entry.is_symlink() for entry in root.iterdir()):
            raise ValueError('study requires a fresh empty directory; existing state is never modified')
        with sqlite3.connect(root/'study.sqlite') as db:
            if (root/'report.json').exists():
                raise ValueError('report already exists; study directory is consumed')
            db.execute('CREATE TABLE IF NOT EXISTS study (id INTEGER PRIMARY KEY,status TEXT,report TEXT)')
            if db.execute('SELECT 1 FROM study').fetchone():
                raise ValueError('study already consumed; no resume or replay')
            db.execute('INSERT INTO study VALUES (1,?,?)',('running',json.dumps(report)))
            db.commit()
            def checkpoint():
                db.execute('UPDATE study SET status=?,report=? WHERE id=1',(report['status'],json.dumps(report,allow_nan=False)))
                db.commit()
                _export(root/'report.json',report)
            active = None
            try:
                checkpoint()
                for scenario in study.SCENARIOS:
                    for arm in study.ARMS:
                        for mode, chunks in (('continuous',((0,32),)),('restarted',((0,8),(8,8),(16,8),(24,8)))):
                            folder = root/f'{scenario}-{arm}-{mode}'
                            for start,count in chunks:
                                if len(report['calls']) >= MAX_CALLS or report['claimed_pipeline_episodes']+count > 1024:
                                    raise ValueError('study budget exhausted')
                                if _hashes(protocol) != protocol['source_sha256']:
                                    raise ValueError('source drift')
                                active = {'scenario':scenario,'arm':arm,'mode':mode,'start':start,'count':count,'status':'pending'}
                                report['calls'].append(active)
                                report['claimed_pipeline_episodes'] += count
                                checkpoint()
                                started = time.monotonic()
                                row = _validate(executor(folder,scenario,arm,start,count),scenario,arm,start,count)
                                if _hashes(protocol) != protocol['source_sha256']:
                                    raise ValueError('source drift')
                                active.update(status='complete',evidence=row,elapsed_seconds=time.monotonic()-started)
                                report['completed_pipeline_episodes'] += count
                                checkpoint()
                                active = None
                comparisons = []
                for scenario in study.SCENARIOS:
                    for arm in study.ARMS:
                        rows = [call for call in report['calls'] if call['scenario']==scenario and call['arm']==arm]
                        base = rows[0]['evidence']
                        continued = rows[1:]
                        match = all(base[key] == [v for call in continued for v in call['evidence'][key]]
                                    for key in ('outcomes','strategies','payload_sha256'))
                        match = match and all(base[key] == continued[-1]['evidence'][key] for key in ('feedback_after','consumed'))
                        comparisons.append({'scenario':scenario,'arm':arm,'equivalent':match,'hits':base['hits']})
                report.update(status='complete' if all(r['equivalent'] for r in comparisons) else 'equivalence_failed', comparisons=comparisons)
                checkpoint()
                return report
            except BaseException as error:
                report['status']='failed_consumed'
                report['error']='child_timeout' if isinstance(error,TimeoutError) else 'experiment_aborted'
                if active is not None: active['status']='failed_consumed'
                checkpoint()
                if isinstance(error,(KeyboardInterrupt,SystemExit)): raise
                return report
