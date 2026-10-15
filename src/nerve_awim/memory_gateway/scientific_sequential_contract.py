"""Registration for the unsigned, simulation-only Loop 40.2 gate."""
from hashlib import sha256
import json
import math
import statistics


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def number(value, low=0, high=float('inf')):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError('finite_bounded_number_required')
    return value


def plateau_minimum(dev_seed_deltas, item_budget):
    """Registered 2-SD noise floor in net item wins (registered minimum three wins)."""
    if len(dev_seed_deltas) < 3:
        raise ValueError('three_development_seed_deltas_required')
    for delta in dev_seed_deltas:
        number(delta, -1, 1)
    return max(3, math.ceil(2 * statistics.stdev(dev_seed_deltas) * item_budget))


def register(value):
    required = {'study_id', 'bank', 'gate', 'mode', 'candidate', 'incumbent',
                'deployed_incumbent', 'reverted_only_candidate', 'dev_seed_deltas', 'schedule'}
    if set(value) != required:
        raise ValueError('exact_registration_fields_required')
    if value['mode'] != 'exploratory' or value['bank']['split'] != 'synthetic':
        raise PermissionError('unsigned_gate_is_simulation_only')
    if set(value['bank']) != {'manifest', 'split'} or not value['bank']['manifest']:
        raise ValueError('bank_manifest_required')
    if value['incumbent'] != value['deployed_incumbent'] or value['reverted_only_candidate'] is not True:
        raise ValueError('marginal_deployed_incumbent_required')
    for field in ('study_id', 'candidate', 'incumbent'):
        if type(value[field]) is not str or not value[field]:
            raise ValueError('identity_required')
    if value['candidate'] == value['incumbent']:
        raise ValueError('distinct_candidate_required')
    g = value['gate']
    if set(g) != {'alpha', 'bet', 'futility_e', 'minimum_net_wins', 'item_budget', 'strata', 'order_seed'}:
        raise ValueError('exact_gate_fields_required')
    number(g['alpha'], 1e-12, .05); number(g['bet'], 1e-6, .999999)
    number(g['futility_e'], 0, .999999)
    if type(g['item_budget']) is not int or g['item_budget'] < 1:
        raise ValueError('positive_integer_budget_required')
    if g['minimum_net_wins'] != plateau_minimum(value['dev_seed_deltas'], g['item_budget']):
        raise ValueError('development_noise_floor_required')
    if not g['strata'] or len(set(g['strata'])) != len(g['strata']):
        raise ValueError('unique_strata_required')
    schedule = value['schedule']
    if len(schedule) != g['item_budget'] or len({s['item_id'] for s in schedule}) != len(schedule):
        raise ValueError('unique_complete_schedule_required')
    if any(set(s) != {'item_id', 'stratum'} or not s['item_id'] or s['stratum'] not in g['strata'] for s in schedule):
        raise ValueError('registered_schedule_required')
    # Every complete round includes each stratum; strata cannot be postponed until after stopping.
    width = len(g['strata'])
    if any({s['stratum'] for s in schedule[i:i+width]} != set(g['strata'])
           for i in range(0, len(schedule)-width+1, width)):
        raise ValueError('stratified_rounds_required')
    body = json.loads(canonical(value))
    return {'version': 1, 'registration': body, 'sha256': sha256(canonical(body).encode()).hexdigest()}
