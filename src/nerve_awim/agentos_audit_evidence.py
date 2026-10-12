"""Deterministic oracle for bounded, explicitly simulated audit evidence.

This grades typed predicates, not natural-language truth or production health.
A source's kind declares its capability; assertions and summaries have none.
Only a matching, fresh root observation establishes a fact. Derived records are
validated as a provenance DAG but never upgraded to independent observations.
The fixture host supplies trusted source kinds; this oracle does not authenticate
real-world evidence. Execution predicates describe the named recorded request,
not general provider reachability, future availability or live execution.
Validation errors raise ValueError with the invalid field path; caller output
errors become a failed judge result. No model, network or filesystem writes.
"""
from copy import deepcopy
from hashlib import sha256
import math
from pathlib import Path
import re

SCHEMA = 'agentos-audit-evidence-v1'
_IDENT = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}\Z')
_CLAIMS = {'credential_present': 'credential_probe', 'catalog_listed': 'catalog',
           'execution_success': 'execution_receipt', 'zero_price': 'pricing'}
_FIELDS = {'credential_probe': {'present'}, 'catalog': {'listed'},
           'execution_receipt': {'request_id', 'success'},
           'pricing': {'input_usd', 'output_usd'},
           'assertion': {'text'}, 'summary': {'text'}}


def _require(condition, path, description):
    if not condition:
        raise ValueError(path + ': ' + description)


def _keys(value, keys, path):
    _require(type(value) is dict and set(value) == keys, path, 'exact object fields required: '+','.join(sorted(keys)))


def _identifier(value, path):
    _require(type(value) is str and _IDENT.fullmatch(value) is not None, path, 'bounded identifier required')


def _time(value, path):
    _require(type(value) is int and 0 <= value <= 2**53-1, path, 'nonnegative exact integer <=2**53-1 required')


def validate_bundle(bundle):
    """Validate exact JSON schemas and acyclic provenance; return an isolated copy.

    Claim fields: kind,model,provider,at,max_age; execution additionally request_id.
    Source fields: id,kind,model,provider,observed_at,derived_from,fields.
    Identifiers are bounded ASCII tokens. Timestamps are integer UTC seconds.
    Zero-price refers only to input/output prices in this simulated schema; it
    makes no claim about ancillary charges, future prices or real account spend.
    """
    _keys(bundle, {'schema','simulated','claim','sources'}, 'bundle')
    _require(bundle['schema'] == SCHEMA and type(bundle['schema']) is str, 'bundle.schema', 'unsupported schema')
    _require(bundle['simulated'] is True, 'bundle.simulated', 'must be exactly true')
    claim = bundle['claim']
    _require(type(claim) is dict, 'claim', 'object required')
    kind = claim.get('kind')
    _require(type(kind) is str and kind in _CLAIMS, 'claim.kind', 'unsupported predicate')
    claim_keys = {'kind','model','provider','at','max_age'}
    if kind == 'execution_success':
        claim_keys.add('request_id')
    _keys(claim, claim_keys, 'claim')
    for key in ('model','provider'):
        _identifier(claim[key], 'claim.'+key)
    for key in ('at','max_age'):
        _time(claim[key], 'claim.'+key)
    if kind == 'execution_success':
        _identifier(claim['request_id'], 'claim.request_id')
    sources = bundle['sources']
    _require(type(sources) is list and len(sources) <= 64, 'sources', 'list of at most64 required')
    indexed = {}
    for index, source in enumerate(sources):
        path = 'sources['+str(index)+']'
        _keys(source, {'id','kind','model','provider','observed_at','derived_from','fields'}, path)
        for key in ('id','model','provider'):
            _identifier(source[key], path+'.'+key)
        _require(source['id'] not in indexed, path+'.id', 'duplicate source ID')
        indexed[source['id']] = source
        source_kind = source['kind']
        _require(type(source_kind) is str and source_kind in _FIELDS, path+'.kind', 'unsupported evidence capability')
        _time(source['observed_at'], path+'.observed_at')
        parents = source['derived_from']
        _require(type(parents) is list and len(parents) <= 64, path+'.derived_from', 'bounded list required')
        for parent in parents:
            _identifier(parent, path+'.derived_from')
        _require(len(set(parents)) == len(parents), path+'.derived_from', 'duplicate parent')
        fields = source['fields']
        _keys(fields, _FIELDS[source_kind], path+'.fields')
        if source_kind in ('credential_probe','catalog','execution_receipt'):
            key = {'credential_probe':'present','catalog':'listed','execution_receipt':'success'}[source_kind]
            _require(type(fields[key]) is bool, path+'.fields.'+key, 'exact boolean required')
        if source_kind == 'execution_receipt':
            _identifier(fields['request_id'], path+'.fields.request_id')
        if source_kind == 'pricing':
            for key,value in fields.items():
                _require(type(value) in (int,float) and 0 <= value <= 10**12 and math.isfinite(value), path+'.fields.'+key, 'finite nonnegative price <=1e12 required')
        if source_kind in ('assertion','summary'):
            _require(type(fields['text']) is str and len(fields['text']) <= 4096, path+'.fields.text', 'bounded text required')
    visiting, visited = set(), set()
    def visit(ident):
        _require(ident in indexed, 'sources.derived_from', 'missing parent '+ident)
        _require(ident not in visiting, 'sources.derived_from', 'cycle at '+ident)
        if ident in visited:
            return
        visiting.add(ident)
        for parent in indexed[ident]['derived_from']:
            visit(parent)
        visiting.remove(ident)
        visited.add(ident)
    for ident in indexed:
        visit(ident)
    return deepcopy(bundle)


