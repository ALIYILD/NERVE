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
