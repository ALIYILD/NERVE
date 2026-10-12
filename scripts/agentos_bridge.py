"""Connect NERVE to the existing local Agent OS, with durable learning receipts."""
import argparse
from datetime import datetime, timezone
import itertools
import json
import os
from pathlib import Path
import signal
import random
import sqlite3
import subprocess
import sys
import tempfile
import uuid
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from nerve_awim.agentos_learning import (AgentOSLearning, BASELINE, CONTEXT,
    atomic_json, expected_handoff, host_lock, judge_handoff)
from nerve_awim.improvement_loop import run_improvement_loop
from nerve_awim.learning_study import Episode, canonical
from nerve_awim.agentos_claude import ClaudeReviewer
from nerve_awim.agentos_experiments import RepositoryExperiments

HOME = Path.home()
REPO = Path(__file__).resolve().parents[1]
VAULT = HOME/'AgentOS-Vault'
STATE = HOME/'.agentic-os/nerve'


def recover_interrupted_repository(host):
    """Call once after acquiring the exclusive host lock, never from publish."""
    path=host.directory/'repository-learning.sqlite3'
    if not path.exists():
        return
    experiments=RepositoryExperiments(path)
    with sqlite3.connect(path) as db:
        interrupted=[r[0] for r in db.execute("SELECT id FROM studies WHERE status IN ('started','frozen')")]
    for study_id in interrupted:
        experiments.fail(study_id,'Previous host exited before completing the experiment; reservations remain consumed.')


def claude_key():
    key=os.environ.get('ANTHROPIC_API_KEY','').strip()
    env=Path(os.environ.get('ANTHROPIC_API_KEY_FILE',str(HOME/'.agentic-os/anthropic.env'))).expanduser()
    if not key and env.exists():
        text=env.read_text().strip()
        if text.startswith('sk-ant-api') and '\n' not in text:
            key=text
        for line in env.read_text().splitlines():
            if line.startswith('ANTHROPIC_API_KEY='):
                key=line.split('=',1)[1].strip().strip('\"\'')
    return key if key.startswith('sk-ant-api') else None


def jev_review(host):
    path=host.directory/'latest-study.json'
    if not path.exists():
        raise RuntimeError('complete the learning study before semantic review')
    study_data=json.loads(path.read_text())
    state={'study':study_data,'scope':host.status()['scope']}
    questions={
        'broad_gain':{'type':'noul','instructions':'Does the supplied evidence establish broad general intelligence improvement beyond a small synthetic evidence-handoff fixture?'},
        'bounded_claim':{'type':'noul','instructions':'Does the report clearly limit its result to the tested task and distinguish observed gains from proof of general improvement?'}}
    host.reserve_calls('jev',1,daily_limit=1)
    request=urllib.request.Request('http://127.0.0.1:3737/api/jev',
        data=json.dumps({'state':json.dumps(state),'questions':questions}).encode(),
        headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=40) as response:
        value=json.loads(response.read(100000))
    answers=value.get('answers',{})
    for name in questions:
        answer=answers.get(name,{})
        if answer.get('type')!='noul' or type(answer.get('noul')) not in (int,float) or not 0<=answer['noul']<=1:
            raise ValueError('invalid semantic review response')
    result={'model':value.get('model'),'answers':answers,'usage':value.get('usage'),
            'advisory_only':True,'promotion_authorized':False,'cost_usd':None}
    atomic_json(host.directory/'jev-review.json',result)
    return result


