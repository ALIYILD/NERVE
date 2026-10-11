"""Paired held-out lesson comparison; reports never approve ledger entries."""
from copy import deepcopy
from .learning_study import canonical, validate_stream


def evaluate_lesson(lesson, episodes, *, predict, judge, max_calls=100):
    """Declare all development tasks as train; evaluate only the fresh tail.

    Host owns dataset provenance and independent, stateless prediction/judging.
    Exact overlap is rejected; semantic overlap and earlier experiments cannot
    be detected here. No expected answers or judging feedback reach predict.
    """
    if type(lesson) is not str or not 1 <= len(lesson) <= 2048:
        raise ValueError('bounded lesson required')
    stream = validate_stream(episodes)
    heldout = [item for item in stream if item.phase == 'evaluation']
    if type(max_calls) is not int or not 1 <= max_calls <= 2000 or 2*len(heldout) > max_calls:
        raise ValueError('insufficient bounded prediction-call quota')
    outcomes = {'baseline': [], 'lesson': []}
    for index, item in enumerate(heldout):
        # Alternate order to reduce systematic first-call effects.
        order = ('baseline', 'lesson') if index % 2 == 0 else ('lesson', 'baseline')
        outputs = {}
        for arm in order:
            outputs[arm] = predict(deepcopy(item.task), lesson if arm == 'lesson' else None)
            canonical(outputs[arm])
            outputs[arm] = deepcopy(outputs[arm])
        for arm in ('baseline', 'lesson'):
            accepted = judge(deepcopy(item.task), outputs[arm], deepcopy(item.expected))
            if type(accepted) is not bool:
                raise ValueError('independent boolean judge required')
            outcomes[arm].append(accepted)
    baseline, candidate = outcomes['baseline'], outcomes['lesson']
    return {'tasks': len(heldout), 'prediction_calls': 2*len(heldout),
            'baseline_hits': sum(baseline), 'lesson_hits': sum(candidate),
            'wins': sum(b and not a for a, b in zip(baseline, candidate)),
            'losses': sum(a and not b for a, b in zip(baseline, candidate)),
            'promotion_authorized': False, 'cost_usd': None,
            'scope': 'single held-out comparison, not proof of generalization'}
