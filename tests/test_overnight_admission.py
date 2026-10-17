"""Admission failures must precede session creation or any remote dispatch."""
import hashlib
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import overnight_cycle as cycle
import overnight_cycle_preflight as preflight


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


@pytest.fixture
def admitted(tmp_path):
    root=tmp_path/'repo'; shared=tmp_path/'shared'; shared.mkdir()
    source={}
    for name in ('scripts/overnight_cycle.py','scripts/overnight_cycle_preflight.py'):
        path=root/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_text('# tested\n')
        source[name]=preflight.hashed(path)
    checks=dict(tests_passed=True,source_sha256=source)
    for name in ('log','receipt'):
        path=root/(name+'.json'); write(path,{'passed':True})
        checks[name]=path.name; checks[name+'_sha256']=preflight.hashed(path)
    write(root/'research/overnight-20261017/cycle-readiness.json',checks)
    event=dict(event='preflight_ok',pod_id='p',issued_by='operator',digest='d',replay_hash='a'*64)
    (shared/'ledger.jsonl').write_text(json.dumps(event)+'\n')
    write(shared/'pod-B.lock',dict(pod_id='p'))
    authorization=dict(preflight_event_sha256=hashlib.sha256(json.dumps(event,sort_keys=True,separators=(',',':')).encode()).hexdigest())
    return root,shared,authorization,dict(pod_id='p'),'d'


def test_matching_operator_preflight_and_test_evidence(admitted):
    assert preflight.require_cycle_admission(*admitted)==admitted[2]['preflight_event_sha256']


@pytest.mark.parametrize('change,error',[
    ('ledger','current_preflight_ok_missing'),('binding','current_preflight_binding_required'),
    ('source','cycle_focused_evidence_stale'),('receipt','cycle_focused_evidence_tampered'),
    ('log','cycle_focused_evidence_tampered'),('lock','admitted_pod_lock_required'),
    ('later_failure','preflight_superseded_by_failure'),
])
def test_refusal_boundaries(admitted,change,error):
    root,shared,auth,connection,model=admitted
    if change=='ledger': (shared/'ledger.jsonl').write_text('{"event":"preflight_failed"}\n')
    elif change=='binding': auth['preflight_event_sha256']='b'*64
    elif change=='source': (root/'scripts/overnight_cycle.py').write_text('# changed')
    elif change in ('receipt','log'): (root/(change+'.json')).write_text('{}')
    elif change=='lock': write(shared/'pod-B.lock',dict(pod_id='other'))
    elif change=='later_failure':
        with (shared/'ledger.jsonl').open('a') as f: f.write(json.dumps(dict(event='preflight_failed',pod_id='p'))+'\n')
    with pytest.raises(ValueError,match=error): preflight.require_cycle_admission(*admitted)


def test_session_checks_admission_before_creating_session(tmp_path,monkeypatch):
    shared=tmp_path/'shared';shared.mkdir(); private=tmp_path/'private'
    auth=dict(authorized=True,identity_replay_passed=True,model_digest=cycle.MODEL,
              connection={'pod_id':'p'},program_sha256='program')
    write(shared/'W2-cycle-resume-authorization.json',auth)
    monkeypatch.setattr(cycle,'SHARED',shared);monkeypatch.setattr(cycle,'PRIVATE',private)
    monkeypatch.setattr(cycle,'hashfile',lambda _: 'program')
    monkeypatch.setattr(cycle,'validate_connection',lambda _: 'p')
    def reject(*args): raise ValueError('current_preflight_ok_missing')
    monkeypatch.setattr(preflight,'require_cycle_admission',reject)
    with pytest.raises(ValueError,match='current_preflight_ok_missing'): cycle.session({'pod_id':'p'})
    assert not private.exists()