def native(host, profile, prompt, *, max_tokens=2048, inspect=False, cue_context=None, inspect_profile=False):
    """Installed runtime, bounded text, no tools, free model, process timeout."""
    # Only an operational caller supplies this trusted context. Research and
    # no-cue comparison arms retain the unchanged default request contract.
    cue_preparation = None
    if cue_context is not None and not inspect:
        from nerve_awim.cue_host import CueHost
        if cue_context != 'handoff':
            raise PermissionError('unsupported operational cue context')
        cue_preparation = CueHost(host).prepare(profile, 'handoff', permission_granted=True)
    catalog=host.directory/'free-models.json'
    if inspect_profile:
        if inspect is not True:
            raise ValueError('profile inspection cannot dispatch inference')
        available=[]
    elif not catalog.exists() or datetime.now().timestamp()-catalog.stat().st_mtime>86400:
        # System curl uses macOS's maintained CA trust; never disable TLS checks.
        raw=subprocess.check_output(['curl','--fail','--silent','--show-error','--max-time','20',
            'https://openrouter.ai/api/v1/models'],timeout=25)
        if len(raw)>5000000:
            raise ValueError('provider catalog too large')
        data=json.loads(raw)
        available=[m['id'] for m in data['data'] if m['id'].endswith(':free')
                   and all(float(m.get('pricing',{}).get(k,'-1'))==0 for k in ('prompt','completion'))]
        atomic_json(catalog,available)
    else:
        available=json.loads(catalog.read_text())
    if not inspect:
        host.reserve_calls('hermes-free', 1, daily_limit=20)
    checkout = HOME/'.hermes/hermes-agent'
    launcher = json.loads(subprocess.check_output(
        [str(HOME/'.local/bin/hermes'), '--print-runtime-command'], text=True, timeout=10))
    # Resolve the selected dependency environment without installing anything.
    resolve = ('import sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); '
               'from pm.environments import project_python; print(project_python(Path(sys.argv[1])))')
    python = subprocess.check_output([launcher[0], '-I', '-c', resolve, str(checkout)],
                                     text=True, timeout=10).strip()
    code = 'import sys,runpy; sys.path.insert(0,sys.argv[1]); runpy.run_path(sys.argv[2],run_name="__main__")'
    with tempfile.TemporaryDirectory(prefix='nerve-native-') as tmp:
        env = {k:v for k,v in os.environ.items() if k in ('PATH','HOME','LANG','LC_ALL','TMPDIR')}
        env.update(HERMES_HOME=tmp, HERMES_RUNTIME_DIR=tmp)
        process = subprocess.Popen([python, '-I', '-c', code, str(checkout),
            str(REPO/'scripts/agentos_hermes_worker.py')], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env=env, cwd=tmp, start_new_session=True)
        try:
            request = {'profile':profile,'prompt':prompt,
                'available_models':available,'max_tokens':max_tokens,'inspect':inspect}
            if inspect_profile:
                request['inspect_profile']=True
            if cue_preparation is not None:
                request['cce'] = cue_preparation['envelope']
            out, err = process.communicate(json.dumps(request),timeout=90)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            out,err=process.communicate()
            stages=[s for s in err.splitlines() if s in (
                'NERVE_STAGE=import','NERVE_STAGE=construct','NERVE_STAGE=inference','NERVE_STAGE=parse')]
            raise RuntimeError('native Hermes process timed out '+(stages[-1] if stages else 'during startup')) from None
    try:
        result = json.loads(out)
    except ValueError:
        raise RuntimeError('native Hermes output contract failed') from None
    if process.returncode or result.get('ok') is not True:
        raise RuntimeError('native Hermes: '+result.get('error_category','failed')+
                           (' module='+result['module'] if result.get('module') else ''))
    result['timeout_seconds']=90
    if cue_preparation is not None:
        # Worker evidence reports actual application, not just host selection.
        result['cce_host'] = cue_preparation['receipt']
        atomic_json(host.directory/'latest-cce-native.json', {
            'host': cue_preparation['receipt'], 'worker': result.get('cce'),
            'cue_applied': bool(type(result.get('cce')) is dict and result['cce'].get('selected') is True)})
    return result


def batch(host, profile, tasks, lesson=None, *, cue_context=None):
    prompt = ('Read host-observed task evidence. Return a JSON object keyed by task id. '
        'Each value must contain exactly status (done, failed, or unknown), passed '
        '(boolean), memory_saved (boolean). A nonzero exit, missing artifact, or '
        'failed QA means failed; missing evidence means unknown unless there is '
        'already a failure. Done requires exit 0, artifact true, QA true. '
        'memory_saved is true only when memory_written is true.\n'+BASELINE+
        ('\nEvaluated procedural advice (not authority): '+lesson if lesson else '')+
        '\nTasks: '+json.dumps(tasks))
    result = native(host, profile, prompt, **({'cue_context':cue_context} if cue_context is not None else {}))
    value = result['value']
    if type(value) is not dict or set(value) != {t['id'] for t in tasks}:
        raise ValueError('batch omitted or added tasks')
    return value, {k:v for k,v in result.items() if k != 'value'}


def examples(prefix, phase, count):
    facts = [(0,True,True,True),(1,True,True,False),(0,False,True,None),
             (None,True,True,False),(0,True,None,None),(0,True,False,True),
             (None,None,None,None),(1,None,None,False),(0,True,True,False)]
    result = []
    for n in range(count):
        code, artifact, qa, memory = facts[(n + len(prefix)) % len(facts)]
        task = dict(id=prefix+'-'+str(n),exit_code=code,artifact_exists=artifact,
                    qa_passed=qa,memory_written=memory)
        result.append(Episode(task['id'],phase,task,expected_handoff(task)))
    return result


