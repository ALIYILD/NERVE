"""Prospective advisor accounting; no authority to evaluate or promote candidates."""
from math import exp, isfinite
import os
from nerve_awim.jev_batch import JevBatchReviewer
from nerve_awim.jev_optional import numeric_summary

ADVISORS = ('template', 'socratic', 'jev')
RULE = {'eta': 0.5, 'exploration': 0.1, 'initial_weights': dict.fromkeys(ADVISORS, 1/3),
        'reward': 'negative_brier', 'feedback': 'selected_candidate_only',
        'reliability_edges': [0, .2, .4, .6, .8, 1]}


def probability(p):
    if type(p) not in (int, float) or not isfinite(p) or not 0 <= p <= 1:
        raise ValueError('finite_probability_required')
    return float(p)


def calibration(pairs):
    pairs = [(probability(p), y) for p, y in pairs]
    if any(type(y) is not int or y not in (0, 1) for _, y in pairs):
        raise ValueError('binary_verdict_required')
    positive = [p for p, y in pairs if y]
    negative = [p for p, y in pairs if not y]
    bins = []
    for i in range(5):
        values = [(p, y) for p, y in pairs if min(int(p*5), 4) == i]
        bins.append(dict(lower=i/5, upper=(i+1)/5, n=len(values),
                         mean_prior=sum(p for p, _ in values)/len(values) if values else None,
                         keep_rate=sum(y for _, y in values)/len(values) if values else None))
    return dict(n=len(pairs), brier=sum((p-y)**2 for p, y in pairs)/len(pairs) if pairs else None,
                auc=sum((p > n) + .5*(p == n) for p in positive for n in negative)
                    /(len(positive)*len(negative)) if positive and negative else None,
                auc_reason=None if positive and negative else 'both_verdict_classes_required',
                reliability_bins=bins)


def summarize(rows):
    """Exclude historical rows lacking prospective priors, never backfill forecasts."""
    pairs = {a: [] for a in ADVISORS}
    losses = dict.fromkeys(ADVISORS, 0.)
    families = {f: {g: {'n': 0, 'kept': 0, 'keep_rate': None}
                    for g in ADVISORS[:2]} for f in ('A', 'B')}
    excluded = []
    live, fixture = [], []
    seen = set()
    for row in rows:
        if row['experiment_id'] in seen:
            raise ValueError('duplicate_experiment')
        seen.add(row['experiment_id'])
        if row.get('verdict') not in ('kept', 'reverted') or not row.get('advisor_prior'):
            excluded.append(row['experiment_id'])
            continue
        if row.get('replay_verified') is not True:
            raise ValueError('verified_replay_required')
        y = int(row['verdict'] == 'kept')
        priors = row['advisor_prior']
        for advisor in ADVISORS:
            if advisor not in priors:
                continue
            p = probability(priors[advisor]['p_keep'])
            pairs[advisor].append((p, y))
            losses[advisor] += (p-y)**2
            if advisor == 'jev':
                (fixture if priors[advisor].get('label') == 'no-live-jev' else live).append((p, y))
        stat = families[row['family']][row['generator']]
        stat['n'] += 1
        stat['kept'] += y
        stat['keep_rate'] = stat['kept']/stat['n']
    raw = {a: exp(-RULE['eta']*losses[a]) for a in ADVISORS}
    weights = {a: (1-RULE['exploration'])*raw[a]/sum(raw.values()) + RULE['exploration']/3
               for a in ADVISORS}
    for family in families.values():
        t, s = family['template'], family['socratic']
        family['higher_keep_rate'] = (None if not t['n'] or not s['n'] else
                                     'tie' if t['keep_rate'] == s['keep_rate'] else
                                     'template' if t['keep_rate'] > s['keep_rate'] else 'socratic')
    return dict(rule=RULE, advisors={a: calibration(pairs[a]) for a in ADVISORS},
                jev_live=calibration(live), jev_fixture=calibration(fixture),
                trust_weights=weights, families=families, excluded_without_prospective_verdict=excluded,
                interpretation='selection_conditional; no causal generator comparison')


def triage(proposals, weights):
    if set(weights) != set(ADVISORS) or abs(sum(weights.values())-1) > 1e-9:
        raise ValueError('normalized_advisor_weights_required')
    def score(proposal):
        priors = proposal['advisor_prior']
        if not priors or not set(priors) <= set(ADVISORS):
            raise ValueError('known_nonempty_advisors_required')
        return sum(probability(priors[a]['p_keep'])*probability(weights[a]) for a in priors)/sum(weights[a] for a in priors)
    return sorted(proposals, key=lambda p: (-score(p), p['proposal_sha256']))


def jev_prior(baseline, candidates, reserve_call):
    """Live jev_batch budget is claimed before HTTP; absent key yields a fixture."""
    if not isinstance(candidates, dict) or not 1 <= len(candidates) <= 6:
        raise ValueError('one_to_six_candidates_required')
    numeric_summary(baseline)
    for value in candidates.values():
        numeric_summary(value)
    if os.environ.get('TYPESAFE_API_KEY'):
        reserve_call('jev')  # Host's durable quota claim, including failed calls.
        answers = JevBatchReviewer().review_many(baseline=baseline, candidates=candidates)
        label = 'live-jev'
    else:
        # The fixed fixture is explicitly not a prediction from a live model.
        return {name: dict(p_keep=.5, risk_probability=.5, label='no-live-jev',
                           fixture='neutral-risk-v1', live_calls=0,
                           advisory_only=True) for name in candidates}
    return {name: dict(p_keep=1-answer.risk_probability, risk_probability=answer.risk_probability,
                       label=label, model=answer.model, advisory_only=True)
            for name, answer in answers.items()}
