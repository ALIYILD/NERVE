import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import overnight_cycle as cycle
from nerve_awim.memory_gateway import overnight_cycle_candidates as candidate


def test_stratified_selection_and_exhaustion():
    tasks=[cycle.bank5.item(bytes(32),'dev',s,i) for s in cycle.bank5.STRATA for i in range(25)]
    chosen=cycle.select(tasks,42,set())
    assert len(chosen)==100 and len({t['task_id'] for t in chosen})==100
    assert len({t['stratum'] for t in chosen})==9
    second=cycle.select(tasks,43,{t['task_id'] for t in chosen})
    assert not {t['task_id'] for t in chosen}&{t['task_id'] for t in second}
    with pytest.raises(ValueError,match='fresh_dev_exhausted'):
        cycle.select(tasks,44,{t['task_id'] for t in chosen+second})


def test_canonical_a_not_relabelled_as_b():
    task=cycle.bank3.item(bytes(32),'dev','supported-measurement',0)
    a=candidate.prepare(candidate.initial('A'),task['query'],task['evidence'])
    b=candidate.prepare(candidate.mutate(candidate.initial('A'),'routing'),task['query'],task['evidence'])
    assert a['kind']=='a3'
    assert b['kind']=='b4'
    assert a['prepared']['route']=='deterministic_abstention'
    assert b['prepared']['route']=='model'


def test_frozen_v5_safety_and_controls_across_strata():
    config=candidate.mutate(candidate.initial('B'),'extraction-schema')
    rows=[]
    for s in cycle.bank5.STRATA:
        for i in range(12):
            t=cycle.bank5.item(bytes(32),'dev',s,i)
            p=candidate.prepare(config,t['query'],t['evidence'])
            assert cycle.payload(p) is None
            row,score,_=cycle.judge(t,config,config,dict(candidate='ABSTAIN',incumbent='ABSTAIN'))
            assert score['strict_correct']
            assert not row['safety_error']
            rows.append(row)
    assert sum(r['candidate'] for r in rows)>sum(r['always-abstain'] for r in rows)


def test_safety_gate_and_loss_bound():
    rows=[dict(task_id=str(i),candidate=True,incumbent=False,safety_error=False,
               **{'always-abstain':False,'random':False}) for i in range(100)]
    assert cycle.transport.engine.decide(rows)['kept']
    rows[0]['safety_error']=True
    assert not cycle.transport.engine.decide(rows)['kept']
    rows[0]['safety_error']=False
    for row in rows[:2]:row.update(candidate=False,incumbent=True)
    assert not cycle.transport.engine.decide(rows)['kept']


def test_immutable_registration_refuses_overwrite(tmp_path):
    p=tmp_path/'registration.json'
    cycle.save(p,{'first':1})
    with pytest.raises(ValueError,match='immutable_record_changed'):
        cycle.save(p,{'first':2})


def test_replay_detects_row_tampering(tmp_path, monkeypatch):
    config=candidate.mutate(candidate.initial('B'),'extraction-schema')
    tasks=[cycle.bank5.item(bytes(32),'dev','supported-measurement',i) for i in range(100)]
    cycle.save(tmp_path/'tasks.json',tasks)
    cycle.save(tmp_path/'registration.json',dict(candidate=config,incumbent=config,
        tasks_sha256=cycle.hashfile(tmp_path/'tasks.json'),source_sha256={},protected_sha256={}))
    monkeypatch.setattr(cycle,'assert_protected',lambda _:None)
    for i,t in enumerate(tasks):
        row,_,_=cycle.judge(t,config,config,dict(candidate='ABSTAIN',incumbent='ABSTAIN'))
        cycle.save(tmp_path/f'row-{i:03}.json',row)
    rows,result=cycle.replay(tmp_path)
    assert result['replay_verified'] and not result['kept']
    assert result['wins']==result['losses']==0
    p=tmp_path/'row-000.json';changed=json.loads(p.read_text());changed['candidate']=False
    p.write_text(json.dumps(changed))
    with pytest.raises(ValueError,match='row_replay_mismatch'):
        cycle.replay(tmp_path)


def test_call_caps_claim_before_dispatch(tmp_path, monkeypatch):
    monkeypatch.setattr(cycle,'PRIVATE',tmp_path)
    monkeypatch.setattr(cycle,'AUTH',None)
    for i in range(40):cycle.reserve_call('jev','a'*64)
    with pytest.raises(ValueError,match='jev_cap'):
        cycle.reserve_call('jev','a'*64)
    assert len(list((tmp_path/'calls').glob('*.json')))==40
    cycle.reserve_call('socratic','b'*64)