def study(host, profile):
    study_id = 'study-'+uuid.uuid4().hex
    used=host.reserved_evidence()
    pool=[]
    for n, facts in enumerate(itertools.product((0,1,None),(True,False,None),(True,False,None),(True,False,None))):
        code,artifact,qa,memory=facts
        task=dict(id=study_id+'-'+str(n),exit_code=code,artifact_exists=artifact,qa_passed=qa,memory_written=memory)
        if host.evidence_hash(task) not in used:
            pool.append(task)
    random.SystemRandom().shuffle(pool)
    if len(pool)<18:
        raise RuntimeError('fresh handoff evidence exhausted; add a new independently judged task family')
    groups=[]
    for start,end,phase in ((0,3,'train'),(3,8,'evaluation'),(8,13,'evaluation'),(13,18,'evaluation')):
        groups.append([Episode(t['id'],phase,t,expected_handoff(t)) for t in pool[start:end]])
    training,selection,retained,final=groups
    host.reserve_holdout(study_id+'-development',[e.task for e in training+selection+retained])
    host.reserve_holdout(study_id,[e.task for e in final])
    train_outputs, receipt = batch(host,profile,[e.task for e in training])
    for e in training:
        host.observe(profile,e.task,train_outputs[e.task['id']],mode='study-training')
    proposal = native(host,'nina-memory-librarian',
        'Propose a short reusable lesson for evidence handoff, based only on these '
        'training examples and observed answers. Return JSON with exactly lesson '
        '(string, 1-2048 characters). Do not claim to approve, store or run anything.\n'+
        json.dumps([{'task':e.task,'expected':e.expected,'observed':train_outputs[e.task['id']]}
                    for e in training]))
    lesson = proposal['value'].get('lesson')
    if type(lesson) is not str or not 1 <= len(lesson) <= 2048:
        raise ValueError('bounded generated lesson required')
    # Batch once per split/arm. Only the current split reaches this model call;
    # expected values and final results never reach the proposer.
    partitions = {e.task['id']:group for group in (selection,retained,final) for e in group}
    cache, calls = {}, [receipt, {k:v for k,v in proposal.items() if k!='value'}]
    def predict(task, advice):
        group = partitions[task['id']]
        key = (group[0].episode_id, advice)
        if key not in cache:
            values, info = batch(host,profile,[e.task for e in group],advice)
            if info.get('requested_model') != receipt.get('requested_model'):
                raise RuntimeError('model changed within paired study; comparison rejected')
            cache[key] = values
            calls.append(info)
        return cache[key][task['id']]
    report = run_improvement_loop(training,selection,final,
        propose=lambda _:lesson,predict=predict,judge=judge_handoff,
        iterations=1,regression=retained)
    memory = host.accept_study(profile,study_id,report)
    result = {'id':study_id,'profile':profile,'report':report,'approved_memory':memory,
              'native_sessions':calls,'hermes_revision':subprocess.check_output(
                  ['git','-C',str(HOME/'.hermes/hermes-agent'),'rev-parse','HEAD'],text=True).strip(),
              'limitation':'Small synthetic handoff fixture; fresh IDs do not make task templates independent. No broad capability gain claim.'}
    atomic_json(host.directory/'latest-study.json',result)
    atomic_json(VAULT/'Journal/nerve'/f'{study_id}.json',result)
    return result


def collect_missions(host):
    """Read existing local mission metadata; require actual QA and terminal run."""
    db_path = HOME/'.hermes/kanban/boards/agentos-maintenance/kanban.db'
    if not db_path.exists():
        return {'added':0,'reason':'maintenance board unavailable'}
    added = rejected = 0
    with sqlite3.connect(f'file:{db_path}?mode=ro',uri=True) as db:
        db.row_factory = sqlite3.Row
        for manifest_path in sorted((VAULT/'Journal/maintenance-missions').glob('*/mission.json'))[-30:]:
            try:
                manifest=json.loads(manifest_path.read_text())
                verification=json.loads((manifest_path.parent/'verification.json').read_text())
                if verification.get('accepted') is not True or not verification.get('checks') or verification.get('issues'):
                    rejected += 1
                    continue
                # A host review may veto an optimistic agent QA verdict. It is
                # optional for historical missions, but present evidence fails closed.
                host_review_path = manifest_path.parent/'host-review.json'
                if host_review_path.exists():
                    review = json.loads(host_review_path.read_text())
                    if (type(review) is not dict or review.get('accepted') is not True
                            or type(review.get('checks')) is not list or not review['checks']
                            or type(review.get('issues')) is not list or review['issues']):
                        rejected += 1
                        continue
                # Independent verifier must itself have completed on a distinct
                # profile, and both promised worker artifacts must be present.
                if not all((manifest_path.parent/name).is_file() for name in ('routing.json','scheduling.json')):
                    rejected += 1
                    continue
                verifier = db.execute('SELECT r.profile,r.ended_at,t.status FROM task_runs r '
                    'JOIN tasks t ON t.id=r.task_id WHERE r.task_id=? ORDER BY r.id DESC LIMIT 1',
                    (manifest['verifier_id'],)).fetchone()
                if not verifier or verifier['status']!='done' or not verifier['ended_at']:
                    rejected += 1
                    continue
                for task_id in manifest.get('worker_ids',[]):
                    row = db.execute('SELECT r.id,r.profile,r.started_at,r.ended_at,t.status FROM task_runs r '
                        'JOIN tasks t ON t.id=r.task_id WHERE r.task_id=? ORDER BY r.id DESC LIMIT 1',(task_id,)).fetchone()
                    if not row or row['profile']==verifier['profile'] or row['status']!='done' or not row['ended_at']:
                        continue
                    added += host.ingest_mission('maintenance-'+str(row['id']),row['profile'],success=True,
                        duration=row['ended_at']-row['started_at'],source=str(manifest_path.relative_to(VAULT)))
            except (OSError,ValueError,KeyError,TypeError):
                rejected += 1
        # Supervisor-observed timeouts are failures even without a QA artifact.
        # Reclaimed leases are unknown, not automatically task failures.
        for row in db.execute("SELECT id,profile,started_at,ended_at FROM task_runs WHERE outcome='timed_out' AND ended_at IS NOT NULL"):
            if row['profile'] and row['ended_at'] >= row['started_at']:
                added += host.ingest_mission('maintenance-'+str(row['id']),row['profile'],success=False,
                    duration=row['ended_at']-row['started_at'],source='agentos-maintenance:supervisor-timeout')
    return {'added':added,'unverified_missions':rejected,
            'limitation':'QA-accepted completion observations; not causal evidence that memory helped.'}


