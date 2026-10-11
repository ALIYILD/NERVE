"""Bounded lesson search; final holdout is opened once after selection freezes."""
from copy import deepcopy
from .learning_study import Episode, validate_stream
from .skill_validation import evaluate_lesson


def run_improvement_loop(training, selection, final, *, propose, predict, judge,
                         iterations=10, max_prediction_calls=1000, regression=()):
    """Trusted host callbacks, no automatic code execution or release authority.

    Repeated selection results may guide proposals. Final tasks and answers are
    never passed to propose. Host must enforce isolation, costs, timeouts and
    durable holdout nonreuse across invocations. Failures abort without a report.
    """
    training, selection, final = deepcopy((tuple(training), tuple(selection), tuple(final)))
    regression = deepcopy(tuple(regression))
    if type(iterations) is not int or not 1 <= iterations <= 10:
        raise ValueError('one to ten iterations required')
    if any(item.phase != 'train' for item in training):
        raise ValueError('training prefix required')
    if any(item.phase != 'evaluation' for item in selection + final + regression):
        raise ValueError('selection and final must be evaluation episodes')
    validate_stream(training + selection + regression + final)
    if regression and len(regression) < 5:
        raise ValueError('at least five retained regression tasks required')
    if len(selection) < 5 or len(final) < 5:
        raise ValueError('at least five selection and five final tasks required')
    required = 2 * (iterations * (len(selection) + len(regression)) + len(final))
    if type(max_prediction_calls) is not int or not required <= max_prediction_calls <= 20000:
        raise ValueError('insufficient bounded prediction-call quota')
    incumbent, history, seen, calls = None, [], set(), 0
    for index in range(iterations):
        candidate = propose({'iteration': index + 1, 'incumbent': incumbent,
                             'training': deepcopy(training), 'history': deepcopy(history)})
        if type(candidate) is not str or not 1 <= len(candidate) <= 2048:
            raise ValueError('bounded lesson proposal required')
        if candidate in seen:
            history.append({'iteration': index + 1, 'status': 'duplicate_skipped'})
            continue
        seen.add(candidate)
        previous = incumbent
        report = evaluate_lesson(candidate, training + selection,
            predict=lambda task, lesson: predict(task, previous if lesson is None else lesson),
            judge=judge, max_calls=2*len(selection))
        calls += report['prediction_calls']
        # Any observed regression blocks replacement, even with positive net gain.
        keep = report['wins'] > 0 and report['losses'] == 0
        regression_report = None
        if keep and regression:
            # Compare with the original baseline, so accumulated changes cannot
            # progressively forget a previously working retained capability.
            regression_report = evaluate_lesson(candidate, training + regression,
                predict=predict, judge=judge, max_calls=2*len(regression))
            calls += regression_report['prediction_calls']
            keep = regression_report['losses'] == 0
        if keep:
            incumbent = candidate
        history.append({'iteration': index + 1, 'status': 'kept' if keep else 'reverted',
                        'selection': report, 'regression': regression_report})
    final_report = None
    if incumbent is not None:
        # Include selection in the exclusion prefix; it is never final evidence.
        development = training + tuple(Episode(e.episode_id, 'train', e.task, e.expected) for e in selection + regression)
        final_report = evaluate_lesson(incumbent, development + final, predict=predict,
                                      judge=judge, max_calls=2*len(final))
        calls += final_report['prediction_calls']
    improved = final_report is not None and final_report['wins'] > 0 and final_report['losses'] == 0
    return {'history': history, 'selected_lesson': incumbent, 'final': final_report,
            'prediction_calls': calls, 'proposal_calls': iterations,
            'status': 'observed_final_gain' if improved else 'no_verified_improvement',
            'promotion_authorized': False,
            'scope': 'bounded offline experiment; not statistical or general improvement proof'}