def test_global_revocation_blocks_before_any_session_side_effect(tmp_path, monkeypatch):
    shared=tmp_path/'shared';shared.mkdir()
    (shared/'inference-revoked.json').write_text('{}')
    private=tmp_path/'new-session'
    monkeypatch.setattr(cycle,'SHARED',shared)
    monkeypatch.setattr(cycle,'PRIVATE',private)
    with pytest.raises(ValueError,match='W0_inference_revoked_no_calls'):
        cycle.session({})
    assert not private.exists()


def test_hermes_identity_inspection_needs_no_live_audit(monkeypatch):
    from types import SimpleNamespace
    requests=[]
    def inspect_only(command, **kwargs):
        requests.append(json.loads(kwargs['input']))
        return SimpleNamespace(stdout=json.dumps({'configured_model':cycle.HERMES_MODEL,'provider':'anthropic'}))
    monkeypatch.setattr(cycle.subprocess,'run',inspect_only)
    assert cycle.hermes_identity('proposer')=={'configured_model':cycle.HERMES_MODEL,'provider':'anthropic'}
    assert requests[0]['inspect'] and requests[0]['inspect_profile']


def test_registered_fallback_worker_transport(monkeypatch, tmp_path):
    from types import SimpleNamespace
    connection=dict(host='194.68.245.122',port=22019,pod_id='lvojhtouu5gede',
                    remote_worker='/workspace/bank_v5_fallback_remote.py')
    monkeypatch.setattr(cycle,'POD',connection['pod_id'])
    monkeypatch.setattr(cycle,'PRIVATE',tmp_path)
    cycle.save(tmp_path/'session-registration.json',dict(connection=connection,remote_worker_sha256='a'*64,
               preflight_sha256='b'*64,protected={}))
    monkeypatch.setattr(cycle,'require_preflight',lambda *args: 'b'*64)
    monkeypatch.setattr(cycle,'assert_protected',lambda pins: None)
    commands=[]
    def fake_remote(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(stdout=json.dumps({'pod_id':connection['pod_id']}))
    monkeypatch.setattr(cycle.subprocess,'run',fake_remote)
    assert cycle.remote(connection,'identity')['pod_id']==connection['pod_id']
    assert commands[0][-3:]==['/workspace/bank_v5_fallback_remote.py','a'*64,'identity']
    assert 'root@194.68.245.122' in commands[0]
    for change in ({'pod_id':'other'},{'remote_worker':'/tmp/arbitrary.py'},
                   {'remote_worker':'/workspace/v5_remote_call.py'},{'port':True}):
        with pytest.raises(ValueError,match='pinned_pod_connection_required'):
            cycle.remote(dict(connection,**change),'identity')
    with pytest.raises(ValueError,match='worker_action_forbidden'):
        cycle.remote(connection,'bootstrap')
    assert len(commands)==1
    monkeypatch.setattr(cycle,'POD','5xndo7i7s5r9zn')
    with pytest.raises(ValueError,match='registered_pod_mismatch'):
        cycle.remote(connection,'identity')
    assert len(commands)==1



def test_remote_worker_hash_mismatch_executes_no_worker(tmp_path):
    import subprocess
    from hashlib import sha256
    marker=tmp_path/'model-call-marker'
    worker=tmp_path/'worker.py'
    good=("from pathlib import Path\nPath("+repr(str(marker))+").write_text('dispatched')\n").encode()
    worker.write_bytes(good)
    expected=sha256(good).hexdigest()
    worker.write_bytes(good+b"# changed remote source\n")
    command=[sys.executable,'-c',cycle.PINNED_WORKER_LAUNCHER,str(worker),expected,'call']
    refused=subprocess.run(command,text=True,capture_output=True)
    assert refused.returncode!=0 and 'remote_worker_hash_mismatch' in refused.stderr
    assert not marker.exists()  # No worker execution, hence no possible model dispatch.
    worker.write_bytes(good)
    allowed=subprocess.run(command,text=True,capture_output=True)
    assert allowed.returncode==0, allowed.stderr
    assert marker.read_text()=='dispatched'


def test_remote_connection_must_match_immutable_registration(tmp_path,monkeypatch):
    connection=dict(host='194.68.245.122',port=22019,pod_id='lvojhtouu5gede',
                    remote_worker='/workspace/bank_v5_fallback_remote.py')
    monkeypatch.setattr(cycle,'POD',connection['pod_id'])
    monkeypatch.setattr(cycle,'PRIVATE',tmp_path)
    cycle.save(tmp_path/'session-registration.json',dict(connection=connection,remote_worker_sha256='a'*64))
    def denied(*args,**kwargs):raise AssertionError('SSH must not run')
    monkeypatch.setattr(cycle.subprocess,'run',denied)
    with pytest.raises(ValueError,match='registered_connection_mismatch'):
        cycle.remote(dict(connection,port=22020),'call')


def test_preflight_requires_current_owner_pod_and_start(tmp_path,monkeypatch):
    monkeypatch.setattr(cycle,'SHARED',tmp_path)
    monkeypatch.setattr(cycle.time,'time',lambda: 200)
    (tmp_path/'coordinator-owner.json').write_text(json.dumps({'window':'W0-owner'}))
    ledger=tmp_path/'ledger.jsonl'
    auth={'pod_started_epoch':100,'expires_epoch':300}
    good=dict(event='preflight_ok',window='W0-owner',pod_id='pod-B',time='1970-01-01T00:02:30+00:00')
    for rows in ([],[dict(good,window='observer')],[dict(good,pod_id='other')]):
        ledger.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        with pytest.raises(ValueError,match='current_preflight_ok_required'):
            cycle.require_preflight(auth,'pod-B')
    ledger.write_text(json.dumps(dict(good,time='1970-01-01T00:00:30+00:00'))+'\n')
    with pytest.raises(ValueError,match='preflight_not_current_pod_start'):
        cycle.require_preflight(auth,'pod-B')
    ledger.write_text(json.dumps(good)+'\n')
    pin=cycle.require_preflight(auth,'pod-B')
    assert pin==cycle.digest(good)
    assert cycle.require_preflight(auth,'pod-B',pin)==pin
    with pytest.raises(ValueError,match='preflight_binding_changed'):
        cycle.require_preflight(auth,'pod-B','0'*64)
    ledger.write_text(json.dumps(good)+'\n'+json.dumps(dict(good,event='preflight_failed'))+'\n')
    with pytest.raises(ValueError,match='current_preflight_ok_required'):
        cycle.require_preflight(auth,'pod-B',pin)
    ledger.write_text(json.dumps(good)+'\n')
    (tmp_path/'inference-revoked.json').write_text('{}')
    with pytest.raises(ValueError,match='inference_revoked'):
        cycle.require_preflight(auth,'pod-B',pin)


def test_remote_identity_cannot_bypass_preflight(tmp_path,monkeypatch):
    connection=dict(host='194.68.245.122',port=22019,pod_id='lvojhtouu5gede',
                    remote_worker='/workspace/bank_v5_fallback_remote.py')
    monkeypatch.setattr(cycle,'PRIVATE',tmp_path)
    monkeypatch.setattr(cycle,'POD',connection['pod_id'])
    cycle.save(tmp_path/'session-registration.json',dict(connection=connection,remote_worker_sha256='a'*64,
               preflight_sha256='b'*64,protected={}))
    def refused(*args):raise ValueError('current_preflight_ok_required')
    monkeypatch.setattr(cycle,'require_preflight',refused)
    def no_ssh(*args,**kwargs):raise AssertionError('SSH must not run without admission')
    monkeypatch.setattr(cycle.subprocess,'run',no_ssh)
    with pytest.raises(ValueError,match='current_preflight_ok_required'):
        cycle.remote(connection,'identity')


def test_quarantine_keeps_historical_residuals_until_a_cycle_store_exists():
    incumbent=candidate.initial('A')
    historical=[dict(candidate_id='historical-v3',failure_class='incorrect_selection')]
    state=dict(n=1,incumbent=incumbent,experience={'data':{'episodes':historical}})
    assert cycle.incumbent_episodes(state)==historical
    current=dict(candidate_id=cycle.digest(incumbent),failure_class='incorrect_selection')
    rejected=dict(candidate_id='rejected-config',failure_class='none')
    state.update(cycle_experience=True,experience={'data':{'episodes':[current,rejected]}})
    assert cycle.incumbent_episodes(state)==[current]