def publish(host, extra=None):
    import agentos_audit_study as audit
    import agentos_audit_shadow as shadow
    import agentos_autoresearch as autoresearch
    status=host.status()
    from nerve_awim.cue_host import CueHost
    status['cognitive_cues'] = CueHost(host).status()
    status['audit_evidence_study']=audit.status(host)
    status['audit_shadow']=shadow.status(host)
    status['autoresearch']=autoresearch.status(host)
    study_file=host.directory/'latest-study.json'
    if study_file.exists():
        s=json.loads(study_file.read_text())
        status['last_study']={k:s[k] for k in ('id','profile','approved_memory','limitation')}
        status['last_study']['result']=s['report']['status']
        status['last_study']['final']=(s['report']['final'] if s['report']['final'] is not None
                                       else 'Not opened: no selection gain.')
    status.update(extra or {})
    status['source_repository']=str(REPO)
    status['claude_budget_usd']=25
    reviewer=ClaudeReviewer(host.directory/'claude-review.sqlite3')
    status['claude_budget']=reviewer.report()
    status['claude_status']='configured' if claude_key() else 'credential_not_connected'
    pending_path=host.directory/'pending-repository-study.json'
    status['pending_repository_study']=json.loads(pending_path.read_text()) if pending_path.exists() else None
    status['repository_learning']=RepositoryExperiments(host.directory/'repository-learning.sqlite3').summary()
    status['repository_diagnosis']=repository_diagnosis(host)
    native_file=host.directory/'latest-native.json'
    if native_file.exists():
        status['native_hermes']=json.loads(native_file.read_text())
    status['routing_advice']=host.recommend_profiles(
        ['coordinator','dashboard-operator','workflow-integrity-auditor'],incumbent='coordinator')
    status['automatic_learning']={'enabled':(HOME/'Library/LaunchAgents/com.aliyildirim.nerve.learning.plist').exists(),'provider':'hermes-free',
        'trigger':'Queued studies retry after UTC budget reset; otherwise 3 new supervisor-confirmed failures, at most once per UTC day; fresh tasks required',
        'daily_native_session_limit':20,'paid_calls':False}
    atomic_json(host.directory/'status.json',status)
    approved=[]
    for profile in ('coordinator','qa-release','nina-memory-librarian'):
        approved.extend({'profile':profile,'id':r.memory_id,'content':r.content,'expires':r.valid_until}
                        for r in host.recall(profile))
    atomic_json(host.directory/'context.json',{'context':CONTEXT,'lessons':approved})
    pending=status['pending_repository_study']
    pending_note=('Queued repository study: '+str(pending['profile'])+' / '+str(pending['cohort'])+
        '; deferred on '+str(pending['requested_day'])+' UTC; '+
        str(pending.get('remaining_sessions','?'))+' of '+str(pending.get('required_sessions',8))+
        ' required native sessions available. Retries after the UTC daily budget resets.\n\n') if pending else ''
    audit_pending=status['audit_evidence_study'].get('pending')
    audit_note=('Queued audit study: '+str(audit_pending.get('profile','unknown'))+
        '; requested '+str(audit_pending.get('requested_day','unknown'))+' UTC; '+
        str(audit_pending.get('remaining_sessions','?'))+' of '+str(audit_pending.get('required_sessions',8))+
        ' required sessions available. Scheduler retries after UTC reset while this Mac is awake.\n\n') if audit_pending else ''
    note = ('# NERVE — Agent OS learning\n\n'+
        'AWIM coordination and evaluated-memory track. [[agent-os-capability-registry]]\n\n'+
        'Updated: '+status['updated_at']+'\n\n'+
        'Learning: scoped evidence-handoff lessons; recent failed outcomes can revoke a lesson.\n'+
        'Hermes: installed profiles; native isolated text sessions on configured free models.\n'+
        'Operational receipts: '+str(sum(r['tasks'] for r in status['missions']))+' verified completions or supervisor-confirmed failures.\n'+
        'Approved lessons: '+str(len(approved))+'. No model-weight training or source self-modification.\n\n'+
        'Latest study: '+str(status.get('last_study',{}).get('result','not run'))+'\n\n'+
        'Repository repair study: '+status['repository_learning']['status']+'; '+
        str(status['repository_learning']['active_lessons'])+' active lessons; '+
        str(status['repository_learning']['rollbacks'])+' rollbacks.\n\n'+
        'Diagnosis: '+status['repository_diagnosis']['summary']+'\n\n'+
        pending_note+
        'Audit evidence study: '+str(status['audit_evidence_study'].get('status','not_run'))+
        '. Results are scoped shadow evidence, not operational approval.\n\n'+
        audit_note+
        'Audit shadow monitoring: '+str(status['audit_shadow'].get('status','not_run'))+
        '. No operational activation is authorized.\n\n'+
        'Autoresearch: '+str(status['autoresearch'].get('status','paused'))+
        '; enabled='+str(status['autoresearch'].get('enabled',False))+
        '. Bounded experiments resume on the 15-minute scheduler; fresh evidence and budget are required.\n\n'+
        'Registered follow-on cohorts: '+str(len(status['autoresearch'].get('registered_cohorts',[])))+
        '; latest follow-on study: '+str(status['autoresearch'].get('registered_study',{}).get('status','not_run'))+
        '. Accepted follow-on advice remains experimental and unmonitored.\n\n'+
        'Receipts: `~/.agentic-os/nerve/status.json`; [[Journal/nerve]].\n')
    (VAULT/'Memory/nerve-status.md').write_text(note)
    return status


