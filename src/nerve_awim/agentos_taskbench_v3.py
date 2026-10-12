"""Operational evidence cohort: adapted scenarios, not historical production fixes.

Evidence supplied by local investigation, 2026-10-12:
* ~/AgentOS-Vault/scripts/agent-os-maintenance-mission.py: unfinished tasks
  gate later missions; empty mission directories do not establish task creation.
* maintenance board task_runs: Oct3 QA timed_out248s at240s limit, reclaimed,
  then done; Oct5 scheduling auditor timed_out243s then exhausted its retry.
* Oct5 auditor log: repeated manual schedule counts, interrupted before writing
  scheduling.json; dependent QA/coordinator remain todo.

These observations motivate distinct join/timing/state policies, not eleven
independent incidents. Fixtures inject faults into newly implemented read-only
report policies. Final families test retry-chain aggregation, mission receipt
completeness and prerequisite release. Sharing the operational domain limits
claims of statistical independence or transfer to arbitrary maintenance tasks.
"""
from hashlib import sha256
from pathlib import Path
from .agentos_taskbench import RepairTask, _function, _BUILTINS, _ATTRS


def dataset(repo_root=None):
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[2]
    specs = [
        ('train', 'latest_run_by_task',
         "(run['started_at'], run['id']) > (old['started_at'], old['id'])", "(run['started_at'], run['id']) < (old['started_at'], old['id'])",
         'Normalize evidence: retain latest run per task by greatest (started_at,id), irrespective of input order. Skip records lacking truthy task_id/id or EXACT int started_at (bool invalid); return copied run dictionaries keyed by task_id. Inputs otherwise normalized; never mutate them.',
         ("a=dict(task_id='t',id='a',started_at=10); b=dict(task_id='t',id='b',started_at=20); assert fn([b,a]) == {'t':b}",
          "a=dict(task_id='t',id='a',started_at=10); b=dict(task_id='t',id='b',started_at=10); assert fn([b,a]) == {'t':b}",
          "assert fn([dict(task_id='t',id='x',started_at=True), {}, dict(task_id='t',id='x')]) == {}",
          "r=dict(task_id='t',id='x',started_at=0); out=fn([r]); out['t']['id']='z'; assert r['id']=='x'",
          "assert set(fn([dict(task_id=x,id=x,started_at=0) for x in ('a','b')])) == {'a','b'}", "assert fn([]) == {}")),
        ('train', 'schedule_inventory',
         "if job.get('enabled') is not True:", "if not job.get('enabled'):",
         'Count enabled normalized job records by kind cron/interval/once plus invalid. First occurrence of each nonempty exact-str id consumes identity even if disabled; each duplicate/missing/bad ID increments invalid. Only EXACT True enables a job. Unknown kind increments invalid only for enabled valid-ID jobs. Return all four integer counts; no mutations. kind is a normalized field supplied by the report adapter, not claimed to exist in raw jobs.json.',
         ("assert fn([dict(id='a',enabled=True,kind='cron'),dict(id='b',enabled=1,kind='once')]) == dict(cron=1,interval=0,once=0,invalid=0)",
          "assert fn([dict(id='a',enabled=False,kind='cron'),dict(id='a',enabled=True,kind='cron')])['invalid']==1",
          "assert fn([dict(id='a',enabled=True,kind='unknown'),dict(id='b',enabled=False,kind='bad')])['invalid']==1",
          "assert fn([{},dict(id=True),dict(id='')])['invalid']==3",
          "assert fn([dict(id=k,enabled=True,kind=k) for k in ('cron','interval','once')]) == dict(cron=1,interval=1,once=1,invalid=0)",
          "assert fn([])==dict(cron=0,interval=0,once=0,invalid=0)")),
        ('selection', 'timeout_diagnosis',
         'elapsed <= limit + tick_grace', 'elapsed <= limit',
         'Require exact int limit>0 and tick_grace>=0 else ValueError. Non-timed_out status returns not_timeout. For timed_out require exact int started_at/finished_at with finish>=start else missing_timing. Duration<limit is early_timeout; limit<=duration<=limit+tick_grace watchdog_window; above is late_watchdog. This is wall-clock evidence only, never provider-outage diagnosis.',
         ("assert fn(dict(status='timed_out',started_at=100,finished_at=343),240)=='watchdog_window'",
          "assert fn(dict(status='timed_out',started_at=0,finished_at=300),240)=='watchdog_window'",
          "assert fn(dict(status='timed_out',started_at=0,finished_at=301),240)=='late_watchdog'",
          "assert fn(dict(status='timed_out',started_at=0,finished_at=239),240)=='early_timeout'",
          "assert fn(dict(status='timed_out',started_at=0,finished_at=240),240,0)=='watchdog_window'",
          "assert fn(dict(status='timed_out',started_at=True,finished_at=240),240)=='missing_timing'",
          "assert fn(dict(status='timed_out',started_at=2,finished_at=1),240)=='missing_timing'",
          "assert fn(dict(status='done'),240)=='not_timeout'; raises(ValueError,fn,{},True); raises(ValueError,fn,{},240,-1)")),
        ('selection','dependency_readiness',
         "rows[x].get('status') != 'done'", "rows[x].get('status') not in ('done', 'review')",
         'Index normalized task rows by id. Return invalid for non-list depends_on, non-string IDs, self-dependency, or duplicate task rows referenced as dependencies. Return missing for any absent dependency; waiting unless every dependency status is exactly done (review and archived are NOT done; this evidence gate is deliberately stricter than Hermes scheduler archived release); otherwise ready. Absent depends_on means empty. Missing takes precedence over waiting; invalid precedes missing.',
         ("assert fn(dict(id='t',depends_on=['a']),[dict(id='a',status='review')])=='waiting'",
          "assert fn(dict(id='t',depends_on=['a']),[dict(id='a',status='done')])=='ready'",
          "assert fn(dict(id='t',depends_on=['a','b']),[dict(id='a',status='blocked')])=='missing'",
          "assert fn(dict(id='t',depends_on=['a']),[dict(id='a',status='done')]*2)=='invalid'",
          "assert fn(dict(id='t',depends_on=['t']),[])=='invalid'; assert fn(dict(id='t',depends_on='a'),[])=='invalid'",
          "assert fn(dict(id='t'),[])=='ready'; assert fn(dict(id='t',depends_on=[True]),[])=='invalid'",
          "for status in ('mystery','archived'):\n assert fn(dict(id='t',depends_on=['a']),[dict(id='a',status=status)])=='waiting'")),
        ('selection','retry_disposition',
         "failures >= maximum", "failures > maximum",
         'Recommend only: validate exact int max_consecutive_failures>=1, consecutive_failures>=0, now, cooldown>=0 else invalid. Filter runs by task_id; none=>no_attempt; missing truthy id/exact int started_at=>unknown. Latest by (started_at,id): running/claimed=>active, done=>complete, statuses other than timed_out/failed/reclaimed=>unknown. For retryable latest status, task.consecutive_failures >=max_consecutive_failures=>exhausted. Then require exact int finished_at<=now else unknown; elapsed<cooldown=>cooldown else eligible. Exhaustion precedes timestamp validation; lifetime attempt count never establishes consecutive failures.',
         ("r=dict(task_id='t',id='a',started_at=0,finished_at=240,status='timed_out'); assert fn(dict(id='t',max_consecutive_failures=1,consecutive_failures=1),[r],300,0)=='exhausted'",
          "r=dict(task_id='t',id='a',started_at=0,finished_at=240,status='timed_out'); assert fn(dict(id='t',max_consecutive_failures=2,consecutive_failures=1),[r,r],300,60)=='eligible'",
          "r=dict(task_id='t',id='a',started_at=0,finished_at=240,status='timed_out'); assert fn(dict(id='t',max_consecutive_failures=2,consecutive_failures=1),[r],299,60)=='cooldown'",
          "r=dict(task_id='t',id='a',started_at=0,finished_at=301,status='failed'); assert fn(dict(id='t',max_consecutive_failures=2,consecutive_failures=1),[r],300,0)=='unknown'",
          "assert fn(dict(id='t',max_consecutive_failures=True,consecutive_failures=1),[],0,0)=='invalid'; assert fn(dict(id='t',max_consecutive_failures=2,consecutive_failures=1),[],0,0)=='no_attempt'",
          "for status, expected in [('done','complete'),('running','active'),('claimed','active'),('mystery','unknown')]:\n assert fn(dict(id='t',max_consecutive_failures=1,consecutive_failures=1),[dict(task_id='t',id='a',started_at=0,status=status)],0,0)==expected",
          "assert fn(dict(id='t',max_consecutive_failures=2,consecutive_failures=1),[dict(task_id='t',id='a',started_at=True,status='failed')],0,0)=='unknown'",
          "r=[dict(task_id='t',id=str(i),started_at=i,finished_at=i+1,status='failed') for i in range(5)]; assert fn(dict(id='t',max_consecutive_failures=2,consecutive_failures=1),r,100,0)=='eligible'",
          "for f in (True,-1,None):\n assert fn(dict(id='t',max_consecutive_failures=2,consecutive_failures=f),[],0,0)=='invalid'")),
        ('retention','artifact_receipt_status',
         "receipt.get('run_id') != run.get('id') or receipt.get('task_id') != task.get('id')", "receipt.get('run_id') != run.get('id') and receipt.get('task_id') != task.get('id')",
         'Ordered diagnostic: absent run or run.task_id!=task.id=>unknown_run; absent receipt=>missing; receipt run_id/task_id must BOTH match=>wrong_attempt otherwise; exact int written_at/started_at with written>=start else stale; receipt.path must equal truthy task.expected_artifact else wrong_path; validated must be EXACT True else unverified; otherwise verified. Treat receipts as report evidence, not actual filesystem verification.',
         ("t=dict(id='t',expected_artifact='scheduling.json'); r=dict(id='r',task_id='t',started_at=10); p=dict(run_id='old',task_id='t',written_at=10,path='scheduling.json',validated=True); assert fn(t,r,p)=='wrong_attempt'",
          "t=dict(id='t',expected_artifact='a'); r=dict(id='r',task_id='t',started_at=10); p=dict(run_id='r',task_id='other',written_at=10,path='a',validated=True); assert fn(t,r,p)=='wrong_attempt'",
          "t=dict(id='t',expected_artifact='a'); r=dict(id='r',task_id='t',started_at=10); p=dict(run_id='r',task_id='t',written_at=10,path='a',validated=True); assert fn(t,r,p)=='verified'; p['written_at']=9; assert fn(t,r,p)=='stale'",
          "t=dict(id='t',expected_artifact='a'); r=dict(id='r',task_id='t',started_at=10); p=dict(run_id='r',task_id='t',written_at=10,path='b',validated=True); assert fn(t,r,p)=='wrong_path'; p['path']='a'; p['validated']=1; assert fn(t,r,p)=='unverified'",
          "assert fn(dict(id='t'),None,None)=='unknown_run'; assert fn(dict(id='t'),dict(task_id='t'),None)=='missing'")),
        ('retention','mission_admission',
         "'review', 'claimed', 'triage'", "'review', 'claimed'",
         'If existing_mission is non-None with truthy task_ids return already_created. Mere existing empty directory is not a mission. Active statuses ready/running/todo/blocked/review/claimed/triage/scheduled block admission; terminal done/cancelled/failed/archived allow it. Any unknown/missing status returns unknown_state BEFORE blocked. Return eligible if neither. Read-only proposal; no directory creation.',
         ("assert fn([dict(status='triage')],None)=='blocked'",
          "for s in ('ready','running','todo','blocked','review','claimed','scheduled'):\n assert fn([dict(status=s)],None)=='blocked'",
          "assert fn([dict(status=s) for s in ('done','cancelled','failed','archived')],{})=='eligible'",
          "assert fn([],dict(task_ids=['t']))=='already_created'; assert fn([],dict(task_ids=[]))=='eligible'",
          "assert fn([dict(status='blocked'),dict(status='unexpected')],None)=='unknown_state'; assert fn([{}],None)=='unknown_state'")),
        ('retention','stale_claims',
         "r.get('id') == task.get('run_id') and r.get('task_id') == task.get('id')", "r.get('task_id') == task.get('id')",
         'Require exact int now and lease>0 else ValueError. For each running/claimed task join runs by BOTH task.run_id==run.id and task.id==run.task_id. Exactly one matching active running/claimed run is required. Its exact-int heartbeat must be 0..now and older than lease STRICTLY. Return sorted unique stale task IDs. Ignore missing/ambiguous/inactive/future/invalid heartbeats; do not reclaim tasks.',
         ("t=dict(id='t',run_id='new',status='running'); r=dict(id='old',task_id='t',status='running',heartbeat_at=0); assert fn([t],[r],100,60)==[]",
          "t=dict(id='t',run_id='r',status='claimed'); r=dict(id='r',task_id='t',status='running',heartbeat_at=0); assert fn([t],[r],61,60)==['t']; assert fn([t],[r],60,60)==[]",
          "t=dict(id='t',run_id='r',status='running'); r=dict(id='r',task_id='t',status='running',heartbeat_at=0); assert fn([t],[r,r],100,60)==[]",
          "t=dict(id='t',run_id='r',status='running');\nfor h in (True,-1,101,None):\n assert fn([t],[dict(id='r',task_id='t',status='running',heartbeat_at=h)],100,60)==[]",
          "assert fn([],[],0,1)==[]; raises(ValueError,fn,[],[],True,1); raises(ValueError,fn,[],[],0,0)")),
        ('final','retry_chain_summary',
         "last == 'done' and timeouts", "last == 'done' or timeouts",
         'Filter runs to task_id; collapse identical records by truthy id. Missing id/non-exact-int start=>{state:unknown,attempts:0,timeouts:0}; conflicting duplicate=>{state:ambiguous,attempts:number unique before conflict,timeouts:0}. Empty=>unknown/0/0. Sort unique attempts by(started_at,id); count timed_out. State recovered only if LAST status done AND any timeouts; complete if last done without timeouts; otherwise unresolved. Return state,attempts,timeouts.',
         ("r=[dict(id='a',task_id='t',started_at=0,status='timed_out'),dict(id='b',task_id='t',started_at=1,status='failed')]; assert fn('t',r)==dict(state='unresolved',attempts=2,timeouts=1)",
          "r=[dict(id='a',task_id='t',started_at=0,status='timed_out'),dict(id='b',task_id='t',started_at=1,status='done')]; assert fn('t',r[::-1])==dict(state='recovered',attempts=2,timeouts=1)",
          "r=dict(id='a',task_id='t',started_at=0,status='done'); assert fn('t',[r,r])==dict(state='complete',attempts=1,timeouts=0)",
          "a=dict(id='a',task_id='t',started_at=0,status='failed'); b=dict(a); b['status']='done'; assert fn('t',[a,b])==dict(state='ambiguous',attempts=1,timeouts=0)",
          "assert fn('t',[])==dict(state='unknown',attempts=0,timeouts=0); assert fn('t',[dict(id='a',task_id='t',started_at=True)])['state']=='unknown'",
          "assert fn('t',[dict(id='a',task_id='other',started_at=0,status='done')])['attempts']==0")),
        ('final','mission_terminal_state',
         "r.get('task_id') == task['id'] and r.get('run_id') == task.get('run_id') and r.get('validated') is True", "r.get('task_id') == task['id'] and r.get('validated') is True",
         'Mission task IDs must be nonempty and unique. Join tasks by ID, require exactly one row per member else unknown; ignore outsiders. Any failed/cancelled member=>failed; otherwise any status not done=>incomplete. For every done member require truthy run_id and exactly ONE receipt joining its task_id AND current run_id with validated EXACT True else unverified. All pass=>verified_complete. Extra unvalidated/wrong-attempt receipts are ignored; no filesystem claim.',
         ("t=dict(id='t',status='done',run_id='new'); p=dict(task_id='t',run_id='old',validated=True); assert fn(['t'],[t],[p])=='unverified'",
          "t=dict(id='t',status='done',run_id='r'); p=dict(task_id='t',run_id='r',validated=True); assert fn(['t'],[t],[p])=='verified_complete'; assert fn(['t'],[t],[p,p])=='unverified'",
          "assert fn([],[],[])=='unknown'; assert fn(['t','t'],[],[])=='unknown'; assert fn(['t'],[],[])=='unknown'",
          "t=dict(id='t',status='done',run_id='r'); assert fn(['t'],[t,t],[])=='unknown'; assert fn(['t','u'],[dict(id='t',status='done'),dict(id='u',status='failed')],[])=='failed'",
          "assert fn(['t'],[dict(id='t',status='review')],[])=='incomplete'; assert fn(['t'],[dict(id='t',status='done',run_id='r')],[dict(task_id='t',run_id='r',validated=1)])=='unverified'")),
        ('final','successor_release',
         "if len(proofs) != 1:", "if len(proofs) > 1:",
         'For every depends_on ID, require exactly one matching task row with status done and truthy run_id; then exactly one receipt matching BOTH prerequisite task ID and its CURRENT run ID, validated EXACT True. Missing, stale, duplicate or unverified proofs leave prerequisite unmet. Return sorted unique unmet IDs; absent depends_on=>empty. Inputs normalized string/list schemas. Read-only dependency proposal, never change status.',
         ("t=dict(depends_on=['a']); a=dict(id='a',status='done',run_id='r'); assert fn(t,[a],[])==['a']",
          "t=dict(depends_on=['a']); a=dict(id='a',status='done',run_id='r'); p=dict(task_id='a',run_id='r',validated=True); assert fn(t,[a],[p])==[]; assert fn(t,[a],[p,p])==['a']",
          "assert fn(dict(depends_on=['z','a','z']),[],[])==['a','z']; assert fn({},[],[])==[]",
          "t=dict(depends_on=['a']); a=dict(id='a',status='done',run_id='new'); p=dict(task_id='a',run_id='old',validated=True); assert fn(t,[a],[p])==['a']",
          "t=dict(depends_on=['a']); a=dict(id='a',status='done',run_id='r'); p=dict(task_id='a',run_id='r',validated=1); assert fn(t,[a],[p])==['a']; assert fn(t,[a,a],[])==['a']")),
    ]
    splits = {phase: [] for phase in ('train','selection','retention','final')}
    module = 'agentos_maintenance_policy.py'
    for phase,name,old,new,requirements,checks in specs:
        original = _function(root,module,name)
        if original.count(old) != 1:
            raise ValueError('policy source changed; re-review v3 mutation: '+name)
        family = 'maintenance-evidence:'+name
        public = dict(id='repair-'+sha256(family.encode()).hexdigest()[:12], family=family,
                      source=original.replace(old,new,1), function=name,
                      requirements=requirements+' Return JSON {"code":"..."} with exactly one replacement function and the same signature. No imports, decorators, annotations, nested functions, global/nonlocal, file/network access, introspection or print. Safe builtins: '+','.join(_BUILTINS)+'. Allowed attributes: '+','.join(sorted(_ATTRS))+'. Hidden checks run in an isolated process.',
                      revision=sha256((module+original).encode()).hexdigest())
        splits[phase].append(RepairTask(public,original,'',tuple(checks)))
    return splits
