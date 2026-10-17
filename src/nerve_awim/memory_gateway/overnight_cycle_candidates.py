"""Bounded candidate seams. Never receives task labels or writes protected code."""
from copy import deepcopy
from . import scientific_candidate_v3 as a
from . import scientific_family_b_v4 as b
from . import scientific_family_b_v5 as v5
from . import scientific_candidate_registration as templates

SEAMS = ('routing', 'extraction-schema', 'prompt-fragment', 'retrieval-order',
         'source-selection', 'abstention-rule')


def template_hypotheses(episodes, head):
    module = templates.candidates
    result = []
    for cluster in module._clusters(episodes):
        config = module.SPACE[module._mutation(cluster['failure_class'])]
        result.append(module.register_hypothesis(config, cluster, store_head=head,
                                                mode='deterministic_failure_rules'))
    return result


def initial(family):
    return {'base': 'a3' if family == 'A' else 'b4', 'seams': []}


def mutate(incumbent, seam):
    if seam not in SEAMS or seam in incumbent['seams']:
        raise ValueError('new_single_registered_seam_required')
    candidate = deepcopy(incumbent)
    candidate['seams'].append(seam)
    return candidate


def prepare(config, query, evidence):
    evidence = deepcopy(evidence)
    seams = config['seams']
    if 'retrieval-order' in seams:
        evidence.sort(key=lambda r: r['source_id'])
    if config['base'] == 'a3':
        p = a.prepare(query, evidence, arm='candidate')
        if 'routing' not in seams or p['gate_reason'] not in ('unsupported_query', 'unsupported_evidence'):
            return {'kind': 'a3', 'prepared': p, 'decision': None}
    p = b.prepare(query, evidence)
    if 'extraction-schema' in seams:
        return {'kind': 'b5', 'prepared': p, 'decision': v5.decide(query, evidence)}
    if p['route'] == 'model':
        if 'prompt-fragment' in seams:
            p['system'] += '\nFor agreeing current sources use the lexicographically smallest source ID. Preserve the exact numeric value.'
        if 'source-selection' in seams:
            allowed = p['schema']['properties']['source_id']['enum']
            p['schema']['properties']['source_id']['enum'] = [min(allowed)]
        if 'abstention-rule' in seams:
            p['system'] += '\nAbstain if any current matching measurement conflicts; never resolve a conflict by majority.'
    return {'kind': 'b4', 'prepared': p, 'decision': None}
