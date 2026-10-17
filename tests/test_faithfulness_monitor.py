from copy import deepcopy
import json
import pytest
from nerve_awim.memory_gateway import faithfulness_monitor as fm
from nerve_awim.memory_gateway import overnight_advisors as advisors


def pair():
    claims={k:[] for k in fm.FIELDS}
    claims['sources_used']=['context:proposer']
    return {'proposer':dict(claims,complete=True)}, {'proposer':deepcopy(claims)}


def test_matching_and_immutable_seed(tmp_path):
    trace,report=pair()
    first=fm.record(tmp_path,'fixture',trace,report,provenance='fixture')
    assert first['consistent']
    assert fm.record(tmp_path,'fixture',trace,report,provenance='fixture')==first
    assert json.loads(next(tmp_path.iterdir()).read_text())['provenance']=='fixture'


@pytest.mark.parametrize('field',fm.FIELDS)
def test_invented_actions(field):
    trace,report=pair();report['proposer'][field].append('invented')
    result=fm.monitor(trace,report)
    assert result['label']=='unfaithful_report'
    assert any(m.get('reason')=='unjournaled_claim' for m in result['mismatches'])


def test_omitted_fallback_and_duplicate_claim():
    trace,report=pair();trace['proposer']['fallbacks_taken']=['alternate_source']
    report['proposer']['sources_used']*=2
    reasons={m['reason'] for m in fm.monitor(trace,report)['mismatches']}
    assert reasons=={'unreported_action','unjournaled_claim'}


@pytest.mark.parametrize('report',[None,{},'I ran all tests',{'other':{}}])
def test_missing_unstructured_or_wrong_actor(report):
    trace,_=pair()
    assert not fm.monitor(trace,report)['consistent']


def test_incomplete_journal():
    trace,report=pair();trace['proposer']['complete']=False
    assert not fm.monitor(trace,report)['consistent']


def test_quarantine_excluded_from_calibration_and_counted():
    trace,report=pair();report['proposer']['tests_run']=['pytest:passed']
    result=fm.monitor(trace,report)
    row=dict(experiment_id='fixture',generator='socratic',agent_involving=True,agent_kinds=['socratic'],
             verdict='unfaithful_report',report_trace_consistency=result,advisor_prior={})
    assert fm.coverage([row])==dict(eligible=1,checked=1,missing=0,quarantined=1,socratic=1,agent_node=0,exercised=True)
    assert all(v['n']==0 for v in advisors.summarize([row])['advisors'].values())


def test_execution_and_learning_fail_closed(tmp_path):
    import sys
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
    import overnight_cycle as cycle
    trace,report=pair();report['proposer']['tools_called']=['unobserved_tool']
    for name,value in [('agent-journal',trace),('agent-self-report',report),
                       ('report-trace-consistency',dict(fm.monitor(trace,report),consistent=True))]:
        (tmp_path/(name+'.json')).write_text(json.dumps(value))
    with pytest.raises(ValueError,match='unfaithful_report'):
        cycle.execute(tmp_path,{},None,{})
    with pytest.raises(ValueError,match='unfaithful_report'):
        cycle.ingest(tmp_path,'A',{})
