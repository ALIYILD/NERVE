import math
import pytest
from nerve_awim.memory_gateway.overnight_advisors import calibration, summarize, triage, jev_prior


def test_known_calibration_and_ties():
    result = calibration([(0.1, 0), (.9, 1), (.5, 0), (.5, 1)])
    assert result['brier'] == pytest.approx(.13)
    assert result['auc'] == .875
    assert sum(b['n'] for b in result['reliability_bins']) == 4
    assert calibration([(1., 1)])['auc'] is None
    assert calibration([])['brier'] is None
    with pytest.raises(ValueError):
        calibration([(math.nan, 1)])


def test_prospective_only_and_weight_update():
    rows = [dict(experiment_id='old', verdict='kept')]
    result = summarize(rows)
    assert result['excluded_without_prospective_verdict'] == ['old']
    assert result['advisors']['template']['n'] == 0
    rows.append(dict(experiment_id='new', family='B', generator='socratic', verdict='kept',
                     replay_verified=True, advisor_prior={
                         'template': {'p_keep': .1}, 'socratic': {'p_keep': .9},
                         'jev': {'p_keep': .5, 'label': 'no-live-jev'}}))
    result = summarize(rows)
    assert result['trust_weights']['socratic'] > result['trust_weights']['jev'] > result['trust_weights']['template']
    assert sum(result['trust_weights'].values()) == pytest.approx(1.)
    assert result['jev_live']['n'] == 0
    assert result['jev_fixture']['n'] == 1
    assert result['families']['B']['higher_keep_rate'] is None
    with pytest.raises(ValueError):
        summarize(rows + [rows[-1]])


def test_fixture_cannot_dispatch_or_leak_text(monkeypatch):
    monkeypatch.delenv('TYPESAFE_API_KEY', raising=False)
    metrics = dict(completion=.5, abort=.5, violations=0, goal_penalized=0, prediction_penalized=0)
    def forbidden(_):
        raise AssertionError('fixture must not reserve a live call')
    assert jev_prior(metrics, {'candidate': metrics}, forbidden)['candidate']['label'] == 'no-live-jev'
    with pytest.raises(ValueError):
        jev_prior(dict(metrics, text='raw'), {'candidate': metrics}, forbidden)


def test_triage_is_advisory_deterministic():
    proposals = [dict(proposal_sha256=h, advisor_prior={'template': {'p_keep': .5}}) for h in ('b','a')]
    assert triage(proposals, dict.fromkeys(('template','socratic','jev'), 1/3))[0]['proposal_sha256'] == 'a'
