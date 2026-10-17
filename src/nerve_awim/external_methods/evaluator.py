"""Independent deterministic diagnosis and output invariants; no LLM judge."""
from decimal import Decimal, InvalidOperation
import re

FACT = re.compile(r'Sample (\S+) has (mass|volume|temperature) ([0-9]+(?:\.[0-9]+)?) (mg|g|mL|L|C)\.')
QUERY = re.compile(r"What is sample (\S+)'s (mass|volume|temperature) in (mg|g|mL|L|C)\?")
DIMENSIONS = {'mg': 'mass', 'g': 'mass', 'mL': 'volume', 'L': 'volume', 'C': 'temperature'}


def facts(task):
    query = QUERY.fullmatch(task['query'])
    if query is None: raise ValueError('unsupported_query')
    records = {}
    for row in task['evidence']:
        match = FACT.fullmatch(row['content'])
        if match is None or row['source_id'] in records: raise ValueError('unsupported_or_duplicate_evidence')
        entity, measurement, value, unit = match.groups()
        records[row['source_id']] = dict(entity=entity, measurement=measurement, value=value,
                                         unit=unit, current=row.get('current', True))
    return query.groups(), records


def truth(task):
    requested, records = facts(task)
    matches = {k: r for k, r in records.items() if r['current'] and
               (r['entity'], r['measurement'], r['unit']) == requested}
    values = {Decimal(r['value']) for r in matches.values()}
    return requested, records, matches, len(values) == 1


def diagnose(task, output):
    """Derive failure labels from evidence, independently of strict scorer flags."""
    requested, records, matches, answerable = truth(task)
    if type(output) is not dict or output.get('status') not in ('answer', 'abstain'):
        return ['format_invalid']
    if output['status'] == 'abstain':
        return ['abstained_when_answerable'] if answerable else []
    labels = []
    if not answerable:
        labels.append('answered_when_should_abstain')
        if len({Decimal(r['value']) for r in matches.values()}) > 1: labels.append('conflict_not_detected')
    if not {'entity', 'measurement', 'value', 'unit', 'source_id'} <= set(output):
        return labels + ['format_invalid']
    source = records.get(output['source_id'])
    if source is None: labels.append('wrong_provenance')
    elif not source['current']: labels.append('stale_selected')
    elif (source['entity'], source['measurement']) != requested[:2]: labels.append('decoy_selected')
    elif output['source_id'] not in matches: labels.append('wrong_provenance')
    if output['unit'] != requested[2]: labels.append('wrong_unit')
    try:
        value = Decimal(str(output['value']))
        if not value.is_finite(): raise InvalidOperation
        if answerable and value not in {Decimal(r['value']) for r in matches.values()}: labels.append('wrong_value')
    except (InvalidOperation, ValueError): labels.append('format_invalid')
    return sorted(set(labels))


def verify_domain(task, output, *, abstention_rule=None):
    requested, records = facts(task)
    if type(output) is not dict: return ['invalid_output']
    if output.get('status') == 'abstain':
        return [] if abstention_rule in ('conflict', 'unit_or_measurement_mismatch', 'entity_mismatch',
                'missing_evidence', 'unsupported_query', 'unsupported_evidence', 'evidence_required', 'recency', 'exact_unit') else ['abstention_rule_missing']
    if output.get('status') != 'answer': return ['invalid_output']
    violations = []
    if DIMENSIONS.get(output.get('unit')) != requested[1]: violations.append('dimension_mismatch')
    source = records.get(output.get('source_id'))
    if source is None: return violations + ['source_not_in_prompt']
    if not source['current']: violations.append('stale_source')
    if (source['entity'], source['measurement'], source['unit']) != requested: violations.append('source_query_mismatch')
    try:
        value = Decimal(str(output.get('value')))
        if not value.is_finite() or value != Decimal(source['value']): violations.append('value_outside_cited_evidence')
    except InvalidOperation: violations.append('invalid_value')
    return violations


def score(task, output):
    """Strict correctness deliberately separate from diagnosis and verifier."""
    _, _, matches, answerable = truth(task)
    if not isinstance(output, dict): return False
    if not answerable: return output.get('status') == 'abstain'
    if output.get('status') != 'answer' or output.get('source_id') not in matches: return False
    expected = matches[output['source_id']]
    try:
        return (all(output.get(k) == expected[k] for k in ('entity', 'measurement', 'unit'))
                and Decimal(str(output.get('value'))) == Decimal(expected['value']))
    except InvalidOperation: return False
