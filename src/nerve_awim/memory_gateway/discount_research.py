"""Fresh v3 discounted-evidence heuristic study; not Thompson-sampling reproduction.

Reuses the durable bounded coordinator. Public synthetic answers are host-held,
not independently sealed. Every recommendation requires separate review.
"""
from hashlib import sha256
from pathlib import Path
from . import policy_research_loop as loop
from . import self_study

SCENARIOS = loop.SCENARIOS
SPLITS = (('train', (4001, 4002)), ('validation', (5001, 5002)),
          ('holdout', tuple(range(6001, 6011))))
BASELINE = (3, 'relevance', None)
CANDIDATES = (BASELINE,) + tuple((w, 'relevance', d)
                               for w in (3, 10) for d in (1, 3, 10))


def _cases(seed, scenario):
    return loop._cases(seed, scenario, splits=SPLITS, domain='discount-research-v3')


def protocol_manifest():
    protocol = loop.protocol_manifest()
    protocol.pop('protocol_sha256')
    protocol.update(version=3, evaluator_revision='discount-research-transform-v3',
        candidates=[list(c) for c in CANDIDATES], baseline=list(BASELINE),
        max_generations=2, candidates_per_generation=4, patience=2,
        max_trial_calls=272, splits={s: list(seeds) for s, seeds in SPLITS},
        dataset_sha256=loop._digest([(seed, scenario, _cases(seed, scenario))
            for _, seeds in SPLITS for seed in seeds for scenario in SCENARIOS]),
        candidate_order='baseline then window(3,10) x discount half-life(1,3,10)',
        candidate_fields=['window', 'tie_break', 'discount_half_life'],
        discount_semantics='each judged observation discounted by scope-local age, inside bounded window; Beta(1,1) prior remains fixed',
        rationale='Discounted evidence for nonstationary feedback; deterministic heuristic, not Thompson sampling or a reproduction of its guarantees.',
        decay_half_life=None)
    protocol['evaluator_source_sha256']['discount_research.py'] = sha256(
        Path(__file__).read_bytes()).hexdigest()
    return {**protocol, 'protocol_sha256': loop._digest(protocol)}


def _evaluate(seed, scenario, config, fixed=None):
    return self_study._execute_trial(_cases(seed, scenario), seed, scenario,
        window=None if fixed else config[0], fixed=fixed, tie_break=config[1],
        discount_half_life=config[2], evaluator_revision='discount-research-transform-v3')


def _validate(row, seed, scenario, fixed=None, *, config=None):
    loop._validate(row, seed, scenario, fixed)
    if config is not None:
        expected = {'window': None if fixed else config[0], 'tie_break': config[1],
                    'discount_half_life': config[2], 'decay_half_life': None,
                    'fixed_strategy': fixed}
        if any(key not in row or row[key] != value or type(row[key]) is not type(value)
               for key, value in expected.items()):
            raise ValueError('evaluator configuration does not match requested arm')
    outcomes = row.get('feedback_outcomes')
    if not isinstance(outcomes, list) or len(outcomes) != 20 or any(type(v) is not bool for v in outcomes):
        raise ValueError('invalid feedback outcomes')
    return row


def run_discount_research(path, run_id):
    """Consume one fresh finite protocol; never promote or deploy its result."""
    return loop._run(path, run_id, _evaluate, manifest=protocol_manifest(), validator=_validate)
