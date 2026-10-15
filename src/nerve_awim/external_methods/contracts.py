"""Preregistration, capacity and typed repair contracts; see adoption design note."""
from hashlib import sha256
import json
import math


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


def number(value, low=0, high=float('inf')):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError('finite_bounded_number_required')
    return value


CAPACITY = {'prompt_tokens', 'output_tokens', 'model_size', 'rules', 'retrieval_k',
            'tools', 'memory_reads', 'autonomy', 'model_calls'}


def capacity(value):
    if set(value) != CAPACITY | {'model_digest'} or not value['model_digest']:
        raise ValueError('complete_capacity_declaration_required')
    for key in CAPACITY:
        number(value[key])
    return value


def capacity_cost(candidate, incumbent, prices):
    capacity(candidate); capacity(incumbent)
    if set(prices) != CAPACITY:
        raise ValueError('registered_capacity_prices_required')
    return sum(max(0, candidate[k] - incumbent[k]) * number(prices[k]) for k in CAPACITY)


ROUTES = {
    'abstained_when_answerable': ['abstention-rule'],
    'answered_when_should_abstain': ['abstention-rule'],
    'conflict_not_detected': ['abstention-rule'],
    'wrong_provenance': ['extraction-schema'], 'format_invalid': ['extraction-schema'],
    'wrong_unit': ['extraction-schema'],
    'wrong_value': ['prompt-fragment', 'retrieval-order'],
    'decoy_selected': ['prompt-fragment', 'retrieval-order'],
    'stale_selected': ['abstention-rule', 'retrieval-order'],
}
SEAMS = {
    'abstention-rule': {'rule'}, 'extraction-schema': {'fields'},
    'prompt-fragment': {'text'}, 'retrieval-order': {'order'}, 'routing': {'model'},
}


def validate_patch(patch, *, max_characters=1024, allowed_models=()):
    if set(patch) != {'seam', 'patch'} or patch['seam'] not in SEAMS:
        raise ValueError('named_seam_required')
    seam, body = patch['seam'], patch['patch']
    if type(body) is not dict or set(body) != SEAMS[seam]:
        raise ValueError('seam_fields_required')
    if seam == 'abstention-rule' and body['rule'] not in ('conflict', 'recency', 'exact_unit', 'evidence_required'):
        raise ValueError('registered_rule_required')
    if seam == 'extraction-schema' and body['fields'] != ['value', 'unit', 'source_id']:
        raise ValueError('fixed_schema_keys_required')
    if seam == 'prompt-fragment' and (type(body['text']) is not str or not 1 <= len(body['text']) <= max_characters):
        raise ValueError('bounded_prompt_required')
    if seam == 'retrieval-order' and body['order'] not in ('current_first', 'exact_match_first', 'source_id'):
        raise ValueError('registered_order_required')
    if seam == 'routing' and body['model'] not in allowed_models:
        raise ValueError('registered_model_required')
    # Patches are data only. There is no import/eval/exec or arbitrary code seam.
    return digest(patch)


def route(histogram, attempts, budget):
    if type(budget) is not int or budget < 1:
        raise ValueError('positive_attempt_budget_required')
    for count in histogram.values(): number(count)
    walls = sorted(k for k, count in histogram.items() if count and k not in ROUTES)
    for regime in sorted(histogram, key=lambda k: (-histogram[k], k)):
        if not histogram[regime]: continue
        for seam in ROUTES.get(regime, []):
            if number(attempts.get(regime + ':' + seam, 0)) < budget:
                return {'status': 'proposed', 'regime': regime, 'seam': seam, 'walls': walls}
    return {'status': 'wall' if walls else 'attempt_budget_exhausted', 'walls': walls}


REGISTRATION_FIELDS = {
    'study_id', 'model', 'prompts', 'schemas', 'sampling', 'transport', 'bank',
    'exclusions', 'outcomes', 'mode', 'pilot_history', 'robustness',
    'holdout_unread_attestation', 'candidate', 'incumbent', 'capacity',
    'incumbent_capacity', 'prices', 'gate', 'rollback', 'tier',
}


def register(value):
    if set(value) != REGISTRATION_FIELDS:
        raise ValueError('registration_v2_fields_required')
    for key in REGISTRATION_FIELDS:
        if value[key] is None: raise ValueError('registration_field_missing:' + key)
    for name, keys in {
        'model': {'identifier', 'checkpoint_digest', 'quantisation', 'runtime'},
        'sampling': {'temperature', 'top_p', 'seeds', 'token_limit'},
        'transport': {'timeout', 'retry_limit'},
        'bank': {'manifest', 'split', 'fresh_items'},
        'exclusions': {'malformed', 'refused', 'timeout'},
        'outcomes': {'primary', 'secondary', 'interpretation'},
        'pilot_history': {'drafts', 'calibrations', 'dev_studies', 'findings'},
        'robustness': {'variants', 'order_seeds', 'stateful'},
        'gate': {'alpha', 'bet', 'item_budget', 'minimum_net_wins', 'futility_e', 'strata', 'order_seed'},
    }.items():
        if type(value[name]) is not dict or set(value[name]) != keys:
            raise ValueError('registration_section_required:' + name)
    if value['mode'] not in ('confirmatory', 'exploratory') or value['tier'] not in ('A', 'B', 'C'):
        raise ValueError('registered_mode_and_tier_required')
    if value['holdout_unread_attestation'] is not True:
        raise ValueError('holdout_attestation_required')
    if value['bank']['split'] not in ('dev', 'synthetic', 'holdout'):
        raise ValueError('registered_split_required')
    if value['bank']['fresh_items'] is not True:
        raise ValueError('adaptive_holdout_reuse_not_supported')
    for name in ('study_id', 'candidate', 'incumbent', 'rollback'):
        if type(value[name]) is not str or not value[name]: raise ValueError('identity_required')
    if not value['prompts'] or not value['schemas'] or not value['sampling']['seeds']:
        raise ValueError('verbatim_inputs_and_seeds_required')
    number(value['sampling']['temperature']); number(value['sampling']['top_p'], 0, 1)
    number(value['sampling']['token_limit'], 1); number(value['transport']['timeout'], 0.001)
    number(value['transport']['retry_limit'])
    for key in ('drafts', 'calibrations', 'dev_studies'): number(value['pilot_history'][key])
    if value['robustness']['stateful'] and len(set(value['robustness']['order_seeds'])) < 2:
        raise ValueError('shuffled_order_seeds_required')
    g = value['gate']
    number(g['alpha'], 1e-12, 0.05); number(g['bet'], 1e-6, .999999)
    number(g['futility_e'], 0, .999999); number(g['minimum_net_wins'], 1)
    if type(g['item_budget']) is not int or g['item_budget'] < 1 or not g['strata']:
        raise ValueError('positive_budget_and_strata_required')
    capacity_cost(value['capacity'], value['incumbent_capacity'], value['prices'])
    body = json.loads(canonical(value))
    return {'version': 2, 'registration': body, 'sha256': digest(body)}
