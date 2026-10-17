import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('claude_worker',ROOT/'scripts/overnight_hermes_worker.py')
worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
sys.path.insert(0,str(ROOT/'scripts'))
import overnight_cycle as cycle


def test_api_key_resolution_has_no_openrouter_or_oauth_fallback(tmp_path,monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY',raising=False)
    monkeypatch.setenv('OPENROUTER_API_KEY','wrong-provider-key')
    root=tmp_path/'profiles/backend-engineer';root.mkdir(parents=True)
    (tmp_path/'.env').write_text('OPENROUTER_API_KEY=wrong\n')
    assert worker.anthropic_key(tmp_path,root)==''
    (tmp_path/'.env').write_text('ANTHROPIC_API_KEY="fixture-only"\n')
    assert worker.anthropic_key(tmp_path,root)=='fixture-only'
    monkeypatch.setenv('ANTHROPIC_API_KEY','env-fixture')
    assert worker.anthropic_key(tmp_path,root)=='env-fixture'


def test_direct_claude_identity():
    identity=worker.inspect_native_profile('backend-engineer',worker.MODEL,worker.MODEL,'fixture')
    assert identity['provider']=='anthropic'
    assert identity['availability_fallback'] is False
    assert identity['attested'] is False


def test_missing_credential_stops_before_call_reservation(monkeypatch):
    identity=dict(provider='anthropic',configured_model=cycle.HERMES_MODEL,credential_present=False)
    monkeypatch.setattr(cycle,'hermes_identity',lambda role:identity)
    monkeypatch.setattr(cycle,'reserve_call',lambda *a:pytest.fail('must not reserve or dispatch'))
    with pytest.raises(ValueError,match='ANTHROPIC_API_KEY_not_configured'):
        cycle.hermes('proposer',{},'registration',identity,{'trace':{},'report':{}})


def test_native_claude_report_roundtrip_without_network(monkeypatch):
    identity=dict(provider='anthropic',configured_model=cycle.HERMES_MODEL,credential_present=True)
    monkeypatch.setattr(cycle,'hermes_identity',lambda role:identity)
    reservations=[];monkeypatch.setattr(cycle,'reserve_call',lambda *a:reservations.append(a))
    h=dict(seam='routing',prediction='fixture',falsifying_test='fixture')
    report=dict(sources_used=['context:proposer'],tests_run=[],tools_called=[],fallbacks_taken=[])
    def dispatch(command,**kwargs):
        request=json.loads(kwargs['input'])
        assert request['provider']=='anthropic' and request['model']==worker.MODEL
        assert request['max_tokens']==1024
        return SimpleNamespace(stdout=json.dumps(dict(ok=True,native_hermes=True,provider='anthropic',
            requested_model=worker.MODEL,tools=0,availability_fallback=False,value=dict(hypothesis=h,self_report=report))))
    monkeypatch.setattr(cycle.subprocess,'run',dispatch)
    audit={'trace':{},'report':{}}
    assert cycle.hermes('proposer',{},'registration',identity,audit)==h
    assert reservations==[('socratic','registration')]
    assert cycle.faithfulness.monitor(audit['trace'],audit['report'])['consistent']


def test_paid_allocation_reserved_before_dispatch(tmp_path,monkeypatch):
    monkeypatch.setattr(cycle,'PRIVATE',tmp_path)
    monkeypatch.setattr(cycle,'AUTH',None)
    claim=cycle.reserve_call('socratic','registered-hash')
    record=json.loads(claim.read_text())
    assert record['api_allocation_usd']==0.5
    assert record['api_provider']=='anthropic'


def test_paid_call_respects_resume_budget_before_claim(tmp_path,monkeypatch):
    import time
    monkeypatch.setattr(cycle,'PRIVATE',tmp_path/'private')
    monkeypatch.setattr(cycle,'SHARED',tmp_path/'shared')
    monkeypatch.setattr(cycle,'AUTH',dict(expires_epoch=time.time()+60,resume_compute_cap_usd=0.25))
    monkeypatch.setattr(cycle,'accounting',lambda _:dict(compute_usd=0,active_cycle_interval=dict(compute_usd=0)))
    with pytest.raises(ValueError,match='combined_compute_API_budget_stop'):
        cycle.reserve_call('socratic','registration')
    assert not (tmp_path/'private').exists()


def test_workspace_header_is_confined_to_anthropic_route(tmp_path,monkeypatch):
    monkeypatch.delenv('ANTHROPIC_WORKSPACE_ID',raising=False)
    root=tmp_path/'profile';root.mkdir()
    (tmp_path/'.env').write_text('ANTHROPIC_WORKSPACE_ID=wrkspc_fixture123\n')
    workspace=worker.anthropic_workspace(tmp_path,root)
    config=worker.isolated_config(worker.MODEL,workspace)
    assert config['custom_providers']==[dict(name='anthropic-workspace',base_url='https://api.anthropic.com',extra_headers={'anthropic-workspace-id':'wrkspc_fixture123'})]
    assert config['fallback_providers']==[]
    assert 'custom_providers' not in worker.isolated_config(worker.MODEL,'')
    monkeypatch.setenv('ANTHROPIC_WORKSPACE_ID','invalid\nheader')
    with pytest.raises(ValueError,match='invalid_anthropic_workspace_id'):
        worker.anthropic_workspace(tmp_path,root)


def test_installed_hermes_attaches_workspace_header_without_inference(tmp_path):
    import os
    import subprocess
    checkout=Path.home()/'.hermes/hermes-agent'
    python=checkout/'.venv/bin/python'
    if not python.is_file():pytest.skip('installed Hermes integration only')
    (tmp_path/'config.yaml').write_text(json.dumps(worker.isolated_config(worker.MODEL,'wrkspc_fixture123')))
    code="""
from agent.anthropic_adapter import build_anthropic_client
client=build_anthropic_client('sk-ant-api03-fixture', 'https://api.anthropic.com')
try:
    assert client.default_headers.get('anthropic-workspace-id')=='wrkspc_fixture123'
finally:
    client.close()
print('workspace_header_verified_without_inference')
"""
    result=subprocess.run([str(python),'-c',code],capture_output=True,text=True,timeout=25,
                          env=dict(os.environ,HERMES_HOME=str(tmp_path),PYTHONPATH=str(checkout)))
    assert result.returncode==0, 'Native Hermes header construction failed'
    assert 'workspace_header_verified_without_inference' in result.stdout