def retry_pending_audit(host):
    """Called under the host lock; budget-deferred audits retry after UTC reset."""
    path=host.directory/'pending-audit-study.json'
    if not path.exists():
        return None
    try:
        pending=json.loads(path.read_text())
        requested=datetime.strptime(pending['requested_day'],'%Y-%m-%d').date()
        if requested >= datetime.now(timezone.utc).date():
            return None
        import agentos_audit_study as audit
        return audit.study(host,native,pending['profile'])
    except Exception as error:
        atomic_json(host.directory/'audit-cycle-error.json',{'error_category':type(error).__name__})
        return {'status':'failed','error_category':type(error).__name__}


def repository_diagnosis(host):
    """Read-only explanation; never grants advice approval or changes evidence."""
    from nerve_awim.agentos_diagnostics import diagnose
    path=host.directory/'latest-repository-study.json'
    if not path.exists():
        return {'status':'not_run','summary':'No repository experiment receipt is available.'}
    try:
        receipt=json.loads(path.read_text())
        report=diagnose(receipt)
        experiments=RepositoryExperiments(host.directory/'repository-learning.sqlite3')
        latest=experiments.summary()
        if report['study_id']!=latest.get('study_id'):
            raise ValueError('receipt does not describe latest ledger study')
        stored=experiments.status(report['study_id'])
        if stored['revision']!=receipt.get('judge_revision') or stored['model']!=report['model']:
            raise ValueError('receipt evaluator or model differs from ledger')
        if stored['status']=='completed' and stored['summary']!=receipt['result']:
            raise ValueError('receipt result differs from ledger')
        return report
    except (ValueError,LookupError,TypeError):
        return {'status':'invalid_receipt','summary':'The latest receipt could not be validated against the current study.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('status','cycle','study','probe','run','recall','sync-gbrain','jev-review','claude-review',
        'repository-study','repository-run','repository-tasks','repository-diagnose','audit-study','audit-status',
        'audit-shadow','audit-shadow-status','autoresearch-enable','autoresearch-pause',
        'autoresearch-status','autoresearch-tick','autoresearch-submit','autoresearch-register-cohort',
        'arc-run','arc-inspect','arc-replay','arc-evaluate','arc-improve','arc-candidate-status',
        'arc-release-status','arc-stage','arc-promote','arc-rollback','arc-reconcile',
        'adaptation-inspect','adaptation-validate-config','adaptation-replay','adaptation-evaluate',
        'adaptation-run','adaptation-demo','adaptation-status','adaptation-reset','adaptation-kill',
        'research-fast-memory-train','research-fast-memory-evaluate',
        'cce-status','cce-inspect','cce-revoke','cce-demo','cce-approve','cce-route','cce-readiness','cce-profile',
        'cce-local-inspect','cce-local-smoke','cce-dataset-status'))
    parser.add_argument('--repository',type=Path,help='Authorized local repository for read-only adaptation')
    parser.add_argument('--candidate')
    parser.add_argument('--config',type=Path)
    parser.add_argument('--budget',type=Path)
    parser.add_argument('--suite',type=Path)
    parser.add_argument('--checkpoint',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--synthetic',action='store_true')
    parser.add_argument('--scenario')
    parser.add_argument('--reason')
    parser.add_argument('--split',choices=('development','heldout'),default='development')
    parser.add_argument('--adaptation-mode',choices=('off','shadow','active-development'),default='active-development')
    parser.add_argument('--cue-candidate',help='Scoped CCE candidate identifier')
    parser.add_argument('--cue-review',help='Operator review reference for cue approval or revocation')
    parser.add_argument('--cue-generation',type=int,help='Expected CCE route generation from cce-route')
    parser.add_argument('--cue-valid-for',type=float,default=86400,help='CCE approval lifetime in seconds (at most seven days)')
    parser.add_argument('--cue-model',help='Installed local model name for CCE research')
    parser.add_argument('--cue-model-digest',help='Expected local model manifest SHA256')
    parser.add_argument('--allow-local-inference',action='store_true',help='Allow four bounded local CCE smoke calls')
    parser.add_argument('--profile')
    parser.add_argument('--task',type=Path)
    parser.add_argument('--review',type=Path,help='Independent host review record for cohort admission')
    parser.add_argument('--source',type=Path,help='Local Python file for the read-only ARC inventory workflow')
    parser.add_argument('--report',type=Path,help='ARC benchmark report destination')
    parser.add_argument('--decision-id')
    parser.add_argument('--manifest-id')
    parser.add_argument('--review-ref')
    parser.add_argument('--observed-status',choices=('succeeded','failed','cancelled'))
    parser.add_argument('--arc-mode',choices=('off','shadow','enforce'),default='shadow')
    parser.add_argument('--context',default='inventory')
    parser.add_argument('--canary-limit',type=int,default=5)
    parser.add_argument('--candidate-budget',type=int,default=3)
    parser.add_argument('--restart',action='store_true')
    parser.add_argument('--state',type=Path,default=STATE)
    parser.add_argument('--task-id')
    parser.add_argument('--study-id',help='Accepted audit study to monitor in shadow mode')
    parser.add_argument('--cohort',choices=('v1','v2','v3'),help='Repository task cohort; default selects fresh evidence automatically')
    parser.add_argument('--review-target',choices=('handoff','repository-experiments','repository-taskbench','repository-runner'),default='handoff')
    args=parser.parse_args()
    requested_profile=args.profile
    if args.command.startswith(('arc-','adaptation-','research-fast-memory-')):
        if args.command.startswith('arc-'):
            from nerve_awim.arc_cli import dispatch
        else:
            from nerve_awim.adaptation_cli import dispatch
        with host_lock(args.state):
            try:
                result=dispatch(args)
            except (ValueError,PermissionError,RuntimeError,LookupError) as error:
                # Provider errors and evidence payloads do not enter ordinary CLI logs.
                result={'status':'blocked','reason_category':type(error).__name__,
                        'guidance':'Inspect the scoped episode or command arguments; no fallback execution was attempted.'}
                print(json.dumps(result,indent=2))
                raise SystemExit(2)
            print(json.dumps(result,indent=2))
        return
    if args.command.startswith('cce-'):
        from nerve_awim.cue_host import CueHost
        with host_lock(args.state):
            host=AgentOSLearning(args.state)
            cues=CueHost(host)
            if args.command=='cce-demo':
                from nerve_awim.cue_cli import demo
                result=demo()
            elif args.command in ('cce-local-inspect','cce-local-smoke'):
                if not args.cue_model or not args.cue_model_digest:
                    parser.error('local CCE research requires --cue-model and --cue-model-digest')
                execute=args.command=='cce-local-smoke'
                if execute and not args.allow_local_inference:
                    parser.error('local smoke requires --allow-local-inference')
                from nerve_awim.cue_ollama import OllamaCueAdapter
                from nerve_awim.cue_local import run_local_smoke
                adapter=OllamaCueAdapter(args.cue_model,args.cue_model_digest,
                    enabled=execute,permission_granted=execute,max_calls=4,max_output_tokens=32)
                result=run_local_smoke(adapter) if execute else adapter.inspect()
                atomic_json(host.directory/(args.command+'.json'),result)
            elif args.command=='cce-status':
                result=cues.status(args.profile)
            elif args.command=='cce-profile':
                if not args.profile:
                    parser.error('CCE profile inspection requires --profile')
                result=native(host,args.profile,'',inspect=True,inspect_profile=True)
                atomic_json(host.directory/'cce-last-profile.json',result)
            elif args.command=='cce-route':
                if not args.profile:
                    parser.error('CCE route inspection requires --profile')
                result=cues.route_status(args.profile)
            elif args.command=='cce-dataset-status':
                if not args.profile:
                    parser.error('CCE dataset status requires --profile')
                result=cues.dataset_status(args.profile)
            else:
                if not args.profile or not args.cue_candidate:
                    parser.error('CCE candidate commands require --profile and --cue-candidate')
                if args.command=='cce-revoke':
                    if not args.cue_review:
                        parser.error('CCE revocation requires --cue-review')
                    result=cues.revoke(args.profile,args.cue_candidate,reason=args.cue_review)
                elif args.command=='cce-approve':
                    if not args.cue_review or args.cue_generation is None:
                        parser.error('CCE approval requires --cue-review and --cue-generation')
                    result=cues.approve(args.profile,args.cue_candidate,
                        expected_generation=args.cue_generation,reason=args.cue_review,
                        valid_for=args.cue_valid_for)
                elif args.command=='cce-readiness':
                    result=cues.readiness(args.profile,args.cue_candidate)
                    atomic_json(host.directory/'cce-last-readiness.json',result)
                else:
                    result=cues.inspect(args.profile,args.cue_candidate)
            atomic_json(host.directory/'cce-status.json',cues.status())
            print(json.dumps(result,indent=2))
        return
    args.profile=args.profile or ('backend-engineer' if args.command.startswith('repository-') or args.command=='cycle' else 'qa-release')
    with host_lock(args.state):
        host=AgentOSLearning(args.state)
        recover_interrupted_repository(host)
        if args.command.startswith('autoresearch-'):
            import agentos_autoresearch as autoresearch
            try:
                if args.command in ('autoresearch-enable','autoresearch-pause'):
                    result=autoresearch.configure(host,args.command=='autoresearch-enable',profile=requested_profile)
                elif args.command=='autoresearch-tick':
                    result=autoresearch.tick(host,native)
                elif args.command=='autoresearch-submit':
                    if args.task is None:
                        raise ValueError('autoresearch-submit requires --task with fresh host-owned simulated evidence')
                    from agentos_audit_bench import read_json
                    result=autoresearch.submit(host,read_json(args.task))
                elif args.command=='autoresearch-register-cohort':
                    if args.task is None or args.review is None:
                        raise ValueError('cohort registration requires --task and --review')
                    from agentos_audit_bench import read_json
                    result=autoresearch.registry.admit(host,read_json(args.task),read_json(args.review),profile=args.profile)
                else:
                    result=autoresearch.status(host)
            finally:
                publish(host)
        elif args.command in ('audit-shadow','audit-shadow-status'):
            import agentos_audit_shadow as shadow
            try:
                if args.command=='audit-shadow':
                    if args.task is None:
                        raise ValueError('audit-shadow requires --task with fresh host-owned simulated evidence')
                    from agentos_audit_bench import read_json
                    result=shadow.monitor(host,native,read_json(args.task),study_id=args.study_id)
                else:
                    result=shadow.status(host)
            finally:
                publish(host)
        elif args.command in ('audit-study','audit-status'):
            import agentos_audit_study as audit
            try:
                result=audit.study(host,native,args.profile) if args.command=='audit-study' else audit.status(host)
            finally:
                publish(host)
        elif args.command=='repository-diagnose':
            result=repository_diagnosis(host)
            publish(host)
        elif args.command in ('repository-study','repository-run','repository-tasks'):
            import agentos_repository as repair
            try:
                if args.command=='repository-study':
                    result=repair.study(host,native,args.profile,VAULT,progress=lambda:publish(host),cohort=args.cohort)
                elif args.command=='repository-run':
                    result=repair.run(host,native,args.profile,args.task_id,cohort=args.cohort)
                else:
                    result=repair.registered_tasks(args.cohort)
            finally:
                publish(host)
        elif args.command=='study':
            try:
                result=study(host,args.profile)
            except Exception as error:
                publish(host,{'last_error':str(error)[:180]})
                raise
            publish(host)
        elif args.command=='cycle':
            collected=collect_missions(host)
            import agentos_autoresearch as autoresearch
            research_status=autoresearch.status(host)
            research_enabled=research_status.get('enabled',False)
            if research_enabled:
                autoresearch.tick(host,native)
            elif not research_status.get('configured',False):
                retry_pending_audit(host)
            with sqlite3.connect(host.path) as db:
                failures=db.execute('SELECT COUNT(*) FROM nerve_missions WHERE success=0').fetchone()[0]
            gate=host.directory/'auto-study.json'
            previous=json.loads(gate.read_text()) if gate.exists() else {}
            today=datetime.now(timezone.utc).strftime('%Y-%m-%d')
            pending_path=host.directory/'pending-repository-study.json'
            pending=json.loads(pending_path.read_text()) if pending_path.exists() else {}
            pending_due=bool(pending) and pending.get('requested_day')!=today
            if not research_enabled and (pending_due or (failures-previous.get('failures',0)>=3 and previous.get('day')!=today)):
                atomic_json(gate,{'day':today,'failures':failures,'status':'started'})
                try:
                    import agentos_repository as repair
                    learned=repair.study(host,native,pending['profile'] if pending_due else args.profile,
                        VAULT,progress=lambda:publish(host),cohort=pending.get('cohort') if pending_due else None)
                    atomic_json(gate,{'day':today,'failures':failures,'status':learned['result']['status']})
                except Exception as error:
                    if pending_due:
                        pending_path.unlink(missing_ok=True)
                    atomic_json(gate,{'day':today,'failures':failures,'status':'failed','error':str(error)[:180]})
            last_attempt=json.loads(gate.read_text()) if gate.exists() else {}
            result=publish(host,{'collection':collected,
                'last_error':last_attempt.get('error','') if last_attempt.get('status')=='failed' else ''})
        elif args.command in ('probe','run'):
            task=json.loads(args.task.read_text()) if args.task else examples('native-probe-'+uuid.uuid4().hex,'train',1)[0].task
            expected_handoff(task)
            memories=host.recall(args.profile)
            selected=memories[0] if memories else None
            values, info=batch(host,args.profile,[task],selected.content if selected else None,
                **({'cue_context':'handoff'} if args.command=='run' else {}))
            result={**info,'output':values[task['id']], 'evaluation':host.observe(args.profile,task,
                values[task['id']],lesson=selected.memory_id if selected else None,
                mode='live' if args.command=='run' else 'probe')}
            cue_receipt=info.get('cce')
            if (type(cue_receipt) is dict and cue_receipt.get('selected') is True
                    and not result['evaluation'].get('duplicate', False)):
                from nerve_awim.cue_host import CueHost
                judged=judge_handoff(task,values[task['id']])
                cue_host=CueHost(host)
                feedback=cue_host.feedback(args.profile,cue_receipt['approval_id'],
                    episode_id=task['id'],safe=judged,correct=judged)
                result['cce_feedback']={'status':feedback['status'],
                    'memory_id':cue_host.export_memory(args.profile,cue_receipt['approval_id'])}
            atomic_json(host.directory/'latest-native.json',result)
            publish(host)
        elif args.command=='recall':
            result=[{'id':r.memory_id,'content':r.content} for r in host.recall(args.profile)]
        elif args.command=='jev-review':
            result=jev_review(host)
        elif args.command=='claude-review':
            reviewer=ClaudeReviewer(host.directory/'claude-review.sqlite3',claude_key())
            targets={'handoff':'src/nerve_awim/agentos_learning.py',
                     'repository-experiments':'src/nerve_awim/agentos_experiments.py',
                     'repository-taskbench':'src/nerve_awim/agentos_taskbench.py',
                     'repository-runner':'scripts/agentos_repository.py'}
            code=(REPO/targets[args.review_target]).read_text()
            if len(code.encode())>22000:
                raise ValueError('review target exceeds bounded review context')
            try:
                review=reviewer.complete('Review this public NERVE implementation for concrete correctness problems. '
                    'Prioritize reward integrity, temporal leakage, forgetting, concurrency and honest claims. '
                    'Return concise actionable findings. No tools are available.',code)
                result={'review':review,'target':targets[args.review_target],
                        'advisory_only':True,'budget':reviewer.report()}
                atomic_json(host.directory/'claude-review.json',result)
            finally:
                publish(host)
        elif args.command=='sync-gbrain':
            publish(host)
            content=(VAULT/'Memory/nerve-status.md').read_text()
            cmd=[str(HOME/'.bun/bin/gbrain'),'put','nerve-agentos-learning']
            done=subprocess.run(cmd,input=content,text=True,capture_output=True,timeout=30)
            result={'ok':done.returncode==0,'slug':'nerve-agentos-learning'}
            atomic_json(host.directory/'gbrain-receipt.json',result)
        else:
            result=publish(host)
        print(json.dumps(result,indent=2))


if __name__=='__main__':
    try:
        main()
    except BlockingIOError:
        print(json.dumps({'status':'busy','reason':'Another NERVE operation holds the host lock; scheduled cycles retry later.'}))