def expected_decision(bundle):
    """Return a decision and the complete exact set of applicable root citations.

    Freshness is inclusive: at-max_age <= observed_at <= at. Execution requires
    exact request/model/provider identity. Other predicates match model/provider.
    Conflicting applicable observations yield unknown with both sources cited;
    no applicable observations yields unknown with no citations. Newer conflicting
    evidence does not silently supersede an earlier still-applicable observation.
    """
    checked = validate_bundle(bundle)
    claim = checked['claim']
    evidence = []
    for source in checked['sources']:
        if source['kind'] != _CLAIMS[claim['kind']] or source['derived_from']:
            continue
        if source['model'] != claim['model'] or source['provider'] != claim['provider']:
            continue
        if not claim['at']-claim['max_age'] <= source['observed_at'] <= claim['at']:
            continue
        fields = source['fields']
        if claim['kind'] == 'execution_success' and fields['request_id'] != claim['request_id']:
            continue
        if claim['kind'] == 'credential_present':
            value = fields['present']
        elif claim['kind'] == 'catalog_listed':
            value = fields['listed']
        elif claim['kind'] == 'execution_success':
            value = fields['success']
        else:
            value = fields['input_usd'] == 0 and fields['output_usd'] == 0
        citation = dict(source_id=source['id'], fields=sorted(['model','provider','observed_at']+['fields.'+key for key in fields]))
        evidence.append((value,citation))
    values = {value for value,_ in evidence}
    decision = 'supported' if values == {True} else 'contradicted' if values == {False} else 'unknown'
    return dict(decision=decision, citations=sorted([citation for _,citation in evidence],key=lambda row:row['source_id']))


def judge_decision(bundle, output):
    """Grade typed output against host truth; no prose/LLM grading or partial pass.

    Output must have exactly decision and citations. Citation/field order is
    irrelevant but duplicates, unknown fields and unsupported references fail.
    Invalid input bundles raise ValueError; malformed candidate output is a
    structured invalid_output failure. Expected values are host-only feedback.
    """
    expected = expected_decision(bundle)
    try:
        _keys(output, {'decision','citations'}, 'output')
        _require(type(output['decision']) is str and output['decision'] in ('supported','contradicted','unknown'), 'output.decision', 'invalid enum')
        citations = output['citations']
        _require(type(citations) is list and len(citations) <= 64, 'output.citations', 'bounded list required')
        normalized, seen = [], set()
        for row in citations:
            _keys(row, {'source_id','fields'}, 'output.citation')
            _identifier(row['source_id'], 'output.citation.source_id')
            _require(row['source_id'] not in seen, 'output.citations', 'duplicate source')
            seen.add(row['source_id'])
            fields = row['fields']
            _require(type(fields) is list and 1 <= len(fields) <= 16 and all(type(f) is str for f in fields), 'output.citation.fields', 'bounded nonempty string list required')
            _require(len(set(fields)) == len(fields), 'output.citation.fields', 'duplicate field')
            normalized.append(dict(source_id=row['source_id'],fields=sorted(fields)))
        normalized.sort(key=lambda row:row['source_id'])
    except ValueError as error:
        return dict(passed=False,category='invalid_output',error=str(error),expected=expected)
    if output['decision'] != expected['decision']:
        return dict(passed=False,category='decision_mismatch',expected=expected)
    if normalized != expected['citations']:
        return dict(passed=False,category='citation_mismatch',expected=expected)
    return dict(passed=True,category='passed',expected=expected)


def evaluator_revision():
    """Hash this implementation, so changed semantics require a fresh revision."""
    return sha256(Path(__file__).read_bytes()).hexdigest()
