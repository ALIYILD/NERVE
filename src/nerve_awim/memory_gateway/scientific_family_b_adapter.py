"""Versioned, label-free family-B input preparation; not unchanged skill v1.

No bank items, generator or expected-answer access. Raw names, measurements, source IDs, numeric
lexemes, record multiplicity and order survive parsing. Both arms share inputs.
"""
from decimal import Decimal
import json
import re
from .scientific_task_bank import RULES
from .scientific_candidate_execution import _inputs, ABSTAIN, QUERY, FACT
from .scientific_candidate_v3 import SYSTEM as CANDIDATE_SYSTEM
from .scientific_compact_dev_transport import SYSTEM as BASELINE_SYSTEM

VERSION = 'family-b-adapted-v3-input-v1'
MAX_RECORDS = 12
MAX_OUTPUT_TOKENS = 128
SEED = 20261016
_NUMBER = r'[0-9]{1,12}(?:\.[0-9]{1,12})?'
_NAME = r'[A-Za-z][A-Za-z0-9]{0,64}'
_UNIT = r'mg|g|mL|L|C'
_MEASUREMENT = r'mass|dry mass|mass fraction|volume|temperature'
PATTERNS = (
    re.compile(rf'(?P<measurement>{_MEASUREMENT}) of sample (?P<entity>{_NAME}): (?P<value>{_NUMBER}) (?P<unit>{_UNIT}) \((?:current|superseded)\)\.', re.I),
    re.compile(rf'For (?P<entity>{_NAME}), the (?P<measurement>{_MEASUREMENT}) measurement was (?P<value>{_NUMBER}) (?P<unit>{_UNIT})\.'),
    re.compile(rf'The laboratory recorded (?P<value>{_NUMBER}) (?P<unit>{_UNIT}) as (?P<measurement>{_MEASUREMENT}) for (?P<entity>{_NAME})\.'),
)


def parse_record(record):
    for pattern in PATTERNS:
        match = pattern.fullmatch(record['content'])
        if match:
            value = match.groupdict()
            value['measurement'] = value['measurement'].lower()
            return dict(value, source_id=record['source_id'], current=record['current'])
    old = FACT.fullmatch(record['content'])
    if old:
        return dict(zip(('entity','measurement','value','unit'),old.groups()),source_id=record['source_id'],current=record['current'])
    raise ValueError('unregistered_evidence_grammar')


def prepare(query, evidence, arm):
    _inputs(query, evidence)
    if arm not in ('adapted_v1','adapted_bootstrap'):raise ValueError('registered_arm_required')
    if not 1 <= len(evidence) <= MAX_RECORDS:raise ValueError('bounded_records_required')
    requested = QUERY.fullmatch(query)
    if not requested:raise ValueError('registered_query_required')
    parsed = [parse_record(record) for record in evidence]
    current = [record for record in parsed if record['current']]
    matching = [record for record in current if (record['entity'],record['measurement'],record['unit']) == (requested.group(1),'mass','mg')]
    eligible = bool(matching) and len({Decimal(record['value']) for record in matching}) == 1
    reason = 'matching_current_evidence' if eligible else 'conflict' if matching else 'unit_or_measurement_mismatch'
    # Preserve the ENTIRE evidence list and order. No source choice or filtering.
    facts = [{'entity':record['entity'],'measurement':record['measurement'],'value':record['value'],
              'unit':record['unit'],'source_id':record['source_id'],'current':record['current']} for record in parsed]
    schema = {'type':'object','properties':{'value':{'type':'number'},'unit':{'type':'string','enum':sorted({r['unit'] for r in parsed})},
        'source_id':{'type':'string','enum':[r['source_id'] for r in parsed]}},'required':['value','unit','source_id'],'additionalProperties':False}
    task_rules = RULES.split('Return exactly')[0]
    user = task_rules+'\nQuery: '+query+'\nRecords in supplied order: '+json.dumps(facts,separators=(',',':'))
    system = CANDIDATE_SYSTEM if arm=='adapted_v1' else BASELINE_SYSTEM
    system += ' Source identifiers are the full listed source_id strings. '
    system += ('Return only value, unit, source_id as JSON.' if arm=='adapted_v1' else 'Return value|unit|source_id or ABSTAIN exactly.')
    return {'arm':arm,'query':query,'records':parsed,'route':'model' if arm=='adapted_bootstrap' or eligible else 'deterministic_abstention',
            'gate_reason':reason,'system':system,'user':user,'schema':schema if arm=='adapted_v1' else None}


def _object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('duplicate_json_key')
        result[key]=value
    return result


def decode(raw, prepared):
    if type(raw) is not str or not 1<=len(raw)<=16384:raise ValueError('bounded_raw_required')
    if raw=='ABSTAIN' and (prepared['route']=='deterministic_abstention' or prepared['arm']=='adapted_bootstrap'):return dict(ABSTAIN)
    if prepared['route']!='model':raise ValueError('deterministic_abstention_required')
    if prepared['arm']=='adapted_v1':
        value=json.loads(raw,object_pairs_hook=_object,parse_int=Decimal,parse_float=Decimal,
                        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite')))
        if not isinstance(value,dict) or set(value)!={'value','unit','source_id'} or type(value['value']) is not Decimal:raise ValueError('strict_schema_required')
        amount=value['value']; unit=value['unit']; source=value['source_id']
    else:
        match=re.fullmatch(rf'({_NUMBER})\|({_UNIT})\|([A-Za-z0-9_.:-]{{1,96}})',raw)
        if not match:raise ValueError('strict_triplet_required')
        amount=Decimal(match.group(1));unit=match.group(2);source=match.group(3)
    if not amount.is_finite() or abs(amount.adjusted())>24 or amount.as_tuple().exponent < -24:raise ValueError('bounded_numeric_required')
    record=next((r for r in prepared['records'] if r['source_id']==source),None)
    if record is None or type(unit) is not str or unit not in {r['unit'] for r in prepared['records']}:raise ValueError('unknown_output_reference')
    # Copy identity only from the model-cited record; NEVER repair its value/unit/source.
    return {'status':'answer','entity':record['entity'],'measurement':record['measurement'],'value':format(amount,'f'),'unit':unit,'source_id':source}
