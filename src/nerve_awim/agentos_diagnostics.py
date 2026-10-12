"""Read-only diagnoses of archived host-judged repository experiments.

This reports receipt evidence, not causal explanations or new evaluation results.
"""
from collections import Counter

SCOPE = 'agentos-repository-repair-v1'
PHASES = ('selection', 'retention', 'final')
CATEGORIES = {'passed', 'patch_rejected', 'sandbox_unavailable', 'timeout',
              'execution_failed', 'invalid_runner_report', 'behavior_failed'}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _count(value):
    return type(value) is int and value >= 0


def diagnose(receipt):
    """Return a bounded diagnosis; reject malformed or contradictory evidence.

    Missing phases in failed/incomplete receipts are unknown, not unopened.
    Archived v1 receipts predate the cohort field and are identified as v1.
    No model calls, file writes, patch execution, or promotion occur here.
    """
    _require(type(receipt) is dict, 'receipt object required')
    for key in ('id', 'model'):
        _require(type(receipt.get(key)) is str and bool(receipt[key].strip()),
                 f'{key} required')
    _require(receipt.get('scope') == SCOPE, 'unsupported receipt scope')
    cohort = receipt.get('cohort', 'v1')
    _require(type(cohort) is str and bool(cohort.strip()), 'cohort required')
    result = receipt.get('result')
    _require(type(result) is dict, 'result object required')
    status = result.get('status')
    _require(status in ('no_gain', 'observed_gain', 'failed', 'incomplete', 'running', 'frozen'),
             'unsupported result status')
    _require(result.get('general_improvement_proven', False) is False,
             'general improvement claim unsupported')
    if 'scope' in result:
        _require(result['scope'] == SCOPE, 'result scope mismatch')
    artifacts = receipt.get('artifacts')
    _require(type(artifacts) is list, 'artifact list required')
    training = []
    paired = {phase: {} for phase in PHASES}
    seen = set()
    for artifact in artifacts:
        _require(type(artifact) is dict, 'artifact object required')
        phase, arm, tid = (artifact.get(k) for k in ('phase', 'arm', 'task_id'))
        _require(phase in ('train',) + PHASES and arm in ('baseline', 'lesson'),
                 'invalid artifact phase or arm')
        _require(type(tid) is str and bool(tid), 'artifact task ID required')
        _require((phase, arm, tid) not in seen, 'duplicate artifact')
        seen.add((phase, arm, tid))
        check = artifact.get('check')
        _require(type(check) is dict and type(check.get('passed')) is bool,
                 'boolean host judgment required')
        category = check.get('category')
        _require(type(category) is str and category in CATEGORIES, 'unknown judgment category')
        _require((category == 'passed') == check['passed'], 'contradictory judgment')
        hits, total = check.get('tests_passed'), check.get('tests_total')
        _require(_count(hits) and _count(total) and total > 0 and hits <= total,
                 'valid host test counts required')
        _require(not check['passed'] or hits == total, 'incomplete passing judgment')
        _require(check.get('scope') == SCOPE, 'judgment scope mismatch')
        if phase == 'train':
            _require(arm == 'baseline', 'training must be baseline only')
            training.append(check)
        else:
            paired[phase].setdefault(tid, {})[arm] = check['passed']
    phases = {}
    unopened, unknown = [], []
    for phase in PHASES:
        summary = result.get(phase)
        if summary is None:
            _require(status not in ('no_gain', 'observed_gain'), 'completed phase summary missing')
            unknown.append(phase)
            continue
        _require(type(summary) is dict and type(summary.get('evaluated')) is bool,
                 'phase evaluation flag required')
        counts = {key: summary.get(key) for key in ('tasks', 'baseline_hits', 'lesson_hits', 'wins', 'losses')}
        _require(all(_count(v) for v in counts.values()), 'nonnegative integer phase counts required')
        if not summary['evaluated']:
            _require(not any(counts.values()) and not paired[phase], 'unopened phase contains evidence')
            unopened.append(phase)
        else:
            pairs = paired[phase]
            _require(counts['tasks'] > 0 and len(pairs) == counts['tasks'] and
                     all(set(p) == {'baseline', 'lesson'} for p in pairs.values()),
                     'complete paired artifacts required')
            expected = dict(tasks=len(pairs),
                            baseline_hits=sum(p['baseline'] for p in pairs.values()),
                            lesson_hits=sum(p['lesson'] for p in pairs.values()),
                            wins=sum(p['lesson'] and not p['baseline'] for p in pairs.values()),
                            losses=sum(p['baseline'] and not p['lesson'] for p in pairs.values()))
            _require(counts == expected, 'phase summary disagrees with artifacts')
        phases[phase] = dict(evaluated=summary['evaluated'], **counts)
    gain = (len(phases) == 3 and all(p['evaluated'] for p in phases.values()) and
            phases['selection']['wins'] > 0 and phases['final']['wins'] > 0 and
            all(p['losses'] == 0 for p in phases.values()))
    promoted = status == 'observed_gain'
    lesson_id = result.get('lesson_id')
    if promoted:
        _require(gain and type(lesson_id) is str and bool(lesson_id), 'promotion lacks gain evidence')
    else:
        _require(lesson_id is None, 'non-gain receipt claims promotion')
    if status == 'no_gain':
        _require(phases['selection']['evaluated'] and not gain, 'contradictory no-gain result')
    selection = phases.get('selection', {})
    ceiling = bool(selection.get('evaluated') and selection['tasks'] > 0 and
                   selection['baseline_hits'] == selection['tasks'])
    regression = any(p['losses'] > 0 for p in phases.values())
    classification = ('failed' if status == 'failed' else
                      'incomplete' if status in ('incomplete', 'running', 'frozen') else
                      'observed_scoped_gain' if promoted else
                      'regression' if regression else
                      'selection_ceiling_tie' if ceiling and selection['wins'] == selection['losses'] == 0 else
                      'no_gain')
    categories = dict(sorted(Counter(c['category'] for c in training).items()))
    actions = []
    if categories.get('patch_rejected'):
        actions.append('Inspect rejected training outputs against the patch contract; improve output formatting and validate it locally before a new study.')
    if ceiling:
        actions.append('Design fresh independent task families with greater difficulty and freeze their evaluation before inference; do not reuse these fixtures as fresh evidence.')
    if regression:
        actions.append('Inspect the paired losses and retain the baseline; test any revised advice on fresh independent tasks.')
    if classification in ('failed', 'incomplete'):
        actions.append('Inspect recorded execution failures or missing evidence before scheduling another bounded study; preserve consumed task reservations.')
    if promoted:
        actions.append('Monitor the scoped lesson on fresh tasks and apply the existing rollback rules; this receipt does not establish general improvement.')
    summaries = {
        'failed': 'The study failed; no candidate was promoted.',
        'incomplete': 'The study is incomplete; no candidate was promoted.',
        'observed_scoped_gain': 'The receipt reports a scoped paired gain and candidate promotion; general improvement is unproven.',
        'regression': 'Paired losses were observed; no candidate was promoted.',
        'selection_ceiling_tie': 'Both selection arms passed every task; the baseline reached the selection ceiling and no candidate was promoted.',
        'no_gain': 'No qualifying paired gain was recorded; no candidate was promoted.',
    }
    return dict(summary=summaries[classification], study_id=receipt['id'], cohort=cohort, model=receipt['model'], scope=SCOPE,
                result_status=status, diagnosis=classification,
                training=dict(tasks=len(training), hits=sum(c['passed'] for c in training),
                              category_counts=categories),
                phases=phases, phases_unopened=unopened, phases_unknown=unknown,
                selection_ceiling=ceiling, candidate_promoted=promoted,
                general_improvement_proven=False, native_cost_usd=None,
                native_cost_status='unknown', next_actions=actions,
                limitation='Archived host judgments only; no new evaluation or causal explanation. Scoped fixture results do not prove general improvement.')
